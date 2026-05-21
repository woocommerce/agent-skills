# Agent Skills for WooCommerce

**Teach AI coding assistants how to build WooCommerce extensions the right way.**

Agent Skills are portable bundles of instructions, checklists, and scripts that help AI assistants (Claude, Copilot, Codex, Cursor, etc.) understand WooCommerce-extension patterns, avoid common mistakes, and follow current conventions.

This repo is the sibling of [`WordPress/agent-skills`](https://github.com/WordPress/agent-skills), which covers portable WordPress core fundamentals. If you're building a WooCommerce extension, install both: this one gives you the WooCommerce-extension layer, and `WordPress/agent-skills` gives you the WP-core layer underneath.

## Why Agent Skills?

AI coding assistants are powerful, but they often:

- Generate outdated WooCommerce patterns (pre-HPOS, pre-Blocks, pre-Abilities-API).
- Miss WooCommerce conventions around services containers, Domain classes, and `Internal/` namespacing.
- Skip the WooCommerce-extension-specific scaffolding required for features like the Abilities API.
- Reinvent helpers that already exist in WC Core.

Agent Skills solve this by giving AI assistants **expert-level WooCommerce-extension knowledge** in a format they can actually use.

## Available Skills

| Skill | What it teaches |
|-------|-----------------|
| **abilities-api-implement** | End-to-end implementation playbook for registering [WordPress Abilities API](https://github.com/WordPress/abilities-api) capabilities in a WooCommerce extension. Covers audit-precondition, Domain class shape, loader-only registrar, paginated output envelope, in-plugin contract tests, and the WC 10.9 dependency boundary. |

More skills will land as the repo grows.

## Quick Start

### Install globally for Claude Code

```bash
git clone git@github.com:woocommerce/agent-skills.git
cd agent-skills

# Build the distribution
node shared/scripts/skillpack-build.mjs --clean

# Install all skills globally (available across all projects)
node shared/scripts/skillpack-install.mjs --global
```

This installs skills to `~/.claude/skills/` where Claude Code will automatically discover them.

### Install into a specific extension repo

```bash
# After cloning and building:
node shared/scripts/skillpack-install.mjs \
  --dest=/path/to/your/wc-extension \
  --targets=claude,codex,cursor
```

This installs skills to `.claude/skills/`, `.codex/skills/`, and `.cursor/skills/` inside the target repo.

### Other targets

The build/install scripts emit skill packs for:

- **Claude** (`.claude/skills/`)
- **Codex** (`.codex/skills/`)
- **VS Code** Copilot Chat (`.github/skills/`)
- **Cursor** (`.cursor/skills/`)

Pass `--targets=` to install only some.

## Relationship to `WordPress/agent-skills`

This repo focuses on the WooCommerce-extension layer. For portable WordPress core fundamentals — Abilities API basics (`wp-abilities-api`), audit (`wp-abilities-audit`), verify (`wp-abilities-verify`), REST API, block development, etc. — install [`WordPress/agent-skills`](https://github.com/WordPress/agent-skills) alongside this one. The skills here reference upstream where appropriate rather than duplicating the teaching.

The two repos use the same build/install tooling. They are siblings, not parent/child — neither mirrors the other automatically.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/authoring-guide.md](docs/authoring-guide.md).

## License

GPL-2.0-or-later. See [LICENSE](LICENSE).
