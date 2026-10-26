"""Portable synthetic rejection fixtures; no compiler database or native execution."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import rust_seal as seal


class RustSealTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.recipes = [dict(compiler='/compiler', flags=['-DNDEBUG'], object=f'/old/{i}.o',
            source=str(seal.CORE / 'StarByteArray.cpp') if i == 4 else f'/src/{i}.cpp') for i in range(113)]
        self.native = patch.object(seal.stage, 'recipe', return_value=('/compiler', ['-DNDEBUG'], [], []))
        self.native.start()
        self.addCleanup(self.native.stop)

    def test_mock_recipes_backend_commands(self):
        for backend, count in [('native', 115), ('rust', 116)]:
            jobs, cmds = seal.jobs_and_commands(self.root, self.recipes, backend, '/rust.a')
            self.assertEqual(len(jobs), count)
            self.assertEqual(len(cmds), count * 2 + (5 if backend == 'native' else 6))
            for name, argv in cmds:
                if name.startswith(('deps-', 'compile-')):
                    self.assertEqual('-DSTAR_USE_RUST_BYTE_ARRAY' in argv, backend == 'rust')
                    self.assertNotIn('-ivfsoverlay', argv)
            link = dict(cmds)['link-lab']
            self.assertLess(link.index(str(self.root / 'candidate-core.a')), link.index('/rust.a'))

    def test_missing_off_source(self):
        with self.assertRaisesRegex(ValueError, 'OFF source'):
            seal.branches('#ifdef STAR_USE_RUST_BYTE_ARRAY\non\n#endif\n')
        self.assertEqual(seal.branches('#pragma once\n#ifdef STAR_USE_RUST_BYTE_ARRAY\non\n#else\nold\n#endif\n', True), ('on\n', '#pragma once\nold\n'))

    def test_changed_unrelated_source(self):
        p = self.root / 'unrelated.cpp'
        p.write_text('old')
        baseline = dict(status='ACCEPTED_NATIVE_BEFORE_PRODUCTION_MUTATION',
            owned_before={str(x): '0' * 64 for x in seal.OWNED}, bindings={str(p): seal.sha(p)})
        p.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'binding drift'):
            seal.check_baseline(baseline, {})

    def test_bool_mode_and_scope(self):
        with self.assertRaisesRegex(ValueError, 'backend mode'):
            seal.jobs_and_commands(self.root, self.recipes, False, '/rust.a')
        with self.assertRaises(ValueError):
            seal.equal(dict(seal.SCOPE, native_executions=False), seal.SCOPE, 'typed scope')

    def test_protocol_removes_only_foreign_throw(self):
        expected = seal.protocol_source()
        self.assertNotIn('&c,throws)', expected)
        self.assertNotIn('static uint32_t throws(', expected)
        self.assertIn('throw &token', expected)
        self.assertIn('star_byte_array_run', expected)
        with self.assertRaises(ValueError):
            seal.equal(expected + ' CHECK(star_byte_array_run(SB_BA_CTOR,&c,throws)==3);\n', expected, 'foreign throw')

    def command_fixture(self):
        exe = self.root / 'compiler'
        exe.write_bytes(b'never executed')
        argv = [str(exe), '-DSTAR_USE_RUST_BYTE_ARRAY', '-c', 'real.cpp']
        row = dict(name='compile-0', command=argv, executable=str(exe), before=seal.sha(exe), after=seal.sha(exe), returncode=0)
        for ext in ('stdout', 'stderr'):
            p = self.root / ('compile-0.' + ext)
            p.write_bytes(b'')
            row[ext] = seal.sha(p)
        seal.stage.dump(self.root / 'compile-0.command.json', row)
        return row, [('compile-0', list(argv))]

    def test_missing_flag_and_bool_exit(self):
        row, expected = self.command_fixture()
        seal.host.check_commands(self.root, [row], expected)
        row['command'].remove('-DSTAR_USE_RUST_BYTE_ARRAY')
        with self.assertRaisesRegex(ValueError, 'exact configured command'):
            seal.host.check_commands(self.root, [row], expected)
        row['command'] = expected[0][1]
        row['returncode'] = False
        with self.assertRaisesRegex(ValueError, 'integer zero'):
            seal.host.check_commands(self.root, [row], expected)

    def write_map(self, extra='', symbols=True):
        objects = [str(self.root / 'lab.o'), str(self.root / 'candidate-core.a(4.o)'), '/rust.a(libstar_engine_ffi.a123.o)']
        if extra:
            objects.append(extra)
        text = '# Object files:\n' + ''.join(f'[{i}] {p}\n' for i, p in enumerate(objects)) + '# Sections:\n# Symbols:\n'
        if symbols:
            text += '0x100 0x10 [ 2] _star_byte_array_run\n0x110 0x10 [ 2] _star_byte_array_call_count\n'
        (self.root / 'lab.map').write_text(text)

    def test_cpp_controller_route_and_missing_rust_symbols(self):
        self.write_map()
        seal.check_map(self.root, 'lab', 'rust', '/rust.a', self.recipes)
        self.write_map(str(self.root / 'controller.o'))
        with self.assertRaisesRegex(ValueError, 'controller map'):
            seal.check_map(self.root, 'lab', 'rust', '/rust.a', self.recipes)
        self.write_map(symbols=False)
        with self.assertRaisesRegex(ValueError, 'actual Rust symbol route'):
            seal.check_map(self.root, 'lab', 'rust', '/rust.a', self.recipes)

    def test_archive_member_hash(self):
        data = b'!<arch>\n'
        names = []
        for i in range(113):
            name = f'{i}.o'
            names.append(name.encode())
            payload = f'object{i}'.encode()
            (self.root / name).write_bytes(payload)
            data += f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(payload):<10}`\n'.encode() + payload + (b'\n' if len(payload) % 2 else b'')
        (self.root / 'candidate-core.a').write_bytes(data)
        (self.root / 'archive-table.stdout').write_bytes(b'\n'.join(names) + b'\n')
        seal.check_archive(self.root)
        (self.root / '4.o').write_bytes(b'different')
        with self.assertRaisesRegex(ValueError, 'member bytes'):
            seal.check_archive(self.root)

    def test_changed_golden(self):
        (self.root / 'expected.jsonl').write_bytes(b'changed golden')
        with self.assertRaisesRegex(ValueError, 'golden corpus'):
            seal.check_generated(self.root, 'native')

    def inventory_fixture(self):
        current = seal.INVENTORY_TEST.read_text()
        old = current
        for before, after in reversed(seal.INVENTORY_EDITS):
            self.assertEqual(old.count(after), 1)
            old = old.replace(after, before, 1)
        p = self.root / 'test_contract.py'
        p.write_text(current)
        return p, old

    def test_exact_inventory_projection_old_and_new_receipts(self):
        p, old = self.inventory_fixture()
        with patch.object(seal, 'INVENTORY_TEST', p), patch.object(seal, 'original', return_value=old):
            for digest in ('45769897063cbc7d63b8bbbf86f3a13f87d4d63dde8b3ccd1f58151086e8a67d', seal.sha(p)):
                seal.rehash_compiler_bindings({str(p): digest})
            with self.assertRaisesRegex(ValueError, 'recorded inventory'):
                seal.rehash_compiler_bindings({str(p): '0' * 64})

    def test_inventory_unrelated_edit_is_not_exempt(self):
        p, old = self.inventory_fixture()
        p.write_text(p.read_text() + '\n# unrelated test edit\n')
        with patch.object(seal, 'INVENTORY_TEST', p), patch.object(seal, 'original', return_value=old):
            with self.assertRaisesRegex(ValueError, 'only native OFF'):
                seal.rehash_compiler_bindings({str(p): seal.sha(p)})

    def test_inventory_exception_does_not_exempt_other_inputs(self):
        p, old = self.inventory_fixture()
        other = self.root / 'unrelated.py'
        other.write_text('before')
        bindings = {str(p): seal.sha(p), str(other): seal.sha(other)}
        other.write_text('after')
        with patch.object(seal, 'INVENTORY_TEST', p), patch.object(seal, 'original', return_value=old):
            with self.assertRaisesRegex(ValueError, 'binding drift'):
                seal.rehash_compiler_bindings(bindings)

    def test_own_source_and_test_bindings(self):
        code = seal.verifier_bindings()
        self.assertIn(str(Path(__file__).resolve()), code)
        self.assertIn(str(Path(seal.__file__).resolve()), code)
        seal.rehash(code)


if __name__ == '__main__':
    unittest.main()
