#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -v 2>&1 | tee evidence/automated-tests.log
for file in scripts/*.sh bootguard/preflight/*.sh bootguard/recovery/update-binary; do bash -n "$file"; done
