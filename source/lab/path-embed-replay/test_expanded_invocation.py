import copy
from pathlib import Path
import unittest
from uuid import uuid4
from expanded_invocation import bind, parse, verify


class ExpandedInvocationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[3] / 'build/path-embed-link-witness-r1' / ('fixture-' + uuid4().hex)
        self.root.mkdir(parents=True)
        for name in ['ld', 'lto.dylib', 'native.o', 'library.a', 'runtime.a']:
            (self.root / name).write_bytes(name.encode())
        self.argv = [str(self.root / 'ld'), '-demangle', '-lto_library', str(self.root / 'lto.dylib'),
                     '-dynamic', '-arch', 'arm64', '-platform_version', 'macos', '27.0', '27.0',
                     '-syslibroot', str(self.root / 'SDK.sdk'), '-o', str(self.root / 'binary'),
                     str(self.root / 'native.o'), str(self.root / 'library.a'),
                     '-framework', 'Foundation', '-weak_framework', 'UniformTypeIdentifiers',
                     '-ldl', '-lc++', '-lSystem', str(self.root / 'runtime.a'),
                     '-map', str(self.root / 'binary.map'), '-t', '-trace_implicit_libraries']
        self.baseline = bind(self.argv)

    def test_driver_runtime_and_plugin_prebound_outputs_never_inputs(self):
        files = {Path(f['requested']).name for f in self.baseline['files']}
        self.assertEqual(files, {'ld', 'lto.dylib', 'native.o', 'library.a', 'runtime.a'})
        (self.root / 'binary').write_bytes(b'new output')
        (self.root / 'binary.map').write_bytes(b'new map')
        verify(self.baseline, self.argv)

    def test_omitted_driver_runtime_and_implicit_root_rejected(self):
        for token in [str(self.root / 'runtime.a'), '-lSystem', '-lc++']:
            changed = [x for x in self.argv if x != token]
            with self.subTest(token=token), self.assertRaises(ValueError):
                verify(self.baseline, changed)

    def test_runtime_bytes_changed_even_after_coherent_rehash(self):
        (self.root / 'runtime.a').write_bytes(b'changed')
        self.assertNotEqual(bind(self.argv), self.baseline)
        with self.assertRaises(ValueError):
            verify(self.baseline, self.argv)

    def test_intermediate_alias_target_change_detected(self):
        original = self.root / 'runtime.a'
        original.rename(self.root / 'retained-runtime.a')
        original.symlink_to('retained-runtime.a')
        baseline = bind(self.argv)
        original.rename(self.root / 'retained-alias')
        original.symlink_to('library.a')
        with self.assertRaises(ValueError):
            verify(baseline, self.argv)

    def test_unknown_flag_response_file_and_duplicate_output_rejected(self):
        for changed in [self.argv + ['-filelist', '/foreign'], self.argv + ['@response'],
                        self.argv + ['-o', '/extra-output'], self.argv + ['-arch', 'arm64']]:
            with self.subTest(changed=changed[-2:]), self.assertRaises(ValueError):
                parse(changed)
        changed = list(self.argv);changed[changed.index('-map')] = '-o'
        with self.assertRaises(ValueError):
            parse(changed)

    def test_nonregular_input_and_boolean_alias_rejected(self):
        import os
        fifo = self.root / 'fifo.a';os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            bind(self.argv + [str(fifo)])
        changed = copy.deepcopy(self.baseline);changed['files'][0]['size'] = True
        with self.assertRaises(ValueError):
            verify(changed, self.argv)

    def test_input_output_collision_and_relative_input_rejected(self):
        changed = list(self.argv);changed[changed.index('-o') + 1] = str(self.root / 'native.o')
        with self.assertRaises(ValueError):
            parse(changed)
        with self.assertRaises(ValueError):
            parse(self.argv + ['relative.o'])


if __name__ == '__main__':
    unittest.main()
