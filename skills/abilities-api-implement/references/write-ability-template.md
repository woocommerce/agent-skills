# Write Ability Template — WooCommerce extension (WC 10.9 loader)

> **Upstream first.** For the portable input-schema and schema-default gotchas this file references, read `wp-abilities-api/references/input-schema-gotchas.md` in WordPress/agent-skills first if installed. This file layers the write-specific patterns — the explicit-false annotation discipline, the four-check input-validation guard, the Shape 3 mandate, and the external-service-idempotency boundary — on top.
>
> **Read these first too:**
>
> - `wc-1009-dependency.md` — the same lazy-autoload property applies; the Domain class is safe to ship despite WC < 10.9 stores never having `AbilityDefinition`.
> - `registrar-template.md` and `first-ability-template.md` — the Domain class shape and the `ABILITY_CLASSES` wire are unchanged from reads.

Phase IV — register any write abilities listed in the audit. Write abilities have stricter requirements than reads: explicit-false assertions on every annotation, defensive input validation, and explicit handling of schema-default normalization.

## Scope

The Domain-class shape and the `ABILITY_CLASSES` wire are identical for reads and writes. Use `first-ability-template.md` for the worked-example class layout (file location, namespace, `use` imports, `@phan-file-suppress` header, the `extends Abstract<Plugin>Ability implements AbilityDefinition` signature, the static-method layout). This file teaches the write-specific discipline that layers on top: Shape 3, explicit-false annotations, four-check input validation, schema-defaults handling.

## Shape rule for writes — Shape 3 is mandatory

Write abilities MUST use Shape 3 (shared service class) and not Shape 2 (delegate to REST). Three reasons:

1. **The metric trap.** Most non-trivial REST controllers emit telemetry (analytics events, hook fires, internal counters). Routing a write through the REST controller via `rest_do_request()` makes every agent-driven invocation indistinguishable from a human action in the extension's analytics. For any state change that surfaces in a merchant-facing dashboard or contributes to a reporting metric, this contaminates the numbers. Use a shared service.
2. **Notification + audit-log side effects.** Many writes trigger emails, in-product notifications, and audit-log entries that were designed around human-initiated UI flows. Routing an agent call through the same REST handler fires all of them — including notifications for state changes the agent is about to undo on the next call. Service-layer extraction lets the ability and the REST handler each opt into the side effects deliberately.
3. **Drift prevention.** A write whose business logic lives in the REST handler will diverge from the ability the moment someone refactors the controller. A write whose business logic lives in a shared service stays in sync because both the ability and the REST handler call the same code.

The grouping rule: extract the service first (its own atomic refactor commit), then register the ability on top of it. Never land a write ability backed by `Abstract<Plugin>Ability::delegate_to_rest_controller()` — that's the anti-pattern this section exists to flag.

If the audit doc proposes a write whose backing controller has no extractable service layer (the business logic IS the REST handler), PAUSE and ask the user. Two valid paths: (a) extract the service in this PR as a prerequisite refactor; (b) defer the write to a follow-up PR after the service extraction lands. Do not silently fall back to Shape 2 for writes.

## Annotation shape — every value explicitly asserted

Write abilities flip at least `readonly` to `false`. The other two (`destructive`, `idempotent`) depend on semantics:

| Semantic | `readonly` | `destructive` | `idempotent` |
|---|---|---|---|
| Additive write — attaches data, opens a record, submits without irreversible effect | `false` | `false` | `false` |
| Irreversible state change — cancel, refund, delete, send-to-customer | `false` | **`true`** | `false` |
| Fully repeatable write — same input always produces the same effect, safe to retry | `false` | `false` | **`true`** |

The third row is rare. Most writes are non-idempotent from the caller's perspective: a second invocation produces a second downstream effect (a duplicate API call, a duplicate notification, a duplicate row). Only flag `idempotent: true` when the service genuinely de-duplicates by the caller's input.

### Idempotency at the external-service boundary

