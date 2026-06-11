#!/usr/bin/env bash
# Regenerate the dogfood symlink farms under .claude/skills/ and .claude/commands/.
#
# This repo IS the plugin and loads its own skills and commands live during
# development. The distributables live in skills/ and commands/; the two farms
# under .claude/ mirror them as per-entry symlinks so the in-context project
# picks them up.
#
# .claude/skills/ mirrors every skills/* entry (skill dirs AND the shared docs
# AND contracts/), so each skill's ../GITHUB.md-style progressive-disclosure
# links still resolve against .claude/skills/. .claude/commands/ mirrors every
# commands/*.md — the collapsed pure commands (thin wrappers over bin/<name>),
# distinct from the agent-native skills.
#
# Repo-local skills that must NOT ship (release) live as real directories directly
# under .claude/skills/, outside skills/. They are left untouched here.
#
# Idempotent: drops the existing symlinks and recreates them. Run after adding,
# renaming, or removing a skill or command. See ADR 0005 and ADR 0008.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
farm="$root/.claude/skills"
cmd_farm="$root/.claude/commands"

mkdir -p "$farm" "$cmd_farm"

# Drop stale symlinks only — real dirs (the repo-local skills) survive.
find "$farm" -maxdepth 1 -type l -delete
find "$cmd_farm" -maxdepth 1 -type l -delete

for path in "$root"/skills/*; do
  name="$(basename "$path")"
  ln -s "../../skills/$name" "$farm/$name"
done

for path in "$root"/commands/*.md; do
  [ -e "$path" ] || continue
  name="$(basename "$path")"
  ln -s "../../commands/$name" "$cmd_farm/$name"
done

echo "relinked $(find "$farm" -maxdepth 1 -type l | wc -l | tr -d ' ') skills into $farm"
echo "relinked $(find "$cmd_farm" -maxdepth 1 -type l | wc -l | tr -d ' ') commands into $cmd_farm"
