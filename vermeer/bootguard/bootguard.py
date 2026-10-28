#!/usr/bin/env python3
"""BootGuard offline verifier and file-only fault model. No device write backend."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

PARTITIONS = ('boot_a','init_boot_a','vendor_boot_a','dtbo_a','vbmeta_a')
HISTORICAL = dict(zip(PARTITIONS, (
 '5b030bc2a740166fa9c34daa851f5174199067332675abe200245fe11473a95e',
 'e70351d22243ce995bec0fc755dc8e2c63cb161f0dcb16bd11366f6937ca9e7a',
 '45320eae7815fa043f0e4034cd4ae33cf423ed8d546a7815ff439c7a7b86a040',
 'aac33c81251f8789a32eb4330067b86bc5853b58c1101ca9a7699041178232df',
 '403175daae8c10b1e2c2ec40f83980480edafd2c9a84a9cc28f9170ce7cbe1a9')))
BUILD = 'OS3.0.302.0.WNKCNXM'

def digest(data): return hashlib.sha256(data).hexdigest()

def regular(path):
    path = Path(path).absolute()
    for component in [path, *path.parents]:
        s = component.lstat()
        if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0) & 0x400:
            raise ValueError('symlink/reparse path refused')
    s=path.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
        raise ValueError('requires ordinary single-link file')
    return path

def file_hash(path):
    h=hashlib.sha256()
    with regular(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def verify_backups(directory, manifest):
    errors=[]; results={}
    if set(manifest) != set(PARTITIONS):
        return {'ok':False,'errors':['exact five A-slot partition entries required'],'files':{}}
    for name in PARTITIONS:
        item=manifest[name]
        try:
            if set(item) != {'file','sha256','bytes'} or item['file'] != name+'.img':
                raise ValueError('fixed basename required; no traversal')
            if not isinstance(item['bytes'],int) or item['bytes']<=0:
                raise ValueError('invalid size')
            path=regular(Path(directory)/item['file'])
            actual=file_hash(path)
            if path.stat().st_size != item['bytes'] or actual != item['sha256']:
                raise ValueError('backup size/hash mismatch')
            results[name]={'sha256':actual,'historical_match':actual==HISTORICAL[name]}
        except (OSError,ValueError,KeyError,TypeError) as e: errors.append(name+': '+str(e))
    return {'ok':not errors,'errors':errors,'files':results}

def preflight(observation, backup_result, now=None):
    """A report can satisfy offline checks, but cannot authorize a live write."""
    failures=[]
    expected={'product':'vermeer','build':BUILD,'android':'16','current_slot':'a',
              'target_slot':'b','virtual_ab':True,'snapshot_merge':'none',
              'selinux':'Enforcing','avb_protection_enabled':True,
              'bootloader_unlocked':True,'ota_pending':False}
    for key,value in expected.items():
        if observation.get(key) != value: failures.append('identity/state:'+key)
    try:
        when=datetime.fromisoformat(observation['captured_utc'].replace('Z','+00:00'))
        age=((now or datetime.now(timezone.utc))-when).total_seconds()
        if not 0 <= age <= 900: failures.append('stale_observation')
    except (KeyError,ValueError,TypeError): failures.append('missing_capture_time')
    # Orange unlocked boot state alone does not mean verification was disabled.
    if observation.get('verified_boot_state') not in ('orange','green'): failures.append('unexpected_avb_state')
    required=['target_boot_chain_matches_system','rescue_boot_tested_current_build',
              'full_abi_pass','vendor_modules_crc_pass','system_modules_crc_pass',
              'boot_image_structure_pass','root_manager_compatibility_pass']
    for key in required:
        if observation.get(key) is not True: failures.append('missing_verified_evidence:'+key)
    if observation.get('root_mode') != observation.get('candidate_root_mode'):
        if observation.get('lkm_removal_verified') is not True:
            failures.append('root_mode_transition_unverified')
    if observation.get('root_mode') not in ('lkm','builtin','none'): failures.append('unknown_root_mode')
    if observation.get('candidate_root_mode') not in ('lkm','builtin','none'): failures.append('unknown_candidate_root_mode')
    if observation.get('kpm_patch_count',0) > 1: failures.append('duplicate_kpm')
    if observation.get('kpm_autoload') is not False: failures.append('kpm_autoload_not_disabled')
    caps=observation.get('bootcontrol',{})
    for key in ('read_slots_verified','set_active_semantics_verified','retry_decrement_verified',
                'fallback_verified','mark_success_timing_verified'):
        if caps.get(key) is not True: failures.append('bootcontrol:'+key)
    retries=caps.get('native_retry_count')
    if not isinstance(retries,int) or isinstance(retries,bool) or not 1 <= retries <= 7:
        failures.append('bootcontrol:retry_count_unknown')
    if observation.get('requested_failures')==2 and retries!=2:
        failures.append('two_failure_policy_not_supported')
    if not backup_result.get('ok'): failures.append('backup_verification_failed')
    current=observation.get('current_partition_hashes',{})
    for p in PARTITIONS:
        if not current.get(p) or current.get(p)!=backup_result.get('files',{}).get(p,{}).get('sha256'):
            failures.append('fresh_partition_backup_mismatch:'+p)
    return {'offline_requirements_satisfied':not failures,'failures':failures,
            'deployable':False,'device_write_backend':'disabled',
            'notice':'Input assertions require independent human review; this tool never approves flashing.'}

class BootControlModel:
    """Model only: assumes supplied native semantics; never accesses BootControl HAL."""
    def __init__(self,retries,capabilities_verified=False):
        if not capabilities_verified or type(retries) is not int or not 1 <= retries <= 7:
            raise ValueError('native retry behavior unverified')
        self.remaining=retries; self.successful=False; self.active='b'
    def boot_attempt(self):
        if self.active=='a' or self.successful: return self.active
        if not self.remaining: self.active='a'; return 'a'
        self.remaining-=1; return 'b'
    def mark_success(self,health_pass):
        if health_pass is not True or self.active!='b': raise ValueError('health not passed')
        self.successful=True

def durable(path,data):
    # Only invoked with paths created by simulate() in its private temporary dir.
    with path.open('wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    if os.name=='posix':
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)

def simulate(fail_at=None,corrupt_backup=False):
    """No destination argument: cannot be pointed at a real partition or backup."""
    if fail_at not in (None,'prepared','partial_write','written','verified','committed'):
        raise ValueError('unknown fault point')
    original=b'ORIGINAL_TARGET_B\0'*4096; candidate=b'EXPERIMENTAL_B\0'*8192
    a_bytes=b'PROTECTED_A'; events=[]
    with tempfile.TemporaryDirectory(prefix='bootguard-file-model-') as name:
        root=Path(name); a=root/'a.bin'; b=root/'b.bin'; backup=root/'backup.bin'; journal=root/'journal.json'
        durable(a,a_bytes); durable(b,original); durable(backup,original)
        def step(state):
            durable(journal,json.dumps({'state':state,'old_sha256':digest(original),'new_sha256':digest(candidate)}).encode())
            events.append(state)
            if fail_at==state: raise InterruptedError(state)
        try:
            if corrupt_backup: durable(backup,b'CORRUPTED')
            if file_hash(backup)!=digest(original): raise ValueError('backup corruption before write')
            step('prepared')
            durable(b,candidate[:len(candidate)//2]); step('partial_write')
            durable(b,candidate); step('written')
            if file_hash(b)!=digest(candidate): raise ValueError('readback mismatch')
            step('verified'); step('committed')
        except InterruptedError:
            # Reconstruct from disk journal, not the interrupted process's memory.
            state=json.loads(journal.read_text())
            if state['state']!='committed':
                if file_hash(backup)!=state['old_sha256']: raise ValueError('recovery backup untrusted')
                durable(b,backup.read_bytes()); events.append('restored_original_b')
        except ValueError as e: events.append('refused:'+str(e))
        return {'kind':'ordinary-file-simulation','fault':fail_at,'events':events,
                'a_unchanged':a.read_bytes()==a_bytes,'b_sha256':file_hash(b),
                'b_state':'original' if b.read_bytes()==original else 'candidate' if b.read_bytes()==candidate else 'partial',
                'hardware_power_loss_tested':False,'device_write_performed':False}

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('verify-backups'); q.add_argument('directory'); q.add_argument('manifest')
    q=sub.add_parser('preflight'); q.add_argument('observation'); q.add_argument('backup_result')
    q=sub.add_parser('simulate'); q.add_argument('--fail-at',choices=['prepared','partial_write','written','verified','committed']); q.add_argument('--corrupt-backup',action='store_true')
    a=p.parse_args()
    try:
        if a.command=='verify-backups': result=verify_backups(a.directory,json.loads(Path(a.manifest).read_text()))
        elif a.command=='preflight': result=preflight(json.loads(Path(a.observation).read_text()),json.loads(Path(a.backup_result).read_text()))
        else: result=simulate(a.fail_at,a.corrupt_backup)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result.get('ok') is False or result.get('offline_requirements_satisfied') is False else 0
    except (ValueError,OSError,TypeError,KeyError) as e:
        print(json.dumps({'error':str(e),'deployable':False})); return 2

if __name__=='__main__': raise SystemExit(main())
