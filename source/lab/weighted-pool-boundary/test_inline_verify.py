import sys,unittest
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import inline_verify as V
from native_symbols import LiveSymbol

class StructuralEvidence(unittest.TestCase):
 def test_mapping_order_not_semantics(self):
  V.same({'a':1,'b':{'x':2,'y':3}},{'b':{'y':3,'x':2},'a':1},'structural')
 def test_scalar_and_sequence_types_remain_exact(self):
  for a,b in [(1,True),([1],(1,)),(0.0,-0.0),({'x':1},{'x':True})]:
   with self.assertRaises(ValueError):V.same(a,b,'type')
 def test_role_does_not_downgrade_full_api(self):
  archive=Path('/tmp/ffi.a');names=[b'_sb_wp_run',b'_sb_wp_count',b'_rust_eh_personality'];owners=[dict(symbol=n,name=b'member.o')for n in names];symbols=tuple(LiveSymbol(1,1,1,b'/tmp/ffi.a(member.o)',n)for n in names)
  V.role_providers('combined',symbols,owners,archive)
  diagnostic=tuple(s for s in symbols if s.name!=b'_sb_wp_count')
  V.role_providers('allocation-native',diagnostic,owners,archive)
  with self.assertRaises(ValueError):V.role_providers('combined',diagnostic,owners,archive)
  with self.assertRaises(ValueError):V.role_providers('invented',diagnostic,owners,archive)
 def test_allocation_negative_is_required(self):
  good='PASS\tnative-empty-allocation-parity\toriginal=0\tboundary=0\nPASS\tnative-closure-allocation-denied\tempty-container-and-seeded-zero-uniques\n';bad='FAIL\tboundary empty-container construction allocated native C++ storage\n';V.allocations(good,bad,1)
  for code in [0,True]:
   with self.assertRaises(ValueError):V.allocations(good,bad,code)
if __name__=='__main__':unittest.main()
