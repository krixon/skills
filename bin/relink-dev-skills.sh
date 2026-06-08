#!/usr/bin/env bash
# Regenerate the dogfood symlink farm under .claude/skills/.
#
# This repo IS the plugin and loads its own skills live during development. The
# distributable skills live in skills/; .claude/skills/ mirrors them as a farm of
# per-skill symlinks so the in-context project picks them up — every skills/* entry
# (skill dirs AND the shared docs AND contracts/) is mirrored, so each skill's
# ../GITHUB.md-style progressive-disclosure links still resolve against .claude/skills/.
#
# Repo-local skills that must NOT ship (release) live as real directories directly
# under .claude/skills/, outside skills/. They are left untouched here.
#
# Idempotent: drops the existing symlinks and recreates them. Run after adding,
# renaming, or removing a skill. See ADR 0005.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
farm="$root/.claude/skills"

mkdir -p "$farm"

# Drop stale symlinks only — real dirs (the repo-local skills) survive.
find "$farm" -maxdepth 1 -type l -delete

for path in "$root"/skills/*; do
  name="$(basename "$path")"
  ln -s "../../skills/$name" "$farm/$name"
done

echo "relinked $(find "$farm" -maxdepth 1 -type l | wc -l | tr -d ' ') skills into $farm"
