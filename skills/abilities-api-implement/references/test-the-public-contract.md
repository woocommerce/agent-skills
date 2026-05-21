# Test the public ability contract

Tests where the ability is implemented MUST prove the public ability contract — not the internal callable, not the underlying REST controller, not the service class. Six contract dimensions: **permissions, inputs, annotations, curated output, privacy, and execution behavior**. Each gets at least one test that exercises the ability through `wp_get_ability( $name )` — the same boundary every external consumer (MCP adapter, Command Palette, REST Abilities API, agents) hits.

> Why this reference exists: a registrar's tests that only exercise `Abilities_Registrar::execute_get_thing( $input )` — the static method directly — pass while the public boundary is broken. The `wp_get_ability()` lookup, the `permission_callback` wire-up, the input-schema normalization, and the output curation all sit between the static method and the agent invocation. Direct-call tests miss every one. The contract is what the agent sees; the tests must hit what the agent hits.

## Test base class

This is the conventional pattern in Woo-extension test suites:

```php
namespace My_Plugin\Tests\Integration\Abilities;

use WC_REST_Unit_Test_Case;

abstract class Abilities_TestCase extends WC_REST_Unit_Test_Case {

    protected function setUp(): void {
        parent::setUp();
        // Force-register abilities even if the feature flag is off in tests.
        add_filter( '<plugin_slug>_abilities_enabled', '__return_true' );
        do_action( 'abilities_api_init' );
    }

    protected function get_ability( string $name ) {
        $ability = wp_get_ability( $name );
        $this->assertNotNull( $ability, "Ability {$name} is not registered." );
        return $ability;
    }
}
```

Every ability-contract test extends this base. The base ensures the registration hook has fired and `wp_get_ability()` returns a real instance before any test runs.

## 1. Permissions contract

