#!/system/bin/sh
# Fixed, bounded read-only observation. No file uploads or setting changes.
# Not a controlled benchmark; foreground usage/charging are not controlled.
for sample in 0 1 2 3; do
  printf 'SAMPLE %s\n' "$sample"
  for path in /proc/uptime /proc/sys/kernel/random/boot_id /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io /sys/block/zram0/mm_stat /sys/kernel/mm/lru_gen/enabled /sys/kernel/mm/lru_gen/min_ttl_ms /sys/class/power_supply/battery/status /sys/class/power_supply/battery/temp; do
    printf 'PATH %s\n' "$path"
    cat "$path" 2>/dev/null || printf '%s\n' 'UNKNOWN'
  done
  printf '%s\n' 'PATH /proc/vmstat'
  grep -E '^(pswpin|pswpout|pgmajfault|oom_kill|allocstall|pgscan|pgsteal|workingset_refault|compact_stall)' /proc/vmstat 2>/dev/null
  printf '%s\n' 'PATH /proc/meminfo'
  grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo 2>/dev/null
  printf '%s\n' 'PATH PAGE_SIZE'
  getconf PAGESIZE 2>/dev/null || printf '%s\n' 'UNKNOWN'
  printf '%s\n' 'PATH UPTIME_END'
  cat /proc/uptime
  printf '%s\n' 'END_SAMPLE'
  if [ "$sample" -lt 3 ]; then sleep 10; fi
done
printf '%s\n' 'BOOTGUARD_READ_ONLY_COMPLETE'
