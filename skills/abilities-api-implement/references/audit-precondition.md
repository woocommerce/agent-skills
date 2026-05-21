# Audit Precondition Check

> **Context.** This file validates an audit doc produced by
> `wp-abilities-audit` in WordPress/agent-skills. For the canonical
> schema validator, read `wp-abilities-verify/references/audit-schema-validation.md`
> in that repo first — it owns the portable schema checks. This file is the
> WooCommerce-extension wrapper that additionally checks plugin-family
> cross-check against CWD, capability-gate re-verification against the
> plugin-local base REST controller, and the use-case contract sanity
> check.

The pre-flight check that runs before any scaffolding. Hard handoff — if
the audit doc is missing, unparseable, or fails required-field validation,
the implement skill STOPS rather than guessing.

The schema this file extends is defined upstream in
`wp-abilities-audit/references/audit-schema.md` (WordPress/agent-skills).

## 1. Resolve the audit doc path

Resolution order:

1. Explicit path passed as the skill argument.
2. Most recent file matching `*abilities-audit*.md` in `plans/` — prefer the
   operator's vault directory if one is configured (e.g. a `plans/` directory
   inside the operator's notes vault), otherwise the plugin-local
   `plans/`.
3. If neither resolves, ERROR with guidance to run the `wp-abilities-audit`
   skill from WordPress/agent-skills first (or a locally-installed
   equivalent).

Never scaffold without an explicit audit doc on disk.

## 2. Parse the YAML metadata block

The audit doc format is Markdown with a fenced ```yaml block inside the body
(NOT YAML frontmatter — the frontmatter is reserved for a `Last updated`
header). Parse the fenced block.

The YAML may contain inline comments (`# confirmed: y — ...`). Standard YAML
parsers drop these on load. That's fine for structural validation but is
important for the `capability_gate` field — see §5 below.

## 3. Schema validation — defer to `wp-abilities-verify`

Top-level required fields, metadata fields (`repo`, `branch_audited`,
`audited_at`, `auditor`, `baseline_abilities`), and the
`proposed_abilities` entry shape are all owned by the canonical schema
validator upstream.

**Run `wp-abilities-verify/references/audit-schema-validation.md` first.**
The Woo-extension-specific checks in §4–§7 below layer on top — they do
not re-enumerate field tables that the upstream validator already owns.

If `wp-abilities-verify` is not installed, derive the field set from
`wp-abilities-audit/references/audit-schema.md` instead. Either way, do not
proceed past this section without a clean schema pass.

## 4. Handle `backing: null` as a WARNING, not an error

An ability with `backing: null` is a known gap — the auditor flagged the
ability but couldn't identify a backing endpoint. Emit a WARNING like:

```
WARNING: ability <name> has backing: null. This ability needs user
resolution before scaffolding. Options typically are:
  (a) back against an alternative endpoint (if there is one — check audit notes)
  (b) implement a new REST controller as a prerequisite PR
  (c) scope the ability down to what an existing endpoint supports
  (d) defer to a follow-up sprint

How would you like to proceed?
```

Pause for the operator's choice and record it in the PR description's
"Deliberately deferred" section. Null-backing entries need human judgment
that the skill cannot automate — do NOT silently skip them.

## 5. Re-verify the capability gate at scaffold time

The audit's `capability_gate` field is a string, typically with an inline
comment like:

```yaml
capability_gate: manage_woocommerce  # confirmed: y — base <Plugin>_REST_Controller::check_permission() at <path-to-controller> line <N>
```

YAML parsers strip the comment. Even if the comment survives, line numbers
drift between audit time and scaffold time. So:

1. Parse the value portion (e.g. `manage_woocommerce`).
2. Re-read the plugin's base REST controller from the current working
   branch. Locate it by family convention:
   - **woo-extension (preferred path):** grep
     `includes/admin/class-wc-<plugin>-rest-controller.php` and similar
     classic-WP-layout paths for `extends.*REST_Controller`.
   - **woo-extension (PSR-4 layout fallback):**
     `grep -rE "extends.*REST_Controller" src/` to find the base class,
     then extract the `current_user_can(...)` argument from its
     `check_permission()` (or `permission_callback`) method.
3. Extract the actual capability string from the re-read source.
4. If it matches the audit's declared value, proceed.
5. If it differs, PAUSE and ask the user which is correct — the declared
   audit value may be stale (code has moved on since the audit), or the
   audit may be wrong (rare, but possible if the auditor misread the
   base-class inheritance chain).

Record the verified capability string (not the audit string) in the
registrar's capability helper. The registrar template reinforces this rule.

## 6. Cross-check `plugin_family` with CWD detection

