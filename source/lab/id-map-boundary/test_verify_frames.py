import copy,importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('frame_replay',Path(__file__).with_name('verify_frames.py'));v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class FrameMembership(unittest.TestCase):
    def fixture(self):return dict(acceptedPredecessorCommands=list(v.PRE),commands=list(v.NEW),retainedFailedCommands=list(v.FAILED))
    def test_exact_roles(self):v.membership(self.fixture())
    def test_duplicate_role_same_count(self):
        f=self.fixture();f['acceptedPredecessorCommands'][0]=f['acceptedPredecessorCommands'][1]
        with self.assertRaisesRegex(ValueError,'exact accepted/failed role membership'):v.membership(f)
    def test_failed_compile_cannot_disappear(self):
        f=self.fixture();f['retainedFailedCommands']=[]
        with self.assertRaises(ValueError):v.membership(f)
if __name__=='__main__':unittest.main()
