---
name: abilities-api-implement
description: "End-to-end implementation playbook for registering WordPress Abilities API capabilities in a WooCommerce extension. Builds on the portable skills in WordPress/agent-skills (`wp-abilities-api`, `wp-abilities-audit`, `wp-abilities-verify`) and adds the Woo-extension scaffolding, conventions, and PR workflow."
compatibility: "WordPress 6.9+, WooCommerce 10.9+, PHP 7.4+"
---

# Abilities API Implement — WooCommerce extension playbook

This skill drives a WooCommerce extension from "no abilities registered"
to "draft PR open, ability surface verified" in one pass. It consumes an
audit doc produced upstream by `wp-abilities-audit` and walks through the
phases: scaffold the registrar, land one commit per ability, run the
integration harness, open the PR.

Hard handoff — this skill requires a valid audit doc and exits with an
error if one cannot be found or parsed.

## Relationship to the upstream skills

The portable parts of this playbook live in **WordPress/agent-skills**:

| Upstream skill | What it owns |
|---|---|
| `wp-abilities-audit` | Produces the audit doc this skill consumes. Plugin-family detection, grouping heuristic, audit schema. |
| `wp-abilities-api` | Portable patterns — delegate-helper pattern, error-code vocabulary, input-schema gotchas (pagination key drift, schema defaults), plugin-family patterns. |
| `wp-abilities-verify` | Integration harness — wp-env enumerate / annotations / execute / permission-gate checks, audit-schema validation. |

This skill owns the **WooCommerce-extension layer** on top:

- Registrar scaffolding parameterized for a WooCommerce-extension's
  namespace, autoload layout, test base class, and bootstrap entry point.
  Non-Woo plugin families (Jetpack-family, generic WordPress plugins) are
  out of scope for this playbook — use the upstream `wp-abilities-api`
  skill (`WordPress/agent-skills`) directly with the host project's own
  conventions.
- WooCommerce-extension primitives — namespace rules, MCP exposure choice,
  the shared `woocommerce` category convention,
  the `woocommerce_ability_definition_classes` loader path,
  required `meta.mcp.public` / `meta.mcp.type` defaults.
- One-atomic-commit-per-ability convention for clean review.
- PR template that respects the target repository's own
  `.github/pull_request_template.md` and provides the abilities-specific
  sections to fill in.
- Audit-precondition checks that catch the bugs we have repeatedly seen at
  scaffold time (capability-gate drift, plugin-family mismatch, missing
  backing controller).

## Overview

Given an audit doc, this skill produces:

1. A new `Abilities_Registrar` class under the extension's source tree.
2. One atomic commit per registered ability (reference ability first, reads
   next, writes last).
3. Unit tests covering shape + permission + execute-path assertions.
4. An integration harness run captured as a Markdown artifact.
5. An open PR against the extension's repo.

The skill stops at push + PR. It does not post to issue trackers or chat.
It does not attempt to resume from a partial run — if something breaks
mid-run, fix up and re-invoke from the failing phase manually.

## Loader-only — what you can rely on

This skill scaffolds the WC 10.9 `AbilityDefinition` + `woocommerce_ability_definition_classes` loader shape. On stores running WC < 10.9 the registrar silently no-ops — no polyfill, no fallback registration path. The structural gate is a `class_exists()` check on `\Automattic\WooCommerce\Internal\Abilities\AbilitiesLoader`; the safety net during rollout is the per-plugin `<plugin_slug>_abilities_enabled` feature flag.

**Read `references/wc-1009-dependency.md` before scaffolding** — it covers why no polyfill ships, the lazy-autoload property that makes Domain classes safe to ship to WC < 10.9 stores, and the test-environment implications (CI matrices on WC < 10.9 skip cleanly via `markTestSkipped`).

## Usage

Invoke from inside the extension's working tree:

```
/woocommerce:abilities-api-implement <path-to-audit-doc>
```

