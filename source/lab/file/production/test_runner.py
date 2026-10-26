"""No compiler/Rust execution. Durable failure controls for runner construction."""
import sys
sys.dont_write_bytecode=True
import unittest
from unittest.mock import patch
from pathlib import Path
import runner as r

class RunnerContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=r.authenticate();cls.rs,cls.libs=r.recipes()
        cls.out=r.BASE/'test-plan-only'

    def test_dependency_resolution_is_unique_per_scan_not_across_scans(self):
        source, header = Path('/frozen/source.cpp'), Path('/frozen/shared.hpp')
        jobs = [('a', None, [], source), ('b', None, [], source)]
        data = 'object: /frozen/source.cpp /frozen/shared.hpp /frozen/shared.hpp\n'
        for _ in range(2):
            with patch.object(r, 'jobs', return_value=jobs), patch.object(Path, 'read_text', return_value=data), \
                    patch.object(Path, 'resolve', autospec=True, side_effect=lambda p: p) as resolve:
                self.assertEqual(r.dependencies(self.out, self.rs), {source, header})
                self.assertEqual(sum(call.args == (header,) for call in resolve.call_args_list), 1)
        with patch.object(r, 'jobs', return_value=jobs), patch.object(Path, 'read_text', return_value='object: /frozen/shared.hpp\n'):
            with self.assertRaisesRegex(ValueError, 'dependency source membership'):
                r.dependencies(self.out, self.rs)

    def test_exact_foreign_throw_omission(self):
        g=r.generated(self.old)
        self.assertEqual(g['protocol-rust.cpp'],r.rename(self.old['protocol.cpp'].replace(r.OMITTED,'')))
        self.assertIn('static uint32_t throws(',g['protocol-rust.cpp'])
        self.assertIn('star_file_run(34,&dummy,throws)',g['protocol-rust.cpp'])
        self.assertIn('star_file_run(0,nullptr,throws)',g['protocol-rust.cpp'])
        self.assertIn(r.rename(r.OMITTED),g['protocol-native.cpp'])
        for text in [self.old['protocol.cpp'].replace(r.OMITTED,''),self.old['protocol.cpp']+r.OMITTED]:
            with self.assertRaises(ValueError):r.generated({**self.old,'protocol.cpp':text})

    def test_only_named_selector_and_fresh_113_each(self):
        jobs=r.jobs(self.out,self.rs)
        for backend in ('native','rust'):
            core=[j for j in jobs if j[0].startswith(backend+'/') and j[0].split('/')[1].isdigit()]
            self.assertEqual(len(core),113)
            self.assertEqual([str(j[3]) for j in core],[x['source'] for x in self.rs])
            for _,_,flags,_ in core:
                self.assertEqual([f for f in flags if 'STAR_USE_RUST' in f],[] if backend=='native' else ['-DSTAR_USE_RUST_FILE'])
        # Moving File in the recipe must move object selection with it.
        moved=list(reversed(self.rs))
        p=dict(r.plan(self.out,moved,self.libs,r.ARCHIVE))
        self.assertEqual(p['symbols-rust'][-1],str(self.out/'rust'/(str(r.index(moved,'StarFile.cpp'))+'.o')))

    def test_link_membership_plan(self):
        p=dict(r.plan(self.out,self.rs,self.libs,r.ARCHIVE))
        for b in ('native','rust'):
            for name in ('corpus','supplement','removal'):
                argv=p['link-'+b+'-'+name]
                objs=[s for s in argv if s.endswith('.o')]
                self.assertEqual(len(objs),114)
                self.assertTrue(all(s.startswith(str(self.out)+'/') for s in objs))
                self.assertEqual(argv.count(str(r.ARCHIVE)),1)
            rem=p['link-'+b+'-removal']
            self.assertNotIn(str(self.out/b/(str(r.index(self.rs,'StarFile_unix.cpp'))+'.o')),rem)
            self.assertIn(str(self.out/b/'platform.o'),rem)
            self.assertEqual(sum(n.startswith(b+'-removal-') for n in p),12)
        self.assertNotIn(str(r.ARCHIVE),p['link-native-protocol'])
        self.assertIn(str(r.ARCHIVE),p['link-rust-protocol'])

    def test_counter_positive_bypass_corruptions(self):
        positive=''.join(f'{i} 3 2 1\n' for i in range(34)).encode()
        zero=''.join(f'{i} 0 0 0\n' for i in range(34)).encode()
        r.counts(positive,True);r.counts(zero,False)
        for data,kind in [(zero,True),(positive,False),(positive.replace(b'0 3 2 1',b'0 4 2 1'),True),(positive.split(b'\n',1)[1],True),(positive.replace(b'33 3',b'32 3'),True)]:
            with self.assertRaises(ValueError):r.counts(data,kind)

    def test_fixed_oracles(self):
        self.assertEqual(len(r.contract.expected().splitlines()),139)
        with self.assertRaises(ValueError):r.contract.check(r.contract.expected().split(b'\n',1)[1])
        with self.assertRaises(ValueError):r.contract.check(r.contract.expected().replace(b'default-mode\t0',b'default-mode\t1'))
        self.assertEqual(r.generated(self.old)['StarFile_unix.instrumented.cpp'].encode().replace(r.removal.NEW,r.removal.OLD),(r.LAB/'StarFile_unix.original.cpp').read_bytes())

    def test_archive_paths_separate(self):
        for p in r.ARCHIVES:self.assertEqual(r.select_archive(p),p)
        with self.assertRaises(ValueError):r.select_archive(r.BASE/'unqualified.a')
        a=r.plan(self.out,self.rs,self.libs,r.ARCHIVES[0]);b=r.plan(self.out,self.rs,self.libs,r.ARCHIVES[1])
        self.assertNotEqual(a,b)

    def test_apple_map_non_utf8_symbols(self):
        raw=b'# Object files:\n[  1] /owned/one.o\n[  2] /owned/two.o\n# Sections:\n# Symbols:\n\xc0\xff\n'
        self.assertEqual(r.object_entries(raw),['/owned/one.o','/owned/two.o'])
        with self.assertRaises(ValueError):r.object_entries(raw.replace(b'# Object files:',b'# omitted:'))
        with self.assertRaises(UnicodeDecodeError):r.object_entries(raw.replace(b'/owned/one.o',b'/owned/\xff.o'))
        # Reject wrong actual object membership even if trailing symbols parse.
        plan=[('link-native-layout',['clang',str(self.out/'one.o'),'-o',str(self.out/'native/layout')])]
        with patch.object(Path,'read_bytes',return_value=raw):
            with self.assertRaisesRegex(ValueError,'actual ordered link objects'):
                r.link_membership(self.out,plan,r.ARCHIVE)

    def test_production_source_corruption_rejected(self):
        target=r.ROOT/'source/core/StarFile.cpp'
        real=Path.read_text
        def altered(path,*args,**kwargs):
            text=real(path,*args,**kwargs)
            return text+'\n' if path==target else text
        with patch.object(Path,'read_text',altered):
            with self.assertRaisesRegex(ValueError,'exact production branches'):r.authenticate()

if __name__=='__main__':unittest.main()
