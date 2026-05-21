# Contributing to Agent Skills for WooCommerce

We welcome contributions. This project captures WooCommerce-extension expertise in a structured format that AI coding assistants can read and follow.

## Why Contribute Here?

**You don't need to be a coding wizard.** Agent Skills is primarily about capturing *knowledge* and *best practices*. If you understand WooCommerce extensions deeply — payment gateways, shipping methods, subscription add-ons, the Abilities API, the REST surface — you can make a meaningful contribution.

Most of our skills are written in Markdown. The "code" is mostly procedural checklists, decision trees, and reference documentation. If you can explain a WooCommerce concept clearly, you can contribute here.

This repo is the sibling of [`WordPress/agent-skills`](https://github.com/WordPress/agent-skills): that repo holds portable WordPress core fundamentals; this repo holds the WooCommerce-extension-specific layer that builds on them.

## Ways to Contribute

### 1. Improve Existing Skills

The easiest way to start:

- **Fix outdated information** — WooCommerce evolves quickly. If you spot something that's changed, open a PR.
- **Add missing edge cases** — Did you hit a gotcha that isn't documented? Add it to the "Failure modes" section.
- **Clarify procedures** — If a step confused you, it'll confuse others. Make it clearer.
- **Expand references** — Add deeper documentation on specific topics.

### 2. Create New Skills

Have expertise in a WooCommerce-extension area we don't cover yet? Consider adding a new skill.

Before starting:
1. Check [existing skills](skills/) to avoid overlap.
2. Check [`WordPress/agent-skills`](https://github.com/WordPress/agent-skills/tree/trunk/skills) — if a portable WP skill already covers it, contribute upstream instead.
3. Review the [Authoring Guide](docs/authoring-guide.md) for structure requirements.
4. Open an issue to discuss scope (optional but recommended for larger skills).

Scaffold a new skill:

```bash
node shared/scripts/scaffold-skill.mjs <skill-name> "<description>"
```

### 3. Add Evaluation Scenarios

Every skill needs at least one scenario under `eval/scenarios/` as a `.json` file. Each describes:
- A realistic prompt/task
- What the AI should do
- How to verify it worked

This is a great low-barrier contribution.

### 4. Report Issues

Found a skill giving bad advice? AI following a procedure that doesn't work? Open an issue with:
- Which skill
- What went wrong
- What the correct behavior should be

## Skill Structure

Each skill follows this structure:

```
skills/<skill-name>/
├── SKILL.md              # Main instructions (short, procedural)
├── references/           # Deep-dive docs on specific topics
│   └── *.md
└── scripts/              # Deterministic helpers (optional)
    └── *.mjs
```

### SKILL.md Requirements

Every `SKILL.md` needs:

1. **YAML frontmatter** with `name`, `description`, and `compatibility`
2. **When to use** — Conditions that trigger this skill
3. **Inputs required** — What the AI needs to gather first
4. **Procedure** — Step-by-step checklist
5. **Verification** — How to confirm it worked
6. **Failure modes / debugging** — Common problems and fixes
7. **Escalation** — When to ask for human help

See any existing skill for examples.

## Guidelines

### Keep It Practical

- Focus on what extension authors actually need to do.
- Include concrete examples, not abstract theory.
- Link to official WooCommerce / WordPress docs for deep dives.

### Keep It Current

- Target WooCommerce **10.9+**, WordPress core **6.9+**, and PHP **7.4+**.
- Avoid patterns that fight WooCommerce conventions (services container, Domain classes, Internal/ namespacing, etc.).
- Update `compatibility:` frontmatter when requirements change.

### Keep It Portable

- A skill in this repo should apply to any WooCommerce extension, not one specific extension.
- If your example needs a plugin-specific class name or capability, frame it as an example (`myplugin/get-something`), not as the canonical reference.
- For portable WordPress core knowledge, link to the corresponding skill in `WordPress/agent-skills` rather than duplicating it.

### Keep It Testable

- Add at least one eval scenario for new skills (`.json` only — see `eval/scenarios/README.md`).
- Run `node eval/harness/run.mjs` before submitting.

### Keep It Small

- Prefer small, focused skills over mega-skills.
- Keep `SKILL.md` short — push depth into `references/`.
- One skill should do one thing well.

## Submitting Changes

1. Fork the repo.
2. Create a branch (`git checkout -b improve-<skill-name>`).
3. Make your changes.
4. Run validation: `node eval/harness/run.mjs`.
5. Commit with a clear message.
6. Open a pull request.

For significant changes, consider opening an issue first to discuss the approach.

## Questions?

Open an issue or start a discussion. We're happy to help you get started.

---

*Your WooCommerce knowledge can help thousands of extension authors get better AI assistance. Thank you for contributing!*
