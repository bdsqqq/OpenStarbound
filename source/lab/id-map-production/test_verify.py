import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('production_replay',HERE/'verify.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class ProductionControls(unittest.TestCase):
 def test_exact_roles(self):v.membership(dict(commands=v.expected()))
 def test_duplicate_backend_role_same_count(self):
  roles=v.expected();roles[roles.index('on-native')]='off-native'
  with self.assertRaises(ValueError):v.membership(dict(commands=roles))
 def test_missing_actual_on_trace_rejected(self):
  roles=v.expected();roles.remove('on-trace')
  with self.assertRaises(ValueError):v.membership(dict(commands=roles))
 def test_current_selector_blocks(self):v.configuration._selectors((v.R/'source/CMakeLists.txt').read_text())
 def test_default_on_rejected(self):
  s=(v.R/'source/CMakeLists.txt').read_text().replace('option(STAR_USE_RUST_ID_MAP "Use experimental Rust IdMap controllers" OFF)','option(STAR_USE_RUST_ID_MAP "Use experimental Rust IdMap controllers" ON)')
  with self.assertRaises(AssertionError):v.configuration._selectors(s)
 def test_missing_aggregate_gate_rejected(self):
  s=(v.R/'source/CMakeLists.txt').read_text().replace(' OR STAR_USE_RUST_ID_MAP)',' )')
  with self.assertRaises(AssertionError):v.configuration._selectors(s)
if __name__=='__main__':unittest.main()
