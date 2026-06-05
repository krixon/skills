---
name: write-skill
description: Create new agent skills with proper structure, progressive disclosure, and bundled resources. Use when user wants to create, write, or build a new skill.
---

# Writing Skills

## Process

1. **Gather requirements** - ask user about:
   - What task/domain does the skill cover?
   - What specific use cases should it handle?
   - Does it need executable scripts or just instructions?
   - Any reference materials to include?

2. **Draft the skill** - create:
   - SKILL.md with concise instructions
   - Additional reference files if SKILL.md would exceed ~100 lines
   - Utility scripts for deterministic operations

3. **Review with user** - present draft and ask:
   - Does this cover your use cases?
   - Anything missing or unclear?
   - Should any section be more/less detailed?

## Skill Structure

```
skill-name/
├── SKILL.md           # Main instructions (required)
├── REFERENCE.md       # Detailed docs (if needed)
├── EXAMPLES.md        # Usage examples (if needed)
└── scripts/           # Utility scripts (if needed)
    └── helper.py
```

`SKILL.md` and bundled reference docs are `UPPERCASE-KEBAB.md` (e.g. `REFERENCE.md`, `TESTABLE-INTERFACES.md`). Scripts live under `scripts/` and keep normal lowercase names (`helper.py`, `hitl-loop.template.sh`).

## SKILL.md Template

```md
---
name: skill-name
description: Brief description of capability. Use when [specific triggers].
---

# Skill Name

## Quick start

[Minimal working example]

## Workflows

[Step-by-step processes with checklists for complex tasks]

## Advanced features

[Link to separate files: See [REFERENCE.md](REFERENCE.md)]
```

## Authoring detail

See [REFERENCE.md](REFERENCE.md) for:

- **Frontmatter** — every optional field and when to use it (capability at zero body-text cost).
- **Description requirements** — format and good/bad examples for the one line the agent routes on.
- **When to add scripts** vs generate code.
- **When to split files** into REFERENCE/EXAMPLES.
- **Embedding templates and examples** — `<tag>` vs code-fence delimiter rules.

## Review Checklist

After drafting, verify:

- [ ] Description includes triggers ("Use when...")
- [ ] SKILL.md under 100 lines
- [ ] No time-sensitive info
- [ ] Consistent terminology
- [ ] Concrete examples included
- [ ] Reference chains kept shallow (SKILL.md links one level out; reference docs may cross-link a sibling for downstream-only detail)
- [ ] Inline templates use `<tags>`; verbatim samples use `md`-labelled fences
