#!/usr/bin/env bash
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
WORK=${VERMEER_WORK:-$HOME/vermeer-build}
OUT=$WORK/out-baseline
ROOT_STAGE=$WORK/root-sukisu-v4.2.1-r2
test -s "$OUT/Module.symvers" || { echo 'Complete baseline build required; modules_prepare is insufficient'; exit 2; }
if [ ! -d "$ROOT_STAGE" ]; then python3 "$PROJECT/scripts/prepare-root.py" "$ROOT_STAGE"; fi
python3 - "$ROOT_STAGE" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1]); m=json.loads((p/'stage-manifest.json').read_text())
k=p/('SukiSU-Ultra-'+m['source_commit'])/'kernel/Kbuild'
assert m['source_commit']=='d6b36700f3bd0a4c1585549b470dd30bb8774534'
assert hashlib.sha256(k.read_bytes()).hexdigest()==m['kbuild_sha256']
assert m['KPM'] is False and m['SUSFS'] is False
PY
export PATH="$WORK/toolchains/clang-r450784e/bin:$PATH"
exec > >(tee "$PROJECT/evidence/root-lkm-build.log") 2>&1
trap 'code=$?; printf "{\"exit_code\":%s,\"loaded\":false}\n" "$code" > "$PROJECT/evidence/root-lkm-build-exit.json"' EXIT
make -C "$OUT" ARCH=arm64 LLVM=1 KCFLAGS=-D__ANDROID_COMMON_KERNEL__ \
 M="$ROOT_STAGE/SukiSU-Ultra-d6b36700f3bd0a4c1585549b470dd30bb8774534/kernel" \
 CONFIG_KSU=m CONFIG_KPM=n -j2 modules
mkdir -p "$PROJECT/build/root-lkm"
cp "$ROOT_STAGE/SukiSU-Ultra-d6b36700f3bd0a4c1585549b470dd30bb8774534/kernel/kernelsu.ko" "$PROJECT/build/root-lkm/"
python3 "$PROJECT/scripts/kernel_audit.py" module "$PROJECT/build/root-lkm/kernelsu.ko" > "$PROJECT/evidence/root-lkm-module.json"
echo 'Compile experiment only. Not signed for or compatible-proven with the phone. Never insmod this artifact.'
