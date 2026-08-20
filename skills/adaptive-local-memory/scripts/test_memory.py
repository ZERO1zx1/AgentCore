import json, subprocess, sys, tempfile, unittest
from pathlib import Path
SCRIPT=Path(__file__).with_name("memory.py")
class MemoryTest(unittest.TestCase):
    def cli(self,root,*args,expected=0):
        r=subprocess.run([sys.executable,str(SCRIPT),*args,"--root",str(root)],text=True,capture_output=True); self.assertEqual(r.returncode,expected,r.stderr); return r
    def test_lifecycle(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.cli(root,"record","--problem","pytest cannot import module","--cause","wrong working directory","--action","run from repository root","--evidence","pytest passed","--tags","pytest,python","--status","verified"); lesson=json.loads(r.stdout)["id"]
            self.assertEqual(json.loads(self.cli(root,"recall","--query","python pytest import").stdout)["matches"][0]["id"],lesson)
            self.cli(root,"feedback","--id",lesson,"--result","success","--evidence","reproduced and passed")
            self.assertTrue(json.loads(self.cli(root,"validate").stdout)["valid"])
            usage=json.loads(self.cli(root,"stats").stdout); self.assertEqual(usage["lesson_limit"],100); self.assertEqual(usage["byte_limit"],524288)
            self.assertEqual(json.loads(self.cli(root,"compact").stdout)["removed"],0)
    def test_secret_rejected(self):
        with tempfile.TemporaryDirectory() as root: self.cli(root,"record","--problem","auth failed","--cause","token=supersecretvalue123","--action","rotate","--evidence","login passed",expected=2)
if __name__=="__main__": unittest.main()
