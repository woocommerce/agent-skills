---
name: woocommerce-stale-pr-audit
description: "Audit a fixed cohort of inactive WooCommerce pull requests against current trunk, linked issues, review history, repository labels, and representative user flows, then produce evidence-backed actions and a private checklist report. Use for stale or backlog PR cohort reviews, not ordinary single-PR code review."
compatibility: "WooCommerce 10.9+ source repositories, PHP 7.4+, GitHub CLI, Python 3.9+, Node.js 20+"
---

# WooCommerce stale PR audit

## When to use

Use this skill when a maintainer wants to review a defined cohort of inactive
pull requests and decide whether each PR should close, remain open, or receive an
owner decision. It covers cohort collection, current-trunk comparison,
representative user testing, action recommendations, and a checklist report.

Run the audit read-only. Closing, commenting, labeling, assigning, pushing, or
merging are separate actions that require explicit authorization.

## Inputs required

Collect these before starting:

- GitHub repository as `owner/name`.
- Positive whole-number inactivity threshold, such as 60 or 90 days. Use 90 only
  when the user does not specify one.
- Exact as-of timestamp used to calculate the cutoff.
- Default branch and authoritative remote.
- Required output location and whether private publication is expected.
- Available local test tooling and safe environment capacity.

Calculate `cutoff = asOf - inactivityDays` and define cohort membership
explicitly. The bundled collector uses open PRs with `updatedAt < cutoff`.

## Procedure

1. **Read `references/workflow.md` completely.** It defines evidence collection,
   current-trunk comparison, runtime-testing rules, bounded parallel work,
   checklist persistence, publication, and the mutation boundary.
2. **Read `references/audit-schema.md` before producing records.** Use its field
   contract, enums, and consolidation invariants unchanged across workers.
3. Inspect the checkout with `git status --short --branch`. Preserve unrelated
   work and use isolated worktrees for branch inspection and testing.
4. Fetch the current default branch and record its full commit SHA.
5. Freeze the cohort:

   ```bash
   python3 scripts/collect_cohort.py \
     --repo woocommerce/woocommerce \
     --inactive-days 60 \
     --as-of 2026-08-25T00:00:00Z \
     --output work/cohort-raw.json
   ```

   Preserve `inactivityDays`, `asOf`, `cutoffExclusive`, ordered PR numbers, and
   captured trunk metadata. Do not rewrite membership when PRs later change.
6. For every PR, recover its intended outcome, inspect linked issues and
   discussion, compare the exact change with current trunk and history, assess
   compatibility risk, classify Bug versus Enhancement using live repository
   labels, and identify a current reviewer or owning team when it should remain
   open.
7. Run a representative user flow when the behavior is runnable. Record setup,
   exact code state, fixtures, user steps, expected and observed results,
   assertions, teardown, and verified cleanup. Do not call CI, unit tests, source
   inspection, or a successful build “user testing.”
8. Write one audit record per frozen cohort member. Validate it:

   ```bash
   python3 scripts/validate_audit.py \
     --cohort work/cohort-raw.json \
     --audit work/audit.json \
     --labels work/repository-labels.json
   ```

9. Immediately before reporting, fetch current state:

   ```bash
   node scripts/fetch_live_state.mjs \
     --repo woocommerce/woocommerce \
     --cohort work/cohort-raw.json \
     --output work/cohort-live-state.json
   ```

10. When approval-loss observations matter, fetch authoritative dismissal events:

    ```bash
    node scripts/fetch_review_dismissals.mjs \
      --repo woocommerce/woocommerce \
      --cohort work/cohort-raw.json \
      --output work/review-dismissals.json
    ```

11. Produce a private checklist report. Keep initial audit recommendations,
    final live GitHub state, and the user's handled state as separate layers.
    Preserve handled-state choices and user edits when refreshing the artifact.

## Verification

- Cohort count, ordered numbers, threshold, as-of timestamp, and cutoff reconcile.
- Every cohort PR occurs exactly once in the audit and no extra PR appears.
- Current-trunk conclusions cite a fetched SHA and concrete evidence.
- All runnable tests identify the tested code state and verify cleanup.
- Proposed labels exist in the live repository vocabulary and are not already
  present; Bug versus Enhancement is explicit.
- Keep-open and owner-decision records name a reviewer or team with a reason.
- Recommendation, relevance, priority, complexity, and confidence totals each
  equal the frozen cohort size.
- All four packaged copies build successfully:

  ```bash
  node shared/scripts/skillpack-build.mjs --clean \
    --targets=codex,vscode,claude,cursor \
    --skills=woocommerce-stale-pr-audit
  ```

## Failure modes / debugging

- **Cohort changed during the audit:** retain the original membership and record
  the change only in final live state.
- **GitHub connection reports more data:** paginate it, or mark evidence
  incomplete. Never silently treat `first: 100` as complete.
- **The old branch does not run:** test current trunk as a control and, when
  useful, a temporary clean merge or minimal port. Distinguish an obsolete branch
  from an unresolved user need.
- **No representative flow exists:** use `not-runnable-obsolete` only with
  evidence that the flow or subsystem is gone. Staleness alone is not evidence.
- **Counts changed after human review:** show initial and final counts with their
  timestamps instead of overwriting history.
- **Publication cannot be verified:** save the artifact locally and report the
  access or rendering gap.

## Escalation

Ask the maintainer when the cutoff rule, repository scope, linked issue validity,
compatibility impact, product ownership, or acceptable test substitute remains
ambiguous after source and discussion review. Ask before any external mutation or
before increasing local environment concurrency beyond known-safe capacity.