If no argument is passed, the skill auto-detects the most recent
`*abilities-audit*.md` under `plans/` (vault or extension-local).

## Precondition — audit doc must be valid

Before any scaffolding, validate the audit doc produced by
`wp-abilities-audit`.

**Read `references/audit-precondition.md` now** for the precondition
checklist. It validates on top of — not in place of — `wp-abilities-verify`'s
canonical audit-schema validator. If the `wp-abilities-verify` skill from
WordPress/agent-skills is installed, also read
`wp-abilities-verify/references/audit-schema-validation.md` for the
canonical schema checks; run those first, then the Woo-extension-specific
checks in `audit-precondition.md`.

If the precondition check fails, STOP. Do not partially scaffold.

## Plan of execution

The implementation follows a six-phase sequence. Each phase ends with one or
more atomic commits.

### Phase I — Scaffold the coordinator + Domain folder

Create:

- `Abilities_Registrar` coordinator — `init()` with the feature-flag gate and the WC 10.9 loader gate, the empty `ABILITY_CLASSES` const, the `append_classes()` filter callback, the `CATEGORY_SLUG = 'woocommerce'` constant, and the `<CanCapHelper>()` capability helper. The coordinator does NOT register the category — Woo Core owns the `woocommerce` slug (see `woo-extension-primitives.md` §5).
- `Domain/Abstract<Plugin>Ability` — `CATEGORY_SLUG` const (mirror of the registrar's) + `delegate_to_rest_controller()` (used by Shape-2 reads in Phase III). Add the pagination helpers from `paginated-output-envelope.md` now if you already know the surface has list-shaped abilities, or defer them until the first list-shaped Domain class lands.
- Phase-I tests — six cases: feature-flag-off bail, loader-absent bail, loader-present filter wire, `append_classes()` round-trip, capability helper, and `init()` idempotency under the `$initialized` static guard.

Wire `Abilities_Registrar::init()` into the extension's bootstrap.

**Feature flag gate.** The registrar's `init()` must short-circuit when the
`<plugin_slug>_abilities_enabled` filter returns false (the default during
rollout). This lets the registration scaffolding ship without committing to
a final ability shape. The filter is per-site opt-in; flip the default to
true once the surface is stable.

**Read `references/registrar-template.md` now** — it contains the
WooCommerce-extension class template, test base class rules, feature-flag
pattern, and bootstrap wiring locations. For the portable mechanics this
file adapts (call-shape patterns, delegate-helper signature, error-code
vocabulary), read `wp-abilities-api`'s
`references/plugin-family-patterns.md`, `references/delegate-helper-pattern.md`,
and `references/error-code-vocabulary.md` first (if that skill is
installed).

**Read `references/wc-1009-dependency.md` now** — it covers the loader-gate rationale: why the coordinator's `woo_abilities_loader_available()` check is the structural gate (and the feature flag is only the rollout safety net), why the `::class` constants in `ABILITY_CLASSES` don't autoload the Domain classes on WC < 10.9, and the `markTestSkipped` pattern for the per-ability tests in subsequent phases.

**Read `references/woo-extension-primitives.md` now** — it captures the
WooCommerce-extension rules that the audit doc cannot encode by itself:
ability namespace, the `woocommerce_ability_definition_classes` loader,
deprecated-MCP-endpoint exposure choice, required metadata defaults, and
the shared `woocommerce` category convention (§5 — including the
plugin-slug-as-category antipattern and the do-not-re-register rule).
These rules apply to every ability registered in Phases II–IV.

**Commit shape:** `feat(abilities): scaffold Abilities_Registrar coordinator + Domain base`.

### Phase II — Register the first ability (reference pattern)

Pick the simplest safe read — usually a zero-arg "get <thing>-summary" or "get <thing>-statuses" style ability that does not require constructing a `WP_REST_Request`. This commit establishes the Domain-class reference pattern the remaining abilities will copy: one `Domain/<Name>.php` file per ability, implementing `AbilityDefinition` with `get_name()` / `get_registration_args()` / `execute()` static methods, listed in `Abilities_Registrar::ABILITY_CLASSES`.

**Read `references/first-ability-template.md` now** — it walks through the
registration helper, the execute callback with defensive guards, the
dual-state return handling, and the two required tests (shape + permission).

**Alternative backing controllers:** if the audit's Notes for this ability
mention an alternative backing controller (e.g. one controller in the admin
namespace and another in a reports namespace with different output shapes),
PAUSE and confirm with the user before scaffolding.

**Commit shape:** `feat(abilities): add <plugin-slug>/<ability-name> ability`.

### Phase III — Register remaining reads

After ability #2 lands, pick the right path for each remaining read before
extracting any helper.

**Shape preference for the Woo-extension overlay:**

| Shape | Pattern | When to use |
|---|---|---|
| 3 — Shared service | Ability + REST + UI all call a shared service class (`<PluginNamespace>\Internal\Service\<Thing>_Service` — a sibling of the `\Internal\Abilities` namespace, not a child) | **Default.** Mandatory for writes (Phase IV). The default for reads too: a shared domain/service helper consumes the same code path the UI and REST controller already use, and the ability layer curates output for agent consumption. |
| 2 — Delegate to REST | Ability builds a `WP_REST_Request` and calls `rest_do_request()` via the `delegate_to_rest_controller` helper | **Explicitly-reviewed escape hatch** for low-risk reads. Acceptable only when the backing controller is verified side-effect-free AND the REST handler doesn't add transport artifacts (envelope shape, `_links`, embedded hypermedia, header-derived fields) the ability would inherit unchanged AND request-context helpers (`current_user_can` paths, `is_admin()`, `did_action`, header-based behavior) the controller depends on behave the same outside a REST request lifecycle. |
| 1 — Re-implement | Ability has its own SQL / validation | **Avoid.** Drift is guaranteed. |

Why Shape 3 is the Woo-extension default (not "preferred"):

- **REST output carries transport artifacts.** Controllers shape their output for HTTP — envelope keys, `_links`, embedded hypermedia, links to next/prev pages. The ability layer wants the curated payload, not the transport shape; Shape 3 lets the ability call the domain helper and assemble the agent-facing shape itself.
- **Request-context helpers behave differently outside REST.** `current_user_can` checks behind nonce verification, `is_admin()` branches, `did_action('rest_api_init')` guards, header-based capability resolution — all routinely pass under REST and break under CLI / cron / agent invocations. Shape 2 inherits all of those silently.
- **The metric trap.** Backing controllers routinely emit analytics events, fire WP hooks, or dispatch notifications. Every agent-driven Shape 2 invocation contaminates those counters — agents show up in dashboards as "humans hit this endpoint." Shape 3 lets the ability call the domain helper directly and emit its own ability-tagged side effects (or none).
- **First-call REST bootstrap cost.** `rest_do_request()` calls `rest_get_server()`, which lazy-instantiates `WP_REST_Server` and fires `rest_api_init` once per request. Inside a REST request lifecycle the cost is amortized; outside it (CLI, cron, non-REST MCP transport, agent workflows) the first delegating ability call pays the full bootstrap.

**Decision order at scaffold time:**

1. Is there already a domain/service helper for this operation? → Shape 3, call it.
2. Does the audit's `side_effects` field declare anything non-empty (telemetry hooks, audit logs, notifications, cache writes, lock acquisitions)? → Shape 3, extract a service if none exists.
3. Is the ability predominantly invoked outside REST? → Shape 3.
4. Does the REST handler emit transport artifacts or rely on request-context helpers (see "Why Shape 3 is the default" above)? → Shape 3.
5. None of the above and the read is genuinely low-risk → Shape 2 is acceptable as an explicitly-reviewed escape hatch. Note the trade-off and the verified preconditions in the PR's "Notes for reviewers."

For Shape 2 in the loader-only pattern, `delegate_to_rest_controller()` is a `protected static` method on `Abstract<Plugin>Ability` (the local abstract base — see `registrar-template.md`). Domain classes call it as `self::delegate_to_rest_controller(...)`.

For Shape 2, the canonical helper implementation, signature, dual-response-
shape unwrap, and the two-exception rule for zero-arg abilities live
upstream:

**If the `wp-abilities-api` skill from WordPress/agent-skills is installed,
read its `references/delegate-helper-pattern.md` now.** Otherwise the
template in `references/registrar-template.md` includes a self-contained
helper that builds a `WP_REST_Request`, calls `rest_do_request()`, and
unwraps both `WP_REST_Response` and raw-array return shapes.

For pagination parameters, some backing controllers use a different key
(e.g. `pagesize` instead of `per_page`):

**If the `wp-abilities-api` skill is installed, read its
`references/input-schema-gotchas.md` now (section: pagination key drift).**
Otherwise the detection heuristic is: grep the backing controller's
`get_collection_params()` (or equivalent) for `pagesize`, `page_size`, or
other non-`per_page` pagination keys, and translate at the ability boundary
rather than propagating the non-standard key into the ability's input
schema.

**Commit shape:**
- Service extraction (Shape 3): `refactor(<plugin>): extract <Thing>_Service for shared business logic`.
- Helper extraction (Shape 2): `refactor(abilities): extract delegate_to_rest_controller helper`.
- Each ability: `feat(abilities): add <plugin-slug>/<ability-name> ability`.

### Phase IV — Register writes

If the audit has any write abilities, land them after all reads are in. **First-pass batches default to read-only.** Adding a write widens the agent-facing action surface; the discipline below keeps batch scaffolding from doing so accidentally.

**Explicit write gate — review all four before adding any write ability:**

1. **Behavior.** The operation is a genuine state transition (terminal close, refund, void, status change with downstream consequences) — not a mutating GET dressed as a POST and not a setter masquerading as a read. Cross-check against the audit doc's `intent` and `use_case_fit` fields.
2. **Permission gate.** The cap is enforced at the canonical source recorded in the audit's `permission.source` (the domain / service / admin-action layer, not just the REST controller's `permission_callback`). The ability's `permission_callback` consults that canonical source, not the REST callback by reflex. Cross-link upstream: `wp-abilities-audit/references/capability-gate-tracing.md`.
3. **Service path.** Shape 3 is mandatory (Phase III table). A shared service class exists for the operation OR is extracted in a `refactor()` commit landed before this write ability's commit.
4. **Annotations.** Each value reflects the actual behavior, not a copy-paste from the read abilities — `readonly: false`, `destructive: <true|false>` explicit, `idempotent: <true|false>` explicit. The verify skill's adversarial check will catch lies; better to set them honestly the first time.

