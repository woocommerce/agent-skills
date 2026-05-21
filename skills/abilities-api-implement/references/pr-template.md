# PR Template

Phase VI — the PR body for a WooCommerce extension that registers
abilities.

## Before generating the PR body — read the repo's own template

WooCommerce extensions ship their own `.github/pull_request_template.md`
(or a `.github/PULL_REQUEST_TEMPLATE/` directory of named variants).
Inspect those before generating anything:

```bash
ls .github/pull_request_template.md .github/PULL_REQUEST_TEMPLATE/ 2>/dev/null
```

If the extension's template exists, fill its required sections
naturally. Do NOT replace the repository's template with a project-level
template — that loses information the maintainers expect (changelog
checkboxes, mobile-tested fields, release-note callouts, etc.).

The sections below are what the abilities work itself needs to surface.
Slot them into the extension's template, or use them as the body
verbatim if the extension has no template.

## Parameterization

Fill in from the audit doc + the harness output:

| Placeholder | Source |
|---|---|
| `<PluginName>` | Audit `plugin` (canonical human name, e.g. WooCommerce Gift Cards). |
| `<plugin-slug>` | Audit `plugin` (lowercase, kebab where used as ability prefix). |
| `<plugin-family>` | Audit `plugin_family`. |
| `<category-slug>` | Registrar's `CATEGORY_SLUG`. |
| `<reads>` | List of read-ability names, with one-line descriptions. |
| `<writes>` | List of write-ability names, with one-line descriptions + annotation notes. |
| `<BackingControllers>` | Unique list of backing controller / service classes used. |
| `<Capability>` | Re-verified capability (e.g. `manage_woocommerce`). |
| `<BaseController>` | The base REST controller (or service) that mirrors the capability. |
| `<Deferred>` | `excluded_from_mvp` from the audit + anything deferred at scaffold time. |
| `<HarnessOutputPath>` | `plans/<YYYY-MM-DD>-<plugin-slug>-abilities-harness-output.md`. |
| `<TestCommand>` | The extension's own test command (read AGENTS.md or composer.json/package.json scripts). |
| `<WpEnvUpCommand>` | The extension's environment-startup command. |

## Template body (abilities-specific sections)