`idempotent: false` on the registration annotation means duplicate calls **from the agent's perspective** produce duplicate effects on the backing system — for a write that hits an external API (a payment processor, a shipping carrier, a CRM, an email service), that's a duplicate request against the upstream.

Idempotency at the external-service layer (e.g. an `Idempotency-Key` HTTP header on the outbound request) is the **shared service's responsibility**, not the ability's. The execute method must NOT generate an idempotency key:

- The shared service is where key generation, storage, and retry-replay logic lives. Verify against the extension's actual service implementation before scaffolding — if the service does NOT yet handle idempotency keys, raise that as a follow-up rather than papering over it in the ability layer.
- For the agent: the `idempotent: false` annotation broadcasts "I am not safe to retry on your side." Agent-side retry logic must guard on duplicate-call detection before re-invoking the ability.

Do not generate UUIDs or `wp_generate_uuid4()` in the execute method in an attempt to make the ability idempotent — that only de-duplicates at the agent ↔ ability boundary while leaving the ability ↔ external service boundary still vulnerable, and worse, it hides the non-idempotency from the agent.

## Permission callback discipline — public writes are never accidental

A `permission_callback` of `__return_true` makes the write ability callable by every visitor — including unauthenticated traffic on a site with the REST bridge exposed. For a WooCommerce extension the answer is almost always: **do not ship the ability** rather than ship it public.

- A public write that modifies merchant state, sends a customer communication, or moves money is a privilege-escalation primitive. The default answer is "no".
- If a public write is genuinely required (e.g. a shopper-facing form submission), it MUST gate internally on an unforgeable capability — a signed claim, a session token, a per-resource secret — and the PR MUST document the gating mechanism in "Notes for reviewers".
- The shape test must assert the public framing is deliberate (e.g. a subscriber-allowed assertion that intentionally **passes**, paired with a comment explaining the trust decision) so a future refactor that "tightens" the callback to a capability check trips the test.

If you are not sure whether the write should be public, gate it.

## Domain class — file shape

