#!/usr/bin/env python3
"""Validate cohort coverage and the deterministic stale-PR audit contract."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


REQUIRED = {
    "number", "title", "url", "updatedAt", "ageDays", "category", "intent",
    "linkedIssues", "issueValidity", "discussionEvidence", "trunkEvidence",
    "relevanceStatus", "recommendation", "rationale", "userImpact", "priority",
    "complexity", "staleCodeRisk", "currentLabels", "proposedLabels", "reviewers",
    "draftComment", "userTestScenario", "confidence",
}
ENUMS = {
    "relevanceStatus": {"already-in-trunk", "issue-invalid", "obsolete-subsystem", "still-relevant", "uncertain"},
    "recommendation": {"close", "keep-open", "needs-owner-decision"},
    "priority": {"P0", "P1", "P2", "P3"},
    "complexity": {"low", "medium", "high"},
    "confidence": {"low", "medium", "high"},
}
TEST_MODES = {"wp-browser", "wp-cli-user-flow", "docs-render", "tooling-build", "not-runnable-obsolete"}
RUNNABLE_KEYS = {"codeState", "preconditions", "setup", "steps", "expected", "observed", "assertions", "cleanup", "cleanupVerified", "result", "limitations"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def strings(values) -> list[str]:
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str)]


def label_vocabulary(payload) -> set[str]:
    if payload is None:
        return set()
    if isinstance(payload, list):
        return {item if isinstance(item, str) else item.get("name") for item in payload} - {None}
    candidates = payload.get("labels", payload.get("nodes", []))
    if isinstance(candidates, dict):
        candidates = candidates.get("nodes", [])
    return {item if isinstance(item, str) else item.get("name") for item in candidates} - {None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--labels", type=Path, help="Optional JSON repository-label vocabulary")
    args = parser.parse_args()

    cohort = load(args.cohort)
    audit = load(args.audit)
    cohort_numbers = cohort.get("numbers") or [item["number"] for item in cohort.get("pullRequests", [])]
    records = audit.get("pullRequests") if isinstance(audit, dict) else audit
    if not isinstance(records, list):
        raise SystemExit("audit must be an array or an object with pullRequests")
    vocabulary = label_vocabulary(load(args.labels) if args.labels else None)

    errors: list[str] = []
    warnings: list[str] = []
    audit_cohort = audit.get("cohort", {}) if isinstance(audit, dict) else {}
    if audit_cohort:
        for field in ("inactivityDays", "asOf", "cutoffExclusive"):
            if cohort.get(field) != audit_cohort.get(field):
                errors.append(
                    f"audit cohort {field} {audit_cohort.get(field)!r} does not match "
                    f"source cohort {cohort.get(field)!r}"
                )
    else:
        warnings.append(
            "audit has no cohort metadata; inactivityDays, asOf, and cutoffExclusive could not be cross-checked"
        )

    record_numbers = [record.get("number") for record in records]
    duplicate_numbers = sorted(number for number, count in Counter(record_numbers).items() if count > 1)
    missing = sorted(set(cohort_numbers) - set(record_numbers))
    extra = sorted(set(record_numbers) - set(cohort_numbers))
    if len(records) != len(cohort_numbers):
        errors.append(f"record count {len(records)} does not equal cohort count {len(cohort_numbers)}")
    if duplicate_numbers:
        errors.append(f"duplicate PR numbers: {duplicate_numbers}")
    if missing:
        errors.append(f"missing PR numbers: {missing}")
    if extra:
        errors.append(f"extra PR numbers: {extra}")

    for record in records:
        number = record.get("number", "?")
        absent = sorted(REQUIRED - set(record))
        if absent:
            errors.append(f"PR #{number}: missing fields: {', '.join(absent)}")
            continue
        for field, allowed in ENUMS.items():
            if record[field] not in allowed:
                errors.append(f"PR #{number}: invalid {field}: {record[field]!r}")
        for field in ("title", "url", "category", "intent", "issueValidity", "rationale", "userImpact", "staleCodeRisk"):
            if not isinstance(record[field], str) or not record[field].strip():
                errors.append(f"PR #{number}: {field} must be a non-empty string")
        if not record["discussionEvidence"] and not record["trunkEvidence"]:
            errors.append(f"PR #{number}: no discussion or trunk evidence")

        current = set(strings(record["currentLabels"]))
        proposed = strings(record["proposedLabels"])
        overlap = sorted(current.intersection(proposed))
        if overlap:
            errors.append(f"PR #{number}: proposed labels already applied: {overlap}")
        if vocabulary:
            unknown = sorted(set(proposed) - vocabulary)
            if unknown:
                errors.append(f"PR #{number}: proposed labels absent from repository vocabulary: {unknown}")
        if not any("bug" in label.lower() or "enhancement" in label.lower() for label in current.union(proposed)):
            warnings.append(f"PR #{number}: no explicit Bug or Enhancement label was found")

        if record["recommendation"] != "close" and not record["reviewers"]:
            errors.append(f"PR #{number}: non-close recommendation lacks reviewer routing")
        if record["recommendation"] == "close" and record["relevanceStatus"] in {"still-relevant", "uncertain"}:
            warnings.append(f"PR #{number}: close plus {record['relevanceStatus']} needs explicit manual review")

        scenario = record["userTestScenario"]
        if not isinstance(scenario, dict) or scenario.get("mode") not in TEST_MODES:
            errors.append(f"PR #{number}: invalid or missing userTestScenario.mode")
            continue
        if scenario["mode"] == "not-runnable-obsolete":
            if not scenario.get("reason") or not scenario.get("evidence"):
                errors.append(f"PR #{number}: non-runnable scenario needs reason and evidence")
        else:
            missing_test = sorted(RUNNABLE_KEYS - set(scenario))
            if missing_test:
                errors.append(f"PR #{number}: runnable test missing: {', '.join(missing_test)}")
            if scenario.get("cleanupVerified") is not True:
                errors.append(f"PR #{number}: cleanup was not verified")
            if scenario["mode"] == "wp-browser" and not scenario.get("steps"):
                errors.append(f"PR #{number}: wp-browser scenario has no browser steps")

    aggregates = {
        field: dict(
            sorted(
                Counter(record.get(field) for record in records).items(),
                key=lambda item: str(item[0]),
            )
        )
        for field in ("relevanceStatus", "recommendation", "priority", "complexity", "confidence")
    }
    result = {"valid": not errors, "errors": errors, "warnings": warnings, "aggregates": aggregates}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
