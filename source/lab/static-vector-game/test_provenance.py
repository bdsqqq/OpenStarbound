"""Pure small-file controls; no CLI child, compiler, tool probe or game launch."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('_sv_bounded_provenance', Path(__file__).with_name('provenance.py'))
pv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pv)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        patcher = patch.object(pv.ad, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.source = self.put(self.root / 'source/game/example.cpp', 'int fixture;\n')
        self.side = pv.ad.build_root() / 'reference'
        self.snapshot = self.side / 'build-inputs.json'
        self.build = self.side / 'cmake'
        self.binary = self.put(self.side / 'bin/starbound', 'fake binary, never executable')
        self.put(self.build / 'CMakeCache.txt', 'STAR_USE_RUST_STATIC_VECTOR:BOOL=OFF\n')
        self.put(self.build / 'compile_commands.json', json.dumps([
            {'file': str(self.source), 'directory': str(self.build)}]))
        # Any accidental future tool probe fails, rather than spawning a child.
        guard = patch.object(pv.bp.subprocess, 'run', side_effect=AssertionError('subprocess forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def put(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def argv(self, phase):
        args = [phase, '--source-root', str(self.root)]
        if phase in ('begin', 'configured', 'seal'):
            args += ['--snapshot', str(self.snapshot)]
        if phase == 'begin':
            args += ['--build-dir', str(self.build)]
        if phase in ('seal', 'verify'):
            args += ['--binary', str(self.binary)]
        return args

    def invoke(self, phase, argv=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            pv.main(self.argv(phase) if argv is None else argv)
        return out.getvalue()

    def fails(self, phase, argv=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as failure:
                pv.main(self.argv(phase) if argv is None else argv)
        self.assertNotEqual(failure.exception.code, 0)
        self.assertEqual(out.getvalue(), '')
        self.assertTrue(err.getvalue())
        return err.getvalue()

    def prepare(self):
        self.invoke('begin')
        self.invoke('configured')

    def replace_same_bytes(self, path):
        before = path.stat()
        replacement = path.with_name('fixture-replacement')
        replacement.write_bytes(path.read_bytes())
        os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
        os.replace(replacement, path)
        self.assertNotEqual(before.st_ino, path.stat().st_ino)

    def test_all_phases_keep_payload_and_exact_stdout_and_file_bytes(self):
        for role in ('reference', 'candidate'):
            with self.subTest(role=role):
                self.side = pv.ad.build_root() / role
                self.snapshot = self.side / 'build-inputs.json'
                self.build = self.side / 'cmake'
                self.binary = self.put(self.side / 'bin/starbound', 'fixture binary')
                self.put(self.build / 'CMakeCache.txt', 'STAR_USE_RUST_STATIC_VECTOR:BOOL=OFF\n')
                self.put(self.build / 'compile_commands.json', json.dumps([
                    {'file': str(self.source), 'directory': str(self.build)}]))
                expected = pv.bp.begin(self.root, self.build)
                self.assertEqual(self.invoke('begin'), '')
                self.assertEqual(self.snapshot.read_bytes(), (json.dumps(expected, indent=2, sort_keys=True) + '\n').encode())
                expected = pv.bp.configured(expected, self.root)
                self.assertEqual(self.invoke('configured'), '')
                self.assertEqual(self.snapshot.read_bytes(), (json.dumps(expected, indent=2, sort_keys=True) + '\n').encode())
                with patch.object(pv.bp, '_write', side_effect=AssertionError('legacy bypass')):
                    stdout = self.invoke('seal')
                    proof = json.loads(stdout)
                    self.assertEqual(stdout, json.dumps(proof, sort_keys=True) + '\n')
                    self.assertEqual(self.invoke('verify'), stdout)
                sidecar = pv.bp.sidecar(self.binary)
                self.assertEqual(sidecar.read_bytes(), (json.dumps(proof, indent=2, sort_keys=True) + '\n').encode())
                self.assertLess(sidecar.stat().st_size, pv.ad.controller_limit(sidecar))
                self.assertEqual({k: proof[k] for k in expected}, expected)

    def test_configured_passes_original_content_pin(self):
        self.invoke('begin')
        original = pv.bounded_input(self.snapshot)[0]
        with patch.object(pv.ad, 'write_common', wraps=pv.ad.write_common) as writer:
            self.invoke('configured')
        self.assertEqual(writer.call_args.args[2], original)

    def test_configured_same_byte_inode_replacement_before_publication_fails(self):
        self.invoke('begin')
        configured = pv.bp.configured
        def change(value, root):
            result = configured(value, root)
            self.replace_same_bytes(self.snapshot)
            return result
        with patch.object(pv.bp, 'configured', side_effect=change), patch.object(pv.ad, 'write_common') as writer:
            self.assertIn('changed', self.fails('configured'))
            writer.assert_not_called()
        self.assertNotIn('compile_source_files', json.loads(self.snapshot.read_text()))

    def test_seal_same_byte_snapshot_replacement_before_publication_fails(self):
        self.prepare()
        hash_file = pv.bp._hash
        def change(path):
            result = hash_file(path)
            if path == self.binary:
                self.replace_same_bytes(self.snapshot)
            return result
        with patch.object(pv.bp, '_hash', side_effect=change), patch.object(pv.ad, 'write_common') as writer:
            self.assertIn('changed', self.fails('seal'))
            writer.assert_not_called()
        self.assertFalse(pv.bp.sidecar(self.binary).exists())

    def test_verify_same_byte_sidecar_replacement_fails_without_stdout(self):
        self.prepare()
        self.invoke('seal')
        verify = pv.bp.verify
        def change(binary, root):
            result = verify(binary, root)
            self.replace_same_bytes(pv.bp.sidecar(binary))
            return result
        with patch.object(pv.bp, 'verify', side_effect=change):
            self.assertIn('changed', self.fails('verify'))

    def test_oversize_snapshot_rejected_before_any_identity_hash_or_read(self):
        self.put(self.snapshot, 'x' * 33)
        with patch.object(pv.ad, 'controller_limit', return_value=32), \
                patch.object(pv.ad, 'sha', side_effect=AssertionError('unbounded hash')), \
                patch.object(pv.bp, '_read', side_effect=AssertionError('unbounded read')):
            self.assertIn('byte limit', self.fails('configured'))
            self.assertIn('byte limit', self.fails('seal'))

    def test_oversize_sidecar_rejected_before_verify_or_hash(self):
        self.put(pv.bp.sidecar(self.binary), 'x' * 33)
        with patch.object(pv.ad, 'controller_limit', return_value=32), \
                patch.object(pv.ad, 'sha', side_effect=AssertionError('unbounded hash')), \
                patch.object(pv.bp, 'verify', side_effect=AssertionError('unbounded verify')):
            self.assertIn('byte limit', self.fails('verify'))

    def test_hardlinked_snapshot_rejected_before_hash(self):
        self.invoke('begin')
        os.link(self.snapshot, self.side / 'fixture-link')
        with patch.object(pv.ad, 'sha', side_effect=AssertionError('alias hash')):
            self.assertIn('regular', self.fails('configured'))

    def test_nonregular_snapshot_rejected_before_hash(self):
        self.snapshot.mkdir()
        with patch.object(pv.ad, 'sha', side_effect=AssertionError('directory hash')):
            self.assertIn('regular', self.fails('configured'))

    def test_symlink_input_rejected_before_hash(self):
        self.snapshot.symlink_to(self.source)
        with patch.object(pv.ad, 'sha', side_effect=AssertionError('symlink hash')):
            self.fails('configured')

    def test_symlink_parent_rejected(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.side, target_is_directory=True)
        args = self.argv('begin')
        args[args.index('--snapshot') + 1] = str(alias / 'build-inputs.json')
        self.fails('begin', args)

    def test_hardlinked_binary_rejected_before_seal(self):
        self.prepare()
        os.link(self.binary, self.side / 'fixture-binary-link')
        with patch.object(pv.bp, 'seal', side_effect=AssertionError('alias binary')):
            self.fails('seal')

    def test_exact_paths_roles_and_no_extraneous_fields(self):
        cases = [
            ('begin', '--source-root', str(self.root.parent)),
            ('begin', '--snapshot', str(self.side / 'other.json')),
            ('begin', '--snapshot', str(pv.ad.build_root() / 'wrong/build-inputs.json')),
            ('begin', '--build-dir', str(self.side / 'other-cmake')),
            ('seal', '--binary', str(pv.ad.build_root() / 'candidate/bin/starbound')),
            ('verify', '--binary', str(self.side / 'bin/not-starbound')),
        ]
        for phase, flag, value in cases:
            with self.subTest(phase=phase, flag=flag, value=value):
                args = self.argv(phase)
                args[args.index(flag) + 1] = value
                self.fails(phase, args)
        for phase, extra in [('begin', ['--binary', str(self.binary)]),
                             ('configured', ['--build-dir', str(self.build)]),
                             ('seal', ['--build-dir', str(self.build)]),
                             ('verify', ['--snapshot', str(self.snapshot)]),
                             ('begin', ['--unknown', 'flag'])]:
            with self.subTest(phase=phase, extra=extra):
                self.fails(phase, self.argv(phase) + extra)
        self.fails('begin', ['begin', '--source-root', str(self.root)])

    def test_payload_cannot_redirect_cmake_inputs(self):
        self.invoke('begin')
        value = json.loads(self.snapshot.read_text())
        value['build_dir'] = str(self.root / 'unrelated')
        self.snapshot.write_text(json.dumps(value))
        with patch.object(pv.bp, 'configured', side_effect=AssertionError('redirected read')):
            self.fails('configured')

    def test_missing_inputs_fail(self):
        self.fails('configured')
        self.fails('seal')
        self.fails('verify')

    def test_stale_partial_blocks_begin_without_retry_or_cleanup(self):
        partial = self.put(self.snapshot.with_name('.build-inputs.json.partial'), 'retained failure')
        for _ in range(2):
            self.fails('begin')
        self.assertEqual(partial.read_text(), 'retained failure')
        self.assertFalse(self.snapshot.exists())
        self.assertEqual(list(self.side.glob('.*partial')), [partial])

    def test_new_only_begin_and_seal_cannot_overwrite(self):
        self.prepare()
        before = self.snapshot.read_bytes()
        self.fails('begin')
        self.assertEqual(self.snapshot.read_bytes(), before)
        self.invoke('seal')
        sidecar = pv.bp.sidecar(self.binary)
        before = sidecar.read_bytes()
        self.fails('seal')
        self.assertEqual(sidecar.read_bytes(), before)

    def test_wrong_original_pin_is_rejected(self):
        self.invoke('begin')
        identity, state = pv.bounded_input(self.snapshot)
        identity['sha256'] = '0' * 64
        before = self.snapshot.read_bytes()
        with patch.object(pv, 'bounded_input', return_value=(identity, state)):
            self.assertIn('identity mismatch', self.fails('configured'))
        self.assertEqual(self.snapshot.read_bytes(), before)

    def test_missing_injected_publication_fails(self):
        self.prepare()
        with patch.object(pv.bp, 'seal', return_value={'unpublished': True}):
            self.assertIn('did not publish', self.fails('seal'))
        self.assertFalse(pv.bp.sidecar(self.binary).exists())

    def test_overflow_control_detects_unsafe_unchecked_writer(self):
        value = {'oversize': 'x' * 128}
        with patch.object(pv.bp, 'begin', return_value=value), patch.object(pv.ad, 'controller_limit', return_value=32):
            self.assertIn('byte limit', self.fails('begin'))
            self.assertFalse(self.snapshot.exists())
            partial = self.snapshot.with_name('.build-inputs.json.partial')
            self.assertLessEqual(partial.stat().st_size, 32)
            # isolated unsafe control: the same test oracle sees the legacy bypass.
            with patch.object(pv.ad, 'write_common', side_effect=pv.bp._write):
                self.invoke('begin')
            self.assertGreater(self.snapshot.stat().st_size, 32)
            with self.assertRaisesRegex(ValueError, 'byte limit'):
                pv.bounded_input(self.snapshot)


if __name__ == '__main__':
    unittest.main()
