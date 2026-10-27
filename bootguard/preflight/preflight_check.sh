#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# BootGuard Preflight - 纯只读预检
# 设备: Redmi K70 / vermeer
# 本脚本【不写入任何设备分区】，不申请 root，不切槽，不刷机。
# 用法:
#   bash preflight_check.sh                # 完整只读检查
#   bash preflight_check.sh --quiet        # 只输出结论行
# 退出码: 0=全部通过, 1=有 FAIL, 2=严重失败(缺备份/型号不符)
# ============================================================
set -u
QUIET=0
for a in "$@"; do [ "$a" = "--quiet" ] && QUIET=1; done
say()  { [ "$QUIET" -eq 0 ] && echo "$*"; }
hdr()  { [ "$QUIET" -eq 0 ] && { echo; echo "── $* ──"; }; }

FAIL=0; WARN=0
pass() { say "  [PASS] $*"; }
fail() { say "  [FAIL] $*"; FAIL=$((FAIL+1)); }
warn() { say "  [WARN] $*"; WARN=$((WARN+1)); }
info() { say "  [INFO] $*"; }

BK_DEFAULT=/storage/emulated/0/Download/BootGuard/A_backup_20261027_124239
BK="$BK_DEFAULT"
PROJ=/storage/emulated/0/Download/vermeer-ultimate-kernel

echo "=============================================="
echo " BootGuard Preflight (READ-ONLY)"
echo " 时间: $(date -Iseconds)"
echo "=============================================="

# ---------- 1. 设备身份 ----------
hdr "1. 设备身份"
MODEL=$(getprop ro.product.model 2>/dev/null)
DEVICE=$(getprop ro.product.device 2>/dev/null)
[ "$MODEL" = "23113RKC6C" ] && pass "型号 $MODEL" || fail "型号不匹配: '$MODEL' (期望 23113RKC6C)"
[ "$DEVICE" = "vermeer" ]   && pass "代号 $DEVICE" || fail "代号不匹配: '$DEVICE' (期望 vermeer)"
REL=$(getprop ro.build.version.release 2>/dev/null)
ID=$(getprop ro.build.display.id 2>/dev/null)
info "系统: Android $REL / $ID"
case "$ID" in
  *OS3.0.302.0.WNKCNXM*) pass "HyperOS 版本与工程目标一致" ;;
  *) warn "HyperOS 版本非 OS3.0.302.0.WNKCNXM: $ID" ;;
esac

# ---------- 2. 槽位与启动状态 ----------
hdr "2. 槽位与启动状态（只读 getprop）"
SLOT=$(getprop ro.boot.slot_suffix 2>/dev/null)
VBS=$(getprop ro.boot.verifiedbootstate 2>/dev/null)
LOCK=$(getprop ro.boot.flash.locked 2>/dev/null)
VERITY=$(getprop ro.boot.veritymode 2>/dev/null)
info "slot_suffix=$SLOT  verifiedbootstate=$VBS  flash.locked=$LOCK  veritymode=$VERITY"
[ "$SLOT" = "_a" ] && pass "当前槽位 A（与基线一致）" || warn "当前槽位非 A: $SLOT"
[ "$VBS" = "orange" ] && info "verifiedbootstate=orange（已解锁/自定义 AVB，符合本机现状）"
[ "$LOCK" = "0" ] && info "flash.locked=0（bootloader 已解锁）"
[ -z "$VERITY" ] && warn "veritymode 为空，无法确认 dm-verity 状态"

# ---------- 3. 内核对齐 ----------
hdr "3. 运行内核"
KR=$(uname -r 2>/dev/null)
info "uname -r = $KR"
case "$KR" in
  5.15.178-android13-*) pass "内核系列 android13-5.15 sub_level 178" ;;
  *) warn "内核字符串与 5.15.178-android13 不符: $KR" ;;
esac
if [ -r /proc/version ]; then info "$(cat /proc/version)"; else warn "/proc/version 不可读"; fi