```php
<?php
/**
 * <Action> <thing> ability definition.
 *
 * @package <Plugin>
 */

// @phan-file-suppress PhanUndeclaredClassMethod, PhanUndeclaredFunction @phan-suppress-current-line UnusedSuppression -- Abilities API + AbilityDefinition added in WC 10.9; suppression covers older-WC compat runs where this class never loads.

namespace <Namespace>\Domain;

use Automattic\WooCommerce\Abilities\AbilityDefinition;
use <Namespace>\Abilities_Registrar;

/**
 * Registers the <plugin-slug>/<write-ability-name> ability.
 *
 * <Description, including the two-phase behaviour and the non-idempotency
 * warning if applicable. Agents read the description property; the doc-block
 * is for human reviewers.>
 *
 * @internal Only loaded when WooCommerce 10.9+ is active.
 */
class <Name> extends Abstract<Plugin>Ability implements AbilityDefinition {

    public static function get_name(): string {
        return '<plugin-slug>/<write-ability-name>';
    }

    public static function get_registration_args(): array {
        return [
            'label'               => __( '<Human-readable label>', '<textdomain>' ),
            'description'         => __( '<Description — include the two-phase behaviour and non-idempotency warning if applicable.>', '<textdomain>' ),
            'category'            => self::CATEGORY_SLUG,
            'input_schema'        => [
                'type'                 => 'object',
                // Top-level `default` is deliberately ABSENT here. The read
                // template uses `'default' => (object) []` so `execute(null)`
                // validates; adding the same key on a schema with `required`
                // fields would have `WP_Ability::normalize_input()` substitute
                // the empty object before `validate_input()` runs, silently
                // bypassing required-field enforcement on indirect
                // invocation paths (MCP, REST bridge). For write abilities,
                // force the caller to pass a real input.
                'required'             => [ '<required_field>' ],
                'properties'           => [
                    '<required_field>' => [
                        'type'        => 'string',
                        'description' => __( '<Field description>.', '<textdomain>' ),
                    ],
                    '<bool_field>'     => [
                        'type'        => 'boolean',
                        'default'     => false,
                        'description' => __( '<Why the default is false>.', '<textdomain>' ),
                    ],
                    '<object_field>'   => [
                        'type'                 => 'object',
                        'description'          => __( '<Field description>.', '<textdomain>' ),
                        'additionalProperties' => false,
                        // Set to `true` ONLY if the backing controller independently validates every sub-key. Default closed; document exceptions in the PR.
                        'properties'           => [
                            // Enumerate the expected sub-fields explicitly.
                        ],
                    ],
                ],
                'additionalProperties' => false,
            ],
            'execute_callback'    => [ self::class, 'execute' ],
            'permission_callback' => [ Abilities_Registrar::class, '<CanCapHelper>' ],
            'meta'                => [
                'annotations'  => [
                    'readonly'    => false,
                    'destructive' => false,  // or true if this moves/destroys value
                    'idempotent'  => false,
                ],
                'show_in_rest' => true,
                'mcp'          => [
                    // Writes default to `public => false`. Flipping to true
                    // makes the ability MCP-discoverable to every connected
                    // agent the moment the feature flag flips on; for a
                    // write that touches merchant resources, this is a
                    // privilege-escalation primitive. Set `true` only after
                    // the affirmative trust decision laid out in "Permission
                    // callback discipline" above.
                    'public' => false,
                ],
            ],
        ];
    }

    public static function execute( $input = null ) {
        if ( ! is_array( $input ) ) {
            $input = [];
        }

        // Explicit required-field validation (four checks — see below).
        if ( ! isset( $input['<required_field>'] ) || ! is_string( $input['<required_field>'] ) || '' === $input['<required_field>'] ) {
            return new \WP_Error(
                '<plugin_slug>_missing_<required_field>',
                __( 'A <required_field> is required to <do the thing>.', '<textdomain>' )
            );
        }

        // Apply schema defaults that the Abilities API doesn't inject.
        if ( ! array_key_exists( '<bool_field>', $input ) || null === $input['<bool_field>'] ) {
            $input['<bool_field>'] = false;
        }
        $input['<bool_field>'] = (bool) $input['<bool_field>'];

        if ( ! array_key_exists( '<object_field>', $input ) || null === $input['<object_field>'] ) {
            $input['<object_field>'] = [];
        }

        // Resolve the shared service (Shape 3). Scaffold below shows Path A
        // (static accessor on the plugin main class). For Path B (PSR-11
        // container), replace the next ~10 lines with the container variant
        // in "Service resolution — two paths" below.
        if ( ! class_exists( '\\<PluginNamespace>\\Internal\\Service\\<Thing>_Service' ) ) {
            return new \WP_Error(
                '<plugin_slug>_not_initialized',
                __( '<Plugin> is not initialized.', '<textdomain>' )
            );
        }
        $service = \<PluginMainClass>::get_<service_accessor>();
        if ( ! $service ) {
            return new \WP_Error(
                '<plugin_slug>_not_initialized',
                __( '<Plugin> is not initialized.', '<textdomain>' )
            );
        }

        return $service-><service_write_method>(
            $input['<required_field>'],
            $input['<bool_field>'],
            $input['<object_field>']
        );
    }
}
```

`required` at the object level ensures the Abilities API's schema validator rejects missing required fields BEFORE the execute method runs — but see the schema-defaults gotcha below: `required` is enforced; `default` is not injected.

## Wire the class into the coordinator

Same as reads: add `Domain\<Name>::class` to `Abilities_Registrar::ABILITY_CLASSES`. No `register_<name>_ability()` method.

## Service resolution — two paths

The Domain class needs to resolve the shared service. Pick the path that matches how the extension exposes it (check `includes/Container.php`, `src/Container.php`, or a static accessor on the main plugin class):

**Path A — Static accessor / service locator on the main plugin class.** Returns null when the plugin isn't ready; the `if ( ! $service )` null-check above catches it.

```php
$service = \<PluginMainClass>::get_<service_accessor>();
```

