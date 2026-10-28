#!/usr/bin/env bash
# Linux source/toolchain acquisition only; never accesses a phone.
set -euo pipefail
WORK=${VERMEER_WORK:-$HOME/vermeer-build}
PIN=6f2f96be86b93de6ed58a2c46b456fb49734c382
TOOLPIN=9f759dee5cdc5f85d076c642a192f6a9232f7058
mkdir -p "$WORK/toolchains"
if [ ! -d "$WORK/common" ]; then
  git init "$WORK/common"
  git -C "$WORK/common" remote add origin https://android.googlesource.com/kernel/common
  git -C "$WORK/common" fetch --depth=1 origin "$PIN"
  git -C "$WORK/common" checkout --detach FETCH_HEAD
fi
test "$(git -C "$WORK/common" rev-parse HEAD)" = "$PIN"
ARCHIVE=$WORK/toolchains/clang-r450784e.tar.gz
if [ ! -f "$ARCHIVE" ]; then
  curl --fail --location --retry 2 "https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+archive/$TOOLPIN/clang-r450784e.tar.gz" -o "$ARCHIVE.partial"
  echo "d79f76ed59bdcfbe8681afcded616e89954aa559318caa11ef5e327bc290c1b4  $ARCHIVE.partial" | sha256sum -c -
  mv "$ARCHIVE.partial" "$ARCHIVE"
fi
echo "d79f76ed59bdcfbe8681afcded616e89954aa559318caa11ef5e327bc290c1b4  $ARCHIVE" | sha256sum -c -
if [ ! -d "$WORK/toolchains/clang-r450784e" ]; then
  mkdir "$WORK/toolchains/clang-r450784e"
  tar --no-same-owner -xzf "$ARCHIVE" -C "$WORK/toolchains/clang-r450784e"
fi
"$WORK/toolchains/clang-r450784e/bin/clang" --version
printf '%s\n' 'Source/toolchain ready. Host dependency versions are listed in evidence/build-dependencies.txt.'
