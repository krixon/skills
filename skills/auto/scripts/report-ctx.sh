#!/usr/bin/env bash
# Report the parent session's context-window size as `ctx: NNK`.
# The model runs this once per drain iteration (auto/SKILL.md) so window growth
# stays visible across a long unattended loop.
#
#   report-ctx.sh [transcript.jsonl]
#
# With no argument it resolves the transcript by session id, never by mtime:
# `ls -t` may be shell-aliased (e.g. to eza) and silently return a stale
# transcript from another session, freezing the reported number. An explicit
# path as $1 overrides the lookup (used for testing).
#
# The figure is the status-line context size: input_tokens +
# cache_read_input_tokens + cache_creation_input_tokens from the last transcript
# record carrying a populated usage. We iterate every line and skip ones that
# fail to parse (a streaming/partial trailing record) or carry no usage, then
# keep the last record whose sum is > 0 — so a usage-less final line never reads
# as 0K. python3 is present on macOS + Linux, so no jq or tac dependency.
#
# Never hard-fails: an unresolved transcript or no usable record prints
# `ctx: ?K` and exits 0, so the drain is never blocked.
set -euo pipefail

transcript="${1:-}"
if [[ -z "$transcript" ]]; then
  transcript=$(find "$HOME/.claude/projects" -name "${CLAUDE_CODE_SESSION_ID:-}.jsonl" 2>/dev/null | head -n 1)
fi

if [[ -z "$transcript" || ! -f "$transcript" ]]; then
  echo "ctx: ?K"
  exit 0
fi

python3 - "$transcript" <<'PY'
import json, sys

last = 0
with open(sys.argv[1], encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (ValueError, TypeError):
            continue  # partial/streaming trailing record
        usage = (rec.get("message") or {}).get("usage")
        if not isinstance(usage, dict):
            continue
        total = (
            usage.get("input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
        )
        if total > 0:
            last = total

print(f"ctx: {round(last / 1000)}K" if last > 0 else "ctx: ?K")
PY