```markdown
Registers <PluginName> with the WordPress Abilities API so agents can
interact with the extension without needing direct REST knowledge.
<N> abilities ship in this PR.

#### Read abilities (`readonly: true`, `idempotent: true`)

<reads — one bullet per ability, format:>
- `<plugin-slug>/<ability-name>` — <one-sentence intent>.

#### Write abilities

<writes — one bullet per ability, format:>
- `<plugin-slug>/<ability-name>` — <one-sentence intent>. <Annotation notes: `readonly:false`, `destructive:<bool>`, `idempotent:<bool>`. Call out any non-idempotency or destructive semantic agents need to guard against.>

#### Architecture

- New code under `<path-to-registrar>` (follows the extension's existing autoload convention).
<!-- Include the next bullet only if at least one read uses Shape 2; remove if every read is Shape 3 or zero-arg direct-call. -->
- Shared `Abilities_Registrar::delegate_to_rest_controller()` helper wraps the list-style reads; zero-arg abilities stay on a direct-call path.
- Write abilities use Shape 3 (shared service) — see the abilities-api-implement skill's `write-ability-template.md` for why.
- All abilities gate on `<Capability>` via `<CanCapHelper>()` — matches `<BaseController>::check_permission()`.
- Ability namespace is `<plugin-slug>/*` (NOT `woocommerce/`) per the Woo-extension primitives.
- Abilities opt in to the shared MCP adapter via `meta.mcp.public = true`. They are NOT exposed through the deprecated `/wp-json/woocommerce/mcp` endpoint.

#### Deliberately deferred (tracked for follow-up)

<Deferred — one bullet per item, format:>
- `<name>` — <reason>.

#### Testing instructions

**Unit tests:**

```
<TestCommand> -- --filter Abilities_Registrar_Test
```

Expected: all tests green.

**Integration harness:** run the `wp-abilities-verify` skill from WordPress/agent-skills and paste its Markdown artifact here. It owns the canonical harness (enumerate → annotations → execute reads at Level 1 smoke + Level 2 seeded → write-input validation → permission roundtrip) and emits a paste-ready output block.

**Seeded-data proof.** Alongside the harness output, the template renders a "Seeded data used for verification" block per ability that ran Level 2 — what realistic plugin data was seeded (the audit doc's `seed_data_needs` value, or a concrete description), what id / slug / handle was used as the representative input, and what was asserted (output shape, privacy contract, permission behavior against real records). When `seed_data_needs: null` for an ability, mark it as `pending — Level 1 smoke only`. The point of this block is to let reviewers tell whether execution proved the public ability contract or only proved registration/listing.

Pass criteria: no PHP fatals, no unexpected OKs on the write-ability validation cases, all abilities enumerable, readonly-but-writes detector clean for every `readonly: true` ability, and every ability with a non-null `seed_data_needs` has a Level 2 line showing the seeded input AND the asserted shape/privacy/permission result.

If `wp-abilities-verify` is not installed, run the manual fallback documented in the abilities-api-implement skill's SKILL.md (Phase V) and paste the captured output. The Seeded-data proof block applies the same way.

#### Notes for reviewers

- **Write ability error code:** the Abilities API's schema validation catches missing/non-string required fields before the execute callback fires, so REST-path invocations get `WP_Error(ability_invalid_input)` rather than our custom `<plugin_slug>_missing_<field>`. Our code path still runs when the callback is invoked directly (covered by unit tests). Belt-and-suspenders — both paths reject bad input deterministically.
- **Upstream error codes bubble through** — error codes from any external service (e.g. shipping carrier, payment processor, CRM) surface unchanged on abilities backed by that transport. Left as-is for agent transparency.
- **Capability gate is uniform:** every ability uses `<Capability>`, matching the existing `<BaseController>::check_permission()`. No new permission surface.
- **Rollout posture:** the structural gate is the dependency on WooCommerce 10.9 (the `AbilitiesLoader` `class_exists` guard). This PR additionally uses an `<plugin_slug>_abilities_enabled` filter (default `<true|false> — fill in>`) as a rollout-staging mechanism — fill in the chosen default and the rationale (e.g. "default false during initial pilot; flip to true in a follow-up after harness PASS across N sites" OR "default true; the WC 10.9 dependency is the safety surface"). The filter is optional per `woo-extension-primitives.md` §8; some Woo-extension PRs ship default-on.
- **MCP exposure choice:** the extension's existing REST controllers stay exposed to MCP clients alongside the new abilities. Tightening to abilities-only MCP exposure (via a `show_in_rest_mcp` opt-out on the REST controllers, where applicable) is tracked as a follow-up.
- **Shape choice per ability:** reads in this PR use Shape <2 or 3 — fill in per the skill's Phase III table>. Writes are Shape 3 (shared service) per the mandatory rule. Where Shape 2 (`delegate_to_rest_controller`) is used for a read, the backing controller does not emit telemetry that agent-driven calls would contaminate (verify against the audit doc's `backing` notes).

#### Coverage numbers

- **Abilities registered:** <N> reads + <M> writes.
- **`tools/list` token cost:** <token-count> (measured via `wp-abilities-measure` <or "manually estimated; wp-abilities-measure not installed">). Budget: ≤ 2,000 tokens / plugin.
- **Test count:** <N> unit tests / <M> assertions + integration harness.
- **Lint:** clean (PHPCS / phpstan / equivalent per the extension's convention).
```

## Post-processing steps

After rendering the template:

1. **Fill the extension's own template sections.** If the extension's
   `.github/pull_request_template.md` has sections like "Changes proposed
   in this Pull Request", "Testing instructions", "Changelog entry", or
   release-note checkboxes, fill those naturally with the abilities-PR
   content above.
2. **Verify the changelog step.** Many WooCommerce extensions have a
   changelog-generation step (`composer changelog`, `npm run changelog`,
   or a `changelog.txt` edit) that's enforced by a pre-commit hook or
   CI. Run it before pushing.
3. **Match the extension's test-command convention.** Don't hardcode
   `npm run test:php` if the extension uses `composer test-unit` or
   `vendor/bin/phpunit`. Read `AGENTS.md` / `composer.json` /
   `package.json` scripts to find the canonical command.
4. **Keep local-only verification artifacts out of the commit.** Seed scripts, temporary `wp-env.override.json` files, one-off verification helpers, harness scratch dirs, and inspector PHP snippets used during Phase V should live under the repo's existing gitignored paths (typically `.local/`, `tmp/`, or the operator's own `plans/` directory — never the extension's source tree). Verify with `git status` before staging the PR's commits; if a local artifact looks tracked, add it to the appropriate `.gitignore` rather than committing it. The verification work is still repeatable during the PR because the Seeded-data proof block above documents the inputs.
5. **Match the extension's `wp-env` setup.** Some extensions ship their
   own `.wp-env.json`; others rely on a parent WooCommerce wp-env. Use
   the extension's documented setup before falling back to a fresh
   harness.

## Submitting the PR

```bash
gh pr create \
    --title "feat: register <PluginName> with the WordPress Abilities API" \
    --body-file <path-to-rendered-body>.md \
    --base <extension-default-branch> \
    --draft
```

`--draft` is the default for the initial open — flip to ready-for-review
after the integration harness paste and the maintainers have eyes on the
shape.

Return the PR URL to the operator. The skill's job ends here.

## What NOT to include

- **PII** — test merchant IDs or real customer data from the harness
  output. If the harness logged any, scrub them in the harness-output
  file before referencing it.
- **Secrets** — wp-env typically has a hardcoded admin password and empty
  external-service test keys; those are fine to include, but double-check
  before pasting any config output.
- **`@` mentions of specific humans** unless the operator explicitly
  approves — PR notifications are noisy. Prefer team-handle mentions or
  `cc:` lines.
