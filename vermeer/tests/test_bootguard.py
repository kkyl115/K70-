import importlib.util
import json
import pathlib
import tempfile
import unittest
from datetime import datetime, timezone

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bootguard',ROOT/'bootguard/bootguard.py')
bg=importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)

class BootGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name); self.manifest={}
        for p in bg.PARTITIONS:
            data=(p*32).encode(); (self.root/(p+'.img')).write_bytes(data)
            self.manifest[p]={'file':p+'.img','bytes':len(data),'sha256':bg.digest(data)}
    def good(self):
        o={'product':'vermeer','build':bg.BUILD,'android':'16','current_slot':'a','target_slot':'b',
           'virtual_ab':True,'snapshot_merge':'none','selinux':'Enforcing','avb_protection_enabled':True,
           'bootloader_unlocked':True,'ota_pending':False,'verified_boot_state':'orange',
           'root_mode':'lkm','candidate_root_mode':'lkm','kpm_patch_count':0,'kpm_autoload':False,
           'captured_utc':datetime.now(timezone.utc).isoformat(),'requested_failures':2,
           'current_partition_hashes':{p:d['sha256'] for p,d in self.manifest.items()},
           'bootcontrol':{k:True for k in ['read_slots_verified','set_active_semantics_verified',
             'retry_decrement_verified','fallback_verified','mark_success_timing_verified']}}
        o['bootcontrol']['native_retry_count']=2
        for k in ['target_boot_chain_matches_system','rescue_boot_tested_current_build',
                  'full_abi_pass','vendor_modules_crc_pass','system_modules_crc_pass',
                  'boot_image_structure_pass','root_manager_compatibility_pass']: o[k]=True
        return o
    def evaluate(self,o): return bg.preflight(o,bg.verify_backups(self.root,self.manifest))
    def test_valid_files_still_not_device_approval(self):
        r=self.evaluate(self.good()); self.assertTrue(r['offline_requirements_satisfied']); self.assertFalse(r['deployable'])
    def test_corrupt_backup(self):
        (self.root/'boot_a.img').write_bytes(b'bad'); self.assertFalse(bg.verify_backups(self.root,self.manifest)['ok'])
    def test_wrong_model_version_slot(self):
        for k,v in [('product','marble'),('build','OS4'),('current_slot','b'),('target_slot','a')]:
            with self.subTest(k=k):
                o=self.good(); o[k]=v; self.assertFalse(self.evaluate(o)['offline_requirements_satisfied'])
    def test_unknown_and_insecure_state(self):
        for k,v in [('snapshot_merge','merging'),('snapshot_merge','unknown'),('selinux','Permissive'),
                    ('avb_protection_enabled',False),('ota_pending',True),('kpm_autoload',True),('kpm_patch_count',2)]:
            with self.subTest(k=k,v=v):
                o=self.good(); o[k]=v; self.assertFalse(self.evaluate(o)['offline_requirements_satisfied'])
    def test_root_conflict(self):
        o=self.good(); o['candidate_root_mode']='builtin'; self.assertFalse(self.evaluate(o)['offline_requirements_satisfied'])
    def test_current_readback_required(self):
        o=self.good(); o['current_partition_hashes']['boot_a']='0'*64
        self.assertFalse(self.evaluate(o)['offline_requirements_satisfied'])
    def test_stale_capture(self):
        o=self.good(); o['captured_utc']='2024-01-01T00:00:00Z'; self.assertFalse(self.evaluate(o)['offline_requirements_satisfied'])
    def test_missing_evidence(self):
        o=self.good(); del o['full_abi_pass']; self.assertFalse(self.evaluate(o)['offline_requirements_satisfied'])
    def test_two_attempts_not_assumed(self):
        o=self.good(); o['bootcontrol']['native_retry_count']=3; self.assertFalse(self.evaluate(o)['offline_requirements_satisfied'])
    def test_missing_file(self):
        (self.root/'vbmeta_a.img').unlink(); self.assertFalse(bg.verify_backups(self.root,self.manifest)['ok'])
    def test_path_traversal(self):
        self.manifest['boot_a']['file']='../outside'; self.assertFalse(bg.verify_backups(self.root,self.manifest)['ok'])
    def test_symlink(self):
        p=self.root/'boot_a.img'; p.unlink()
        try: p.symlink_to(self.root/'dtbo_a.img')
        except OSError: self.skipTest('host cannot create symlink')
        self.assertFalse(bg.verify_backups(self.root,self.manifest)['ok'])
    def test_block_device_refused(self):
        if not pathlib.Path('/dev/null').exists(): self.skipTest('POSIX only')
        with self.assertRaises(ValueError): bg.regular('/dev/null')
    def test_power_interruption_models(self):
        for point in ['prepared','partial_write','written','verified']:
            with self.subTest(point=point):
                r=bg.simulate(point); self.assertTrue(r['a_unchanged']); self.assertEqual(r['b_state'],'original')
    def test_commit_survives(self): self.assertEqual(bg.simulate('committed')['b_state'],'candidate')
    def test_noop_on_corrupt_backup(self):
        r=bg.simulate(corrupt_backup=True); self.assertEqual(r['b_state'],'original'); self.assertTrue(r['a_unchanged'])
    def test_unknown_bootloader_refused(self):
        with self.assertRaises(ValueError): bg.BootControlModel(2)
    def test_native_retry_model(self):
        b=bg.BootControlModel(3,True); self.assertEqual([b.boot_attempt() for _ in range(4)],['b','b','b','a'])
    def test_early_success_refused(self):
        b=bg.BootControlModel(2,True)
        with self.assertRaises(ValueError): b.mark_success(False)
    def test_success_stops_fallback_model(self):
        b=bg.BootControlModel(2,True); b.boot_attempt(); b.mark_success(True)
        self.assertEqual([b.boot_attempt() for _ in range(5)],['b']*5)

if __name__=='__main__': unittest.main()