If any of the four review steps surfaces an unknown, pause the write rather than guess. Writes are the most damaging surface to land sloppy.

**Read `references/write-ability-template.md` now** — it walks through the write-ability Domain-class shape (Shape 3 is mandatory — shared service, no HTTP-method-as-argument; never the abstract base's `delegate_to_rest_controller()` for writes), the required-input validation pattern, and the schema-defaults gotcha. For the portable input-schema and schema-defaults gotchas, cross-reference `wp-abilities-api`'s `references/input-schema-gotchas.md` if installed.

**Commit shape:** `feat(abilities): add <plugin-slug>/<ability-name> ability`.

### Phase V — Integration harness

Bring up wp-env, enumerate abilities, verify annotations, execute reads,
exercise write input validation, confirm the permission gate. Capture
output to a Markdown artifact for the PR.

**Two verification levels.** The smoke level catches bootstrap and gross-error regressions; the high-confidence level exercises each ability against the data shape it will see in production. Both go through the public ability boundary (`wp_get_ability( $name )->execute( $input )`), not the registrar's static methods.

- **Level 1 — smoke execution (synthetic inputs).** Confirm each read returns `OK` or a vocabulary `WP_Error`; each write rejects missing-input with `ability_invalid_input` or the plugin's `<plugin_slug>_missing_<field>` code. Catches PHP fatals, un-bootstrapped services, registration failures, write input-validation gaps.
- **Level 2 — high-confidence verification (representative seeded data).** Preferred for every ability whose audit doc declares a non-null `seed_data_needs`. Seed realistic plugin data per that field, call the ability with representative inputs (real ids, real slugs — not synthetic placeholders), and assert (a) the documented output shape, (b) the privacy contract (sensitive fields the ability doesn't promise must not appear), and (c) the permission behavior against real records (anon denied, subscriber denied, the intended role allowed). Level 2 is the one that catches wrong IDs returning the wrong record, cached sentinels being served, permission gates passing on synthetic IDs but not on real ones, filtered-vs-unfiltered label drift, and curated-output drift from a controller field the ability inherits.

When `seed_data_needs: null` for an ability, Level 2 reports `pending (ask the implementer)` and proceeds — dovetails with the WARN-not-FAIL posture on the audit-schema implementation-readiness fields.

**Use the `wp-abilities-verify` skill from WordPress/agent-skills** — it is the portable, authoritative version of the integration harness. Its `references/runtime-harness.md` Check 3 owns the canonical Level 1 / Level 2 split; its other checks cover annotation correctness, permission roundtrip, schema lints, and the readonly-but-writes detector. The skill emits the artifact format this PR template renders.

**Critical gate — the readonly-but-writes detector.** Every `readonly: true`
ability in the audit must come back clean from the verify skill's
adversarial `annotation-correctness` check (see
`wp-abilities-verify/references/annotation-correctness.md`). An ability
that claims `readonly: true` while calling `$wpdb->update`, `update_option`,
`wp_insert_*`, or delegating via a non-GET HTTP method is the bug class
that unit tests do not catch — the mock looks just like the real writer.
**No PASS is allowed without this detector clean.** If the detector flags
an ability, either fix the annotation (set `readonly: false`) or fix the
callback to be genuinely read-only.

If `wp-abilities-verify` is not installed, fall back to a manual harness
run: enumerate abilities via `wp eval 'print_r( array_keys( wp_get_abilities() ) );'`,
spot-check annotations and execute behavior via WP-CLI, and capture both
commands and output in the artifact file.

**Ship the integration harness in the plugin's own test suite, not only
as a one-shot PR artifact.** The `wp-abilities-verify` run produces the
artifact attached to the PR; the in-plugin PHPUnit tests prove the public
contract on every CI run thereafter. Read
`references/test-the-public-contract.md` now — it covers the six contract
dimensions (permissions, inputs, annotations, curated output, privacy,
execution behavior) the in-plugin tests MUST assert through
`wp_get_ability()` and not by calling the registrar's static methods
directly.

**Artifact:** `plans/<YYYY-MM-DD>-<plugin-slug>-abilities-harness-output.md`.

**Commit shape:** if the harness catches a bug, fix it in a small standalone
commit (e.g. `fix(abilities): ...`). The harness-output file itself is NOT
committed to the extension repo — it lives in the user's plans directory
and is referenced in the PR body.

### Phase V.5 — Measure the token cost

Every ability set should ship with a token-cost number. The provisional
budget is ~2,000 tokens per plugin in MCP `tools/list`.

**If the `wp-abilities-measure` skill is installed**, run it against the
freshly-registered ability set and capture two numbers:

- `tools/list` token cost for the plugin's `<plugin-slug>/*` namespace (all abilities sharing the extension's ability-ID prefix; see `woo-extension-primitives.md` §1).
- Per-ability average.

**Budget gate.** If `tools/list` exceeds ~2,000 tokens for the plugin:

1. PAUSE before opening the PR. The plugin's ability surface is too large.
2. The right redesign axis is the **projection layer** (e.g. switch to a
   STRAP / facade / nested-discovery shape for how the abilities surface to
   MCP), not the registration layer. Reshaping registrations first locks
   the surface into a granularity decision before measurement tells us
   which shape works.
3. Re-measure after the projection-layer redesign. If still over budget,
   that's a signal to ship a smaller MVP and defer abilities.

**Fallback when `wp-abilities-measure` is not installed.** Produce a manual
estimate: dump the plugin's `tools/list` payload as JSON via `wp eval` and
count tokens with a tokenizer of your choice. Mark the number as
provisional in the PR body so a reviewer knows the measurement floor.

**The token cost number is required in the PR body's "Coverage numbers"
section.**

### Phase VI — Push and open PR

Open the PR against the extension's default branch.

**Read `references/pr-template.md` now** — it contains the parameterized PR
body template plus the rule for reading the extension repo's own
`.github/pull_request_template.md` first and filling its required sections
rather than overwriting them.

#### Phase VI.1 — Drop the AGENTS.md drift guard

Drop one sentence into the extension's `AGENTS.md` (under an existing
"Working in this area" or "When changing X" section, or create one if none
exists):

