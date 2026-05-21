# Woo-extension primitives

The rules an audit doc cannot encode on its own. Read this before you
scaffold the first ability in any WooCommerce extension.

## 1. Ability namespace = the extension's slug, NOT `woocommerce/`

The `woocommerce/` namespace is reserved for WooCommerce Core. Every
ability your extension registers must use the extension's own slug:

| Extension | Slug | Ability ID |
|---|---|---|
| WooCommerce Gift Cards | `gift-cards` | `gift-cards/get-card-balance` |
| WooCommerce Min/Max Quantities | `min-max-quantities` | `min-max-quantities/get-rules-summary` |
| WooCommerce Shipping | `woocommerce-shipping` | `woocommerce-shipping/get-shipment-summary` |
| WooPayments | `woopayments` | `woopayments/get-account-status` |

Picking the slug:

- Use the extension's plugin slug (the directory name under `wp-content/plugins/`,
  with the `woocommerce-` prefix stripped if it makes the ID redundant).
- Kebab-case.
- Stable. The slug becomes the public ID agents call; renaming it is a
  breaking change for every caller.

If the audit doc proposes ability IDs prefixed with `woocommerce/` or with
a different slug than the extension's own, PAUSE and ask the user. The
audit may be operating on an outdated reading of the rule.

## 2. One class per ability, registered through Woo's loader

The WC 10.9 loader (`\Automattic\WooCommerce\Internal\Abilities\AbilitiesLoader`) iterates classes that implement `\Automattic\WooCommerce\Abilities\AbilityDefinition` and registers each via `wp_register_ability()` with the args returned by `<Class>::get_registration_args()`. The shape this skill teaches:

- One PHP file per ability, under `<plugin-namespace>\Internal\Abilities\Domain\`.
- Each class extends a plugin-local `Abstract<Plugin>Ability` (shared helpers — `CATEGORY_SLUG`, pagination helpers, `delegate_to_rest_controller()`) and implements `AbilityDefinition`.
- A thin `Abilities_Registrar` coordinator holds an `ABILITY_CLASSES` array of `Domain\<Name>::class` constants and appends them to Woo's loader via the `woocommerce_ability_definition_classes` filter.

```php
// Coordinator excerpt — full skeleton in registrar-template.md.
private const ABILITY_CLASSES = [
    Domain\GetSubscriptionStatuses::class,
    Domain\GetSubscriptions::class,
    // ...
];

