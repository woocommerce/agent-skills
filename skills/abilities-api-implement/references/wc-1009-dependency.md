# WC 10.9 dependency — the loader-only stance

> **Read this before scaffolding any registrar.** The other references in this skill assume the rationale captured here.

The Abilities API surface this skill scaffolds depends on **WooCommerce 10.9 or later**. On stores running WC < 10.9 the abilities feature silently no-ops: the `Abilities_Registrar` bails before referencing any `Domain/<Name>` class, no abilities register, `wp_get_ability( '<plugin-slug>/<name>' )` returns null. No polyfill ships. No fallback registration path exists.

## Why no fallback

Forward-looking design. Extensions adopting the Abilities API should depend on the WC 10.9 loader as a first-class requirement rather than papering over its absence. A fallback registrar — one that re-implements the loader's contract on older WC versions — would seed the pattern of "every extension carries its own version-compat layer." Across the ~40 plugins in the wider Abilities Everywhere effort, that propagation cost is the real argument against shipping a fallback.

Practical safety net: every extension registered by this skill gates behind a `<plugin_slug>_abilities_enabled` filter (default false). Stores on WC < 10.9 don't lose anything because they couldn't enable the feature in production today anyway. The feature flag remains the rollout safety net; the loader-only gate is the structural one.

## What "depends on WC 10.9" means concretely

The WC 10.9 loader is `\Automattic\WooCommerce\Internal\Abilities\AbilitiesLoader`. The registrar's gate uses a single `class_exists()` check:

```php
private static function woo_abilities_loader_available(): bool {
    return class_exists( '\\Automattic\\WooCommerce\\Internal\\Abilities\\AbilitiesLoader' );
}
```

WC 10.9 also depends on WP 6.9, which is what introduced `wp_register_ability()` and the `WP_Ability` class. Because the loader is only present on WC 10.9+, and WC 10.9 only runs on WP 6.9+, **a single `class_exists()` check on the loader transitively guarantees** both the WC and WP capabilities the abilities surface needs. No second guard for `function_exists( 'wp_register_ability' )` is required inside `init()`. The registrar does not call `wp_register_ability_category()` at all — Woo Core owns the shared `woocommerce` category (see `woo-extension-primitives.md` §5).

## Why the lazy-autoload trick works

The registrar's `ABILITY_CLASSES` array uses `::class` constants:

```php
private const ABILITY_CLASSES = [
    Domain\GetSubscriptionStatuses::class,
    Domain\GetSubscriptions::class,
    // ...
];
```

`::class` constants are compile-time strings — referencing them does **not** autoload the classes. The classes only resolve when Woo Core's loader actually iterates them, and that iteration only fires on WC 10.9+ where the `AbilityDefinition` interface exists. So even though each Domain class has `use Automattic\WooCommerce\Abilities\AbilityDefinition;` at the top, **the file never loads on WC < 10.9** — Composer's autoloader is asked for the class only after the loader has been confirmed present. PHP's class-resolution lazy evaluation does the rest.

The same property keeps test files safe: PHP `use` imports at the top of a test file do not autoload — only method invocations do. As long as the test's `setUp()` (or first method assertion) skips before any `Domain\<X>::method()` call, the test file loads safely on WC < 10.9.

## Test-environment implications

| Environment | Behaviour |
|---|---|
| PHPUnit on WC < 10.9 | Domain-class tests skip via `markTestSkipped( 'WooCommerce 10.9 AbilitiesLoader required for this test.' )`. The unresolved-interface fatal never fires because no Domain-class method is ever invoked before the skip. |
| PHPUnit on WC 10.9+ | Full coverage runs. Domain classes load and the `wp_get_ability()` shape assertions succeed. |
| Production WC < 10.9 with the feature flag flipped on | The filter applies but produces no abilities. No errors, no notices. `wp_get_ability()` returns null. |
| Production WC 10.9+ with the feature flag flipped on | Abilities register normally via the loader filter. |

**CI pinning.** Until WC 10.9 ships a stable or dev tag, the entire abilities test suite skips on the extension's CI matrix. That is the correct interim state — failing on WC 10.7 would be a false signal. As soon as a WC 10.9 dev/RC tag is available, update the test installer to pin to it and de-skip.

## What is NOT supported

Third-party integration code referencing `<plugin-namespace>\Internal\Abilities\Domain\<Name>` directly **fatals on WC < 10.9** (`Interface AbilityDefinition not found`). This is documented behaviour — direct integration with the Domain classes is not part of the public API.

The supported entry points are:

- `wp_get_ability( '<plugin-slug>/<name>' )` — for callers that want a specific ability.
- The `woocommerce_ability_definition_classes` filter — for callers that want to extend the registered class list.

If you find code in the wild reaching into a `Domain/<Name>` class directly, the right answer is "use the public entry points"; the right answer is not "ship a polyfill so the direct path keeps working."

## Diagnostic surface

If an operator wants to know why abilities aren't registering on a WC < 10.9 store, the bail path is silent by design. The diagnostic surface is:

```
wp eval 'var_dump( class_exists( "\\\\Automattic\\\\WooCommerce\\\\Internal\\\\Abilities\\\\AbilitiesLoader" ) );'
wp wc version
```

No log line is emitted on bail. Logging "WC 10.9 not present" on every page load would be noisy; the silent bail is correct.

## See also

- `registrar-template.md` — the coordinator that implements this gate.
- `paginated-output-envelope.md` — the output-shape convention WC 10.9's loader makes practical to standardize across abilities.
