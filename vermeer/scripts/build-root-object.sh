#!/usr/bin/env bash
# Independent object probe, never substitutes for MODPOST or .ko validation.
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
WORK=${VERMEER_WORK:-$HOME/vermeer-build}
STAGE=$WORK/root-sukisu-v4.2.1-r2
SOURCE=$STAGE/SukiSU-Ultra-d6b36700f3bd0a4c1585549b470dd30bb8774534/kernel
test -d "$STAGE" || python3 "$PROJECT/scripts/prepare-root.py" "$STAGE"
python3 - "$STAGE" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1]); m=json.loads((p/'stage-manifest.json').read_text())
assert m['source_commit']=='d6b36700f3bd0a4c1585549b470dd30bb8774534'
k=p/('SukiSU-Ultra-'+m['source_commit'])/'kernel/Kbuild'
assert hashlib.sha256(k.read_bytes()).hexdigest()==m['kbuild_sha256']
PY
export PATH="$WORK/toolchains/clang-r450784e/bin:$PATH"
# modules_prepare omits SELinux's generated flask.h/av_permissions.h; build
# that subsystem in this isolated output tree instead of copying stale headers.
make -C "$WORK/common" O="$WORK/out-object-probes" ARCH=arm64 LLVM=1 \
  KCFLAGS=-D__ANDROID_COMMON_KERNEL__ -j1 security/selinux/ \
  > "$PROJECT/evidence/root-object-selinux-prerequisite.log" 2>&1
set +e
make -C "$WORK/common" O="$WORK/out-object-probes" M="$SOURCE" \
  ARCH=arm64 LLVM=1 KCFLAGS=-D__ANDROID_COMMON_KERNEL__ CONFIG_KSU=m CONFIG_KPM=n \
  -j1 kernelsu.o > "$PROJECT/evidence/root-object-build.log" 2>&1
rc=$?
set -e
printf '{"exit_code":%s,"module_linked":false,"loaded":false,"scope":"object_compile_only"}\n' "$rc" > "$PROJECT/evidence/root-object-result.json"
tail -15 "$PROJECT/evidence/root-object-build.log"
exit "$rc"
