#!/usr/bin/env python3
"""Freeze an inactive open-PR cohort using GitHub GraphQL and gh authentication."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


QUERY = r"""
query($owner: String!, $repo: String!, $after: String) {
  repository(owner: $owner, name: $repo) {
    nameWithOwner
    url
    defaultBranchRef { name target { ... on Commit { oid committedDate } } }
    pullRequests(first: 50, states: OPEN, orderBy: {field: UPDATED_AT, direction: ASC}, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title url body createdAt updatedAt isDraft state
        additions deletions changedFiles
        mergeable mergeStateStatus reviewDecision
        baseRefName headRefName headRefOid
        maintainerCanModify authorAssociation
        author { login url }
        milestone { number title dueOn }
        labels(first: 100) { totalCount pageInfo { hasNextPage } nodes { name color description } }
        assignees(first: 100) { totalCount pageInfo { hasNextPage } nodes { login url } }
        reviewRequests(first: 100) {
          totalCount pageInfo { hasNextPage }
          nodes {
            requestedReviewer {
              ... on User { login url }
              ... on Team { name slug url organization { login } }
            }
          }
        }
        closingIssuesReferences(first: 100) {
          totalCount pageInfo { hasNextPage }
          nodes { number title url state stateReason createdAt updatedAt closedAt }
        }
        files(first: 100) {
          totalCount pageInfo { hasNextPage }
          nodes { path additions deletions changeType }
        }
        commits(last: 1) {
          totalCount
          nodes { commit { oid committedDate authoredDate messageHeadline } }
        }
        comments(last: 100) {
          totalCount pageInfo { hasPreviousPage }
          nodes { author { login } authorAssociation body createdAt updatedAt url }
        }
        reviews(last: 100) {
          totalCount pageInfo { hasPreviousPage }
          nodes { author { login } authorAssociation state body submittedAt url commit { oid } }
        }
      }
    }
  }
}
"""


def parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def graphql(owner: str, repo: str, after: Optional[str]) -> dict:
    command = [
        "gh", "api", "graphql", "-f", f"query={QUERY}",
        "-f", f"owner={owner}", "-f", f"repo={repo}",
    ]
    if after:
        command.extend(["-f", f"after={after}"])

    last_error = ""
    for attempt in range(5):
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode == 0:
            payload = json.loads(completed.stdout)
            if payload.get("errors"):
                raise RuntimeError(json.dumps(payload["errors"]))
            return payload
        last_error = completed.stderr.strip() or completed.stdout.strip()
        if not any(code in last_error for code in ("HTTP 502", "HTTP 503")):
            break
        time.sleep(2**attempt)
    raise RuntimeError(last_error)


def truncated_connections(node: dict) -> list[str]:
    truncated = []
    for name in ("labels", "assignees", "reviewRequests", "closingIssuesReferences", "files"):
        if node[name]["pageInfo"]["hasNextPage"]:
            truncated.append(name)
    for name in ("comments", "reviews"):
        if node[name]["pageInfo"]["hasPreviousPage"]:
            truncated.append(name)
    return truncated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub repository as owner/name")
    parser.add_argument("--inactive-days", type=int, default=90)
    parser.add_argument("--as-of", type=parse_timestamp, default=datetime.now(timezone.utc))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if "/" not in args.repo:
        parser.error("--repo must be owner/name")
    if args.inactive_days < 1:
        parser.error("--inactive-days must be positive")
    owner, repo = args.repo.split("/", 1)
    cutoff = args.as_of - timedelta(days=args.inactive_days)

    nodes: list[dict] = []
    after: Optional[str] = None
    repository_meta: Optional[dict] = None
    while True:
        repository = graphql(owner, repo, after)["data"]["repository"]
        if repository is None:
            raise RuntimeError(f"repository not found: {args.repo}")
        repository_meta = repository_meta or {
            "nameWithOwner": repository["nameWithOwner"],
            "url": repository["url"],
            "defaultBranchRef": repository["defaultBranchRef"],
        }
        connection = repository["pullRequests"]
        reached_cutoff = False
        for node in connection["nodes"]:
            updated = parse_timestamp(node["updatedAt"])
            if updated >= cutoff:
                reached_cutoff = True
                break
            truncated = truncated_connections(node)
            node["evidenceCoverage"] = {
                "truncatedConnections": truncated,
                "completeForCohortMembership": True,
                "completeForAuditEvidence": not truncated,
            }
            if truncated:
                print(
                    f"warning: PR #{node['number']} requires hydration for: {', '.join(truncated)}",
                    flush=True,
                )
            nodes.append(node)
        print(f"collected={len(nodes)} cursor={connection['pageInfo']['endCursor']}", flush=True)
        if reached_cutoff or not connection["pageInfo"]["hasNextPage"]:
            break
        after = connection["pageInfo"]["endCursor"]

    result = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "asOf": args.as_of.isoformat(),
        "cutoffExclusive": cutoff.isoformat(),
        "inactivityDays": args.inactive_days,
        "definition": f"Open pull requests with GitHub updatedAt before {cutoff.isoformat()}.",
        "repository": repository_meta,
        "count": len(nodes),
        "numbers": [node["number"] for node in nodes],
        "pullRequests": nodes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "count": len(nodes)}))


if __name__ == "__main__":
    main()
