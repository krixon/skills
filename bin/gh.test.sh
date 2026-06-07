#!/usr/bin/env bash
# Tests for the bin/gh wrapper shim. GH_REAL_BIN points at a stub that echoes
# `REAL_GH_CALLED: $*` and exits 0, so we can tell a passthrough (stub ran) from
# a block (stub never ran). argv is crafted directly — these assert the shim's
# behaviour at the argv boundary, which is the whole point of the shim.
set -u

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
shim="$here/gh"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

stub="$tmp/gh-stub"
cat >"$stub" <<'EOF'
#!/usr/bin/env bash
echo "REAL_GH_CALLED: $*"
exit 0
EOF
chmod +x "$stub"

pass=0
fail=0

# run_shim <env-assignments...> -- <argv...>
# Captures combined stdout+stderr and exit code. Each invocation gets a clean
# environment for the variables under test so cases don't leak into each other.
run() {
  local desc="$1"; shift
  local want_exit="$1"; shift
  local want_re="$1"; shift          # regex that MUST appear in output
  local notwant_re="$1"; shift       # regex that MUST NOT appear ("" = skip)
  # Remaining args: VAR=val ... -- argv...
  local -a envs=() argv=()
  local seen_sep=0
  local a
  for a in "$@"; do
    if [ "$a" = "--" ] && [ "$seen_sep" = 0 ]; then seen_sep=1; continue; fi
    if [ "$seen_sep" = 0 ]; then envs+=("$a"); else argv+=("$a"); fi
  done

  local out rc
  out="$(env -u GITHUB_BOT_ACCOUNT -u GH_TOKEN \
         GH_REAL_BIN="$stub" ${envs[@]+"${envs[@]}"} \
         "$shim" ${argv[@]+"${argv[@]}"} 2>&1)"
  rc=$?

  local ok=1
  [ "$rc" = "$want_exit" ] || ok=0
  if [ -n "$want_re" ]; then grep -qE "$want_re" <<<"$out" || ok=0; fi
  if [ -n "$notwant_re" ]; then grep -qE "$notwant_re" <<<"$out" && ok=0; fi

  if [ "$ok" = 1 ]; then
    pass=$((pass+1)); printf 'PASS  %s\n' "$desc"
  else
    fail=$((fail+1))
    printf 'FAIL  %s\n' "$desc"
    printf '      exit=%s (want %s)\n' "$rc" "$want_exit"
    printf '      output: %s\n' "$out"
  fi
}

# 1. bot set, `pr create`, no GH_TOKEN -> BLOCKED.
run "blocked: bot set, pr create, no token" \
    1 "Open the PR as the krixon-bot account" "REAL_GH_CALLED" \
    GITHUB_BOT_ACCOUNT=krixon-bot -- pr create --fill

# 2. bot set, `pr create`, GH_TOKEN=x -> passthrough.
run "passthrough: bot set, pr create, token supplied" \
    0 "REAL_GH_CALLED: pr create" "" \
    GITHUB_BOT_ACCOUNT=krixon-bot GH_TOKEN=x -- pr create --fill

# 3. bot UNSET, `pr create`, no token -> passthrough (inert).
run "inert: bot unset, pr create" \
    0 "REAL_GH_CALLED: pr create" "" \
    -- pr create --fill

# 4. bot set, `pr list` (non-create) -> passthrough.
run "passthrough: bot set, pr list" \
    0 "REAL_GH_CALLED: pr list" "" \
    GITHUB_BOT_ACCOUNT=krixon-bot -- pr list

# 5. create phrase as DATA in an argument -> passthrough.
run "passthrough: issue comment body mentions gh pr create" \
    0 "REAL_GH_CALLED: issue comment" "" \
    GITHUB_BOT_ACCOUNT=krixon-bot -- issue comment --body "please run gh pr create --fill"

# 6. create phrase in a title -> passthrough.
run "passthrough: issue create title mentions gh pr create" \
    0 "REAL_GH_CALLED: issue create" "" \
    GITHUB_BOT_ACCOUNT=krixon-bot -- issue create --title "gh pr create docs"

