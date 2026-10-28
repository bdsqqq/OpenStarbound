import copy,importlib.util,unittest
from pathlib import Path
import providers
from native_symbols import LiveSymbol
class ProviderControls(unittest.TestCase):
    def setUp(self):
        self.archive=Path('/isolated/canonical/libstar_engine_ffi.a');self.owners=[dict(symbol=s,name=('member'+str(i)).encode(),offset=i,sha256='a'*64)for i,s in enumerate(providers.EXPORTS)]
        self.symbols=tuple(LiveSymbol(4096+i*16,16,i,str(self.archive).encode()+b'('+p['name']+b')',p['symbol'])for i,p in enumerate(self.owners))
    def test_exact_live_providers(self):self.assertEqual(len(providers.live(self.symbols,self.owners,self.archive,True)),3)
    def test_cpp_run_spoof_rejected(self):
        rows=list(self.symbols);s=rows[0];rows[0]=LiveSymbol(s.address,s.size,s.object_index,b'/isolated/spoof.o',s.name)
        with self.assertRaises(ValueError):providers.live(tuple(rows),self.owners,self.archive,True)
    def test_duplicate_personality_rejected(self):
        with self.assertRaises(ValueError):providers.live((*self.symbols,self.symbols[2]),self.owners,self.archive,True)
    def test_required_count_not_optional(self):
        with self.assertRaises(ValueError):providers.live((self.symbols[0],self.symbols[2]),self.owners,self.archive,True)
    def test_unused_count_may_dead_strip(self):self.assertEqual(len(providers.live((self.symbols[0],self.symbols[2]),self.owners,self.archive,False)),2)
    def test_mock_controller_export_rejected(self):
        s=LiveSymbol(8192,16,10,b'/isolated/other.o',b'_sb_idmap_mock_fault')
        with self.assertRaises(ValueError):providers.live((*self.symbols,s),self.owners,self.archive,True)
    def test_literal_mock_word_is_not_controller_code(self):
        s=LiveSymbol(8192,16,10,b'/isolated/other.o',b'literal string: mock error')
        self.assertEqual(len(providers.live((*self.symbols,s),self.owners,self.archive,True)),3)
if __name__=='__main__':unittest.main()
