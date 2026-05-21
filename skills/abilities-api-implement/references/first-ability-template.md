# First Ability Template — WooCommerce extension (WC 10.9 loader)

> **Upstream first.** For the portable shape, read `wp-abilities-api/references/plugin-family-patterns.md` in WordPress/agent-skills first if installed. This file walks through the Domain class shape, defensive guards, and the required tests using a generic zero-arg reference ability.
>
> **Read these first too:**
>
> - `wc-1009-dependency.md` — why the Domain class is safe to ship with `use AbilityDefinition;` at the top despite WC < 10.9 stores never having that interface.
> - `registrar-template.md` — the coordinator that will list this Domain class in `ABILITY_CLASSES`.

Phase II — register the first ability. Pick the simplest safe read (usually a zero-arg "get <thing>-statuses" or "get <thing>-summary" style call that does not need to construct a `WP_REST_Request`). This commit establishes the reference pattern the remaining abilities copy.

Worked-example placeholders used throughout this file: `<plugin-slug>/<ability-name>` (e.g. `gift-cards/get-card-balance`, `subscriptions/get-subscription-statuses`); `<Name>` is the PascalCase form (e.g. `GetCardBalance`, `GetSubscriptionStatuses`).

## Before scaffolding — verify the backing

### Re-locate the backing

The audit provides `backing.class` + `backing.callback` + hint line numbers. Line numbers drift; re-grep by `(class, callback_name)`:

```bash
grep -rn "function <callback_name>" <backing.file>
```

If the class/callback no longer resolves, PAUSE and ask the user.

### Watch for alternative backing controllers

If the audit's `notes` on this ability mention an alternative backing controller — for example, one in the admin namespace and a sibling in a reports namespace with different output shapes — PAUSE and confirm with the user before scaffolding. The two controllers typically have different output shapes (a normalized "reports" schema vs raw passthrough) and that choice affects every agent call to the ability.

## Domain class — file shape