# 7. global flag before subcommand -> still BLOCKED.
run "blocked: -R owner/repo pr create, no token" \
    1 "Open the PR as the krixon-bot account" "REAL_GH_CALLED" \
    GITHUB_BOT_ACCOUNT=krixon-bot -- -R owner/repo pr create --fill

run "blocked: --repo owner/repo pr create, no token" \
    1 "Open the PR as the krixon-bot account" "REAL_GH_CALLED" \
    GITHUB_BOT_ACCOUNT=krixon-bot -- --repo owner/repo pr create

run "blocked: glued -Rowner/repo pr create, no token" \
    1 "Open the PR as the krixon-bot account" "REAL_GH_CALLED" \
    GITHUB_BOT_ACCOUNT=krixon-bot -- -Rowner/repo pr create

# 8. global flag before subcommand WITH token -> passthrough.
run "passthrough: --repo owner/repo pr create, token supplied" \
    0 "REAL_GH_CALLED: --repo owner/repo pr create" "" \
    GITHUB_BOT_ACCOUNT=krixon-bot GH_TOKEN=x -- --repo owner/repo pr create

# 9. non-create with global flag still passes.
run "passthrough: bot set, -R owner/repo pr list" \
    0 "REAL_GH_CALLED: -R owner/repo pr list" "" \
    GITHUB_BOT_ACCOUNT=krixon-bot -- -R owner/repo pr list

# 10. boundary: title is ONE quoted token "pr create", not two
#     adjacent tokens -> must NOT block.
run "passthrough: issue create --title \"pr create\" (single token)" \
    0 "REAL_GH_CALLED: issue create --title pr create" "Open the PR as" \
    GITHUB_BOT_ACCOUNT=krixon-bot -- issue create --title "pr create"

# 11. GH_REAL_BIN pointed at the shim itself must NOT recurse.
#     Stage a real-gh stub on PATH; the shim must ignore the self-pointer and
#     resolve the PATH stub instead. Bounded by timeout so a regression (the
#     fork bomb) fails loud instead of hanging.
ghdir="$tmp/ghbin"
mkdir -p "$ghdir"
cat >"$ghdir/gh" <<'EOF'
#!/usr/bin/env bash
echo "PATH_STUB_CALLED: $*"
exit 0
EOF
chmod +x "$ghdir/gh"

# Portable watchdog (macOS has no `timeout`): run in background, poll for exit up
# to a deadline, kill the process group if it overruns (the fork-bomb regression).
d2_outfile="$tmp/d2.out"
env -u GITHUB_BOT_ACCOUNT -u GH_TOKEN \
    GH_REAL_BIN="$shim" PATH="$ghdir:$PATH" \
    "$shim" version >"$d2_outfile" 2>&1 &
d2_pid=$!
d2_rc=""
for _ in $(seq 1 50); do            # 50 * 0.1s = 5s deadline
  if ! kill -0 "$d2_pid" 2>/dev/null; then
    wait "$d2_pid"; d2_rc=$?; break
  fi
  perl -e 'select(undef,undef,undef,0.1)'
done
if [ -z "$d2_rc" ]; then            # still alive => hung/recursing
  kill -9 "$d2_pid" 2>/dev/null
  pkill -9 -P "$d2_pid" 2>/dev/null
  wait "$d2_pid" 2>/dev/null
  d2_rc=124
fi
d2_out="$(cat "$d2_outfile")"
if [ "$d2_rc" != 124 ] && grep -qE "PATH_STUB_CALLED: version" <<<"$d2_out"; then
  pass=$((pass+1)); printf 'PASS  %s\n' "GH_REAL_BIN=self does not recurse, resolves PATH stub"
else
  fail=$((fail+1)); printf 'FAIL  %s\n' "GH_REAL_BIN=self does not recurse, resolves PATH stub"
  printf '      exit=%s (124=timeout/hang)\n' "$d2_rc"
  printf '      output: %s\n' "$d2_out"
fi

echo
echo "summary: $pass passed, $fail failed"
[ "$fail" = 0 ]
