import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('idmap_policy_replay',Path(__file__).with_name('verify_policy.py'));replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
class ReplayControls(unittest.TestCase):
    def test_duplicate_command_role_rejected_even_with_matching_external_pin(self):
        with tempfile.TemporaryDirectory(prefix='idmap-policy-negative-')as d:
            root=Path(d);p=root/'report.json';p.write_text(json.dumps({'commands':['c11','c11','debug','release']}));old=replay.OUT
            try:
                replay.OUT=root
                with self.assertRaisesRegex(ValueError,'exact four-command membership'):replay.audit(hashlib.sha256(p.read_bytes()).hexdigest())
            finally:replay.OUT=old
if __name__=='__main__':unittest.main()
