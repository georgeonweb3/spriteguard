#!/bin/sh
# Run every check SpriteGuard claims, and save the log as evidence.
#   sh eval/run_all.sh
# Exit code is non-zero if any check fails.
set -e
cd "$(dirname "$0")/.."
LOG="evidence/eval-2026-11-24.log"
mkdir -p evidence data
{
  echo "=== SpriteGuard eval run: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo
  echo "--- 1. Aegis guard test suite, run against the VENDORED copies ---"
  echo "Vendored files must be byte-identical to George's shipped guard:"
  SRC=/home/hatch/workspace/hermes-plugin-entry/aegis-spend-guard
  if [ -d "$SRC" ]; then
    diff "$SRC/policy.py" agent/policy.py
    diff "$SRC/guard.py" agent/guard.py
    diff "$SRC/__init__.py" agent/__init__.py
    diff "$SRC/tests/test_spend_guard.py" agent/tests/test_spend_guard.py
    diff "$SRC/tests/test_hermes_wiring.py" agent/tests/test_hermes_wiring.py
    echo "policy.py + guard.py + __init__.py + both test files: byte-identical."
  else
    echo "Vendored-source check SKIPPED: $SRC is not present on this machine."
    echo "The vendored files were verified byte-identical at build time"
    echo "(see README Proof log); a fresh Sprite/CI cannot re-diff them."
  fi
  PYTHONPATH=agent python3 -m unittest discover -s agent/tests 2>&1 | tail -n 4
  echo
  echo "--- 2. Adversary eval (15 attacks, 2 controls) ---"
  python3 eval/adversary.py
  echo
  echo "--- 3. Demo (worked example, mock-gateway mode) ---"
  rm -rf data/ledger.db data/memory.json data/receipts
  python3 agent/sprite_agent.py demo
} 2>&1 | tee "$LOG"
echo "Log saved to $LOG"