The class lives at `<src-root>/Abilities/Domain/<Name>.php` (or `<src-root>/Internal/Abilities/Domain/<Name>.php` — match the coordinator's layout). One file per ability. Class name matches the ability slug in PascalCase (`<plugin-slug>/get-card-balance` → `Domain\GetCardBalance`).

```php
<?php
/**
 * Get <thing> ability definition.
 *
 * @package <Plugin>
 */

// @phan-file-suppress PhanUndeclaredClassMethod, PhanUndeclaredFunction @phan-suppress-current-line UnusedSuppression -- Abilities API + AbilityDefinition added in WC 10.9; suppression covers older-WC compat runs where this class never loads.

namespace <Namespace>\Domain;

use Automattic\WooCommerce\Abilities\AbilityDefinition;
use <Namespace>\Abilities_Registrar;

/**
 * Registers the <plugin-slug>/<ability-name> ability.
 *
 * <One-paragraph why. What merchant or shopper question does this answer?
 * If this is the reference ability for the migration, say so here.>
 *
 * @internal Only loaded when WooCommerce 10.9+ is active. The
 *           Abilities_Registrar short-circuits before referencing this
 *           class on earlier WC versions; PHP's lazy autoload means the
 *           unresolved AbilityDefinition interface FQN never reaches the
 *           parser there.
 */
class <Name> extends Abstract<Plugin>Ability implements AbilityDefinition {

    public static function get_name(): string {
        return '<plugin-slug>/<ability-name>';
    }

    public static function get_registration_args(): array {
        return [
            'label'               => __( '<Human-readable label>', '<textdomain>' ),
            'description'         => __( '<Description — one or two sentences oriented to what the ability does for the caller>.', '<textdomain>' ),
            'category'            => self::CATEGORY_SLUG,
            'input_schema'        => [
                'type'                 => 'object',
                'default'              => (object) [],
                'properties'           => [],
                'additionalProperties' => false,
            ],
            'execute_callback'    => [ self::class, 'execute' ],
            'permission_callback' => [ Abilities_Registrar::class, '<CanCapHelper>' ],
            // output_schema deliberately omitted — see §"output_schema omission rule" below.
            'meta'                => [
                'annotations'  => [
                    'readonly'    => true,
                    'destructive' => false,
                    'idempotent'  => true,
                ],
                'show_in_rest' => true,
                'mcp'          => [
                    'public' => true,
                ],
            ],
        ];
    }

    /**
     * Execute callback.
     *
     * <One-paragraph description of what the ability does at runtime,
     * including any caveats (e.g. "may issue a remote request on cache
     * miss", "returns the cached value when the remote service is
     * unreachable").>
     *
     * @param mixed $input Optional; ability input. <Unused for this ability (empty input_schema) but accepted to match the Abilities API execute_callback signature.>
     * @return array|\WP_Error Array of <thing> data, or WP_Error when the
     *                         plugin has not finished initializing or the
     *                         cached data is unavailable due to a remote
     *                         error.
     */
    public static function execute( $input = null ) {
        unset( $input );

        if ( ! function_exists( '<backing_function>' ) ) {
            return new \WP_Error(
                '<plugin_slug>_not_initialized',
                __( '<Plugin> is not initialized.', '<textdomain>' )
            );
        }

        return <backing_function>();
    }
}
```

## Wire the class into the coordinator

After writing the Domain class, add its `::class` constant to `Abilities_Registrar::ABILITY_CLASSES`:

```php
private const ABILITY_CLASSES = [
    Domain\<Name>::class,
    // ... future Domain classes ...
];
```

That's the entire wire. No `register_<name>_ability()` method, no `wp_register_ability()` call inside the registrar — Woo's loader handles the registration when it iterates the filter return value.

## `meta.mcp.public` — opt into MCP discovery

`meta.mcp.public` defaults to `false`. An ability registered without `mcp.public: true` is valid against the Abilities API but invisible to MCP clients connecting through the bundled WordPress MCP adapter. The whole point of registering abilities is to expose plugin capabilities to agents — leaving this off ships an agent-facing surface that no agent can see.

The read path lives in the `wordpress/mcp-adapter` package (`includes/Abilities/McpAbilityHelperTrait.php` line 37): the adapter reads `$meta['mcp']['public']` and excludes abilities where the value is falsy. Set `'public' => true` for every ability you intend agents to call.

`meta.mcp.type` defaults to `'tool'` and accepts the enum `'tool' | 'resource' | 'prompt'`. Out-of-enum values silently coerce to `'tool'`. Usually omit. Set explicitly only when registering a resource or prompt projection.

## `show_in_rest` vs `mcp.public` — they target different surfaces

Both keys opt an ability into a projection, but the projections are independent:

- `show_in_rest: true` exposes the ability through the Abilities API's own REST namespace (`/wp-json/wp-abilities/v1/...`). The REST bridge — agents talking REST hit this.
- `mcp.public: true` exposes the ability through the WordPress MCP adapter — agents talking MCP hit this.

Most agent-facing abilities want both. Setting one and not the other is deliberate (e.g., a debug-only ability with both `false` for local-only enumeration). Don't conflate them.

## `output_schema` omission rule

Omit `output_schema` by default. The Abilities API does not require it — the field is informational for agents. Duplicating the payload shape in the Domain class couples the registration to any upstream change in the backing service or REST controller. Leave it out and keep the inline comment explaining why; if a reviewer asks, point at the comment.

**List-shaped abilities are the exception.** When the ability returns the paginated envelope from `paginated-output-envelope.md`, do include the `output_schema` — both because the envelope shape is the contract agents grep for, and because `get_collection_output_schema()` makes the schema trivial to build.

## `input_schema.default` is NOT a property-default

Even though the schema has `'default' => (object) []`, the Abilities API's validate path does NOT inject property-level defaults into `$input` before the execute callback runs. This bites harder on write abilities with required fields (see `write-ability-template.md`). For zero-arg reads the empty default is safe because the execute callback ignores input.

The `(object) []` cast (rather than bare `[]`) is deliberate — bare `[]` JSON-encodes to a JSON array at the validator boundary, not an object, and `WP_Ability::normalize_input()` substitutes the top-level default verbatim before `validate_input()` runs. The cast keeps the validator boundary unambiguous for an `object`-typed schema; see `wp-abilities-api/references/input-schema-gotchas.md` upstream for the canonical write-up.

## Execute method — required signature

Always accept `$input` with a `null` default, even for zero-input abilities. The Abilities API passes input positionally; a method with zero parameters would work TODAY but breaks when a future version of this same ability adds input. Make the signature future-compatible from the start.

When the ability genuinely ignores input, `unset( $input );` as the first line documents the intent without firing linter warnings about an unused parameter.

## Three-way discriminator — `false` vs `[]` vs `array`

Backing service methods that cache often return `false` on cache miss + remote error, `[]` on "no data" (connected but nothing to return), and an array on success. Treat all three distinctly:

| Return value | Meaning | Ability response |
|---|---|---|
| `false` | Cache miss + remote error | `WP_Error('<plugin>_<thing>_data_unavailable')` |
| `[]` (empty array) | Connected, no data | `[]` |
| non-empty array | Success | the array |

Coalescing `false` into `[]` (e.g. `return (array) $data;`) hides the error path from the agent. Always use the explicit three-way check.

If the backing service does not use the `false`/`[]`/array convention — many extensions throw exceptions or return `null` instead — adapt the discriminator. The principle is the same: distinguish "failed to fetch" from "fetched, no data" so the agent can retry vs. accept.

## ID-field validation lives in the write template

The worked example here is zero-arg. For abilities with required ID fields, see `write-ability-template.md` — the four-check pattern (array shape, key presence, type, non-empty) and the `empty('0')` gotcha are documented there alongside the write-side worked example.

## Tests — shape + permission (minimum two)

Test class lives at `tests/.../Domain/<Name>Test.php`. The `setUp()` skip guard is mandatory — without it, the test file's `use <Namespace>\Domain\<Name>;` import is safe but any test method invoking `<Name>::method()` fatals on WC < 10.9.

### Setup guard

```php
public function setUp(): void {
    parent::setUp();
    if ( ! class_exists( '\\Automattic\\WooCommerce\\Internal\\Abilities\\AbilitiesLoader' ) ) {
        $this->markTestSkipped( 'WooCommerce 10.9 AbilitiesLoader required for these tests.' );
    }
}
```

### Test 1 — wiring (callbacks point at the Domain class + shared helper)

```php
public function test_registration_args_callbacks_are_wired_to_domain_class() {
    $args = <Name>::get_registration_args();

    $this->assertSame(
        [ <Name>::class, 'execute' ],
        $args['execute_callback'],
        'execute_callback must point to <Name>::execute, not the legacy registrar method.'
    );

    $this->assertSame(
        [ Abilities_Registrar::class, '<CanCapHelper>' ],
        $args['permission_callback'],
        'permission_callback must point to Abilities_Registrar::<CanCapHelper>.'
    );
}
```

This test guards against copy-paste regressions where the `execute_callback` ends up pointing at a sibling Domain class.

### Test 2 — shape (all three annotations asserted + wired permission)

```php
public function test_ability_is_registered_with_expected_shape() {
    if ( ! function_exists( 'wp_get_ability' ) ) {
        $this->markTestSkipped( 'Abilities API query functions not available in this WP version.' );
    }

    $ability = wp_get_ability( '<plugin-slug>/<ability-name>' );
    $this->assertNotNull( $ability, '<plugin-slug>/<ability-name> should be registered.' );
    $this->assertSame( Abilities_Registrar::CATEGORY_SLUG, $ability->get_category() );

    $meta = $ability->get_meta();
    $this->assertIsArray( $meta );
    $this->assertArrayHasKey( 'annotations', $meta );

    $annotations = $meta['annotations'];
    $this->assertTrue( $annotations['readonly'], '<ability-name> should be readonly.' );
    $this->assertFalse( $annotations['destructive'], '<ability-name> should not be destructive.' );
    $this->assertTrue( $annotations['idempotent'], '<ability-name> should be idempotent.' );
    $this->assertTrue(
        $meta['show_in_rest'] ?? false,
        '<ability-name> must be exposed via show_in_rest for the REST bridge.'
    );
    $this->assertTrue(
        $meta['mcp']['public'] ?? false,
        '<ability-name> must be opted into MCP discovery.'
    );

    // Behavioural permission check via the registered ability's own
    // check_permissions(). WP_Ability exposes no public accessor for the
    // raw callable, so this rides on check_permissions() — which still
    // catches the bug class where an ability is accidentally wired to
    // `__return_true` (subscribers would pass through here).
    $subscriber_id = self::factory()->user->create( [ 'role' => 'subscriber' ] );
    wp_set_current_user( $subscriber_id );
    $this->assertFalse(
        $ability->check_permissions( [] ),
        'Wired permission_callback must deny subscribers.'
    );
}
```

## Gotchas — do not re-discover these the hard way

### Public abilities require explicit justification

A `permission_callback` of `__return_true` (or any callable that unconditionally returns `true`) makes the ability callable by every visitor — including unauthenticated traffic on a site with the REST bridge exposed. For a WooCommerce extension this is almost never appropriate; even seemingly-innocent reads (order counts, customer summaries, product inventory) can leak operational data to the public web.

If an ability is **deliberately** public:

1. The Domain class must carry a doc-block explaining the trust decision (what an unauthenticated agent learns and why that's safe).
2. The shape test must include a subscriber-allowed assertion that intentionally **passes** — confirming the ability resolves the permission decision the same way regardless of role, and that the public framing is intentional rather than a copy-paste regression.
3. The PR must call out the public ability in "Notes for reviewers" so the review covers the public exposure path explicitly.

If you can't articulate (1) in one sentence, the ability is not public — gate it.

### Do not re-prime registration in `setUp()`

You might be tempted to write a test helper that calls `do_action('wp_abilities_api_categories_init')` to re-prime registration inside a test's `setUp()`. Don't.

On WP 6.9 that action fires exactly once on bootstrap. Re-firing it produces `_doing_it_wrong` notices ("called too many times") and breaks the test in confusing ways. Tests for abilities are end-to-end through the plugin's normal bootstrap — by the time the test runs, the ability is already registered. Use `wp_get_ability('<name>')` to reach it.

### `output_schema` omission is deliberate — leave the comment in

If a reviewer asks "why is there no output_schema?", point at the inline comment. Do NOT add one back "just in case" — every one you add is a future coupling to an upstream payload change.

### The `$input = null` signature is non-negotiable

See "Execute method — required signature" above. A zero-arg `execute()` looks cleaner but breaks the moment the ability grows inputs. Defaulting `$input` to `null` from the start removes that future cliff.

### `use` imports are NOT autoloads

The Domain class's `use Automattic\WooCommerce\Abilities\AbilityDefinition;` at the top of the file is safe to ship to WC < 10.9 stores. PHP's `use` statement is an alias for the fully-qualified name; it does not trigger Composer's autoloader. Composer is only asked to resolve the FQN when something actually references the class — and on WC < 10.9 the registrar never does, because it bails before adding the loader filter. See `wc-1009-dependency.md` for the full property.

## Commit shape

```
feat(abilities): add <plugin-slug>/<ability-name> ability

Phase II (reference ability). <Two sentences on what the ability does
and why this one was picked as the reference pattern — typically:
simplest safe read, zero-arg, establishes the Domain-class shape the
remaining abilities will copy.>

Adds Domain/<Name>.php implementing AbilityDefinition and lists it in
Abilities_Registrar::ABILITY_CLASSES so Woo's loader picks it up.

Tests: wiring (callbacks point at the Domain class + shared permission
helper) + shape (all 3 annotations asserted + show_in_rest +
mcp.public + behavioural subscriber-denied check).
```

One commit: the Domain class + the test class + the one-line addition to `ABILITY_CLASSES`. Atomic.
