# Stale PR audit workflow

## 1. Establish the immutable audit boundary

Record the repository and host, inactivity threshold, exact as-of timestamp,
derived cutoff, included PR states, cohort count and ordered numbers, default
branch and fetched SHA, and collection command.

GitHub's `updatedAt` reflects issue-style PR activity. The collector calculates
`cutoff = asOf - inactivityDays` and selects open PRs where
`updatedAt < cutoff`. Accept any positive whole-day threshold supplied by the
user; use 90 only when none is provided. If the requested policy differs, define
it before collection.

The cohort is a snapshot. Later closes, merges, comments, draft changes, or other
activity belong in the final-state comparison and never rewrite membership. Pass
the recorded threshold, timestamps, PR numbers, and trunk SHA unchanged to all
workers and report builders.

## 2. Preflight the repository

- Inspect `git status --short --branch` before doing work.
- Never stash, reset, or overwrite unrelated user changes.
- Fetch the default branch from the authoritative remote.
- Use an isolated worktree for applying PR patches or running test fixtures.
- Capture the current repository labels and ownership signals such as CODEOWNERS,
  package ownership, recent maintainers, or owning teams.
- Check GitHub API rate limits before a large run.

## 3. Hydrate evidence without silent truncation

Gather enough paginated data for each PR:

- title, body, author, state/draft status, dates, base/head refs and SHA;
- changed files, diff, commits, and current mergeability;
- review requests, reviews, review threads, comments, and timeline events;
- linked issues and their current state and relevant discussion;
- labels, assignees, milestone, and project signals where relevant.

If a connection cannot be fully paginated, fail or mark the evidence incomplete.
Never turn `first: 100` into a completeness claim without checking `pageInfo` or
`totalCount`.

## 4. Determine intent and current relevance

For each PR:

1. State the original user-visible or maintainer-visible problem in one sentence.
2. Identify the paths, APIs, hooks, strings, docs pages, or workflows it changed.
3. Search current trunk for those paths and semantic successors; old files may
   have moved or been rewritten.
4. Inspect history when trunk contains a similar change. Cite the superseding
   commit or PR when one exists.
5. Re-evaluate the linked issue independently. Its open/closed state alone does
   not establish whether the need is valid.
6. Investigate documented contracts, historical behavior, and real consumers
   when a public hook, API, return value, mutable reference, schema, or extension
   point changes.
7. Separate whether the user need still exists, whether the implementation is
   applicable, and whether the existing branch is salvageable.

Use `already-in-trunk` only with concrete trunk evidence. Use `issue-invalid`
only when the original premise or supported behavior is no longer valid. Use
`obsolete-subsystem` when the affected path has been removed or replaced.
Otherwise use `still-relevant` or `uncertain` and state what remains unknown.

## 5. Run representative user testing

Choose the appropriate mode:

- `wp-browser`: storefront or wp-admin behavior exercised in a browser;
- `wp-cli-user-flow`: a real store operation exercised through WP-CLI or HTTP;
- `docs-render`: build and inspect the current documentation surface;
- `tooling-build`: execute the user-facing maintainer command or output;
- `not-runnable-obsolete`: the subsystem or flow no longer exists, with evidence.

For runnable tests record the environment, exact code state, setup commands,
fixtures, user steps, expected and observed results, assertions, teardown command,
and proof that containers, servers, worktrees, fixtures, and temporary files were
removed.

When an old branch cannot run cleanly:

1. Attempt the exact head when practical.
2. Test the same flow on current trunk as a control.
3. If useful, test a temporary clean merge or minimal port.
4. Label which code state produced each result.
5. Abort the temporary merge and remove the disposable environment.

Testing trunk can prove an issue is already resolved; it does not prove the stale
patch is safe. Failure to boot old code does not prove the user need is obsolete.

## 6. Use bounded parallel work

Delegate only when permitted. Divide work by disjoint PR numbers or technical
domains. Give every worker the frozen cohort, fetched trunk SHA, audit schema,
evidence and testing requirements, a unique output path, and a prohibition on
mutating GitHub or the user's checkout.

Keep one heavy Docker, wp-env, or browser environment active at a time by default.
Static inspection and independent GitHub reads can run concurrently. The primary
agent owns consolidation, contradiction resolution, and aggregate recomputation.

## 7. Consolidate and quality-check

Reject or manually review records with:

- missing, duplicate, or extra PR numbers;
- unsupported `already-in-trunk`, `issue-invalid`, or `close` conclusions;
- `close` plus a still-relevant need but no route to preserve that need;
- no current owner and reason for a non-close recommendation;
- labels absent from the repository vocabulary or already applied;
- the author routed as their own reviewer;
- vague testing, missing teardown, or “the branch is old” as a non-runnable reason;
- compatibility-sensitive changes without contract and consumer investigation;
- aggregate arithmetic that does not reconcile to the cohort.

Spot-check low-confidence records, high-impact recommendations, and all automated
claims of supersession. Record the final trunk SHA and verification timestamp.

## 8. Build the decision artifact

Include methodology, audit boundary, initial cohort and recommendation totals,
final live GitHub states, cross-cohort observations, filters, a handled-status
checklist, per-PR evidence and proposed actions, and limitations.

Checklist state means only that the user handled an item. It must not change the
semantic conclusion. Use a versioned storage key derived from repository and
cohort identity. On refresh, preserve existing handled PR numbers and initialize
newly handled PRs only from verified actions; never overwrite the user's stored
choices wholesale.

## 9. Recheck before handoff

Fetch live state immediately before publication and report open/closed/merged,
open drafts, open ready-for-review, review decisions, and which initial
recommendations were acted on.

For dismissed approvals, use timeline `REVIEW_DISMISSED_EVENT` data. The
authoritative fact is `ReviewDismissedEvent.previousReviewState == APPROVED`.
Classify the reason from `dismissalMessage` and preserve the exact message.

For private publication, verify authentication, access controls, rendered
content, and the final URL. Otherwise deliver a local artifact and state the gap.

## 10. Keep execution separate

The audit proposes actions; it does not authorize them. Closing, commenting,
labeling, assigning, pushing, or merging needs explicit approval. Before executing
approved actions, refresh live state, skip completed work, preserve the approved
scope, and record successes and failures for report reconciliation.
