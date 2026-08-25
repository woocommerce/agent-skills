# Audit record and validation contract

Store a JSON object with audit metadata and a `pullRequests` array. Freeze this
contract before distributing work.

## Top-level metadata

```json
{
  "schemaVersion": 1,
  "generatedAt": "ISO-8601 timestamp",
  "repository": "owner/name",
  "cohort": {
    "asOf": "ISO-8601 timestamp",
    "cutoffExclusive": "ISO-8601 timestamp",
    "inactivityDays": 60,
    "count": 0,
    "numbers": []
  },
  "trunk": {
    "branch": "trunk",
    "sha": "full commit SHA",
    "fetchedAt": "ISO-8601 timestamp"
  },
  "pullRequests": []
}
```

The threshold value is an example, not a constant. Copy the exact
`inactivityDays`, `asOf`, and `cutoffExclusive` values from the frozen cohort.

## Required per-PR fields

```json
{
  "number": 123,
  "title": "PR title",
  "url": "https://github.com/owner/repo/pull/123",
  "updatedAt": "ISO-8601 timestamp",
  "ageDays": 100,
  "category": "short technical or product grouping",
  "intent": "one-sentence original outcome",
  "linkedIssues": [],
  "issueValidity": "evidence-backed current assessment",
  "discussionEvidence": [],
  "trunkEvidence": [],
  "relevanceStatus": "still-relevant",
  "recommendation": "keep-open",
  "rationale": "why this action follows from the evidence",
  "userImpact": "who is affected and how",
  "priority": "P2",
  "complexity": "medium",
  "staleCodeRisk": "specific implementation and compatibility risk",
  "currentLabels": [],
  "proposedLabels": [],
  "reviewers": [],
  "draftComment": "suggested action comment or null",
  "userTestScenario": {},
  "confidence": "medium"
}
```

Evidence entries should include a claim, source URL or local path, and concise
support. Reviewer entries should include a login/team, ownership reason, and
routing evidence. Linked issues should preserve number, URL, state, and relevance.

## Enums

- `relevanceStatus`: `already-in-trunk`, `issue-invalid`,
  `obsolete-subsystem`, `still-relevant`, or `uncertain`.
- `recommendation`: `close`, `keep-open`, or `needs-owner-decision`.
- `priority`: `P0`, `P1`, `P2`, or `P3`.
- `complexity`: `low`, `medium`, or `high`.
- `confidence`: `low`, `medium`, or `high`.
- `userTestScenario.mode`: `wp-browser`, `wp-cli-user-flow`, `docs-render`,
  `tooling-build`, or `not-runnable-obsolete`.

## Runnable user-test scenario

```json
{
  "mode": "wp-browser",
  "codeState": "PR head, trunk control, or temporary merge plus SHA",
  "preconditions": [],
  "setup": [],
  "fixtures": [],
  "steps": [],
  "expected": [],
  "observed": [],
  "assertions": [],
  "cleanup": [],
  "cleanupVerified": true,
  "result": "pass, fail, blocked, or mixed",
  "limitations": []
}
```

`wp-browser` requires real browser interactions. `not-runnable-obsolete` instead
requires a specific reason, evidence that the flow or subsystem no longer exists,
and any trunk control performed.

## Classification rules

- Make Bug versus Enhancement explicit using exact live repository labels.
- Propose only labels not already applied.
- `close` plus `still-relevant` requires a route to preserve the need, such as a
  replacement issue or fresh implementation.
- `close` plus `uncertain` requires manual review.
- Non-close recommendations require a current reviewer or team and ownership
  reason. Do not route the author as their own reviewer.
- Compatibility-sensitive changes require documented/public contract evidence,
  historical behavior, and consumer discovery proportional to impact.
- Draft comments must be ready to post but remain unposted during a read-only
  audit.

## Consolidation invariants

1. Audit count equals frozen cohort count.
2. Every cohort number occurs exactly once and no extra number appears.
3. Required strings are non-empty and enums are valid.
4. Conclusions have discussion and/or trunk evidence appropriate to their strength.
5. Proposed labels are live, absent from current labels, and include a Bug or
   Enhancement determination.
6. Non-close recommendations contain reviewer routing and rationale.
7. Runnable tests contain setup, user steps, expected and observed results,
   assertions, cleanup, and verified cleanup.
8. Non-runnable records have a concrete missing-flow reason.
9. Priority, complexity, confidence, relevance, and recommendation totals each sum
   to cohort size.
10. Audit metadata exactly repeats cohort `inactivityDays`, `asOf`, and
    `cutoffExclusive`.

## Keep three state layers separate

1. **Initial audit:** relevance and recommendation at the audit snapshot.
2. **Final live state:** GitHub state, draft status, labels, review decision, and
   timestamps at recheck.
3. **Handled state:** checklist progress, which says only that the user completed
   their chosen action.

Leadership counts must name the layer and timestamp. Show initial and final values
when they differ instead of rewriting history.
