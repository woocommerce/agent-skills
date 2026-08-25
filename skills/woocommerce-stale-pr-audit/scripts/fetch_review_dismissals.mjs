#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

function usage() {
  return "Usage: fetch_review_dismissals.mjs --repo owner/name --cohort file.json --output file.json";
}

function parseArgs(argv) {
  if (argv.includes("--help") || argv.includes("-h")) {
    process.stdout.write(`${usage()}\n`);
    process.exit(0);
  }
  const args = {};
  for (let index = 0; index < argv.length; index += 2) {
    if (!argv[index]?.startsWith("--") || argv[index + 1] === undefined) {
      throw new Error(usage());
    }
    args[argv[index].slice(2)] = argv[index + 1];
  }
  for (const required of ["repo", "cohort", "output"]) {
    if (!args[required]) throw new Error(`Missing --${required}\n${usage()}`);
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
const [owner, repo] = args.repo.split("/");
if (!owner || !repo) throw new Error("--repo must be owner/name");
const cohort = JSON.parse(fs.readFileSync(args.cohort, "utf8"));
const numbers = cohort.numbers ?? cohort.pullRequests?.map(({ number }) => number);
if (!Array.isArray(numbers)) throw new Error("Cohort must contain numbers or pullRequests");

const eventFields = `
  id databaseId url createdAt previousReviewState dismissalMessage actor { login }
  pullRequestCommit { commit { oid } }
  review {
    id databaseId url state submittedAt author { login } authorAssociation body commit { oid }
  }`;
const events = [];
const startedAt = new Date().toISOString();

for (let offset = 0; offset < numbers.length; offset += 40) {
  const batch = numbers.slice(offset, offset + 40);
  const aliases = batch.map((number) => `
    pr${number}: pullRequest(number: ${number}) {
      number title url
      timelineItems(first: 100, itemTypes: [REVIEW_DISMISSED_EVENT]) {
        pageInfo { hasNextPage endCursor }
        nodes { ... on ReviewDismissedEvent { ${eventFields} } }
      }
    }`).join("\n");
  const query = `query { repository(owner: ${JSON.stringify(owner)}, name: ${JSON.stringify(repo)}) { ${aliases} } }`;
  const response = JSON.parse(execFileSync("gh", ["api", "graphql", "-f", `query=${query}`], {
    encoding: "utf8", maxBuffer: 30 * 1024 * 1024,
  }));
  if (response.errors?.length) throw new Error(JSON.stringify(response.errors));
  for (const number of batch) {
    const pr = response.data.repository[`pr${number}`];
    if (!pr) throw new Error(`Pull request #${number} was not returned by GitHub`);
    if (pr.timelineItems.pageInfo.hasNextPage) {
      throw new Error(`PR #${number} has more than 100 review-dismissal events; add cursor pagination`);
    }
    for (const event of pr.timelineItems.nodes) {
      events.push({
        pullRequest: { number: pr.number, title: pr.title, url: pr.url },
        event: {
          id: event.id, databaseId: event.databaseId, url: event.url,
          createdAt: event.createdAt, previousReviewState: event.previousReviewState,
          dismissalMessage: event.dismissalMessage, actor: event.actor?.login ?? null,
          pullRequestCommitOid: event.pullRequestCommit?.commit?.oid ?? null,
        },
        review: event.review ? {
          id: event.review.id, databaseId: event.review.databaseId, url: event.review.url,
          state: event.review.state, submittedAt: event.review.submittedAt,
          author: event.review.author?.login ?? null,
          authorAssociation: event.review.authorAssociation, body: event.review.body,
          commitOid: event.review.commit?.oid ?? null,
        } : null,
      });
    }
  }
}

events.sort((a, b) => a.pullRequest.number - b.pullRequest.number || a.event.createdAt.localeCompare(b.event.createdAt));
const uniqueNumbers = (items) => [...new Set(items.map(({ pullRequest }) => pullRequest.number))].sort((a, b) => a - b);
const countBy = (items, value) => Object.fromEntries(
  [...new Set(items.map(value))].sort().map((key) => [key, items.filter((item) => value(item) === key).length]),
);
const approvals = events.filter(({ event }) => event.previousReviewState === "APPROVED");
const staleApprovals = approvals.filter(({ event }) => /dismissed due to being stale/i.test(event.dismissalMessage ?? ""));
const draftApprovals = approvals.filter(({ event }) => /dismissed due to the PR being moved to draft status/i.test(event.dismissalMessage ?? ""));
const output = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(), fetchStartedAt: startedAt, repository: args.repo,
  sourceCohort: {
    path: args.cohort,
    count: numbers.length,
    capturedAt: cohort.generatedAt,
    inactivityDays: cohort.inactivityDays,
    asOf: cohort.asOf,
    cutoffExclusive: cohort.cutoffExclusive,
    definition: cohort.definition,
  },
  queryNotes: {
    source: "PullRequest.timelineItems filtered to REVIEW_DISMISSED_EVENT",
    priorStateField: "ReviewDismissedEvent.previousReviewState",
    pagination: "Fails rather than truncates when a PR has more than 100 matching events",
  },
  summary: {
    cohortPullRequests: numbers.length,
    pullRequestsWithDismissal: uniqueNumbers(events).length,
    totalDismissalEvents: events.length,
    byPreviousReviewState: countBy(events, ({ event }) => event.previousReviewState),
    pullRequestsWithDismissedApproval: uniqueNumbers(approvals).length,
    dismissedApprovalEvents: approvals.length,
    pullRequestsWithStaleDismissedApproval: uniqueNumbers(staleApprovals).length,
    staleDismissedApprovalEvents: staleApprovals.length,
    pullRequestsWithDraftStatusDismissedApproval: uniqueNumbers(draftApprovals).length,
    draftStatusDismissedApprovalEvents: draftApprovals.length,
    pullRequestNumbersWithDismissedApproval: uniqueNumbers(approvals),
    pullRequestNumbersWithStaleDismissedApproval: uniqueNumbers(staleApprovals),
  },
  events,
};
fs.mkdirSync(path.dirname(path.resolve(args.output)), { recursive: true });
fs.writeFileSync(args.output, `${JSON.stringify(output, null, 2)}\n`);
console.log(args.output);