public static function append_classes( array $classes ): array {
    return array_merge( $classes, self::ABILITY_CLASSES );
}
```

`::class` constants are compile-time strings — listing them does NOT autoload the Domain classes. The classes resolve only when Woo's loader iterates the filter return value on WC 10.9+. On WC < 10.9 the registrar bails before adding the filter, and the Domain files never load.

### No fallback path

On WC < 10.9 this skill registers nothing. There is no polyfill, no bootstrap-wired fallback that bypasses the loader, no compatibility shim. Three reasons:

1. **Forward-looking design.** Shipping a fallback would seed the pattern of "every extension carries its own version-compat layer," which propagates complexity across the ~40 plugins in the wider Abilities Everywhere effort.
2. **Safety net is the feature flag.** Every ability gates behind a `<plugin_slug>_abilities_enabled` filter (default false). Stores on WC < 10.9 don't lose anything because they couldn't enable the feature in production today anyway.
3. **The lazy-autoload trick only works one way.** A Domain class with `use Automattic\WooCommerce\Abilities\AbilityDefinition;` at the top is only safe to ship because the file never parses on WC < 10.9. A fallback path that tried to load the same class on older WC would fatal on the missing interface.

For the full rationale — including the test-environment implications and the "what is NOT supported" carve-out for third-party integration code reaching into Domain classes directly — read **`references/wc-1009-dependency.md`**.

### Plugin-wide `WC requires at least:` stays at the existing floor

The abilities feature alone has the stricter WC 10.9 dependency. The plugin's `WC requires at least:` header in the main plugin file stays at the existing floor (whatever the extension already requires). The feature-flag default-off plus the silent bail handle the WC < 10.9 case without rolling the whole plugin's floor forward.

## 3. Do NOT expose new extension abilities through `/wp-json/woocommerce/mcp`

The `/wp-json/woocommerce/mcp` REST namespace is the **deprecated**
WooCommerce-specific MCP endpoint kept around for backwards compatibility
with early adopters. New extension abilities should NOT opt into this
endpoint by default — they should live on the **shared** MCP adapter
that the WordPress Abilities API exposes through `meta.mcp.public = true`.

Concretely, this means:

- Do **not** set `expose_in_deprecated_woocommerce_mcp` (or the equivalent
  per-version flag) when registering abilities.
- Do set `meta.mcp.public = true` on every ability you intend agents to
  call (see `first-ability-template.md` §"meta.mcp.public").
- An ability that needs to be reachable through the deprecated endpoint
  for a specific compatibility reason should call that out in the PR's
  "Notes for reviewers" section with the reason.

## 4. Required `meta.mcp` defaults

For every Woo-extension ability registered by this skill:

| Key | Value | Why |
|---|---|---|
| `meta.mcp.public` | `true` (reads) / `false` (writes, with a deliberate decision) | Reads opt-in to MCP discovery by default. Writes opt-out unless the ability is deliberately public — see the write template's "Permission callback discipline" section. |
| `meta.mcp.type` | omit (defaults to `'tool'`) | `tool` is the right default. Out-of-enum values silently coerce to `tool`. Set explicitly only when registering a resource or prompt projection. |
| `meta.annotations.readonly` | `true` for reads, `false` for writes | Drives the readonly-but-writes detector in `wp-abilities-verify`. Lying here is the bug class that mocks don't catch. |
| `meta.annotations.destructive` | `false` for most writes; `true` for irreversible writes | Tells agents whether two consecutive calls are recoverable. See the write template's annotation-semantics table. |
| `meta.annotations.idempotent` | `false` by default; `true` only when same input always produces same effect | Drives agent retry logic. Lying here turns transient network errors into duplicate effects. |
| `meta.show_in_rest` | `true` for any ability you want reachable via the Abilities API's REST bridge | Independent of `mcp.public` — see the first-ability template's "show_in_rest vs mcp.public" section. |

## 5. Category: always `woocommerce`. Never the plugin slug.

Every WooCommerce-extension ability registers under
`category = 'woocommerce'` — the shared category WooCommerce Core registers
for first-party Woo work. Plugin ownership is carried by the ability
**namespace** (the prefix before the `/` in the ability ID:
`woocommerce-subscriptions/get-subscription`, `woopayments/get-account`,
etc.). Namespace and category serve different purposes:

- **Namespace = ownership.** Which plugin registered the ability. Agents
  and humans filter by namespace to scope to a specific extension.
- **Category = discoverability.** A coarse bucket that helps agents
  (Command Palette, MCP `tools/list` consumers) find related abilities
  across the ecosystem without enumerating every plugin's namespace.

This split reflects the Abilities API's stated design intent — categories
exist specifically to solve "if we throw hundreds of abilities at an AI,
its ability to use them effectively degrades rapidly." They are
mandatory, single-valued, and first-registration-wins, all in service of
the discoverability use case. Ownership lives in namespace, where it
belongs. Per the 2026-05-14 Automattic team convergence on the convention,
every Woo-extension ability lands under the shared `woocommerce` category
for the initial rollout.

### Antipattern: plugin slug as category

```php
// WRONG — duplicates namespace, gives the category field no discoverability value.
const CATEGORY_SLUG = 'woocommerce-subscriptions';

