#!/system/bin/sh
# A 阶段：MGLRU 零编译可逆实验（基线 -> 开启 -> 60s/120s 采样）
# 回滚：echo 0 > /sys/kernel/mm/lru_gen/enabled
OUT=/sdcard/Download/vermeer-ultimate-kernel/evidence/mglru_$(date +%Y%m%d_%H%M%S)
mkdir -p "$OUT"

snap() {
  tag=$1
  f="$OUT/$tag.txt"
  {
    echo "===== $tag @ $(date '+%F %T') ====="
    echo "-- lru_gen/enabled --"
    cat /sys/kernel/mm/lru_gen/enabled 2>&1
    echo "-- lru_gen/min_ttl_ms --"
    cat /sys/kernel/mm/lru_gen/min_ttl_ms 2>&1
    echo "-- PSI --"
    for p in cpu io memory; do
      echo "[$p]"
      cat /proc/pressure/$p 2>&1
    done
    echo "-- meminfo --"
    grep -E "^(MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree|AnonPages|Active\(anon\)|Inactive\(anon\)|Active\(file\)|Inactive\(file\)|Unevictable|Mlocked|KReclaimable)" /proc/meminfo
    echo "-- vmstat --"
    grep -E "^(pgscan|pgsteal|pgrefill|pgreuse|pgmajfault|workingset_refault|workingset_activate|pgdemote|thp_fault_alloc|thp_fault_fallback|nr_free_pages|nr_inactive_anon|nr_active_anon|nr_inactive_file|nr_active_file)" /proc/vmstat
    echo "-- zram mm_stat --"
    cat /sys/block/zram0/mm_stat 2>&1
    echo "-- loadavg --"
    cat /proc/loadavg 2>&1
    echo "-- uptime --"
    uptime 2>&1
    echo ""
  } > "$f"
}

echo "== 输出目录: $OUT =="
echo "== 基线快照 =="
snap A0_baseline

echo "== 写入 0x0007 -> /sys/kernel/mm/lru_gen/enabled =="
echo 0x0007 > /sys/kernel/mm/lru_gen/enabled
echo "write_exit=$?"
echo "== 立即读回 =="
cat /sys/kernel/mm/lru_gen/enabled
snap A1_after_write

echo "== 等待 60s =="
sleep 60
snap A2_plus60

echo "== 等待 120s =="
sleep 60
snap A3_plus120

echo "== 采样完成，汇总 =="
for t in A0_baseline A1_after_write A2_plus60 A3_plus120; do
  echo "--- $t ---"
  sed -n '2p' "$OUT/$t.txt"
done
echo "== DONE: $OUT =="