The plugin-family detection rule lives upstream. **If the
`wp-abilities-api` skill from WordPress/agent-skills is installed, read
its `references/plugin-family-patterns.md` now** and apply the detection
rule to the current working directory. Otherwise fall back to the
detection heuristic summarized here:

- **woo-extension:** `composer.json` declares a dependency on
  `woocommerce/woocommerce`, OR the plugin's main header declares
  `WC requires at least:`, OR the plugin lives under a path that contains
  `wp-content/plugins/woocommerce-*` (typical WC ecosystem extensions).
  This is the only supported family for this skill.
- **non-Woo (Jetpack-family or generic WordPress plugin):** CWD path
  contains `projects/packages/` or `projects/plugins/` inside an
  `Automattic/jetpack` checkout, OR the composer namespace is
  `Automattic\\Jetpack\\`, OR the plugin lacks any WooCommerce dependency
  declaration. Detected for the *wrong-skill* check below, not for a
  variant path.

If the detection result is non-Woo OR mismatches the audit's declared
`plugin_family`, ERROR:

```
ERROR: this skill is the WooCommerce-extension implementation playbook.
The current worktree appears to be <detected> (or the audit declares
plugin_family=<declared>). Either:
  - switch to the WooCommerce-extension worktree that matches the audit,
  - re-run `wp-abilities-audit` (WordPress/agent-skills) in the current
    CWD to produce a fresh audit against this layout, or
  - use the upstream `wp-abilities-api` skill (WordPress/agent-skills)
    directly with this project's own conventions — Jetpack-family
    abilities work lives in `Automattic/jetpack` (see @enej's PR stack
    starting at jetpack#48246), not in this Woo-extension playbook.
```

This prevents a woo-extension audit from being executed against a non-Woo
worktree (or vice versa), which would produce wrong namespace, wrong
test base class, and wrong bootstrap wiring.

## 7. Use-case contract sanity check

The contract: **an ability is the natural-language shortcut to an action
a human could already perform in the UI.** If no human would do this
through a supported UI or workflow, it stays a REST endpoint, not an
ability.

The upstream `wp-abilities-api/references/domain-vs-projection.md`
frames this as: *"would a human intentionally do this through a
supported UI or workflow?"* — covering both admin and public-facing
surfaces (storefront, account dashboard) and chain-of-actions workflows,
not just admin.

For each entry in `proposed_abilities`, read the `intent` field aloud
through that frame. If the intent looks like:

- An internal cron job
- A webhook receiver
- Server-to-server-only plumbing (e.g., a sync endpoint never surfaced in
  any UI)
- A transport-layer concern (e.g., "list all REST endpoints")

…then it fails the use-case contract test. The default outcome is a
**WARNING** with the operator prompted to confirm or drop the entry — the
audit doc remains authoritative on intent.

**Escalation when the failing entry has `mcp.public: true`.** If a
contract-failing entry is also opted into MCP discovery, the WARNING
becomes a **mandatory PAUSE** — the operator must explicitly type a
one-sentence justification of the trust decision (matching the
public-abilities discipline in `first-ability-template.md` /
`write-ability-template.md`) before scaffolding proceeds. Otherwise an
ability that fails the use-case contract becomes MCP-discoverable as
soon as the feature flag flips on, which is the failure mode this
escalation exists to prevent.

The contract test is a sanity check on the audit, not a substitute for
it. If `wp-abilities-audit` upstream evolves to enforce the test at audit
time, this section becomes a no-op delegation.

## 8. Line-number hints are hints

`backing.route_registration_line` and `backing.callback_line` are captured
at audit time. They may drift. The registrar-template and
first-ability-template references BOTH say to re-locate routes by
`(class, callback_name)` at scaffold time rather than trusting the numbers.

Do not fail the precondition on mismatched line numbers — just note that
the scaffolder will re-locate.

## Summary — precondition outcomes

| Condition | Outcome |
|---|---|
| Audit doc missing or unparseable | ERROR, stop. |
| Required top-level or `proposed_abilities` field missing (upstream validator) | ERROR, stop. |
| Any entry has `backing: null` | WARNING, pause for operator resolution. |
| `capability_gate` differs from re-read base controller | PAUSE and ask the operator. |
| Use-case contract failure (§7) | WARNING, pause. Mandatory PAUSE with written justification when the failing entry has `mcp.public: true`. |
| `plugin_family` mismatch with CWD | ERROR, stop. |
| Line numbers drift | Note it, re-locate at scaffold time, do not error. |

When the precondition passes, emit a short summary:

```
Audit doc: <path>
Plugin: <name> (family: <family>)
Branch audited: <branch>
Proposed abilities: <count> (reads: <n>, writes: <m>)
Excluded from MVP: <count>
Surfaced gaps: <count>
Capability gate (verified): <capability>
Proceed? [y/N]
```

Only after the operator confirms should Phase I scaffolding begin.
