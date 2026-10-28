import os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.name=='posix','shell mock runs on POSIX')
class RecoveryNoopTests(unittest.TestCase):
    def run_script(self,product,slot):
        with tempfile.TemporaryDirectory() as name:
            root=pathlib.Path(name); prop=root/'getprop'
            prop.write_text('#!/bin/sh\ncase "$1" in ro.product.device) echo "$TEST_PRODUCT";; ro.boot.slot_suffix) echo "$TEST_SLOT";; esac\n'); prop.chmod(0o755)
            env=dict(os.environ,PATH=str(root)+':'+os.environ['PATH'],TEST_PRODUCT=product,TEST_SLOT=slot)
            return subprocess.run(['sh',str(ROOT/'bootguard/recovery/update-binary'),'3','1','unused.zip'],env=env,capture_output=True,text=True)
    def test_normal_a_noop(self):
        r=self.run_script('vermeer','_a'); self.assertEqual(r.returncode,0); self.assertIn('NOOP complete',r.stdout)
    def test_wrong_product(self): self.assertNotEqual(self.run_script('marble','_a').returncode,0)
    def test_wrong_slot(self): self.assertNotEqual(self.run_script('vermeer','_b').returncode,0)
