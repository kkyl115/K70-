#!/usr/bin/env python3
"""Read a supplied config; never mistake compile options for runtime verification."""
import argparse
import hashlib
import json
from pathlib import Path
from kernel_audit import parse_config

FEATURES = {
    'BBG': ['CONFIG_BBG', 'CONFIG_BBG_BLOCK_BOOT', 'CONFIG_BBG_BLOCK_RECOVERY', 'CONFIG_LSM'],
    'BBRv3': ['CONFIG_TCP_CONG_ADVANCED', 'CONFIG_TCP_CONG_BBR', 'CONFIG_TCP_CONG_BBR3', 'CONFIG_DEFAULT_TCP_CONG', 'CONFIG_NET_SCH_FQ'],
    'WireGuard': ['CONFIG_WIREGUARD', 'CONFIG_TUN'],
    'NTSync': ['CONFIG_NTSYNC'],
    'ZRAM': ['CONFIG_ZRAM', 'CONFIG_ZSMALLOC', 'CONFIG_ZRAM_DEF_COMP', 'CONFIG_ZRAM_WRITEBACK', 'CONFIG_LZ4_COMPRESS', 'CONFIG_ZSTD_COMPRESS', 'CONFIG_CRYPTO_LZ4KD', 'CONFIG_LZ4KD_COMPRESS', 'CONFIG_LZ4KD_DECOMPRESS'],
    'DroidSpaces': ['CONFIG_SYSVIPC', 'CONFIG_POSIX_MQUEUE', 'CONFIG_IPC_NS', 'CONFIG_PID_NS', 'CONFIG_DEVTMPFS', 'CONFIG_NET_NS', 'CONFIG_VETH', 'CONFIG_USER_NS', 'CONFIG_CGROUP_PIDS', 'CONFIG_CFS_BANDWIDTH'],
    'DAMON': ['CONFIG_DAMON', 'CONFIG_DAMON_PADDR', 'CONFIG_DAMON_RECLAIM'],
    'MGLRU_PSI': ['CONFIG_LRU_GEN', 'CONFIG_LRU_GEN_ENABLED', 'CONFIG_PSI'],
    'crash_evidence': ['CONFIG_PSTORE', 'CONFIG_PSTORE_RAM', 'CONFIG_PSTORE_CONSOLE'],
    'root_mount_visibility': ['CONFIG_KSU', 'CONFIG_KPM', 'CONFIG_KSU_SUSFS', 'CONFIG_KSU_SUSFS_SUS_MOUNT', 'CONFIG_KSU_SUSFS_SPOOF_UNAME'],
    'scheduler_observation': ['CONFIG_UCLAMP_TASK', 'CONFIG_UCLAMP_TASK_GROUP', 'CONFIG_SCHED_WALT', 'CONFIG_CPU_FREQ_GOV_SCHEDUTIL', 'CONFIG_SCHEDSTATS', 'CONFIG_SCHED_DEBUG', 'CONFIG_FTRACE', 'CONFIG_FTRACE_SYSCALLS'],
    'safety': ['CONFIG_MODVERSIONS', 'CONFIG_CFI_CLANG', 'CONFIG_CFI_PERMISSIVE', 'CONFIG_SECURITY_SELINUX', 'CONFIG_FS_VERITY'],
}

def audit(data):
    config=parse_config(data.decode('utf-8-sig'))
    features={name:{key:config.get(key,'not_recorded') for key in keys} for name,keys in FEATURES.items()}
    core=('CONFIG_SYSVIPC','CONFIG_POSIX_MQUEUE','CONFIG_IPC_NS','CONFIG_PID_NS','CONFIG_DEVTMPFS')
    return {
        'input_sha256': hashlib.sha256(data).hexdigest(),
        'evidence_scope': 'supplied_config_only',
        'features': features,
        'droidspaces_core_requirements_not_shown_enabled': [k for k in core if config.get(k)!='y'],
        'susfs_container_visibility_review_required':config.get('CONFIG_KSU_SUSFS_SUS_MOUNT')=='y',
        'runtime_verified':False, 'source_patch_identity_verified':False,
        'abi_verified':False, 'deployable':False,
    }

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',type=Path)
    args=parser.parse_args()
    print(json.dumps(audit(args.config.read_bytes()),ensure_ascii=False,indent=2))