**Path B — PSR-11 DI container.** Container `get()` typically rethrows on lookup failure with a `ContainerExceptionInterface`; a null-check alone does NOT catch the exception. Pre-check via `->has()` so the `WP_Error` path stays in control:

```php
$container = <plugin_slug>_get_container();
if ( ! $container->has( \<PluginNamespace>\Internal\Service\<Thing>_Service::class ) ) {
    return new \WP_Error( '<plugin_slug>_not_initialized', __( '<Plugin> is not initialized.', '<textdomain>' ) );
}
$service = $container->get( \<PluginNamespace>\Internal\Service\<Thing>_Service::class );
```

## Anti-pattern — do NOT copy this

A pre-Shape-3 version of the execute method delegates through the existing REST controller via `self::delegate_to_rest_controller(...)`:

```php
// ANTI-PATTERN — left here as a teaching artifact. Do not ship this for writes.
return self::delegate_to_rest_controller(
    '\\<BackingControllerClass>',
    'POST',
    '/<plugin>/v1/<route>',
    $input
);
```

Why this is wrong for writes:

- **Telemetry contamination.** Every non-trivial REST controller emits analytics events, fires hooks, or updates internal counters. Agent-driven invocations end up in the extension's analytics indistinguishable from human actions.
- **Notification side effects.** The REST controller fires the customer-facing or merchant-facing notification hooks that were designed for human-initiated UI flows.
- **Authorization-callback double-fire.** `rest_do_request()` invokes the inner controller's `permission_callback` a second time. Any divergence between the outer ability's `permission_callback` and the inner one is an authorization-inconsistency surface — more permissive inside is a bypass; more restrictive is a silent write failure that validates the input, claims success, and stops short of the write.
- **Drift.** The ability and the REST handler share business logic by being routed through the same handler; any refactor that splits the controller's logic from its HTTP shape diverges them.

If the audit doc proposes a write whose backing controller has no extractable service layer, PAUSE — extract the service as a prerequisite refactor or defer the write. Do not fall back to the anti-pattern.

## Required-input validation pattern — four checks

```php
if ( ! is_array( $input ) || ! isset( $input['<id>'] ) || ! is_string( $input['<id>'] ) || '' === $input['<id>'] ) {
    return new \WP_Error( '<plugin_slug>_missing_<id>', ... );
}
```

Four separate checks:

1. `is_array( $input )` — outer shape. Without this, an agent invoking `execute( "id_string" )` would crash at `isset($input['<id>'])`. (The execute method's first `if ( ! is_array( $input ) ) { $input = []; }` covers most of this, but the explicit guard above keeps the validation path readable when the four checks live together.)
2. `isset` — key present.
3. `is_string` — right type. NOT `empty()` — `empty('0')` is `true` and a literal `"0"` may be a legal ID (order ID, row ID).
4. `'' === $input['<id>']` — non-empty. Again, `empty()` would false-reject the string `"0"`.

Add a unit test that passes a non-string (e.g. the integer `123`) for the required field — see Test 3 below. Without it, someone could simplify the guard to `empty()` or `isset()` and a non-string ID would fall through.

Use the standardized `<plugin_slug>_missing_<field>` error code (see `wp-abilities-api/references/error-code-vocabulary.md` upstream).

## Schema defaults gotcha — the Abilities API does NOT inject them

The registration's `input_schema.properties.<bool_field>.default = false` is informational only. The Abilities API's validate path enforces types and `required` but does NOT populate missing properties with their `default` value. If the agent invokes with `{<required_field>: "..."}` and omits `<bool_field>`, the execute method receives `$input` WITHOUT a `<bool_field>` key — not `$input['<bool_field>'] = false`.

The fix is to apply defaults explicitly in the execute method:

```php
if ( ! array_key_exists( '<bool_field>', $input ) || null === $input['<bool_field>'] ) {
    $input['<bool_field>'] = false;
}
$input['<bool_field>'] = (bool) $input['<bool_field>'];
```

The `array_key_exists` + null-check pattern catches both "missing key" and "explicit null" (some serializers produce nulls for optional fields).

If the backing controller would accept a missing field as "use its own default", you can skip this — but the safer path is to normalize. The execute-time normalization documents the expected shape and removes a class of bugs where the backing controller's default differs from the ability's documented default.

## Tests — 3 total (shape + 2 execute-path)

### Setup guard

Same as the read template — `setUp()` skips if `AbilitiesLoader` is absent.

### Test 1 — shape with explicit-false assertions on every annotation

```php
public function test_ability_is_registered_with_expected_shape(): void {
    if ( ! function_exists( 'wp_get_ability' ) ) {
        $this->markTestSkipped( 'Abilities API query functions not available in this WP version.' );
    }

    $ability = wp_get_ability( '<plugin-slug>/<write-ability-name>' );
    $this->assertNotNull( $ability, '<write-ability-name> should be registered.' );
    $this->assertSame( Abilities_Registrar::CATEGORY_SLUG, $ability->get_category() );

    $annotations = $ability->get_meta()['annotations'];
    $this->assertFalse( $annotations['readonly'],    '<write-ability-name> must NOT be readonly.' );
    $this->assertFalse( $annotations['destructive'], '<write-ability-name> is additive (does not destroy or move value).' );
    $this->assertFalse( $annotations['idempotent'],  '<write-ability-name> is NOT idempotent — duplicate calls produce duplicate effects.' );
}
```

Both the `assertFalse` and the message string are deliberate. For read abilities the tests assert `$annotations['readonly']` is TRUE. Copy-paste from a read test is a common bug source — the explicit-false assertion + explanatory message catches it.

### Test 2 — missing required field

```php
public function test_returns_wp_error_when_<required_field>_missing(): void {
    $result = <Name>::execute( [] );
    $this->assertInstanceOf( \WP_Error::class, $result );
    $this->assertSame( '<plugin_slug>_missing_<required_field>', $result->get_error_code() );
}
```

This asserts the custom `<plugin_slug>_missing_<required_field>` code — the code the execute method returns when the input_schema is bypassed (e.g. direct invocation, not through the abilities API's REST bridge).

### Test 3 — non-string required field (type-validation regression guard)

```php
public function test_returns_wp_error_when_<required_field>_not_a_string(): void {
    $result = <Name>::execute( [ '<required_field>' => 123 ] );
    $this->assertInstanceOf( \WP_Error::class, $result );
    $this->assertSame( '<plugin_slug>_missing_<required_field>', $result->get_error_code() );
}
```

Guards the `is_string()` check. Without this test, someone could simplify the guard to `empty()` or `isset()` and a non-string ID would fall through. The integer `123` is a fine canary — non-empty, `isset()`s, but not a string.

## Error codes — two paths, same outcome

When the ability is invoked via the abilities API's REST bridge, the input_schema runs first and rejects missing-required-field inputs with `WP_Error('ability_invalid_input')`. When the execute method is invoked directly (unit tests, or non-REST agent wrappers), the schema is bypassed and the custom `<plugin_slug>_missing_<field>` runs.

Both are acceptable. The integration harness (see `wp-abilities-verify`) surfaces whichever path fires. Document both in the PR "Notes for reviewers" section.

See `wp-abilities-api/references/error-code-vocabulary.md` upstream for the full vocabulary.

## Commit shape

```
feat(abilities): add <plugin-slug>/<write-ability-name> ability

<Two sentences on what it does and why the annotations are what they
are. Call out non-idempotent flag if present and what agent retry
logic has to guard against. Call out destructive flag if present.>

Adds Domain/<Name>.php implementing AbilityDefinition and lists it in
Abilities_Registrar::ABILITY_CLASSES. Delegates to <Thing>_Service
(Shape 3 — shared service) rather than rest_do_request() to keep agent
calls out of merchant analytics and notification fan-out.

Tests: shape (explicit-false asserts on all 3 annotations) +
execute-path (missing <required_field>, non-string <required_field>).
```

One commit: the Domain class + the test class + the `ABILITY_CLASSES` addition. Atomic. If a service extraction is required as a prerequisite, that lands as its own commit immediately before this one.
