# Paginated output envelope — WC 10.9 convention

> **Scope.** Only list-shaped abilities adopt this envelope. Scalar or single-record abilities (`get-<thing>-statuses`, `get-<thing>` by ID, `get-<thing>-count`) return their natural shape directly.

WC 10.9's loader makes a canonical paginated output shape practical to standardize across abilities:

```jsonc
{
  "<collection_key>": [ /* item objects */ ],
  "total_pages": 7,
  "page": 1,
  "per_page": 10
}
```

`<collection_key>` is the property naming the array (`subscriptions`, `orders`, `notes`, `gifts`, etc.). The other three keys are stable across every list-shaped ability.

## Why standardize at the ability layer

Three reasons:

1. **Discoverability.** An agent that learned the envelope on one ability can use the same `page` / `per_page` inputs and the same `total_pages` field on every other ability it discovers in the plugin family. No per-ability schema lookup needed.
2. **Stable wire contract.** Backing REST controllers can disagree on pagination keys (some use `pagesize`, some omit `total_pages`, some return `X-WP-Total` only in headers). The ability layer normalizes.
3. **The total trap.** Many backing controllers compute their result set's total via `X-WP-Total` response headers, not body fields. Agents do not see HTTP response headers; if `total_pages` doesn't appear in the body, the agent has no way to know whether more pages exist.

## Input — pagination properties

Every list-shaped ability adds two integer inputs to its `input_schema['properties']`:

```php
'page' => [
    'type'        => 'integer',
    'minimum'     => 1,
    'default'     => 1,
    'description' => __( 'Page number to return (1-indexed).', '<textdomain>' ),
],
'per_page' => [
    'type'        => 'integer',
    'minimum'     => 1,
    'maximum'     => 100,
    'default'     => 10,
    'description' => __( 'Maximum number of items per page.', '<textdomain>' ),
],
```

`minimum: 1`, `default: 1` on `page`. `minimum: 1`, `maximum: <cap>`, `default: <page-size>` on `per_page`. Pick the page-size default + cap to match the backing controller; `10` + `100` are reasonable starting points.

## Wire-format break: `limit` → `per_page`

If the ability previously exposed a `limit` parameter, the migration is a wire-format break: rename to `per_page`, set `additionalProperties: false` on the input schema so the old name is rejected, and document the break in the migration commit message. No deprecation period, no accept-both.

## Output — collection envelope helpers on the abstract base

The plugin's Domain-ability abstract base class hosts the four helpers that build the canonical envelope. The abstraction is generic — the implementation lives in your plugin's namespace using your plugin's translator domain and method-naming conventions. Each helper does one thing:

| Helper | Returns |
|---|---|
| `get_pagination_input_properties( $default_per_page, $max_per_page )` | The two `page` / `per_page` input-schema properties shown above. Two integer parameters let each ability pick its own defaults and ceiling. |
| `get_collection_output_schema( $collection_key, $item_schema )` | The output-schema object with the named collection array + `total_pages` / `page` / `per_page` siblings + `additionalProperties: false`. Two parameters: the collection property name (`subscriptions`, `orders`, `notes`) and the per-item JSON schema. |
| `compute_total_pages( $total, $per_page )` | `(int) ceil( $total / $per_page )` with safe handling of zero / negative inputs. |
| `extract_total_from_response( \WP_REST_Response $response, array $rows )` | Read `X-WP-Total` from `$response->get_headers()` if present; fall back to `count( $rows )`. The header is what backing REST controllers set; the agent doesn't see headers, so the abstract base bridges. |

Add these as `protected static` methods on the same abstract base class that hosts `delegate_to_rest_controller()` (see `registrar-template.md`). Match your plugin's existing translator-domain, namespace, and helper-naming conventions — don't import a foreign style just to match this reference. Woo Core 10.9 introduced `Internal\Abilities\Domain\AbstractDomainAbility` with the same shape; mirror its method signatures where helpful, but don't extend or import from Woo Core's `Internal\` namespace.

## Use in a list-shaped Domain class

The pattern in a list-shaped ability's `get_registration_args()` and `execute()`:

1. **`input_schema.properties`** merges the ability's own filter properties (status, customer, date range, etc.) with `self::get_pagination_input_properties( <default>, <max> )` so the two pagination keys ride alongside the filters. `additionalProperties: false` rejects unknown keys including the old `limit` name. Top-level `default` is `(object) array()` (the schema-defaults gotcha — see `wp-abilities-api/references/input-schema-gotchas.md` Gotcha 4).
2. **`output_schema`** is `self::get_collection_output_schema( '<collection_key>', <per-item-schema> )` — one call, no duplication of the envelope keys.
3. **`execute()`** re-clamps `page` and `per_page` from `$input` (schema validation is bypassed on direct invocation), assembles the backing-controller params, and calls the delegate helper with the flag that returns the full `WP_REST_Response` so headers are reachable. Convert the response data with `array_values()` to ensure a JSON array (the backing controller may have keyed the rows by ID), then assemble the envelope: `[ '<collection_key>' => $rows, 'total_pages' => self::compute_total_pages( $total, $per_page ), 'page' => $page, 'per_page' => $per_page ]`.

Three reasons the execute method does its own work rather than letting the schema or the backing controller emit the envelope: `additionalProperties: false` won't pass through fields the agent didn't request, the backing controller's response shape may differ (some return `X-WP-Total` headers only; some omit them), and the public boundary the ability presents to agents is the envelope — not the backing controller's wire format. The helpers above keep the assembly in one place across every list-shaped ability in the plugin.

## When NOT to use the envelope

Scalar abilities (`get-<thing>-statuses` returning a status-vocabulary map), single-record abilities (`get-<thing>` returning one record by ID), and count abilities (`get-<thing>-count` returning an integer) return their natural shape directly. Wrapping them in the envelope adds noise without adding discoverability — agents that want a single record do not need `total_pages = 1`.

The list above is structural, not exhaustive — if an ability returns a non-paginated array (e.g. all child rows of a single parent, where the count is bounded by the parent's relationship cardinality), it's a judgment call. Default toward the envelope when the result set could grow; default toward the natural shape when it's bounded.

## See also

- `registrar-template.md` — the `delegate_to_rest_controller()` helper lives on the same abstract base.
- `wc-1009-dependency.md` — why this convention is safe to require unconditionally.
