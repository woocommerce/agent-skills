# Registrar Template — WooCommerce extension (WC 10.9 loader)

> **Upstream first.** For the portable shape of the loader-only pattern, read `wp-abilities-api/references/plugin-family-patterns.md` in WordPress/agent-skills first if installed. This file is the Woo-extension wrapper: namespace, file locations, test base class, bootstrap wiring, and the abstract Domain base.
>
> **Read these references first too:**
>
> - `wc-1009-dependency.md` — why the registrar bails silently on WC < 10.9 with no fallback.
> - `paginated-output-envelope.md` — the abstract base also hosts the paginated-output helpers; cross-reference rather than duplicate.

The Phase I scaffold for the plugin's `Abilities_Registrar` coordinator and its abstract Domain base class. The coordinator does NOT host ability bodies — those land in `Domain/<Name>.php` files in subsequent phases (see `first-ability-template.md`).

## Parameterization — five variables

| Variable | Source | Example |
|---|---|---|
| `<Plugin>` | Human-readable plugin name (no `woocommerce-` prefix in the abstract-base class name) | `MyThing` |
| `<PluginNamespace>` | `composer.json` PSR-4 mapping — the plugin's root namespace, parent of `<Namespace>` | `MyOrg\My_Thing` |
| `<Namespace>` | `<PluginNamespace>` + the abilities-namespace suffix the plugin uses — where the registrar and Domain classes live | `MyOrg\My_Thing\Internal\Abilities` |
| `<Capability>` | Re-read from the base REST controller at scaffold time (see §"Capability-helper rule") | the cap your plugin's base controller enforces |
| `<CanCapHelper>` | `can_<verb>_<object>` — one-verb helper name used everywhere | `can_read_<things>` |

The category slug is **not** a per-extension variable: every Woo extension registers under the shared `woocommerce` category that Woo Core owns. See `woo-extension-primitives.md` §5 for the convention + antipattern.

`<PluginNamespace>` is needed by Phase IV's write template when referring to shared services that live as siblings of the abilities namespace (e.g. `<PluginNamespace>\Internal\Service\<Thing>_Service`).

The audit doc is authoritative for the plugin slug, capability, and helper name — re-grep the consuming extension's `composer.json` before scaffolding to confirm the namespace, and follow the extension's existing class-loading and instantiation patterns rather than transplanting another extension's conventions. The structural shape this template teaches (coordinator + `Domain/` subfolder + WC 10.9 loader hook) is generic; the file paths, class-name style, and bootstrap wiring vary per extension.

## File locations

Two autoload layouts cover the vast majority of WooCommerce extensions. Pick the one that matches the plugin under your CWD (grep `composer.json` for the `autoload.psr-4` key):

| Layout | Coordinator | Abstract base | Domain class | Coordinator test | Domain test |
|---|---|---|---|---|---|
| PSR-4 under `src/Internal/` | `src/Internal/Abilities/Abilities_Registrar.php` | `src/Internal/Abilities/Domain/Abstract<Plugin>Ability.php` | `src/Internal/Abilities/Domain/<Name>.php` | `tests/unit-src/Internal/Abilities/Abilities_Registrar_Test.php` | `tests/unit-src/Internal/Abilities/Domain/<Name>Test.php` |
| PSR-4 under `src/` | `src/Abilities/Abilities_Registrar.php` | `src/Abilities/Domain/Abstract<Plugin>Ability.php` | `src/Abilities/Domain/<Name>.php` | `tests/Unit/Abilities/Abilities_Registrar_Test.php` | `tests/Unit/Abilities/Domain/<Name>Test.php` |

If the extension uses a classic `includes/` (non-PSR-4) layout, follow its naming convention and adapt the locations above. The structural shape — coordinator + `Domain/` subfolder — does not change.

The `Domain/` subfolder mirrors Woo Core 10.9's `Internal\Abilities\Domain\*` convention. "Domain" is a slight misnomer for REST-delegated abilities, but matching Woo Core's structural naming aids cross-codebase navigation.

