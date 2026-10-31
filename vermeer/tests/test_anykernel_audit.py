import gzip
import importlib.util
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('ak_audit', ROOT / 'scripts/audit-anykernel.py')
ak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ak)


class AnyKernelAuditTests(unittest.TestCase):
    def package(self, root='', extra=()):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = Path(tmp.name) / 'input.zip'
        data = bytearray(64)
        data[56:60] = b'ARM\x64'
        config = b'CONFIG_BBG=y\n# CONFIG_BBG_BLOCK_BOOT is not set\nCONFIG_KPM=y\n'
        data += b'IKCFG_ST' + gzip.compress(config) + b'IKCFG_ED'
        data += b'\x005.15.178-android13-8-g362d545d31a5\x00'
        with zipfile.ZipFile(p, 'w') as out:
            out.writestr(root + 'Image', data)
            out.writestr(root + 'anykernel.sh', 'do.devicecheck=0\nblock=boot\n')
            out.writestr(root + 'META-INF/com/google/android/update-binary', '#!/bin/sh\n')
            for name, value in extra:
                out.writestr(name, value)
        return p

    def test_wrapped_archive_is_not_root_installer_or_runtime_proof(self):
        result, config = ak.audit(self.package('wrapped/'))
        self.assertFalse(result['recovery_entry_at_archive_root'])
        self.assertFalse(result['runtime_bbg_verified'])
        self.assertFalse(result['deployable'])
        self.assertEqual(result['bbg']['CONFIG_BBG_BLOCK_BOOT'], 'n')
        self.assertIn('CONFIG_KPM=y', config)

    def test_valid_root_and_all_member_hashes(self):
        result, _ = ak.audit(self.package())
        self.assertTrue(result['recovery_entry_at_archive_root'])
        self.assertTrue(result['member_crc_verified'])
        self.assertEqual(len(result['members']), 3)

    def test_reject_traversal_and_windows_aliases(self):
        for name in ('../escape', '/absolute', 'C:/escape', 'x/../Image'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ak.audit(self.package(extra=[(name, b'bad')]))

    def test_original_zip_name_is_checked_before_host_normalization(self):
        for name in (b'x\\escape', b'x\x00escape'):
            with self.subTest(name=name):
                p = self.package(extra=[('x@escape', b'bad')])
                # Change both ZIP header names, bypassing the writer's host
                # normalization. Names have equal lengths; data CRC is intact.
                payload = p.read_bytes()
                self.assertEqual(payload.count(b'x@escape'), 2)
                p.write_bytes(payload.replace(b'x@escape', name))
                with self.assertRaises(ValueError): ak.audit(p)

    def test_reject_case_collision(self):
        with self.assertRaises(ValueError):
            ak.audit(self.package(extra=[('image', b'other')]))

    def test_reject_symlink(self):
        info = zipfile.ZipInfo('link')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(ValueError):
            ak.audit(self.package(extra=[(info, b'/dev/block/boot_a')]))

    def test_reject_ambiguous_installer(self):
        with self.assertRaises(ValueError):
            ak.audit(self.package(extra=[('other/anykernel.sh', b'block=boot')]))

    def test_crc_corruption_is_not_a_pass(self):
        p = self.package()
        data = p.read_bytes().replace(b'block=boot', b'block=bad!', 1)
        p.write_bytes(data)
        with self.assertRaises(zipfile.BadZipFile):
            ak.audit(p)

    def test_member_size_bound(self):
        info = zipfile.ZipInfo('Image')
        info.file_size = ak.MAX_MEMBER + 1
        with self.assertRaises(ValueError):
            ak.validate_members([info])


if __name__ == '__main__':
    unittest.main()
