#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# Vermeer Ultimate Kernel - 无 Root 证据采集器 (只读)
# 目标: Redmi K70 / vermeer / SM8550 / HyperOS 3.0.302.0.WNKCNXM
# 特性: 不申请 root, 不写任何设备分区, 不修改系统设置
# 用法: bash collect_evidence_noroot.sh [输出目录]
# ============================================================
set -u
OUT="${1:-/storage/emulated/0/Download/vermeer-ultimate-kernel/evidence/noroot_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT" || { echo "无法创建输出目录: $OUT"; exit 1; }

sec() { echo; echo "########## $* ##########"; }
run() { # run <输出文件名> <命令...>
  local f="$OUT/$1"; shift
  { echo "\$ $*"; "$@" 2>&1; echo "[exit=$?]"; } >> "$f"
}
note() { echo "-- $* --"; }

echo "输出目录: $OUT"
: > "$OUT/00_meta.txt"
{
  echo "采集时间: $(date -Iseconds)"
  echo "工具版本: collect_evidence_noroot.sh v1.0"
  echo "root 使用: 无 (全部为 app 权限可读)"
} >> "$OUT/00_meta.txt"

# ---------- 1. 设备与系统 ----------
sec "1. 设备与系统"
{
  echo "== 关键属性 =="
  for p in ro.product.model ro.product.device ro.product.name ro.build.version.release \
           ro.build.version.sdk ro.build.display.id ro.build.fingerprint ro.build.date \
           ro.boot.slot_suffix ro.boot.verifiedbootstate ro.boot.flash.locked \
           ro.boot.vbmeta.device_state ro.boot.veritymode ro.boot.hardware ro.boot.bootloader \
           ro.boot.hwc ro.board.platform ro.soc.model ro.product.cpu.abi \
           ro.config.low_ram ro.crypto.state ro.build.type ro.build.tags \
           ro.kernel.version ro.zygote persist.sys.timezone; do
    printf '%-32s = %s\n' "$p" "$(getprop "$p" 2>/dev/null)"
  done
  echo
  echo "== uname =="
  uname -a
  echo
  echo "== /proc/version =="
  cat /proc/version 2>&1
  echo
  echo "== 电池/温度 (可能不可读) =="
  dumpsys battery 2>&1 | head -20
} > "$OUT/01_device.txt" 2>&1

