#!/system/bin/sh
# Run only manually on the phone if the owner chooses. No su, mount, dd, writes,
# reboot, slot change, mark-boot-successful, or settings changes.
printf '%s\n' 'BootGuard read-only collection v1; output may include device identifiers.'
date -u
uname -a
for prop in ro.product.device ro.product.vendor.device ro.build.version.incremental ro.build.version.release ro.boot.slot_suffix ro.virtual_ab.enabled ro.boot.verifiedbootstate ro.boot.vbmeta.device_state ro.boot.flash.locked sys.boot_completed; do
  printf '%s=' "$prop"
  getprop "$prop"
done
getenforce
cat /proc/version /proc/cmdline /proc/bootconfig /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io 2>/dev/null
cat /proc/modules 2>/dev/null
for path in /sys/devices/system/cpu/cpu[0-9]*/regs/identification/midr_el1 /sys/devices/system/cpu/cpu[0-9]*/cpu_capacity /sys/devices/system/cpu/cpufreq/policy*/related_cpus /sys/devices/system/cpu/cpufreq/policy*/scaling_governor /sys/block/zram*/comp_algorithm /sys/block/zram*/mm_stat; do
  [ -r "$path" ] || continue
  printf '\n%s\n' "$path"
  cat "$path"
done
if command -v bootctl >/dev/null 2>&1; then
  bootctl get-current-slot
  bootctl get-number-slots
  bootctl is-slot-bootable 0
  bootctl is-slot-marked-successful 0
  bootctl is-slot-bootable 1
  bootctl is-slot-marked-successful 1
fi
printf '%s\n' 'UNKNOWN until separately verified: snapshot merge, native retry count, early mark-success timing, complete partition hashes, AVB descriptors, current dlkm CRCs.'
