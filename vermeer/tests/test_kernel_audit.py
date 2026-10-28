import pathlib,struct,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import kernel_audit as ka

class AuditTests(unittest.TestCase):
    def image(self):
        d=bytearray(8192); d[:8]=b'ANDROID!'; struct.pack_into('<I',d,8,64)
        struct.pack_into('<I',d,20,1584); struct.pack_into('<I',d,40,4); d[4152:4156]=b'ARM\x64'; return d
    def test_boot_v4_valid_but_not_deployable(self):
        r=ka.inspect_image(self.image()); self.assertEqual(r['header_version'],4); self.assertFalse(r['deployable'])
    def test_truncated(self):
        with self.assertRaises(ValueError): ka.inspect_image(self.image()[:4100])
    def test_bad_header(self):
        d=self.image(); struct.pack_into('<I',d,20,999)
        with self.assertRaises(ValueError): ka.inspect_image(d)
    def test_bad_signature_extent(self):
        d=self.image(); struct.pack_into('<I',d,1580,0xffffffff)
        with self.assertRaises(ValueError): ka.inspect_image(d)
    def test_unknown(self):
        with self.assertRaises(ValueError): ka.inspect_image(b'garbage')
    def test_reject_non_elf_module(self):
        with self.assertRaises(ValueError): ka.elf_module(b'fake vermagic=5.15')
    def test_config_parser(self):
        self.assertEqual(ka.parse_config('CONFIG_A=y\n# CONFIG_B is not set\n'),{'CONFIG_A':'y','CONFIG_B':'n'})
    def test_matching_crc_not_full_abi(self):
        m={'undefined':['foo'],'versions':{'foo':18},'vermagic':['expected']}
        r=ka.compare_module(m,'0x12 foo vmlinux EXPORT_SYMBOL','expected')
        self.assertEqual(r['symbol_crc_check'],'PASS'); self.assertFalse(r['full_abi_verified'])
    def test_mismatches(self):
        m={'undefined':['foo','missing'],'versions':{'foo':19},'vermagic':['wrong']}
        r=ka.compare_module(m,'0x12 foo vmlinux EXPORT_SYMBOL','expected')
        self.assertEqual(r['symbol_crc_check'],'FAIL'); self.assertEqual(len(r['reasons']),4)
    def test_no_crc_is_unknown_failure(self):
        r=ka.compare_module({'undefined':[],'versions':{},'vermagic':['expected']},'','expected')
        self.assertEqual(r['symbol_crc_check'],'FAIL')

if __name__=='__main__': unittest.main()
