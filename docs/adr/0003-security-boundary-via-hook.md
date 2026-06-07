# 3. Ship the security boundary as an ungated UserPromptSubmit hook

Status: Accepted

## Context

The untrusted-external-content boundary (`SECURITY.md`: data-not-instructions, no shell interpolation) must be in context every turn, whether or not any skill is loaded — a prompt-injection or exfiltration attempt arrives through whatever content the session fetches, independent of the active workflow.

A `CLAUDE.md` `@import` is the obvious always-on channel, and the repo uses it for `VOICE.md`. But `CLAUDE.md` imports are dev-local: they load this checkout's files during development and do not travel with the marketplace-distributed plugin. A boundary delivered only through `@SECURITY.md` would be absent from every installed copy — the exact context where it matters most.

Hooks are the plugin's only portable always-on channel. `hooks/hooks.json`, keyed on `${CLAUDE_PLUGIN_ROOT}`, ships and fires in installed plugins.

## Decision

Deliver the boundary through an ungated `UserPromptSubmit` hook (`hooks/security-boundary.sh`), modeled on `caveman-reminder.sh` but with no marker gate, injecting `SECURITY.md` as `additionalContext` on every turn.

- The hook reads `SECURITY.md` from `${CLAUDE_PLUGIN_ROOT}` rather than embedding a copy — the human-editable file stays the single source.
- It **fails open**: a missing or unreadable `SECURITY.md`, malformed payload, or absent `jq` skips injection for that turn rather than aborting. The boundary is advisory context, so dropping one turn is safe; a non-zero exit would surface a hook error on every prompt and wedge the session.
- Registered in `hooks/hooks.json` (`${CLAUDE_PLUGIN_ROOT}`) and mirrored in `.claude/settings.json` (`${CLAUDE_PROJECT_DIR}`), matching the existing dual-registered hooks.

`CLAUDE.md` does not `@import` `SECURITY.md`: the hook already injects it every turn, so an import would only duplicate the boundary in this checkout's context while still not travelling with the distributed plugin. The `CLAUDE.md`-import-only alternative was rejected: it does not survive distribution, leaving installed plugins without the boundary.

## Consequences

The boundary is advisory, not enforced — the hook injects context, it does not block exfiltration. Hard enforcement (a `PreToolUse` exfil detector) is out of scope and could layer on later. A per-turn context cost is accepted, justified by the rule being security-relevant and small.

This establishes the always-on-via-hook pattern for any standing rule that must survive distribution; #121 can reuse it to move `VOICE.md` off its `CLAUDE.md` import onto the same channel.
