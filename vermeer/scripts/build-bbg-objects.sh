#!/usr/bin/env bash
# BBG source/API experiment only. Never registers an LSM or alters a phone.
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
WORK=${VERMEER_WORK:-$HOME/vermeer-build}
OUT=$WORK/out-object-probes
STAGE=$WORK/bbg-object-probe
test -f "$OUT/security/selinux/flask.h" || { echo 'Run build-root-object.sh to prepare SELinux first'; exit 2; }
python3 - "$PROJECT" "$STAGE" <<'PY'
from pathlib import Path
import json,hashlib,shutil,difflib,sys
project,dest=map(Path,sys.argv[1:])
source=project/'evidence/upstream-research/candidates/bbg'
lock=json.loads((source.parent/'lock.json').read_text())['bbg']
assert lock['commit']=='028ff7fd509e2104596da7cc1ef8e6ce2a0c9082'
if dest.exists(): raise SystemExit('BBG probe destination already exists; refusing overwrite')
for name in lock['files']:
    p=source/name
    provenance=json.loads(p.with_name(p.name+'.provenance.json').read_text())
    assert hashlib.sha256(p.read_bytes()).hexdigest()==provenance['sha256']
    out=dest/name; out.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,out)
p=dest/'Makefile'; original=p.read_text()
start=original.index('GIT_BIN :='); end=original.index('ifeq ($(shell grep -q "file_ioctl_compat"',start)
changed=original[:start]+'REPO_LINK := https://github.com/vc-teahouse/Baseband-guard\nCOMMIT_SHA := 028ff7fd\n\n'+original[end:]
p.write_text(changed)
patch=project/'patches/security/bbg/0001-offline-version.patch'; patch.parent.mkdir(parents=True,exist_ok=True)
patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/Makefile',tofile='b/Makefile')))
PY
export PATH="$WORK/toolchains/clang-r450784e/bin:$PATH"
LSMS=$(sed -n 's/^CONFIG_LSM="\(.*\)"/\1/p' "$OUT/.config")
test -n "$LSMS"
set +e
make -C "$WORK/common" O="$OUT" M="$STAGE" ARCH=arm64 LLVM=1 \
  KCFLAGS=-D__ANDROID_COMMON_KERNEL__ CONFIG_BBG=y "CONFIG_LSM=$LSMS,baseband_guard" \
  -j1 baseband_guard.o tracing/tracing.o blkdev_helper.o > "$PROJECT/evidence/bbg-object-build.log" 2>&1
rc=$?
set -e
printf '{"exit_code":%s,"scope":"objects_only_command_line_config","lsm_registered":false,"device_tested":false}\n' "$rc" > "$PROJECT/evidence/bbg-object-result.json"
tail -15 "$PROJECT/evidence/bbg-object-build.log"
exit "$rc"