The ability denies unauthorized users and allows authorized ones — verified through `check_permissions( $input )` on the public boundary, not by mocking `current_user_can()`. The capability resolution path runs end to end (cap helper → core's `current_user_can()` → role map).

```php
public function test_get_transactions_denies_subscriber(): void {
    $subscriber_id = $this->factory->user->create( array( 'role' => 'subscriber' ) );
    wp_set_current_user( $subscriber_id );

    $allowed = $this->get_ability( '<plugin>/get-transactions' )
        ->check_permissions( array() );

    $this->assertFalse( $allowed, 'Subscriber must not be able to read transactions.' );
}

public function test_get_transactions_allows_shop_manager(): void {
    $manager_id = $this->factory->user->create( array( 'role' => 'shop_manager' ) );
    wp_set_current_user( $manager_id );

    $allowed = $this->get_ability( '<plugin>/get-transactions' )
        ->check_permissions( array() );

    $this->assertTrue( $allowed, 'Shop manager must be able to read transactions.' );
}
```

At least one denied and one allowed test per ability. For input-aware permission checks (rare), parametrize across the relevant input shapes.

## 2. Inputs contract

The ability rejects malformed input with the standardized error vocabulary from `wp-abilities-api/references/error-code-vocabulary.md`. Three classes of input failure, each with its own code:

- Schema violation (wrong type, missing required field in the schema): `ability_invalid_input` from core's normalizer.
- Plugin-level missing input (execute-callback guard fires before the work): `<plugin>_missing_<field>`.
- Plugin-level invalid input (value present, fails domain validation): `<plugin>_invalid_<field>`.

```php
public function test_execute_with_empty_input_returns_invalid_input(): void {
    wp_set_current_user( $this->shop_manager_id );

    $result = $this->get_ability( '<plugin>/get-transaction' )
        ->execute( array() );

    $this->assertWPError( $result );
    $this->assertSame( 'ability_invalid_input', $result->get_error_code() );
}

public function test_execute_with_invalid_id_returns_plugin_specific_code(): void {
    wp_set_current_user( $this->shop_manager_id );

    $result = $this->get_ability( '<plugin>/get-transaction' )
        ->execute( array( 'transaction_id' => '0' ) );

    $this->assertWPError( $result );
    $this->assertSame( '<plugin>_invalid_transaction_id', $result->get_error_code() );
}
```

`PHP empty()`-style false-rejection of `"0"` / `0` IDs is one of the recurring gotchas from `wp-abilities-api/references/input-schema-gotchas.md` (Gotcha 3); the assertion above is the regression guard for it on the *public boundary*.

## 3. Annotations contract — the adversarial check

The annotations on the registered ability MUST match the implementation:

- `readonly: true` → execute path does NOT perform durable writes to user/business state.
- `destructive: false` → execute path does NOT delete, refund, void, or otherwise permanently consume state.
- `idempotent: true` → repeated calls with the same input have no additional effect on the environment beyond the first call.

The adversarial check from `wp-abilities-verify` is the source of this discipline; here we exercise it at unit-test time so it ships with the plugin.

```php
public function test_get_transactions_annotation_readback_matches_implementation(): void {
    $ability = $this->get_ability( '<plugin>/get-transactions' );

    $meta = $ability->get_meta();
    $this->assertTrue( $meta['annotations']['readonly'],   'Claim: readonly.' );
    $this->assertFalse( $meta['annotations']['destructive'], 'Claim: not destructive.' );
    $this->assertTrue( $meta['annotations']['idempotent'],  'Claim: idempotent.' );

    // Adversarial: execute as an admin and snapshot any state that would
    // signal a durable write. For readonly: true we assert no row count
    // change in the plugin's primary table; substitute the relevant table.
    wp_set_current_user( $this->shop_manager_id );

    global $wpdb;
    $row_count_before = (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$wpdb->prefix}<plugin>_transactions" );

    $result = $ability->execute( array() );

    $row_count_after = (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$wpdb->prefix}<plugin>_transactions" );
    $this->assertSame( $row_count_before, $row_count_after, 'readonly: true must not cause durable writes.' );
}
```

For `idempotent: true` abilities, twin-invocation:

```php
public function test_get_account_status_is_idempotent(): void {
    wp_set_current_user( $this->shop_manager_id );

    $first  = $this->get_ability( '<plugin>/get-account-status' )->execute( array() );
    $second = $this->get_ability( '<plugin>/get-account-status' )->execute( array() );

    $this->assertEquals( $first, $second, 'idempotent: true must produce equal output on repeated calls.' );
}
```

Caveat: idempotent in the Abilities API sense means "no additional effect on the environment," not byte-identical output. If the output legitimately includes a server-side timestamp, the assertion should compare the structural shape (without the timestamp field) — see `wp-abilities-verify/references/annotation-correctness.md` for the boundary.

## 4. Curated output contract

The ability returns the documented shape, not the raw REST controller response. If the backing controller emits `WP_REST_Response`, the ability unwraps; if the controller emits an array, the ability passes it through. The test asserts the curated *contract*, not the upstream type.

```php
public function test_get_transactions_returns_array_of_transaction_objects(): void {
    wp_set_current_user( $this->shop_manager_id );

    $result = $this->get_ability( '<plugin>/get-transactions' )->execute( array() );

    $this->assertIsArray( $result, 'Output must be an array; the helper unwraps WP_REST_Response.' );
    if ( count( $result ) > 0 ) {
        $this->assertArrayHasKey( 'transaction_id', $result[0], 'Each row must include transaction_id.' );
        $this->assertArrayHasKey( 'amount', $result[0] );
        $this->assertArrayHasKey( 'currency', $result[0] );
    }
}
```

If the ability documents a pagination envelope per `references/paginated-output-envelope.md`, assert the envelope keys (`items`, `total_count`, `page`, `per_page`) at the top level — not just the inner array shape.

## 5. Privacy contract

The output MUST NOT include PII or sensitive fields the contract doesn't promise. For payments specifically, the ability MUST NOT leak full PANs, full bank account numbers, raw card tokens, or fields whose downstream consumers (an MCP client, a Command Palette suggestion, a screen reader) would surface to the wrong audience.

```php
public function test_get_transactions_does_not_leak_full_pan_or_bank_number(): void {
    wp_set_current_user( $this->shop_manager_id );

    $result = $this->get_ability( '<plugin>/get-transactions' )->execute( array() );
    $this->assertIsArray( $result );

    foreach ( $result as $row ) {
        // Allow the last-4 digits the controller exposes intentionally.
        $this->assertMatchesRegularExpression(
            '/^\*+\d{4}$/',
            $row['card_last_4_display'] ?? '****0000',
            'card_last_4_display must be masked-then-suffix.'
        );

        $this->assertArrayNotHasKey( 'full_pan', $row, 'Full PAN must never appear in output.' );
        $this->assertArrayNotHasKey( 'card_number', $row );
        $this->assertArrayNotHasKey( 'bank_account_number', $row );
        $this->assertArrayNotHasKey( 'iban', $row );

        // Customer email is allowed for shop_manager-and-up roles by design;
        // but the field MUST be marked in the output schema so downstream
        // consumers can suppress it for roles that should not see it.
    }
}
```

Privacy regressions are the most common form of *additive* drift: a controller adds a useful debug field for an internal UI, the ability inherits it, the new field shows up in MCP `tools/describe` and in agent responses. The privacy test is the gate that catches this at the public boundary.

For abilities that surface composed data (e.g. a subscription with its recipient) — see decision D22 in the project's source-of-truth — the privacy test MUST cover the composed path, not just the primary entity. The composition site is where leaks emerge.

## 6. Execution behavior contract

The ability executes through the public boundary, not the internal callable. Direct calls to the registrar's static method (`Abilities_Registrar::execute_get_thing( $input )`) skip the `wp_get_ability()` lookup, the input-schema normalizer, the `permission_callback` wire-up, and any wrapping the bundled MCP adapter or Abilities REST controller applies. Tests at the direct-call layer are useful for unit-testing the execute body, but they do NOT prove the public contract.

```php
public function test_get_transactions_executes_through_the_public_boundary(): void {
    wp_set_current_user( $this->shop_manager_id );

    // Hit wp_get_ability(), not the registrar method.
    $result = wp_get_ability( '<plugin>/get-transactions' )->execute( array() );

    $this->assertNotInstanceOf( \WP_Error::class, $result, 'Public-boundary execute must succeed for shop_manager.' );
    $this->assertIsArray( $result );
}
```

Pair every direct-callable unit test with a public-boundary integration test. The latter catches at least:

- Permission-callback wire-up failures (the cap helper isn't actually attached to the ability registration).
- Input-schema normalization gaps (a default declared in the schema doesn't reach the execute callback).
- Output curation drift (the helper isn't unwrapping the dual response shape).
- MCP-exposure metadata drift (`meta.mcp.public` toggled off by accident, making the ability invisible to the bundled adapter even though `wp_get_ability()` finds it).

The shape: one PHPUnit class per ability or per ability cluster, six contract-dimension tests per ability (one each for permissions, inputs, annotations, curated output, privacy, execution behavior). For a 9-ability rollout that's 54 contract tests — and every one of them is enforcing a guarantee the agent caller depends on.

## Cross-references

- `wp-abilities-api/references/error-code-vocabulary.md` — the error codes the Inputs contract asserts.
- `wp-abilities-api/references/input-schema-gotchas.md` — the schema-default and ID-shape gotchas the regression tests guard.
- `wp-abilities-verify/references/annotation-correctness.md` — the upstream adversarial check; this reference is the implementer-side counterpart that runs at unit-test time.
- `wp-abilities-audit/references/audit-schema.md` `side_effects` field — when an audit declares `side_effects: []`, the Annotations contract test for `readonly: true` is the assertion that proves the empty array.
- `references/woo-extension-primitives.md` — the test base class convention referenced above.
