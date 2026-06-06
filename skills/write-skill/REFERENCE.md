# Write-Skill Reference

Lookup detail for authoring skills. The main flow lives in [SKILL.md](SKILL.md).

## Frontmatter

`name` and `description` are the only required fields. Everything else is optional and adds capability at **zero body-text cost** — reach for frontmatter before adding prose.

| Field | Use it for |
|-------|-----------|
| `name` | Identifier. Keep aligned with the directory name to avoid confusion. |
| `description` | The only thing the agent sees when choosing a skill. See requirements below. |
| `argument-hint` | Autocomplete hint for command-style skills invoked as `/skill <text>`, e.g. `"[issue # or what to triage]"`. Display-only. |
| `disable-model-invocation: true` | Skill is user-invoked only (`/name`); the model never auto-loads it. Use for deliberate setup steps or manual tools. |
| `context: fork` (+ `agent: Explore`) | Run the skill in a subagent that returns only its conclusion. Fits read-only "survey a lot, return a little" skills; keeps the main thread's context clean. Don't use it for skills that need the current conversation or back-and-forth. |

Skip `allowed-tools` in a distributed plugin: read tools are usually already allowed, and the tools worth pre-approving (test runners) vary per repo and can't be hardcoded.

## Description Requirements

The description is **the only thing the agent sees** when choosing which skill to load — surfaced in the system prompt alongside every other installed skill. It must convey what capability the skill provides and when to trigger it (specific keywords, contexts, file types).

**Format**: max 1024 chars, third person. First sentence what it does; second "Use when [specific triggers]".

**Good**: `Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when user mentions PDFs, forms, or document extraction.`

**Bad**: `Helps with documents.` — no way to distinguish it from other document skills.

## When to Add Scripts

Add utility scripts when:

- Operation is deterministic (validation, formatting)
- Same code would be generated repeatedly
- Errors need explicit handling

Scripts save tokens and improve reliability vs generated code.

## When to Split Files

Split into separate files when:

- SKILL.md exceeds 100 lines
- Content has distinct domains (finance vs sales schemas)
- Advanced features are rarely needed

## Embedding Templates and Examples

When content stays inline, pick the delimiter by role:

- **`<kebab-tag>` for a template the model fills in and emits** as content — an epic, an issue, a comment, a file it writes. Contents render as markdown (so they can contain `##` headings) and nest cleanly. Name templates `<thing-template>` and examples `<thing-example>`.
- **Code fence for verbatim content shown literally** — a code snippet, command output, or a file scaffold meant to be copied byte-for-byte. Label markdown fences `md` (not `markdown`).

If a fenced sample must itself contain a fenced block, use a four-backtick outer fence — or, better, switch it to a `<tag>` so the inner fence renders cleanly. Triple-backtick-inside-triple-backtick breaks rendering.
