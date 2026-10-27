#!/system/bin/sh
# ============================================================
# Vermeer Ultimate Kernel - Root 证据采集器
# 用途: 在【SukiSU Ultra 管理器自带的 root 终端】里运行
#       (Termux 拿不到 su 时用这条路径)
#
# 用法:
#   sh /sdcard/Download/vermeer-ultimate-kernel/scripts/collect_evidence_root.sh
#
# 安全: 全程只读。不写分区、不刷机、不切槽、不改系统属性。
#       输出仅写到 /sdcard/Download/vermeer-ultimate-kernel/evidence/root_<时间戳>/
# ============================================================
set -u
TS=$(date +%Y%m%d_%H%M%S)
OUT="/sdcard/Download/vermeer-ultimate-kernel/evidence/root_${TS}"
mkdir -p "$OUT" 2>/dev/null

# --- 必须有 root ---
if [ "$(id -u)" != "0" ]; then
  echo "!! 当前不是 root (uid=$(id -u))。"
  echo "!! 请在 SukiSU Ultra 管理器的终端里执行本脚本，或先 su。"
  exit 1
fi
echo "== root 已确认: $(id) =="
echo "== 输出: $OUT =="

# ---------- 0. identity ----------
{
  echo "采集时间: $(date -Iseconds)"
  echo "id: $(id)"
  echo "uname: $(uname -a)"
  echo "cmdline: $(cat /proc/cmdline 2>&1)"
  echo "selinux: $(getenforce 2>/dev/null || cat /sys/fs/selinux/enforce 2>&1)"
  echo "ksu props:"
  getprop | grep -iE 'ksu|sukisu|kernel_?su' 2>/dev/null
} > "$OUT/10_identity.txt" 2>&1

