#!/system/bin/sh
# Run only manually on the phone if the owner chooses. No su, mount, dd, writes,
# reboot, slot change, mark-boot-successful, or settings changes.
printf '%s\n' 'BootGuard read-only collection v2; review output before sharing. No phone settings are changed.'
date -u
uname -r
for prop in ro.product.device ro.product.vendor.device ro.build.version.incremental ro.build.version.release ro.boot.slot_suffix ro.virtual_ab.enabled ro.boot.verifiedbootstate ro.boot.vbmeta.device_state ro.boot.flash.locked sys.boot_completed ro.lmk.use_psi ro.lmk.thrashing_limit ro.lmk.swap_free_low_percentage; do
  printf '%s=' "$prop"
  getprop "$prop"
done
printf '\n%s\n' 'Qualcomm WALT tunables (only known control values are read):'
for path in /sys/devices/system/cpu/cpufreq/policy*/walt/up_rate_limit_us /sys/devices/system/cpu/cpufreq/policy*/walt/down_rate_limit_us /sys/devices/system/cpu/cpufreq/policy*/walt/hispeed_load /sys/devices/system/cpu/cpufreq/policy*/walt/hispeed_freq /sys/devices/system/cpu/cpufreq/walt/up_rate_limit_us /sys/devices/system/cpu/cpufreq/walt/down_rate_limit_us /sys/devices/system/cpu/cpufreq/walt/hispeed_load /sys/devices/system/cpu/cpufreq/walt/hispeed_freq; do
  printf '\n%s\n' "$path"
  if [ -r "$path" ]; then cat "$path"; else printf '%s\n' 'UNKNOWN: absent or unreadable'; fi
done
printf '\n%s\n' 'Scheduling, I/O and thermal observation; no control nodes are written:'
for path in /dev/cpuset/top-app/cpus /dev/cpuset/foreground/cpus /dev/cpuset/background/cpus /dev/cpuctl/top-app/cpu.uclamp.min /dev/cpuctl/top-app/cpu.uclamp.max /dev/cpuctl/background/cpu.uclamp.max /sys/fs/cgroup/top-app/cpu.uclamp.min /sys/fs/cgroup/top-app/cpu.uclamp.max /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_min_freq /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_max_freq /sys/devices/system/cpu/cpufreq/policy*/schedutil/rate_limit_us /sys/devices/system/cpu/cpufreq/policy*/schedutil/up_rate_limit_us /sys/devices/system/cpu/cpufreq/policy*/schedutil/down_rate_limit_us /sys/block/sd*/queue/scheduler /sys/block/sd*/queue/read_ahead_kb /sys/class/thermal/thermal_zone*/type /sys/class/thermal/thermal_zone*/temp /sys/class/power_supply/battery/status /sys/class/power_supply/battery/temp; do
  printf '\n%s\n' "$path"
  if [ -r "$path" ]; then cat "$path"; else printf '%s\n' 'UNKNOWN: absent or unreadable'; fi
done
getenforce
printf '\n%s\n' 'BBG passive diagnostics; no mount and no write probe:'
ls -ld /sys/kernel/security /sys/kernel/security/lsm 2>&1
grep ' securityfs ' /proc/mounts 2>/dev/null
dmesg 2>/dev/null | grep -i -E 'baseband_guard|baseband.guard|\[bbg\]' | tail -n 20
printf '\n%s\n' '/sys/kernel/mm/lru_gen/min_ttl_ms'
cat /sys/kernel/mm/lru_gen/min_ttl_ms 2>&1
for path in /proc/version /proc/uptime /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io; do
  printf '\n%s\n' "$path"
  if [ -r "$path" ]; then cat "$path"; else printf '%s\n' 'UNKNOWN: absent or unreadable'; fi
done
# Do not print the complete cmdline/bootconfig: those may contain serial numbers.
tr ' ' '\n' < /proc/cmdline 2>/dev/null | grep -E '^androidboot\.(slot|slot_suffix|verifiedbootstate|vbmeta.device_state)='
grep -E '^androidboot\.(slot|slot_suffix|verifiedbootstate|vbmeta.device_state)[[:space:]]*=' /proc/bootconfig 2>/dev/null
cat /proc/modules 2>/dev/null
for path in /sys/kernel/security/lsm /sys/fs/selinux/enforce /sys/kernel/mm/lru_gen/enabled /sys/module/damon_reclaim/parameters/enabled /proc/swaps /proc/sys/vm/swappiness /proc/sys/vm/watermark_scale_factor /proc/sys/net/ipv4/tcp_congestion_control /proc/sys/net/ipv4/tcp_available_congestion_control /sys/devices/system/cpu/cpu[0-9]*/regs/identification/midr_el1 /sys/devices/system/cpu/cpu[0-9]*/cpu_capacity /sys/devices/system/cpu/cpu[0-9]*/thermal_pressure /sys/devices/system/cpu/cpufreq/policy*/related_cpus /sys/devices/system/cpu/cpufreq/policy*/scaling_governor /sys/devices/system/cpu/cpufreq/policy*/scaling_min_freq /sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq /sys/block/zram*/comp_algorithm /sys/block/zram*/disksize /sys/block/zram*/mm_stat /sys/block/zram*/io_stat /sys/block/zram*/bd_stat; do
  printf '\n%s\n' "$path"
  if [ -r "$path" ]; then cat "$path"; else printf '%s\n' 'UNKNOWN: absent or unreadable'; fi
done
printf '\n%s\n' 'Memory and reclaim counters (single snapshot, not a benchmark):'
grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo 2>/dev/null
grep -E '^(pswpin|pswpout|allocstall|pgscan|pgsteal|workingset_refault|compact_stall)' /proc/vmstat 2>/dev/null
printf '\n%s\n' 'Selected running IKCONFIG values (may be hidden; absence is unknown):'
if [ -r /proc/config.gz ] && command -v gzip >/dev/null 2>&1; then
  gzip -dc /proc/config.gz 2>/dev/null | grep -E '^(# )?CONFIG_(BBG|LSM|KSU|KPM|ZRAM|LZ4|CRYPTO_LZ4|LRU_GEN|PSI|DAMON|NTSYNC|SYSVIPC|IPC_NS|PID_NS|DEVTMPFS|MODVERSIONS|CFI|SECURITY_SELINUX|TCP_CONG|DEFAULT_TCP_CONG|WIREGUARD|UCLAMP|SCHED_WALT|CPU_FREQ_GOV_SCHEDUTIL)'
else
  printf '%s\n' 'UNKNOWN: config not readable or gzip unavailable'
fi
printf '\n%s\n' 'NoActive/ReKernel-X: record app mode/version manually; KPM may not appear in /proc/modules.'
printf '%s\n' 'Missing baseband_guard in an unreadable LSM list does not prove BBG disabled. No block write probe is permitted.'
if command -v bootctl >/dev/null 2>&1; then
  printf '\n%s\n' 'bootctl get-current-slot:'
  bootctl get-current-slot
  printf '%s\n' 'bootctl get-number-slots:'
  bootctl get-number-slots
  for slot in 0 1; do
    for query in is-slot-bootable is-slot-marked-successful; do
      bootctl "$query" "$slot"
      result=$?
      printf 'bootctl %s %s exit=%s (raw status; validate HAL semantics)\n' "$query" "$slot" "$result"
    done
  done
fi
printf '%s\n' 'UNKNOWN until separately verified: snapshot merge, native retry count, early mark-success timing, complete partition hashes, AVB descriptors, current dlkm CRCs.'
printf '%s\n' 'BOOTGUARD_READ_ONLY_COMPLETE'
