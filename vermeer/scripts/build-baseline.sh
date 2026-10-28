#!/usr/bin/env bash
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
WORK=${VERMEER_WORK:-$HOME/vermeer-build}
SOURCE=$WORK/common
CLANG=$WORK/toolchains/clang-r450784e/bin
OUT=$WORK/out-baseline
PIN=6f2f96be86b93de6ed58a2c46b456fb49734c382
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$PIN" || { echo 'Wrong source commit'; exit 2; }
test -z "$(git -C "$SOURCE" status --porcelain)" || { echo 'Source must be clean'; exit 2; }
"$CLANG/clang" --version | grep -F 'r450784e' >/dev/null || { echo 'Wrong toolchain'; exit 2; }
for tool in make gcc bc bison flex openssl python3; do command -v "$tool" >/dev/null; done
mkdir -p "$OUT" "$PROJECT/evidence" "$PROJECT/build/baseline"
exec > >(tee "$PROJECT/evidence/baseline-build.log") 2>&1
BUILD_COMPLETE=false
printf '{"status":"running","build_complete":false,"device_verified":false}\n' > "$PROJECT/evidence/baseline-build-exit.json"
record_exit() {
  code=$?
  if [ "$BUILD_COMPLETE" != true ] && [ "$code" -eq 0 ]; then code=125; fi
  printf '{"exit_code":%s,"build_complete":%s,"device_verified":false}\n' "$code" "$BUILD_COMPLETE" > "$PROJECT/evidence/baseline-build-exit.json"
}
trap record_exit EXIT
trap 'exit 130' INT TERM HUP
export PATH="$CLANG:$PATH"
export KBUILD_BUILD_USER=vermeer KBUILD_BUILD_HOST=offline-lab KBUILD_BUILD_VERSION=1
export SOURCE_DATE_EPOCH=$(git -C "$SOURCE" show -s --format=%ct)
export KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$SOURCE_DATE_EPOCH")
# Original source Makefile supports native make. This is an offline compile
# baseline, NOT the full hermetic Google release/Kleaf ABI certification pipeline.
python3 - "$SOURCE" "$OUT" <<'PY'
import pathlib,sys
s,o=map(pathlib.Path,sys.argv[1:])
symbols=set()
for p in sorted((s/'android').glob('abi_gki_aarch64*')):
    if p.suffix or not p.is_file(): continue
    for line in p.read_text().splitlines():
        line=line.strip().split('#',1)[0].strip()
        if line and not line.startswith('['): symbols.add(line)
(o/'abi_symbollist.raw').write_text('\n'.join(sorted(symbols))+'\n')
PY
cp "$PROJECT/configs/baseline/historical-5.15.178.config" "$OUT/.config"
"$SOURCE/scripts/config" --file "$OUT/.config" --set-str UNUSED_KSYMS_WHITELIST "$OUT/abi_symbollist.raw"
# Deliberately distinct release; never impersonate Google's signed artifact.
"$SOURCE/scripts/config" --file "$OUT/.config" --set-str LOCALVERSION '-vermeer-baseline-lab'
make -C "$SOURCE" O="$OUT" ARCH=arm64 LLVM=1 KCFLAGS=-D__ANDROID_COMMON_KERNEL__ olddefconfig
python3 "$PROJECT/scripts/kernel_audit.py" config-diff "$PROJECT/configs/baseline/historical-5.15.178.config" "$OUT/.config" > "$PROJECT/evidence/baseline-config-diff.json"
make -C "$SOURCE" O="$OUT" ARCH=arm64 LLVM=1 KCFLAGS=-D__ANDROID_COMMON_KERNEL__ -j"${JOBS:-2}" Image modules
for file in arch/arm64/boot/Image vmlinux Module.symvers System.map .config; do
  cp "$OUT/$file" "$PROJECT/build/baseline/$(basename "$file")"
done
python3 "$PROJECT/scripts/kernel_audit.py" image "$OUT/arch/arm64/boot/Image" > "$PROJECT/evidence/baseline-Image-inspection.json"
sha256sum "$OUT/arch/arm64/boot/Image" "$OUT/vmlinux" "$OUT/Module.symvers" "$OUT/.config" > "$PROJECT/evidence/baseline-SHA256SUMS.txt"
echo 'Offline compile finished; device ABI/recovery gates remain mandatory. No installer generated.'
BUILD_COMPLETE=true