# ---------- 1. root 相关全部路径与状态 ----------
{
  echo "== su 路径 =="
  for p in /debug_ramdisk/su /sbin/su /system/bin/su /system/xbin/su /data/adb/ksu/bin/su \
           /data/adb/ksu/bin/ksud /data/adb/magisk/su /data/adb/ap/bin/su; do
    if [ -e "$p" ]; then ls -lZ "$p" 2>/dev/null || ls -l "$p"; else echo "MISS $p"; fi
  done
  echo
  echo "== /data/adb 内容 =="
  ls -laZ /data/adb 2>&1
  echo
  echo "== ksu 目录 =="
  ls -laR /data/adb/ksu 2>/dev/null | head -60
  echo
  echo "== 已加载模块 (kernelsu) =="
  grep -iE 'kernelsu|ksu' /proc/modules 2>&1
  echo "总模块数: $(wc -l < /proc/modules 2>/dev/null)"
  echo
  echo "== /sys/module =="
  ls /sys/module 2>&1 | tr '\n' ' '; echo
  ls -d /sys/module/*ksu* /sys/module/*kernel* 2>&1
} > "$OUT/11_root_state.txt" 2>&1

# ---------- 2. 内核 config ----------
{
  if [ -r /proc/config.gz ]; then
    zcat /proc/config.gz > "$OUT/kernel_config.txt" 2>/dev/null || \
      cat /proc/config.gz > "$OUT/kernel_config.gz"
    echo "已导出 /proc/config.gz"
    echo
    echo "== 关键项 =="
    zcat /proc/config.gz 2>/dev/null | grep -E 'MGLRU|LRU_GEN|PSI|ZRAM|LZ4|ZSTD|KSU|KPM|BBR|F2FS|CFI|KCFI|MODVERSIONS|MODULE_SIG|LOCALVERSION|IKHEADERS|UCLAMP|SCHED_WALT|ENERGY_MODEL|DEBUG_FS' 
  else
    echo "!! /proc/config.gz 不可读"
    for alt in /boot/config-$(uname -r) /system/lib/modules/$(uname -r)/config; do
      [ -r "$alt" ] && echo "备选可用: $alt"
    done
  fi
} > "$OUT/12_kernel_config_summary.txt" 2>&1
[ -r /proc/config.gz ] && zcat /proc/config.gz > "$OUT/kernel_config.txt" 2>/dev/null

# ---------- 3. KMI / 模块 CRC 证据 ----------
{
  echo "== 内核版本串 (vermagic 基准) =="
  cat /proc/version
  echo
  echo "== 已加载模块 (含 vermagic 相关) =="
  head -40 /proc/modules
  echo "... 总行数: $(wc -l < /proc/modules)"
  echo
  echo "== 模块目录与 vermagic =="
  for d in /vendor/lib/modules /system/lib/modules /lib/modules; do
    [ -d "$d" ] && { echo "--- $d ---"; ls -l "$d" | head -20; }
  done
  echo
  echo "== 抽取若干厂商模块的 vermagic / __versions CRC =="
  MOD=$(ls /vendor/lib/modules/*.ko 2>/dev/null | head -3)
  for m in $MOD; do
    echo "--- $m ---"
    strings "$m" 2>/dev/null | grep -m3 -E '^5\.15\.|vermagic|android13'
  done
  echo
  echo "== kallsyms 导出符号抽样 (KMI 相关) =="
  for s in ksu_is_safe_mode susfs_enable sched_setaffinity __traceiter_sched_switch \
           register_kprobe kallsyms_lookup_name task_struct; do
    grep -m1 " $s\$" /proc/kallsyms 2>/dev/null || echo "not exported: $s"
  done
} > "$OUT/13_kmi_modules.txt" 2>&1

# ---------- 4. 内存/ZRAM/调度 (root 才能读全) ----------
{
  echo "== swaps =="
  cat /proc/swaps 2>&1
  echo
  echo "== zram0 =="
  for f in disksize comp_algorithm compression_algorithm mem_used mem_limit backing_dev \
           writeback max_comp_streams; do
    [ -r /sys/block/zram0/$f ] && printf '  %-24s %s\n' "$f" "$(cat /sys/block/zram0/$f)"
  done
  echo
  echo "== MGLRU =="
  if [ -e /sys/kernel/mm/lru_gen/enabled ]; then
    echo "enabled=$(cat /sys/kernel/mm/lru_gen/enabled)"
    cat /sys/kernel/mm/lru_gen/min_ttl_ms 2>/dev/null
  else echo "未启用"; fi
  echo
  echo "== PSI =="
  for f in /proc/pressure/cpu /proc/pressure/io /proc/pressure/memory; do
    [ -r "$f" ] && { echo "--- $f ---"; cat "$f"; }
  done
  echo
  echo "== uclamp (0/3/7) =="
  for c in 0 3 7; do
    [ -d /sys/devices/system/cpu/cpu$c/uclamp ] && {
      echo "--- cpu$c ---"
      for f in /sys/devices/system/cpu/cpu$c/uclamp/*; do
        printf '  %-26s %s\n' "$(basename $f)" "$(cat $f 2>/dev/null)"
      done
    }
  done
  echo
  echo "== sched 调参接口 =="
  for f in /proc/sys/kernel/sched_migration_cost_ns /proc/sys/kernel/sched_wakeup_granularity_ns \
           /proc/sys/kernel/sched_min_granularity_ns /proc/sys/kernel/sched_latency_ns \
           /proc/sys/kernel/sched_autogroup_enabled /proc/sys/kernel/sched_util_clamp_min \
           /proc/sys/kernel/sched_util_clamp_max; do
    [ -r "$f" ] && printf '  %-52s %s\n' "$f" "$(cat $f)"
  done
  [ -r /sys/kernel/debug/sched/features ] && echo "sched features: $(cat /sys/kernel/debug/sched/features)"
  echo
  echo "== WALT 接口 =="
  ls /sys/kernel/walt 2>&1 | head -20
} > "$OUT/14_mem_sched.txt" 2>&1

# ---------- 5. 分区与槽位 (只读) ----------
{
  echo "== by-name 分区 =="
  ls -l /dev/block/by-name 2>&1 | head -60
  echo
  echo "== 槽位属性 =="
  for p in ro.boot.slot_suffix ro.boot.verifiedbootstate ro.boot.vbmeta.device_state ro.boot.veritymode; do
    printf '%-34s = %s\n' "$p" "$(getprop $p)"
  done
  echo
  echo "== 各 boot 类分区容量 =="
  for n in boot_a boot_b init_boot_a init_boot_b vendor_boot_a vendor_boot_b dtbo_a dtbo_b vbmeta_a vbmeta_b; do
    d=/dev/block/by-name/$n
    [ -e "$d" ] && printf '%-16s %s bytes\n' "$n" "$(blockdev --getsize64 "$d" 2>/dev/null || echo '?')"
  done
  echo
  echo "== 线上镜像 vs 备份哈希 (只读 dump 前 N MB) =="
  BK=/sdcard/Download/BootGuard/A_backup_20261027_124239
  for n in boot_a init_boot_a vendor_boot_a dtbo_a vbmeta_a; do
    src=/dev/block/by-name/$n; ref=$BK/${n}.img
    if [ -e "$src" ] && [ -f "$ref" ]; then
      sz=$(blockdev --getsize64 "$src" 2>/dev/null)
      refsz=$(stat -c %s "$ref" 2>/dev/null)
      echo "$n: 线上=${sz}B 备份=${refsz}B"
      if [ "$sz" = "$refsz" ]; then
        live=$(sha256sum "$src" 2>/dev/null | cut -d' ' -f1)
        echo "   live_sha256=$live"
        grep "^$live" "$BK/SHA256SUMS" >/dev/null 2>&1 && echo "   → 与备份记录一致" || echo "   → 与备份记录不一致(需人工确认是否预期)"
      fi
    fi
  done
} > "$OUT/15_partitions.txt" 2>&1

# ---------- 6. 备份输出到 sdcard ----------
chmod -R 777 "$OUT" 2>/dev/null
sync
echo
echo "===== 采集完成 ====="
ls -l "$OUT"
echo
echo "把下面这一行发给 AI 即可:"
echo "root 证据已生成: $OUT"
