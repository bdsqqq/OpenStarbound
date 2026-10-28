import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('actual_bridge_replay',Path(__file__).with_name('verify_rust_bridge.py'));v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class ActualBridgeMembership(unittest.TestCase):
    def fixture(self):return dict(acceptedPredecessorCommands=list(v.PRE),commands=list(v.COMMANDS))
    def test_exact_actual_roles(self):v.membership(self.fixture())
    def test_duplicate_role_same_count_rejected(self):
        x=self.fixture();x['commands'][0]=x['commands'][1]
        with self.assertRaises(ValueError):v.membership(x)
    def test_missing_trace_native_execution_rejected(self):
        x=self.fixture();x['commands'].remove('trace')
        with self.assertRaises(ValueError):v.membership(x)
if __name__=='__main__':unittest.main()
