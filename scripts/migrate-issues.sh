#!/bin/bash
# migrate-issues.sh — Reorganize existing docs/issues/ into active/closed structure
# Usage: ./scripts/migrate-issues.sh [--dry-run]
#
# All TaxAssistant GitHub issues are currently CLOSED, so this script moves
# every issue-N.md into docs/issues/closed/by-phase/<phase>/.
# Phase mapping (since GitHub labels do not include phase-X):
#   phase-1   → notification system roadmap (CLAUDE.md §12), issues 51-60
#   unknown   → legacy issues without an explicit phase label

set -euo pipefail

ISSUES_DIR="docs/issues"
DRY_RUN=false

# CUSTOMIZE: Phase ranges based on TaxAssistant's actual issue numbers.
# Re-check with `gh issue list --label phase-X` if labels are added later.
declare -A PHASE_RANGES=(
  ["phase-1"]="51-60"
)

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

execute() {
  if $DRY_RUN; then echo "[DRY] $*"; else eval "$*"; fi
}

detect_phase() {
  local num=$1
  # Try gh CLI first (only if available and authenticated)
  if command -v gh &> /dev/null; then
    local phase
    phase=$(gh issue view "$num" --json labels --jq '.labels[].name' 2>/dev/null | grep -oE 'phase-[0-9a-z]+' | head -1)
    [[ -n "$phase" ]] && echo "$phase" && return
  fi
  # Fallback to ranges
  for p in "${!PHASE_RANGES[@]}"; do
    local range="${PHASE_RANGES[$p]}"
    local start="${range%-*}" end="${range#*-}"
    if (( num >= start && num <= end )); then echo "$p"; return; fi
  done
  echo "unknown"
}

[ -d ".git" ] || { echo "Not in repo root"; exit 1; }
[ -d "$ISSUES_DIR" ] || { echo "$ISSUES_DIR not found"; exit 1; }

execute "mkdir -p $ISSUES_DIR/active $ISSUES_DIR/closed/by-phase"

moved=0
for file in "$ISSUES_DIR"/issue-*.md; do
  [ -e "$file" ] || continue
  num=$(basename "$file" | grep -oE '[0-9]+' | head -1)
  [ -z "$num" ] && continue

  phase=$(detect_phase "$num")
  target="$ISSUES_DIR/closed/by-phase/$phase"
  execute "mkdir -p $target"
  execute "git mv $file $target/"
  echo "  Moved #$num → $phase"
  moved=$((moved + 1))
done

echo "Migrated $moved issues"
if $DRY_RUN; then echo "(DRY RUN — no actual changes)"; fi
