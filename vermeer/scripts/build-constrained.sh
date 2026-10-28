#!/usr/bin/env bash
# Scope ONLY this build's resident RAM. Preserve full LTO/CFI and other workloads.
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
test "$(id -u)" = 0 || { echo 'Requires WSL root for a transient resource scope'; exit 2; }
test -f /sys/fs/cgroup/cgroup.controllers
grep -qw memory /sys/fs/cgroup/cgroup.controllers
bash "$PROJECT/scripts/enable-build-swap.sh"
EXTRA=/home/administrator/vermeer-build/build-extra.swap
test ! -L "$EXTRA"
if [ ! -e "$EXTRA" ]; then
  umask 077
  fallocate -l 4G "$EXTRA"
  chmod 600 "$EXTRA"
  mkswap "$EXTRA"
fi
test -f "$EXTRA"
if ! swapon --show=NAME --noheadings | grep -Fx "$EXTRA" >/dev/null; then swapon "$EXTRA"; fi
# Caller must also check free Windows disk space: the VHD's df is insufficient.
systemd-run --wait --pipe --collect --unit=vermeer-baseline-build \
  --property=MemoryHigh=2G --property=MemoryMax=3G --property=MemorySwapMax=8G \
  --property=OOMPolicy=stop --uid=administrator \
  --setenv=HOME=/home/administrator --setenv=JOBS=2 \
  /bin/bash "$PROJECT/scripts/build-baseline.sh"