## Bootstrap wire

Grep for the extension's main plugin class (`class <Plugin>` in the bootstrap file, usually `<plugin-slug>.php` at the repo root or `includes/class-<plugin-slug>.php`). Find its `init()` method (or whatever the extension calls its bootstrap entry — `init_hooks()`, `run()`, `register()`). Add at the very end:

```php
\<Namespace>\Abilities_Registrar::init();
```

A single call from the plugin's init path is sufficient — the registrar's own `init()` wires the WC 10.9 loader filter.

## Test base class + test command

Grep `tests/unit-src/` (or `tests/Unit/`) for `extends .*_UnitTestCase` / `extends .*TestCase` — use whichever class the extension's existing tests already extend. Do not invent a new one.

The test command follows the extension's own setup. Check the extension's `AGENTS.md` or `composer.json` / `package.json` scripts for the canonical command.

## Re-locate rule — line numbers are hints, names are authoritative

The audit's `route_registration_line` and `callback_line` fields are hints from audit time. Before touching any lines, re-grep the backing controller for `register_routes` and the `<callback_name>` method definition. Use the re-grep result, NOT the audit's line number.

The audit's `(class, callback_name)` pair is authoritative. If the audit's class and callback name don't resolve in the current branch, PAUSE and ask the user whether the backing has moved.

## Capability-helper rule

