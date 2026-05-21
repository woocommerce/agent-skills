# Compatibility policy

This repo is an authoring workspace for WooCommerce-focused Agent Skills. It is the sibling repo to [`WordPress/agent-skills`](https://github.com/WordPress/agent-skills), which covers WordPress core fundamentals.

## Compatibility contract (v1)

Skills in this repo target:

- WooCommerce **10.9+** (where the Abilities API integration ships)
- WordPress core **6.9+** (where the Abilities API itself ships)
- PHP **7.4+** (WooCommerce 10.9+ requires PHP 7.4+)

A skill MAY declare a stricter floor in its own SKILL.md `compatibility:` frontmatter if it depends on later WC/WP/PHP features.

## Authoring rules

Skills should:

- Prefer stable WooCommerce and WordPress APIs.
- Prefer detection + guardrails over hard-coded assumptions.
- If a task requires behavior that differs across WooCommerce versions, ask for a target version (but default guidance should assume WooCommerce 10.9+).
- For portable WordPress-core knowledge (REST API, Abilities API, block development, etc.) that an extension would inherit, reference the corresponding skill in `WordPress/agent-skills` rather than duplicating it here.