// RIGHT — shared with all WC extensions.
const CATEGORY_SLUG = 'woocommerce';
```

If the audit doc proposes a `proposed_categorization` value that is the
plugin slug, PAUSE — that framing is stale. Update the audit to
`woocommerce` before scaffolding the registrar.

### Do NOT re-register the `woocommerce` category

WooCommerce Core 10.9+ registers the `woocommerce` category itself.
Calling `wp_register_ability_category( 'woocommerce', ... )` from your
extension's registrar triggers `_doing_it_wrong` on every init —
the Abilities API rejects duplicate slug registration (first registration
wins; subsequent calls are silently dropped with the notice). The
`registrar-template.md` scaffold reflects this: the coordinator does NOT
call `wp_register_ability_category()` at all. Just reference the slug.

### Future migration to narrower buckets

The `woocommerce` bucket is deliberately broad today. As the ecosystem
fills out and the single category either becomes unwieldy (too many
abilities for an agent to reason over) OR agents observably pick the
wrong tool from the over-broad bucket, the team will introduce narrower
user-intent categories — candidates floated in the convergence include
`catalog`, `order`, `payments`, `subscriptions`. The trigger for that
migration is **observed need**, not "guess in advance" — ship cautiously,
let usage drive shape. When the trigger fires this section will be
updated; existing abilities migrate via a one-line constant change.

## 6. Capability checks: reuse the extension's existing helpers

Most WooCommerce extensions already have capability-check helpers
(static methods, traits, or `current_user_can()` wrappers) used by their
REST controllers, admin screens, and CLI commands. The ability layer
should call into the same helper, NOT duplicate the check inline:

- **Wrong:** `current_user_can( 'manage_woocommerce' )` inline in every
  ability's permission callback.
- **Right:** A single `Abilities_Registrar::<CanCapHelper>()` (or a
  call into the extension's existing helper) that the ability's
  `permission_callback` points at.

Why: if the extension later tightens the gate (e.g., from `manage_woocommerce`
to a more granular capability, or adds a context check beyond
`current_user_can`), the ability stays in sync because both surfaces
call the same code. Duplicating the inline check guarantees drift.

The audit doc's `capability_gate` field is the load-bearing capability
the base REST controller resolves to. `audit-precondition.md` §5 covers
the re-verification procedure.

## 7. Error returns: `WP_Error`, mirroring the extension's prefix

Return `WP_Error` from execute callbacks for validation failures,
permission failures (rare, since `permission_callback` runs first),
and resource-not-found cases. Use error codes that match the extension's
existing conventions:

- If the extension uses `<plugin_slug>_*` codes, mirror that prefix
  (`<plugin_slug>_missing_<field>`, `<plugin_slug>_not_found`).
- If the extension uses `woocommerce_<ext>_*`, mirror that
  (`woocommerce_<ext>_rest_invalid_input`).
- Avoid inventing a new namespace that doesn't appear elsewhere in the
  extension; agents grep through error-code documentation, and a
  one-off prefix is harder to find.

For the minimum vocabulary, see SKILL.md's "Error codes vocabulary"
section.

## 8. Feature-flag gating: rollout posture, not implementation primitive

The structural gate for any abilities-API rollout in a WooCommerce extension is the **dependency on WooCommerce 10.9** (Abilities API + the `woocommerce_ability_definition_classes` loader). Either WC 10.9 is installed and the loader fires the abilities, or it isn't and the registrar bails silently — that's the safety surface that always applies regardless of any per-plugin flag.

A separate `<plugin_slug>_abilities_enabled` filter is **available** for rollout staging but **not mandatory**:

- The filter pattern (default `false`, operators flip on per-site to opt in early) is useful when the extension wants to ship registration scaffolding to a release before committing to a final ability shape — particularly during the initial pilot when a single misshaped ability could affect every MCP-connected agent on every site.
- It is **not** required: some extensions land their abilities default-on, gated only by the WC 10.9 dependency. That posture is fine when the abilities have been exercised through the public boundary (Phase V Level 2), the readonly-but-writes detector is clean, and the extension's release cadence is comfortable shipping the new agent surface to all installs at once.

Pick per plugin and per release. If you use the filter, see `registrar-template.md`'s `init()` skeleton for the pattern; if you don't, the WC 10.9 `class_exists` guard on `AbilitiesLoader` is sufficient. Either way, document the choice in the PR's "Notes for reviewers" so the next implementer doesn't infer a project-wide policy from one PR's decision.
