#!/usr/bin/env bash
# goal-check.sh — run a goal's completion command, log the result, detect stalls.
#
# Usage:
#   scripts/goal-check.sh "<command>"            # run once, log, print PASS/FAIL
#   scripts/goal-check.sh "<command>" --status   # show last 5 runs and stall state
#
# Log lives at .goal/checks.log in the current directory (create .goal/ first
# or let this script do it). Add .goal/ to .gitignore if you do not want it
# committed; progress.md is the committed summary, this log is the raw evidence.
#
# Exit code mirrors the command's exit code so it can be used in hooks or /goal.

set -u

CMD="${1:-}"
MODE="${2:-run}"
LOG_DIR=".goal"
LOG="$LOG_DIR/checks.log"
OUT_DIR="$LOG_DIR/out"

if [[ -z "$CMD" ]]; then
  echo "usage: $0 \"<command>\" [--status]" >&2
  exit 2
fi

mkdir -p "$OUT_DIR"
touch "$LOG"

stall_state() {
  # Stalled = last three runs produced byte-identical output.
  local last3
  last3=$(tail -n 3 "$LOG" | awk -F'\t' '{print $4}')
  local n
  n=$(echo "$last3" | grep -c .)
  if [[ "$n" -lt 3 ]]; then
    echo "not enough runs"
    return
  fi
  if [[ $(echo "$last3" | sort -u | wc -l) -eq 1 ]]; then
    echo "STALLED (3 identical outputs) — change approach, do not rerun"
  else
    echo "moving"
  fi
}

if [[ "$MODE" == "--status" ]]; then
  echo "Last 5 runs:"
  tail -n 5 "$LOG" | awk -F'\t' '{printf "  %s  exit=%s  %s\n", $1, $3, $2}'
  echo "Total runs: $(wc -l < "$LOG")"
  echo "Stall: $(stall_state)"
  exit 0
fi

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RUN_ID=$(wc -l < "$LOG")
OUT_FILE="$OUT_DIR/$RUN_ID.txt"

bash -c "$CMD" >"$OUT_FILE" 2>&1
RC=$?

HASH=$(sha256sum "$OUT_FILE" | cut -c1-16)
printf '%s\t%s\t%s\t%s\n' "$TS" "$CMD" "$RC" "$HASH" >>"$LOG"

if [[ $RC -eq 0 ]]; then
  echo "PASS  run=$RUN_ID  exit=0"
else
  echo "FAIL  run=$RUN_ID  exit=$RC"
  echo "--- last 20 lines ---"
  tail -n 20 "$OUT_FILE"
  echo "--- stall: $(stall_state)"
fi

exit $RC
