#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

function usage() {
  return "Usage: fetch_live_state.mjs --repo owner/name --cohort file.json --output file.json";
}

function parseArgs(argv) {
  if (argv.includes("--help") || argv.includes("-h")) {
    process.stdout.write(`${usage()}\n`);
    process.exit(0);
  }
  const args = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    if (!key?.startsWith("--") || argv[index + 1] === undefined) {
      throw new Error(usage());
    }
    args[key.slice(2)] = argv[index + 1];
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

const pullRequests = [];
const startedAt = new Date().toISOString();
for (let offset = 0; offset < numbers.length; offset += 40) {
  const batch = numbers.slice(offset, offset + 40);
  const aliases = batch.map((number) => `
    pr${number}: pullRequest(number: ${number}) {
      number state isDraft mergedAt closedAt updatedAt reviewDecision
      labels(first: 100) { totalCount pageInfo { hasNextPage } nodes { name } }
    }`).join("\n");
  const query = `query { repository(owner: ${JSON.stringify(owner)}, name: ${JSON.stringify(repo)}) { ${aliases} } }`;
  const response = JSON.parse(execFileSync("gh", ["api", "graphql", "-f", `query=${query}`], {
    encoding: "utf8", maxBuffer: 20 * 1024 * 1024,
  }));
  if (response.errors?.length) throw new Error(JSON.stringify(response.errors));
  for (const number of batch) {
    const pr = response.data.repository[`pr${number}`];
    if (!pr) throw new Error(`Pull request #${number} was not returned by GitHub`);
    if (pr.labels.pageInfo.hasNextPage || pr.labels.totalCount > pr.labels.nodes.length) {
      throw new Error(`Pull request #${number} has more than 100 labels`);
    }
    pullRequests.push({
      number: pr.number, state: pr.state, isDraft: pr.isDraft,
      mergedAt: pr.mergedAt, closedAt: pr.closedAt, updatedAt: pr.updatedAt,
      reviewDecision: pr.reviewDecision,
      labels: pr.labels.nodes.map(({ name }) => name).sort(),
    });
  }
}
pullRequests.sort((a, b) => a.number - b.number);
const countBy = (items, value) => Object.fromEntries(
  [...new Set(items.map(value))].sort().map((key) => [key, items.filter((item) => value(item) === key).length]),
);
const output = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(), fetchStartedAt: startedAt,
  repository: args.repo,
  sourceCohort: {
    path: args.cohort,
    count: numbers.length,
    capturedAt: cohort.generatedAt,
    inactivityDays: cohort.inactivityDays,
    asOf: cohort.asOf,
    cutoffExclusive: cohort.cutoffExclusive,
    definition: cohort.definition,
  },
  aggregates: {
    total: pullRequests.length,
    byState: countBy(pullRequests, ({ state }) => state),
    byReviewDecision: countBy(pullRequests, ({ reviewDecision }) => reviewDecision ?? "NONE"),
    drafts: pullRequests.filter(({ isDraft }) => isDraft).length,
    openDrafts: pullRequests.filter(({ state, isDraft }) => state === "OPEN" && isDraft).length,
    openReadyForReview: pullRequests.filter(({ state, isDraft }) => state === "OPEN" && !isDraft).length,
  },
  pullRequests,
};
fs.mkdirSync(path.dirname(path.resolve(args.output)), { recursive: true });
fs.writeFileSync(args.output, `${JSON.stringify(output, null, 2)}\n`);
console.log(args.output);
