"""Read-only controls against an acquired positive baseline; never edit receipts."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import rust_run as runner

OUT = Path(os.environ.get('STRING_VIEW_QUALIFIED_OUTPUT',str(runner.BASE/'production-r2-cli'))).resolve()
if os.environ.get('STRING_VIEW_QUALIFIED_ARCHIVE'):
    runner.ARCHIVE=runner.select_archive(os.environ['STRING_VIEW_QUALIFIED_ARCHIVE'])


class Reconstruction(unittest.TestCase):
    def test_qualified_reconstruction(self):
        self.assertEqual(len(runner.generated(runner.authenticate())),3)

    def test_only_foreign_throw_invocation_removed(self):
        old=runner.authenticate(); generated=runner.generated(old)
        self.assertEqual(generated['protocol-native.cpp'].replace(runner.OMITTED.replace('sb_','star_'),''), generated['protocol-rust.cpp'])
        self.assertIn('uint32_t throwing(',generated['protocol-rust.cpp'])
        self.assertIn('UINTPTR_MAX-sizeof(uint64_t)+1',generated['protocol-rust.cpp'])
        self.assertIn('saved==std::current_exception()',generated['protocol-rust.cpp'])

    def test_duplicate_omission_rejected(self):
        old=runner.authenticate();old['host_test.cpp']+=runner.OMITTED
        with self.assertRaisesRegex(ValueError,'one foreign throw'):runner.generated(old)

    def test_archive_path_is_explicit_and_bounded(self):
        for p in runner.ARCHIVES:self.assertEqual(runner.select_archive(p),p)
        with self.assertRaisesRegex(ValueError,'unknown aggregate artifact path'):
            runner.select_archive(runner.BASE/'arbitrary.a')

    def test_fresh_selector_objects(self):
        rs,libs=runner.native.recipe();jobs=runner.jobs(OUT,rs)
        for mode in ('native','rust'):
            core=[job for job in jobs if job[0].startswith(mode+'/') and job[0].split('/')[1].isdigit()]
            self.assertEqual(len(core),113)
            for _,_,flags,_ in core:
                self.assertEqual([f for f in flags if 'STAR_USE_RUST' in f],[] if mode=='native' else ['-DSTAR_USE_RUST_STRING_VIEW'])
        self.assertEqual(len(runner.plan(OUT,rs,libs)),2*len(jobs)+22)


@unittest.skipUnless((OUT/'report.json').exists(),'fresh production acquisition required')
class ReceiptControls(unittest.TestCase):
    def test_positive_baseline(self):
        self.assertEqual(runner.verify(OUT)['status'],runner.STATUS)

    def bad_report(self,change,reason):
        original=Path.read_text
        report=json.loads(original(OUT/'report.json'));change(report)
        def read(path,*args,**kwargs):
            return json.dumps(report) if path==OUT/'report.json' else original(path,*args,**kwargs)
        with patch.object(Path,'read_text',read):
            with self.assertRaisesRegex(ValueError,reason):runner.verify(OUT)

    def test_known_bad_binding(self):
        self.bad_report(lambda q:q['bindings'].__setitem__(str(runner.ARCHIVE),'0'*64),'drift')

    def test_wrong_archive(self):
        self.bad_report(lambda q:q.__setitem__('archive',str(OUT/'wrong.a')),'sole archive identity')

    def test_missing_case(self):
        original=Path.read_bytes
        def read(path):
            data=original(path)
            return b''.join(data.splitlines(keepends=True)[:-1]) if path==OUT/'rust-corpus.stdout' else data
        with patch.object(Path,'read_bytes',read):
            with self.assertRaisesRegex(ValueError,'8332 exact cases'):runner.observations(OUT)

    def test_bypass_rejected(self):
        runner.host_run.counts(OUT/'native-corpus.stderr',False)
        with self.assertRaisesRegex(ValueError,'positive controller'):runner.host_run.counts(OUT/'native-corpus.stderr',True)


if __name__=='__main__':unittest.main()
