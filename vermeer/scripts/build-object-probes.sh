#!/usr/bin/env bash
# Object compilation only; no .ko installation or claim of ABI compatibility.
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
WORK=${VERMEER_WORK:-$HOME/vermeer-build}
SOURCE=$WORK/common
OUT=$WORK/out-object-probes
export PATH="$WORK/toolchains/clang-r450784e/bin:$PATH"
test "$(git -C "$SOURCE" rev-parse HEAD)" = 6f2f96be86b93de6ed58a2c46b456fb49734c382
mkdir -p "$OUT" "$WORK/vas-probe" "$WORK/ntsync-probe/include/uapi/linux"
cp "$WORK/out-baseline/.config" "$OUT/.config"
make -C "$SOURCE" O="$OUT" ARCH=arm64 LLVM=1 KCFLAGS=-D__ANDROID_COMMON_KERNEL__ -j1 modules_prepare > "$PROJECT/evidence/object-probes-prepare.log" 2>&1
cp "$PROJECT/patches/scheduler-vas/vas_core.c" "$PROJECT/patches/scheduler-vas/vas_core.h" "$PROJECT/patches/scheduler-vas/vas_probe.c" "$PROJECT/patches/scheduler-vas/Makefile" "$WORK/vas-probe/"
set +e
make -C "$SOURCE" O="$OUT" M="$WORK/vas-probe" ARCH=arm64 LLVM=1 KCFLAGS=-D__ANDROID_COMMON_KERNEL__ -j1 vas_core.o vas_probe.o > "$PROJECT/evidence/vas-kernel-object-build.log" 2>&1
VAS_RC=$?
set -e
NTSYNC=$PROJECT/evidence/upstream-research/candidates/ntsync
cp "$NTSYNC/drivers/misc/ntsync.c" "$WORK/ntsync-probe/"
cp "$NTSYNC/include/uapi/linux/ntsync.h" "$WORK/ntsync-probe/include/uapi/linux/"
printf '%s\n' 'obj-m += ntsync.o' 'ccflags-y += -I$(src)/include' > "$WORK/ntsync-probe/Makefile"
set +e
make -C "$SOURCE" O="$OUT" M="$WORK/ntsync-probe" ARCH=arm64 LLVM=1 KCFLAGS=-D__ANDROID_COMMON_KERNEL__ -j1 ntsync.o > "$PROJECT/evidence/ntsync-kernel-object-build.log" 2>&1
NT_RC=$?
gcc -std=c11 -Wall -Wextra -Werror -fanalyzer -fsyntax-only "$PROJECT/patches/scheduler-vas/vas_core.c" > "$PROJECT/evidence/vas-static-analysis.log" 2>&1
STATIC_RC=$?
set -e
python3 - "$PROJECT" "$VAS_RC" "$NT_RC" "$STATIC_RC" <<'PY'
import json,sys
from pathlib import Path
project=Path(sys.argv[1])
result={'vas_kernel_object_exit':int(sys.argv[2]),'ntsync_unmodified_v6_14_object_exit':int(sys.argv[3]),'vas_host_static_analysis_exit':int(sys.argv[4]),'scope':'compile_only_no_module_link_no_runtime','abi_verified':False,'device_tested':False}
(project/'evidence/object-probes-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
PY
test "$VAS_RC" -eq 0 && test "$NT_RC" -eq 0 && test "$STATIC_RC" -eq 0
