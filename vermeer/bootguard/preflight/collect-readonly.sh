#!/system/bin/sh
# Run only manually on the phone if the owner chooses. No su, mount, dd, writes,
# reboot, slot change, mark-boot-successful, or settings changes.
printf '%s\n' 'BootGuard read-only collection v2; review output before sharing. No phone settings are changed.'
date -u
uname -r
for prop in ro.product.device ro.product.vendor.device ro.build.version.incremental ro.build.version.release ro.boot.slot_suffix ro.virtual_ab.enabled ro.boot.verifiedbootstate ro.boot.vbmeta.device_state ro.boot.flash.locked sys.boot_completed; do
  printf '%s=' "$prop"
  getprop "$prop"
done
getenforce
cat /proc/version /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io 2>/dev/null
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
  bootctl get-current-slot
  bootctl get-number-slots
  bootctl is-slot-bootable 0
  bootctl is-slot-marked-successful 0
  bootctl is-slot-bootable 1
  bootctl is-slot-marked-successful 1
fi
printf '%s\n' 'UNKNOWN until separately verified: snapshot merge, native retry count, early mark-success timing, complete partition hashes, AVB descriptors, current dlkm CRCs.'
