import unittest
from replay import status

class StatusTests(unittest.TestCase):
    def fixture(self):
        return dict(expected_returncode=0),dict(returncode=0,pid=3,pgid=3,reaped=True,group_gone=True,timed_out=False),dict(pid=3,pgid=3)
    def test_native_success(self):status('native',*self.fixture())
    def test_coherent_aborted_process_cannot_change_role_expectation(self):
        p,r,s=self.fixture();p['expected_returncode']=r['returncode']=-6
        with self.assertRaises(ValueError):status('native',p,r,s)
    def test_negative_compiler_must_really_fail(self):
        with self.assertRaises(ValueError):status('lazy-negative',*self.fixture())
    def test_unknown_command_cannot_fill_membership(self):
        with self.assertRaises(ValueError):status('other',*self.fixture())
    def test_unreaped_or_live_group_rejected(self):
        for field in ['reaped','group_gone']:
            p,r,s=self.fixture();r[field]=False
            with self.assertRaises(ValueError):status('native',p,r,s)

if __name__=='__main__':unittest.main()