The re-verification procedure (parse the audit value → re-read the plugin's base REST controller by family convention → extract the actual `current_user_can(...)` argument → PAUSE on mismatch) is owned by `audit-precondition.md` §5. Use the verified value coming out of that check.

**Sanity check the verified value before scaffolding** — `current_user_can( 'read' )` is held by every subscriber on a typical WordPress install, so it is almost never the right gate for merchant or store-management data. If the verified value is `read` (or any other capability granted to subscribers by default), PAUSE — the base controller is probably gating elsewhere (e.g. a `permission_callback` that does its own `current_user_can( 'manage_woocommerce' )` after a preliminary `read` check, or a post-type capability shadow that routes through `map_meta_cap` to a different cap). Re-trace and use the load-bearing capability.

---

## Coordinator skeleton

```php
<?php
/**
 * Class Abilities_Registrar
 *
 * @package <Plugin>
 */

// @phan-file-suppress PhanUndeclaredFunction, PhanUndeclaredClassMethod @phan-suppress-current-line UnusedSuppression -- Abilities API added in WP 6.9; suppression covers the WP 6.8 compat run. @todo Remove when <Plugin> drops WP <6.9.

namespace <Namespace>;

/**
 * Registers <Plugin> abilities with the WordPress Abilities API.
 *
 * Thin coordinator: holds the ABILITY_CLASSES list and the
 * <CanCapHelper>() capability helper that mirrors the load-bearing read
 * gate resolved by the REST controllers.
 *
 * Gated by the `<plugin_slug>_abilities_enabled` filter (default false).
 *
 * Registration pattern: abilities are registered exclusively via Woo
 * Core's `woocommerce_ability_definition_classes` loader filter
 * (introduced in WC 10.9). On stores running WC < 10.9 the feature
 * silently no-ops — see `woo_abilities_loader_available()`.
 *
 * @internal This class may be modified, moved or removed in future releases.
 */
class Abilities_Registrar {

    /**
     * Category slug used for every <Plugin> ability.
     *
     * The `woocommerce` category is owned and registered by WooCommerce
     * Core (10.9+); plugin ownership lives in the ability namespace, not
     * the category. Mirrored on `Abstract<Plugin>Ability::CATEGORY_SLUG`
     * so Domain classes can reference `self::CATEGORY_SLUG` without a
     * cross-namespace static call. See `woo-extension-primitives.md` §5.
     *
     * @var string
     */
    const CATEGORY_SLUG = 'woocommerce';

    /**
     * Ability definition classes registered through the WC 10.9 loader.
     *
     * Every <Plugin> ability is listed here. The ::class constants are
     * compile-time strings — referencing them does NOT autoload the
     * classes. They resolve only when Woo's loader iterates the filter
     * return value on WC 10.9+.
     *
     * @var array<int, class-string>
     */
    private const ABILITY_CLASSES = [
        // Filled in subsequent phases — one Domain\<Name>::class per ability.
    ];

    /**
     * Whether init() has already wired its action callbacks.
     *
     * Without this guard, repeated calls to init() while the feature filter
     * is true would each append a fresh `add_action()` for the registrar
     * callbacks, and WP_Abilities_Registry::register() would emit
     * `_doing_it_wrong` notices for every already-registered slug when the
     * action fires.
     *
     * @var bool
     */
    private static $initialized = false;

    /**
     * Initialize the abilities registration.
     *
     * @return void
     */
    public static function init(): void {
        if ( self::$initialized ) {
            return;
        }

        /**
         * Filter whether <Plugin>'s Abilities API registrations are active.
         *
         * @since x.y.z
         *
         * @param bool $enabled Whether to register <Plugin> abilities. Default false.
         */
        if ( ! apply_filters( '<plugin_slug>_abilities_enabled', false ) ) {
            return;
        }

        if ( ! self::woo_abilities_loader_available() ) {
            // Abilities feature requires WC 10.9. Silently no-op on older
            // versions; the feature flag is the rollout safety net.
            return;
        }

        self::$initialized = true;

        add_filter( 'woocommerce_ability_definition_classes', [ __CLASS__, 'append_classes' ] );
    }

    /**
     * Reset the idempotency guard set by init().
     *
     * @internal Test-isolation helper. Not part of the public API.
     *
     * @return void
     */
    public static function reset_initialized_for_testing(): void {
        self::$initialized = false;
    }

    /**
     * Whether WC 10.9's AbilitiesLoader is available.
     *
     * Used as a hard gate: on WC < 10.9 the abilities feature silently
     * no-ops. WC 10.9 also depends on WP 6.9, so wp_register_ability()
     * is implicitly available wherever the loader exists.
     *
     * @return bool
     */
    private static function woo_abilities_loader_available(): bool {
        return class_exists( '\\Automattic\\WooCommerce\\Internal\\Abilities\\AbilitiesLoader' );
    }

    /**
     * Append <Plugin> ability classes to Woo Core's loader.
     *
     * Filter callback for `woocommerce_ability_definition_classes`.
     *
     * @param array $classes Class names accumulated by the loader.
     * @return array
     */
    public static function append_classes( array $classes ): array {
        return array_merge( $classes, self::ABILITY_CLASSES );
    }

    /**
     * Permission callback for read abilities.
     *
     * Mirrors the REST controllers' resolved read gate.
     *
     * @return bool
     */
    public static function <CanCapHelper>(): bool {
        return current_user_can( '<Capability>' );
    }
}
```

The `Abilities_Registrar` exposes **no** registration helpers (`register_*_ability()` methods) and **no** execute callbacks. Concrete abilities live in `Domain/<Name>` classes — see `first-ability-template.md`.

### Shared helpers may stay on the coordinator

If the plugin has shared helpers used by multiple Domain abilities — capability helpers (`<CanCapHelper>()`), cache-clear hooks, projection/normalization helpers, cache-key constants — they live as public static methods (or constants) on `Abilities_Registrar`. The coordinator is a fine home for cross-ability concerns; it's specifically the per-ability `register_*()` and `execute_*()` methods that move out into `Domain/<Name>.php` files.

## Abstract base — `Domain/Abstract<Plugin>Ability.php`

The Domain classes share helpers via a plugin-local abstract base. Two reasons to define it locally rather than extend Woo Core's `Internal\Abilities\Domain\AbstractDomainAbility`:

1. Woo Core's lives under `Internal\` (implicit internal API). Reaching into it from another plugin couples the extension to a class Woo Core can rename or relocate without warning.
2. The base hosts plugin-specific concerns (the `<textdomain>` for translations, the `delegate_to_rest_controller()` helper's WP_Error code namespace).

Scaffold:

```php
<?php
/**
 * Abstract base class for <Plugin> ability definitions.
 *
 * @package <Plugin>
 */

namespace <Namespace>\Domain;

/**
 * Shared helpers for <Plugin> ability definitions.
 *
 * Mirrors the shape of Woo Core's `Internal\Abilities\Domain\AbstractDomainAbility`
 * without coupling <Plugin> to that class.
 *
 * @internal
 */
abstract class Abstract<Plugin>Ability {

    /**
     * Ability category slug shared across every Domain ability.
     *
     * The `woocommerce` category is owned and registered by WooCommerce
     * Core (10.9+); plugin ownership lives in the ability namespace, not
     * the category. Mirrors `Abilities_Registrar::CATEGORY_SLUG` so Domain
     * classes can reference `self::CATEGORY_SLUG` without a cross-namespace
     * static call. Both consts intentionally exist — the registrar's is the
     * stable public-API surface for outside callers; this one is the
     * per-ability convenience.
     */
    public const CATEGORY_SLUG = 'woocommerce';

    /**
     * Execute a backing REST controller route and return its unwrapped response.
     *
     * Visibility is `protected` so Domain subclasses inherit this helper.
     *
     * @param string $controller_class Fully-qualified backing controller class
     *                                 (informational; surfaces a clear error when not loaded).
     * @param string $method           HTTP method (GET, POST, PUT, DELETE).
     * @param string $route            Resolved route path.
     * @param array  $params           Request parameters.
     * @param bool   $return_response  When true, return the WP_REST_Response object
     *                                 so callers can read response headers (e.g. X-WP-Total).
     * @return array|\WP_REST_Response|\WP_Error
     */
    protected static function delegate_to_rest_controller(
        string $controller_class,
        string $method,
        string $route,
        array $params = [],
        bool $return_response = false
    ) {
        if ( ! class_exists( $controller_class ) ) {
            return new \WP_Error(
                '<plugin_slug>_missing_controller',
                sprintf(
                    /* translators: %s: fully-qualified class name of the missing REST controller. */
                    __( 'REST controller %s is not loaded.', '<textdomain>' ),
                    $controller_class
                ),
                [ 'status' => 500 ]
            );
        }

        $request = new \WP_REST_Request( $method, $route );
        foreach ( $params as $key => $value ) {
            $request->set_param( $key, $value );
        }

        $response = rest_do_request( $request );

        if ( is_wp_error( $response ) ) {
            return $response;
        }

        if ( $response instanceof \WP_REST_Response ) {
            if ( $response->is_error() ) {
                return $response->as_error();
            }
            if ( $return_response ) {
                return $response;
            }
            return $response->get_data();
        }

        return is_array( $response ) ? $response : [ $response ];
    }
}
```

**For pagination helpers — `get_pagination_input_properties()`, `get_collection_output_schema()`, `compute_total_pages()`, `extract_total_from_response()` — read `paginated-output-envelope.md`.** Add them to `Abstract<Plugin>Ability` only when the plugin has at least one list-shaped ability.

### Phan suppression — why it's there

The `wp_register_ability*` functions and `WP_Ability` class don't exist in WP < 6.9. Static analysis runs against both WP versions in CI, hence the compat suppression at the top of the coordinator file. Remove the suppression when the plugin drops WP 6.8 support.

The Domain classes have their own version of this suppression covering the missing `AbilityDefinition` interface on WC < 10.9 — see `first-ability-template.md`.

---

## Phase-I tests

The coordinator's tests live in `tests/.../Abilities_Registrar_Test.php`. Six cases:

1. **Feature-flag off → no wiring.** Default `false` filter means `init()` short-circuits before the loader check.
2. **Loader absent → no wiring.** With the feature filter forced on but `AbilitiesLoader` not present, `init()` returns before adding the `woocommerce_ability_definition_classes` filter.
3. **Loader present → filter wired.** With both gates passing, `init()` adds the `append_classes` callback to the filter.
4. **`append_classes()` round-trip.** The filter callback returns the full `ABILITY_CLASSES` list (and only that list; the test asserts both `assertContains` per class and `assertCount` against the expected size).
5. **Capability helper end-to-end.** Subscribers fail; administrators pass.
6. **`init()` is idempotent.** Two back-to-back `init()` calls (with both gates passing) must register the loader filter callback exactly once — the `$initialized` static guard exists for exactly this. Uses `count_filter_callbacks()` walking `$wp_filter` directly, because `has_filter()` only returns the priority of the first match.

No `test_init_registers_category` case — the coordinator does not register the category. WooCommerce Core owns the `woocommerce` slug; see `woo-extension-primitives.md` §5.

### Test scaffold

```php
<?php
namespace <Namespace>\Tests;

use <TestBaseClass>;
use <Namespace>\Abilities_Registrar;
use <Namespace>\Domain;

/**
 * Tests for the Abilities_Registrar scaffold.
 */
class Abilities_Registrar_Test extends <TestBaseClass> {

    const LOADER_FILTER  = 'woocommerce_ability_definition_classes';
    const FEATURE_FILTER = '<plugin_slug>_abilities_enabled';

    public function tearDown(): void {
        remove_all_filters( self::LOADER_FILTER );
        remove_all_filters( self::FEATURE_FILTER );
        Abilities_Registrar::reset_initialized_for_testing();
        wp_set_current_user( 0 );
        parent::tearDown();
    }

    public function test_init_is_no_op_when_feature_flag_disabled() {
        remove_all_filters( self::LOADER_FILTER );
        remove_all_filters( self::FEATURE_FILTER );

        Abilities_Registrar::init();

        $this->assertFalse(
            has_filter( self::LOADER_FILTER, [ Abilities_Registrar::class, 'append_classes' ] ),
            'Expected init() to short-circuit when the feature filter is unset (default false).'
        );
    }

    public function test_init_bails_when_loader_absent() {
        if ( class_exists( '\\Automattic\\WooCommerce\\Internal\\Abilities\\AbilitiesLoader' ) ) {
            $this->markTestSkipped( 'AbilitiesLoader is present in this environment; bail test only applies when it is absent.' );
        }

        remove_all_filters( self::LOADER_FILTER );
        add_filter( self::FEATURE_FILTER, '__return_true' );

        Abilities_Registrar::init();

        $this->assertFalse(
            has_filter( self::LOADER_FILTER, [ Abilities_Registrar::class, 'append_classes' ] ),
            'init() must not wire the loader filter when AbilitiesLoader is absent.'
        );
    }

    public function test_init_wires_filter_when_loader_present() {
        if ( ! class_exists( '\\Automattic\\WooCommerce\\Internal\\Abilities\\AbilitiesLoader' ) ) {
            $this->markTestSkipped( 'WooCommerce 10.9 AbilitiesLoader required for this test.' );
        }

        remove_all_filters( self::LOADER_FILTER );
        add_filter( self::FEATURE_FILTER, '__return_true' );

        Abilities_Registrar::init();

        $this->assertNotFalse(
            has_filter( self::LOADER_FILTER, [ Abilities_Registrar::class, 'append_classes' ] ),
            'init() must wire the woocommerce_ability_definition_classes filter when AbilitiesLoader is present.'
        );
    }

    public function test_append_classes_returns_all_ability_classes() {
        if ( ! class_exists( '\\Automattic\\WooCommerce\\Internal\\Abilities\\AbilitiesLoader' ) ) {
            $this->markTestSkipped( 'WooCommerce 10.9 AbilitiesLoader required for this test.' );
        }

        $classes = Abilities_Registrar::append_classes( [] );

        $expected = [
            // Filled per-ability as Domain classes land in Phases II–IV.
            // The `use <Namespace>\Domain;` import above resolves
            // `Domain\<Name>::class` references that will go here.
        ];

        foreach ( $expected as $class ) {
            $this->assertContains( $class, $classes, "append_classes() must include $class." );
        }
        $this->assertCount( count( $expected ), $classes, 'append_classes() must return exactly the expected Domain classes.' );
    }

    public function test_<CanCapHelper>_matches_<Capability>_capability() {
        $subscriber_id = self::factory()->user->create( [ 'role' => 'subscriber' ] );
        wp_set_current_user( $subscriber_id );
        $this->assertFalse(
            Abilities_Registrar::<CanCapHelper>(),
            'Subscribers must not pass the <Capability> capability check.'
        );

        $admin_id = self::factory()->user->create( [ 'role' => 'administrator' ] );
        wp_set_current_user( $admin_id );
        $this->assertTrue(
            Abilities_Registrar::<CanCapHelper>(),
            'Administrators must pass the <Capability> capability check.'
        );
    }

    public function test_init_is_idempotent_when_feature_flag_enabled() {
        if ( ! class_exists( '\\Automattic\\WooCommerce\\Internal\\Abilities\\AbilitiesLoader' ) ) {
            $this->markTestSkipped( 'WooCommerce 10.9 AbilitiesLoader required for these tests.' );
        }

        remove_all_filters( self::LOADER_FILTER );
        add_filter( self::FEATURE_FILTER, '__return_true' );

        Abilities_Registrar::init();
        Abilities_Registrar::init();

        $this->assertSame(
            1,
            self::count_filter_callbacks( self::LOADER_FILTER, [ Abilities_Registrar::class, 'append_classes' ] ),
            'init() must not double-register the ability_definition_classes filter callback.'
        );
    }

    /**
     * Count how many times a specific callback is registered on a filter hook.
     *
     * has_filter() returns the priority of the first match or false; it
     * cannot tell us "the same callback is hooked twice." Walk the global
     * $wp_filter structure directly so the idempotency assertion is
     * load-bearing.
     */
    private static function count_filter_callbacks( string $hook, array $callback ): int {
        global $wp_filter;
        if ( ! isset( $wp_filter[ $hook ] ) ) {
            return 0;
        }
        $count = 0;
        foreach ( $wp_filter[ $hook ]->callbacks as $callbacks ) {
            foreach ( $callbacks as $entry ) {
                if ( $entry['function'] === $callback ) {
                    $count++;
                }
            }
        }
        return $count;
    }
}
```

The `reset_initialized_for_testing()` call in `tearDown()` undoes `init()`'s static guard so each case can re-run `init()` from a clean slate. Without it, the first test to call `init()` and pass the feature gate locks every subsequent test in the same process out of the wiring branch.

The `markTestSkipped` guard on tests 3 and 4 is what keeps the suite green on CI matrices running WC < 10.9 — the `Domain\<Name>::class` constants on the right-hand side of `assertContains()` would otherwise force the unresolved-interface fatal at autoload time. See `wc-1009-dependency.md` for the full rationale.

---

## Commit shape

```
feat(abilities): scaffold Abilities_Registrar coordinator + Domain base

Phase I — add the registrar coordinator (with the WC 10.9 loader gate
and the woocommerce_ability_definition_classes filter wire), the
plugin-local Abstract<Plugin>Ability base, the <CanCapHelper>()
capability helper that mirrors <BaseController>::check_permission(),
the feature-flag gate (default off), six unit tests (feature-flag
short-circuit, loader-absent bail, loader-present filter wire,
append_classes() round-trip, capability helper, init() idempotency),
and wire the coordinator into the plugin bootstrap. Concrete abilities
land in subsequent commits.

CATEGORY_SLUG is hardcoded to `woocommerce` — Woo Core (10.9+) registers
that category, so the registrar does not. See `woo-extension-primitives.md` §5.
```
