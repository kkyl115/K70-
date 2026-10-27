#!/system/bin/sh
# B 阶段：解开 "内核 5.15.178 vs 模块 vermagic 5.15.78" 矛盾
# 只读，不修改任何系统状态
OUT=/sdcard/Download/vermeer-ultimate-kernel/evidence/kmi_$(date +%Y%m%d_%H%M%S)
mkdir -p "$OUT"
cd "$OUT" || exit 1

echo "== 输出目录: $OUT =="

echo ""
echo "===== 1 UTS_RELEASE（内核侧基准）====="
uname -r
echo "--- /proc/version ---"
cat /proc/version
echo "--- /sys/kernel/osrelease ---"
cat /sys/kernel/osrelease 2>&1
echo "--- /sys/kernel/version ---"
cat /sys/kernel/version 2>&1

echo ""
echo "===== 2 模块加载策略相关 config ====="
if [ -r /proc/config.gz ]; then
  zcat /proc/config.gz 2>/dev/null | grep -E "CONFIG_MODULE_SIG|CONFIG_MODULE_FORCE|CONFIG_MODVERSIONS|CONFIG_MODULE_UNLOAD|CONFIG_MODULE_COMPRESS|CONFIG_LOCALVERSION|CONFIG_MODULES|CONFIG_STAGING"
else
  echo "/proc/config.gz 不可读"
fi

echo ""
echo "===== 3 各分区实际挂载与模块目录 ====="
for p in /vendor/lib/modules /vendor_dlkm/lib/modules /system/lib/modules /system_dlkm/lib/modules; do
  printf "%-32s -> " "$p"
  readlink -f "$p" 2>&1
done
echo "--- mount（dlkm / vendor / system）---"
mount 2>/dev/null | grep -E "vendor_dlkm|system_dlkm|/vendor |/system " 

echo ""
echo "===== 4 模块数量 ====="
for d in /vendor_dlkm/lib/modules /system_dlkm/lib/modules; do
  n=$(ls "$d"/*.ko 2>/dev/null | wc -l)
  echo "$d : $n 个 .ko"
done

echo ""
echo "===== 5 vermagic 全量统计（关键）====="
STR=/data/data/com.termux/files/usr/bin/strings
if [ -x "$STR" ]; then
  echo "(使用 Termux strings)"
  GETVERM() { "$STR" -a "$1" 2>/dev/null | grep -m1 '^vermagic='; }
else
  echo "(strings 不可用，退回 grep -a)"
  GETVERM() { grep -a -m1 -o 'vermagic=[ -~]*' "$1" 2>/dev/null; }
fi

for d in /vendor_dlkm/lib/modules /system_dlkm/lib/modules; do
  echo "--- $d 的 vermagic 分布 ---"
  for f in "$d"/*.ko; do
    [ -f "$f" ] || continue
    v=$(GETVERM "$f")
    [ -z "$v" ] && v="NO_VERMAGIC_STRING"
    echo "$v"
  done | sort | uniq -c | sort -rn
done

echo ""
echo "===== 6 已加载模块数 vs 分区模块数 ====="
echo "--- /proc/modules 行数 ---"
wc -l < /proc/modules
echo "--- 已加载模块中带 vermagic 冲突迹象的（看 /proc/modules 是否有 - 标记）---"

echo ""
echo "===== 7 分区构建日期（判断 5.15.178 是否真属本 ROM）====="
for p in ro.build.date ro.build.date.utc ro.vendor.build.date ro.vendor_dlkm.build.date ro.system_dlkm.build.date ro.bootimage.build.date ro.vendor.build.fingerprint ro.vendor_dlkm.build.fingerprint ro.system_dlkm.build.fingerprint ro.bootimage.build.fingerprint ro.build.version.incremental ro.vendor.build.version.incremental; do
  printf "%-40s = " "$p"
  getprop "$p" 2>&1
done

echo ""
echo "===== 8 dmesg 相关（vermagic / module / kmi）====="
echo "--- dmesg_restrict ---"
cat /proc/sys/kernel/dmesg_restrict 2>&1
echo "--- 关键词检索 ---"
dmesg 2>&1 | grep -iE "vermagic|should be|module|kmi" | tail -40
echo "--- dmesg 首行（启动头）---"
dmesg 2>&1 | head -3

echo ""
echo "===== 9 已加载模块中，抽样比对分区文件大小是否一致 ====="
for m in kiwi_v2 camera msm_drm ipam goodix_core; do
  for d in /vendor_dlkm/lib/modules /system_dlkm/lib/modules; do
    f="$d/$m.ko"
    if [ -f "$f" ]; then
      printf "%-14s %-32s %s\n" "$m" "$d" "$(ls -l "$f" | awk '{print $5" bytes "$6" "$7" "$8}')"
    fi
  done
done

echo ""
echo "===== DONE: $OUT ====="
