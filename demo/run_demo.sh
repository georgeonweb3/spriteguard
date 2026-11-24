#!/bin/sh
# Reproduce the demo transcript exactly as the judges will see it.
#   sh demo/run_demo.sh
# Writes demo/transcript.txt. No network, no keys, no wallet.
set -e
cd "$(dirname "$0")/.."
rm -rf data
python3 agent/sprite_agent.py demo > demo/transcript.txt 2>&1
cat demo/transcript.txt
