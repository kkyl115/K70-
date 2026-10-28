#!/usr/bin/env bash
# Local WSL build resource only. No Windows config change; no permanent fstab entry.
set -euo pipefail
SWAP=/home/administrator/vermeer-build/build.swap
test "$(id -u)" = 0 || { echo 'Run as WSL root'; exit 2; }
test -d /home/administrator/vermeer-build
test ! -L "$SWAP"
if [ ! -e "$SWAP" ]; then
  AVAILABLE=$(df --output=avail -B1 /home/administrator/vermeer-build | tail -1)
  test "$AVAILABLE" -gt 8589934592 || { echo 'Need 8GiB free before creating 4GiB swap'; exit 2; }
  umask 077
  fallocate -l 4G "$SWAP"
  chmod 600 "$SWAP"
  mkswap "$SWAP"
fi
test -f "$SWAP"
if ! swapon --show=NAME --noheadings | grep -Fx "$SWAP" >/dev/null; then swapon "$SWAP"; fi
swapon --show
free -h