> When you change the code path behind a registered ability, audit the
> registration for required updates (annotations, schema, description).

This is the low-cost human-loop guard against silent drift between the
ability and its backing service / REST controller. Land it in its own
commit:

```
chore(agents): note ability-registration audit when changing controller code
```

## Ambiguity handling — where to pause

Pause and ask the user before proceeding when:

- Any `proposed_abilities` entry in the audit has `backing: null`.
- Any proposed ability's Notes mention an alternative backing controller.
- The audit's `plugin_family` differs from the family auto-detected from
  CWD.
- The capability gate declared in the audit differs from what the base REST
  controller resolves to when re-read at scaffold time.
- The `route_registration_line` / `callback_line` hints from the audit do
  not resolve to a matching `(class, callback_name)` pair in the current
  branch (hints drift; re-grep is authoritative).

Every entry in this list pauses for the operator — there is no safe
auto-resolution path.

## Error codes vocabulary

Every `WP_Error` returned from an execute callback must use the
standardized vocabulary so agents can build retry logic that does not
depend on string matching. The vocabulary is defined upstream:

**If the `wp-abilities-api` skill from WordPress/agent-skills is installed,
read its `references/error-code-vocabulary.md` now.** Otherwise the minimum
set of error codes used by the templates in this skill is:

- `<plugin_slug>_invalid_input` — input failed validation (mirrors the
  Abilities API's own `ability_invalid_input`).
- `<plugin_slug>_missing_<field>` — a specific required field was missing
  when the callback ran without schema validation (e.g. invoked directly).
- `<plugin_slug>_not_found` — a referenced resource (order, product, etc.)
  did not exist.
- `<plugin_slug>_permission_denied` — capability check failed *after* the
  permission_callback already passed (rare; usually indicates a
  data-dependent permission gate the callback re-checks).

Align with the extension's existing `WP_Error` code conventions and text
domain. If the extension already uses `<plugin_slug>_rest_*` or
`woocommerce_<ext>_rest_*` codes elsewhere, mirror that prefix rather than
inventing a new namespace.

## Done criteria

Before declaring done, walk the checklist:

- [ ] All commits atomic — one file per commit is not required, but one
      logical change per commit is.
- [ ] Each registered ability has its own feature commit.
- [ ] Unit tests green locally with the extension's own test command (see
      the extension's `AGENTS.md` or `composer.json`/`package.json`
      scripts).
- [ ] PHPCS (or the extension's lint command) clean on the new files.
- [ ] Integration harness captured to
      `plans/<YYYY-MM-DD>-<plugin-slug>-abilities-harness-output.md` (via
      `wp-abilities-verify` if installed, otherwise the manual fallback).
- [ ] PR body fills the sections required by the extension's own
      `.github/pull_request_template.md`.
- [ ] PR open and linked in the terminal output.

When the checklist is clean, report the PR URL to the user.