# ---------- 2. CPU 拓扑 ----------
sec "2. CPU 拓扑与调度器"
{
  echo "== online / possible =="
  echo "online:   $(cat /sys/devices/system/cpu/online 2>&1)"
  echo "possible: $(cat /sys/devices/system/cpu/possible 2>&1)"
  echo "present:  $(cat /sys/devices/system/cpu/present 2>&1)"
  echo
  for c in /sys/devices/system/cpu/cpu[0-9]*; do
    n=$(basename "$c")
    [ -d "$c/topology" ] || continue
    echo "== $n =="
    for f in physical_package_id core_id cluster_id core_cpus_list thread_siblings_list; do
      [ -r "$c/topology/$f" ] && printf '  %-22s %s\n' "$f" "$(cat "$c/topology/$f" 2>/dev/null)"
    done
    [ -r "$c/cpu_capacity" ] && printf '  %-22s %s\n' cpu_capacity "$(cat "$c/cpu_capacity")"
    # 用 cpuinfo_max_freq 反推核心类型
    for p in /sys/devices/system/cpu/cpufreq/*/; do
      [ -r "$p/related_cpus" ] || continue
      if grep -qw "${n#cpu}" "$p/related_cpus" 2>/dev/null; then
        printf '  %-22s %s\n' "cpufreq_policy" "$(basename "$p")"
        printf '  %-22s %s\n' "  cpuinfo_max_freq" "$(cat "$p/cpuinfo_max_freq" 2>/dev/null)"
        printf '  %-22s %s\n' "  cpuinfo_min_freq" "$(cat "$p/cpuinfo_min_freq" 2>/dev/null)"
        printf '  %-22s %s\n' "  scaling_governor" "$(cat "$p/scaling_governor" 2>/dev/null)"
        printf '  %-22s %s\n' "  scaling_available_gov" "$(cat "$p/scaling_available_governors" 2>/dev/null)"
      fi
    done
  done
  echo
  echo "== 所有 cpufreq policy =="
  for p in /sys/devices/system/cpu/cpufreq/policy*; do
    echo "--- $(basename "$p") ---"
    echo "related_cpus     : $(cat "$p/related_cpus" 2>&1)"
    echo "affected_cpus    : $(cat "$p/affected_cpus" 2>&1)"
    echo "max_freq         : $(cat "$p/cpuinfo_max_freq" 2>&1)"
    echo "min_freq         : $(cat "$p/cpuinfo_min_freq" 2>&1)"
    echo "governor         : $(cat "$p/scaling_governor" 2>&1)"
    echo "available_gov    : $(cat "$p/scaling_available_governors" 2>&1)"
    echo "available_freq_n : $(cat "$p/scaling_available_frequencies" 2>/dev/null | wc -w)"
    echo "cur_freq         : $(cat "$p/scaling_cur_freq" 2>&1)"
  done
  echo
  echo "== uclamp (内核 5.15 若启用) =="
  for c in 0 3 7; do
    [ -d "/sys/devices/system/cpu/cpu$c/uclamp" ] && {
      echo "cpu$c:"; ls "/sys/devices/system/cpu/cpu$c/uclamp" 2>&1 | tr '\n' ' '; echo
      for f in "/sys/devices/system/cpu/cpu$c"/uclamp/*; do
        printf '  %-24s %s\n' "$(basename "$f")" "$(cat "$f" 2>/dev/null)"
      done
    }
  done
  echo
  echo "== sched 特性开关 =="
  for f in /sys/kernel/debug/sched/features /proc/sys/kernel/sched_* ; do
    [ -r "$f" ] && { printf '%-46s %s\n' "$f" "$(head -c 200 "$f" 2>/dev/null | tr '\n' ' ')"; }
  done
  echo
  echo "== 是否 WALT (高通专属) =="
  grep -l . /sys/kernel/walt/* 2>/dev/null | head -5
  ls /sys/kernel/walt 2>&1 | head -10
} > "$OUT/02_cpu_topology.txt" 2>&1

# ---------- 3. 内存管理 ----------
sec "3. 内存管理 (MGLRU / PSI / ZRAM)"
{
  echo "== meminfo =="
  head -30 /proc/meminfo 2>&1
  echo
  echo "== MGLRU =="
  if [ -e /sys/kernel/mm/lru_gen/enabled ]; then
    echo "存在: enabled=$(cat /sys/kernel/mm/lru_gen/enabled 2>&1)"
    cat /sys/kernel/mm/lru_gen/min_ttl_ms 2>&1
  else
    echo "不存在 /sys/kernel/mm/lru_gen/enabled  → 该内核未启用 MGLRU"
  fi
  echo
  echo "== PSI =="
  for f in /proc/pressure/cpu /proc/pressure/io /proc/pressure/memory; do
    [ -r "$f" ] && { echo "--- $f ---"; cat "$f"; } || echo "$f 不可读/不存在"
  done
  echo
  echo "== ZRAM =="
  cat /proc/swaps 2>&1
  for z in /sys/block/zram*; do
    [ -d "$z" ] || continue
    echo "--- $z ---"
    for f in disksize comp_algorithm compression_algorithm mem_used mem_limit \
             backing_dev writeback max_comp_streams; do
      [ -r "$z/$f" ] && printf '  %-22s %s\n' "$f" "$(cat "$z/$f" 2>/dev/null)"
    done
  done
  echo
  echo "== zram 可用压缩算法 =="
  for f in /sys/block/zram0/comp_algorithm /sys/block/zram0/compression_algorithm; do
    [ -r "$f" ] && { echo "$f: $(cat "$f")"; }
  done
  echo
  echo "== LMKD 现状 =="
  getprop | grep -iE 'lmkd|lowmem|zram|swap' 2>/dev/null | head -20
  cat /sys/module/lowmemorykiller/parameters/* 2>/dev/null | head -10
} > "$OUT/03_memory.txt" 2>&1

# ---------- 4. 温控 / 功耗 ----------
sec "4. 温控与电源"
{
  echo "== thermal zones =="
  for t in /sys/class/thermal/thermal_zone*; do
    [ -d "$t" ] || continue
    printf '%-40s type=%-22s temp=%s\n' "$(basename "$t")" \
      "$(cat "$t/type" 2>/dev/null)" "$(cat "$t/temp" 2>/dev/null)"
  done
  echo
  echo "== cooling devices (前20) =="
  for c in /sys/class/thermal/cooling_device*; do
    [ -d "$c" ] || continue
    printf '%-28s type=%-24s cur=%s max=%s\n' "$(basename "$c")" \
      "$(cat "$c/type" 2>/dev/null)" "$(cat "$c/cur_state" 2>/dev/null)" "$(cat "$c/max_state" 2>/dev/null)"
  done | head -20
} > "$OUT/04_thermal.txt" 2>&1

# ---------- 5. 块设备 / 文件系统 ----------
sec "5. 块设备与文件系统"
{
  echo "== /proc/partitions =="
  cat /proc/partitions 2>&1 | head -40
  echo
  echo "== /sys/block 队列调度器 =="
  for b in /sys/block/*; do
    d=$(basename "$b")
    [ -r "$b/queue/scheduler" ] && printf '%-14s %s\n' "$d" "$(cat "$b/queue/scheduler")"
  done
  echo
  echo "== mount (关键) =="
  grep -E ' /(data|system|vendor|metadata|super)? | /data | /metadata | /cache ' /proc/mounts 2>&1
  echo
  echo "== 分区挂载 ro/rw 概览 =="
  awk '{print $1, $2, $4}' /proc/mounts 2>&1 | head -40
} > "$OUT/05_storage.txt" 2>&1

# ---------- 6. 内核安全与 ABI 可读部分 ----------
sec "6. 安全状态"
{
  echo "== boot state =="
  for p in ro.boot.verifiedbootstate ro.boot.flash.locked ro.boot.vbmeta.device_state \
           ro.boot.veritymode ro.boot.warranty_bit ro.boot.secureboot; do
    printf '%-34s = %s\n' "$p" "$(getprop "$p")"
  done
  echo
  echo "== 内核锁定 =="
  cat /sys/kernel/security/lockdown 2>&1
  echo
  echo "== SELinux =="
  getprop ro.boot.selinux
  getprop ro.build.selinux
  cat /sys/fs/selinux/enforce 2>&1
  echo
  echo "== 当前身份 =="
  id
} > "$OUT/06_security.txt" 2>&1

# ---------- 7. 与 root 有关的事实核查 ----------
sec "7. Root 可用性事实核查"
{
  echo "== su 候选路径 =="
  for p in /debug_ramdisk/su /sbin/su /system/sbin/su /system/bin/su /system/xbin/su \
           /su/bin/su /data/adb/ksu/bin/su /data/adb/magisk/su; do
    [ -e "$p" ] && echo "EXIST $p" || echo "MISS  $p"
  done
  echo
  echo "== PATH 里的 su =="
  command -v su 2>&1
  echo "(termux-tools 的占位脚本不算真 su)"
  echo
  echo "== 需要 root 的接口是否可读 =="
  for f in /proc/config.gz /proc/modules /proc/cmdline /proc/kallsyms /data/adb; do
    if [ -r "$f" ]; then echo "可读   $f"; else echo "拒读   $f"; fi
  done
  echo
  echo "== 内核模块目录 =="
  ls /sys/module 2>&1 | tr '\n' ' '; echo
  ls -d /sys/module/*ksu* /sys/module/*kernelsu* 2>&1
} > "$OUT/07_root_facts.txt" 2>&1

# ---------- 8. BootGuard 备份基线核验 ----------
sec "8. BootGuard A 槽备份核验 (只读)"
BK=/storage/emulated/0/Download/BootGuard/A_backup_20261027_124239
{
  if [ -d "$BK" ]; then
    echo "备份目录存在: $BK"
    ls -l "$BK"
    echo
    echo "== 实测 SHA-256 =="
    ( cd "$BK" && sha256sum *.img )
    echo
    echo "== 与任务书基线比对 =="
    declare -A EXP=(
      [boot_a.img]=5b030bc2a740166fa9c34daa851f5174199067332675abe200245fe11473a95e
      [init_boot_a.img]=e70351d22243ce995bec0fc755dc8e2c63cb161f0dcb16bd11366f6937ca9e7a
      [vendor_boot_a.img]=45320eae7815fa043f0e4034cd4ae33cf423ed8d546a7815ff439c7a7b86a040
      [dtbo_a.img]=aac33c81251f8789a32eb4330067b86bc5853b58c1101ca9a7699041178232df
      [vbmeta_a.img]=403175daae8c10b1e2c2ec40f83980480edafd2c9a84a9cc28f9170ce7cbe1a9
    )
    rc=0
    for k in boot_a.img init_boot_a.img vendor_boot_a.img dtbo_a.img vbmeta_a.img; do
      if [ -f "$BK/$k" ]; then
        got=$(sha256sum "$BK/$k" | cut -d' ' -f1)
        if [ "$got" = "${EXP[$k]}" ]; then echo "PASS $k"; else echo "FAIL $k got=$got"; rc=1; fi
      else
        echo "MISSING $k"; rc=1
      fi
    done
    echo "RESULT=$([ $rc -eq 0 ] && echo ALL_PASS || echo MISMATCH)"
  else
    echo "备份目录不存在: $BK"
    echo "RESULT=NO_BACKUP"
  fi
} > "$OUT/08_bootguard_baseline.txt" 2>&1

# ---------- 汇总 ----------
sec "9. 汇总"
{
  echo "采集完成: $(date -Iseconds)"
  echo "输出文件:"
  ls -l "$OUT" | awk 'NR>1{printf "  %-28s %8s\n", $9, $5}'
} | tee "$OUT/00_meta.txt" -a

echo
echo "全部证据已写入: $OUT"
echo "提示: 若 07_root_facts.txt 显示 /proc/config.gz、/proc/modules 均拒读，"
echo "      则内核 config / ABI / 模块 CRC 无法核验，后续补丁决策缺少依据。"