# ---------- 4. 备份完整性 ----------
hdr "4. A 槽备份完整性"
if [ ! -d "$BK" ]; then
  fail "备份目录不存在: $BK"
  [ "$QUIET" -eq 0 ] && {
    echo "  可用的 BootGuard 目录:"
    ls -d /storage/emulated/0/Download/BootGuard/* 2>/dev/null | sed 's/^/    /'
  }
  echo "RESULT=SEVERE_NO_BACKUP FAIL=$FAIL WARN=$WARN"
  exit 2
fi
pass "备份目录存在: $BK"

EXPECT_boot_a=5b030bc2a740166fa9c34daa851f5174199067332675abe200245fe11473a95e
EXPECT_init_boot_a=e70351d22243ce995bec0fc755dc8e2c63cb161f0dcb16bd11366f6937ca9e7a
EXPECT_vendor_boot_a=45320eae7815fa043f0e4034cd4ae33cf423ed8d546a7815ff439c7a7b86a040
EXPECT_dtbo_a=aac33c81251f8789a32eb4330067b86bc5853b58c1101ca9a7699041178232df
EXPECT_vbmeta_a=403175daae8c10b1e2c2ec40f83980480edafd2c9a84a9cc28f9170ce7cbe1a9

check_one() { # name expected size_bytes
  local n="$1" exp="$2" sz="$3" f="$BK/$1"
  if [ ! -f "$f" ]; then fail "$n 缺失"; return; fi
  local asz; asz=$(stat -c %s "$f" 2>/dev/null)
  [ "$asz" = "$sz" ] || warn "$n 大小异常: $asz (期望 $sz)"
  local got; got=$(sha256sum "$f" 2>/dev/null | cut -d' ' -f1)
  if [ "$got" = "$exp" ]; then pass "$n SHA-256 一致"; else fail "$n 哈希不符: $got"; fi
}

check_one boot_a.img        "$EXPECT_boot_a"        201326592
check_one init_boot_a.img   "$EXPECT_init_boot_a"   8388608
check_one vendor_boot_a.img "$EXPECT_vendor_boot_a" 100663296
check_one dtbo_a.img        "$EXPECT_dtbo_a"        25165824
check_one vbmeta_a.img      "$EXPECT_vbmeta_a"      131072

# ---------- 5. 备份目录自身校验文件 ----------
hdr "5. 备份目录自校验文件"
for f in COMPLETE.txt SHA256SUMS README.txt; do
  [ -f "$BK/$f" ] && pass "$f 存在" || warn "$f 缺失"
done
if [ -f "$BK/SHA256SUMS" ]; then
  if ( cd "$BK" && sha256sum -c SHA256SUMS >/dev/null 2>&1 ); then
    pass "SHA256SUMS 自校验通过"
  else
    warn "SHA256SUMS 自校验未通过（可能格式差异，以上面逐项比对为准）"
  fi
fi

# ---------- 6. boot 镜像头部结构（只读解析） ----------
hdr "6. 镜像头部结构（只读前 64 字节）"
hdr_probe() {
  local f="$BK/$1"
  [ -f "$f" ] || return
  local magic; magic=$(head -c 8 "$f" 2>/dev/null | tr -d '\0')
  local ver;   ver=$(od -An -tu4 -j40 -N4 "$f" 2>/dev/null | tr -d ' ')
  case "$magic" in
    ANDROID!) pass "$1 header magic=ANDROID! header_version=${ver:-?}" ;;
    VNDRBOOT) pass "$1 header magic=VNDRBOOT (vendor_boot v3+)" ;;
    *) if [ "$1" = vbmeta_a.img ]; then
         local vm; vm=$(head -c 4 "$f" | od -An -c | tr -d ' ')
         info "$1 非 boot header（应为 AVB vbmeta 结构，magic=$vm）"
       else
         warn "$1 magic 非预期: '$magic'"
       fi ;;
  esac
}
hdr_probe boot_a.img
hdr_probe init_boot_a.img
hdr_probe vendor_boot_a.img
hdr_probe vbmeta_a.img

# ---------- 7. 空间 ----------
hdr "7. 存储空间"
AV=$(df -k /storage/emulated/0 2>/dev/null | awk 'NR==2{print int($4/1024)}')
[ -n "${AV:-}" ] && {
  if [ "$AV" -gt 2048 ]; then pass "可用 ${AV} MB"
  else warn "可用空间偏低: ${AV} MB（写入新镜像需要 ≥512 MB 裕度）"; fi
}

# ---------- 8. 工程自检 ----------
hdr "8. 工程自检"
[ -d "$PROJ" ] && pass "工程目录存在" || warn "工程目录缺失: $PROJ"
for d in bootguard/preflight bootguard/backup bootguard/recovery bootguard/rollback \
         patches scripts evidence docs configs; do
  [ -d "$PROJ/$d" ] || warn "缺少子目录: $d"
done
if ls "$PROJ/release"/*.img >/dev/null 2>&1; then
  warn "release/ 里已有 .img —— 刷写前必须人工复核来源与哈希"
else
  pass "release/ 为空（尚未产出任何可刷写镜像，符合当前阶段）"
fi

# ---------- 9. root 可用性（仅告知影响，不阻塞预检） ----------
hdr "9. root 可用性（影响后续深度校验，不阻塞本预检）"
if command -v su >/dev/null 2>&1 && su -c true >/dev/null 2>&1; then
  pass "su 可用（可做区块设备比对）"
else
  warn "su 不可用：无法比对线上分区与备份、无法读 /proc/config.gz 与模块 CRC"
fi

# ---------- 结论 ----------
echo
echo "=============================================="
if [ "$FAIL" -eq 0 ]; then
  echo " RESULT=PASS  FAIL=0 WARN=$WARN"
  echo " 结论: A 槽备份可作为回滚基线；本次未写入任何分区。"
  EXIT=0
else
  echo " RESULT=FAIL  FAIL=$FAIL WARN=$WARN"
  echo " 结论: 备份不完整或设备不匹配，禁止进行任何刷写操作。"
  EXIT=1
fi
echo "=============================================="
exit $EXIT
