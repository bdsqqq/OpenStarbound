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

    def test_exact_native_repair_and_owned_authentication(self):
        paths, originals = [], {}
        for i, source in enumerate(seal.OWNED):
            p = self.root / source.name
            p.write_bytes(source.read_bytes())
            paths.append(p)
            text = p.read_text()
            if i < 2:
                text = seal.branches(text, i == 1)[1]
                if i == 0:
                    text = text.replace(seal.NATIVE_FILL_EDIT[1], seal.NATIVE_FILL_EDIT[0])
                else:
                    text = text.replace(seal.NATIVE_COPY_EDIT[1], seal.NATIVE_COPY_EDIT[0])
                    # Build the exact proposed OFF header without requiring a
                    # concurrent production write or consulting git in fixtures.
                    on, _ = seal.branches(p.read_text(), True)
                    repaired = seal.exact_edit(text, seal.NATIVE_COPY_EDIT)
                    p.write_text('#pragma once\n#ifdef STAR_USE_RUST_BYTE_ARRAY\n' + on
                                 + '#else\n' + repaired.removeprefix('#pragma once\n') + '#endif\n')
            elif i == 2:
                for token in ('option(STAR_USE_RUST_BYTE_ARRAY "Use experimental Rust ByteArray controllers" OFF)\n',
                              'if(STAR_USE_RUST_BYTE_ARRAY)\n  add_compile_definitions(STAR_USE_RUST_BYTE_ARRAY)\nendif()\n\n',
                              ' OR STAR_USE_RUST_BYTE_ARRAY'):
                    text = text.replace(token, '')
            else:
                text = text.removesuffix('\nmod byte_array;\npub use byte_array::{star_byte_array_call_count, star_byte_array_run, StarByteArrayHost};\n')
            originals[p] = text
        hashes = {str(p): seal.hashlib.sha256(t.encode()).hexdigest() for p, t in originals.items()}
        with patch.object(seal, 'OWNED', paths), patch.object(seal, 'original', side_effect=originals.__getitem__):
            seal.check_owned(hashes)
            for digest in ('0' * 64, False):
                with self.assertRaisesRegex(ValueError, 'original identity'):
                    seal.check_owned(dict(hashes, **{str(paths[0]): digest}))
            header = paths[1].read_text()
            before, after = seal.NATIVE_COPY_EDIT
            for bad in (header.replace(after, before), header.replace(after, after + '\n' + after),
                        header + '// unrelated\n', header.replace(after, after.replace('len != 0', 'len > 1'))):
                with self.subTest(header=bad[-100:]):
                    paths[1].write_text(bad)
                    with self.assertRaises(ValueError):
                        seal.check_owned(hashes)
            paths[1].write_text(header)
            paths[0].write_text(paths[0].read_text().replace(seal.NATIVE_FILL_EDIT[1], seal.NATIVE_FILL_EDIT[0]))
            with self.assertRaisesRegex(ValueError, 'repaired native OFF'):
                seal.check_owned(hashes)
            paths[0].write_text(paths[0].read_text().replace(seal.NATIVE_FILL_EDIT[0], seal.NATIVE_FILL_EDIT[1])
                                .replace('  if (m_size != 0)', '  if (m_size > 1)'))
            with self.assertRaisesRegex(ValueError, 'repaired native OFF'):
                seal.check_owned(hashes)
        with self.assertRaisesRegex(ValueError, 'unique exact repair'):
            seal.exact_edit(seal.NATIVE_FILL_EDIT[0] * 2, seal.NATIVE_FILL_EDIT)

    def test_exact_host_repair(self):
        p = self.root / 'host.hpp'
        p.write_bytes(seal.NEW[0].read_bytes())
        old = p.read_text().replace(seal.HOST_FILL_EDIT[1], seal.HOST_FILL_EDIT[0]).replace(
            seal.HOST_COPY_EDIT[1], seal.HOST_COPY_EDIT[0]).encode()
        repaired = seal.exact_edit(seal.exact_edit(old.decode(), seal.HOST_FILL_EDIT), seal.HOST_COPY_EDIT)
        p.write_text(repaired)
        with patch.object(seal, 'NEW', [p]), patch.object(seal, 'revision_source', return_value=old):
            seal.check_host()
            before, after = seal.HOST_COPY_EDIT
            for bad in (repaired.replace(after, before), repaired.replace(after, after + '\n' + after),
                        repaired + '// unrelated\n', repaired.replace('if(d==0)', 'if(d<=1)'),
                        repaired.replace('need(b<=ByteArrayNativeAccess::size(o));', ''),
                        repaired.replace('std::memcpy(ByteArrayNativeAccess::data(o)+b,c.input,d)',
                                         'std::memcpy(ByteArrayNativeAccess::data(o),c.input,d)')):
                p.write_text(bad)
                with self.assertRaisesRegex(ValueError, 'only host empty fill'):
                    seal.check_host()
            p.write_bytes(old)
            with self.assertRaisesRegex(ValueError, 'only host empty fill'):
                seal.check_host()
            p.write_text(seal.exact_edit(old.decode(), seal.HOST_FILL_EDIT) + '// unrelated\n')
            with self.assertRaisesRegex(ValueError, 'only host empty fill'):
                seal.check_host()
        with patch.object(seal, 'NEW', [p]), patch.object(seal, 'revision_source', return_value=old + b'bad'):
            with self.assertRaisesRegex(ValueError, 'original host identity'):
                seal.check_host()

    def test_copy_repair_sites_are_unique(self):
        for edit in (seal.NATIVE_COPY_EDIT, seal.HOST_COPY_EDIT):
            for old in ('', edit[0] * 2):
                with self.assertRaisesRegex(ValueError, 'unique exact repair'):
                    seal.exact_edit(old, edit)

    def test_fixture_receipts_historical_and_fresh(self):
        p = self.root / 'fixture.cpp'
        old, current = b'old fixture\n', b'complete accepted fixture\n'
        hashes = tuple(seal.hashlib.sha256(x).hexdigest() for x in (old, current))
        p.write_bytes(current)
        with patch.object(seal, 'FIXTURES', {p: hashes}), \
             patch.object(seal, 'original', return_value=old.decode()), \
             patch.object(seal, 'revision_source', return_value=current):
            for digest in hashes:
                seal.check_fixtures({str(p): digest}, required=True)
            seal.check_fixtures({str(p): hashes[1]}, fresh=True, required=True)
            for digest in (hashes[0], '0' * 64, False):
                with self.assertRaisesRegex(ValueError, 'recorded fixture'):
                    seal.check_fixtures({str(p): digest}, fresh=True, required=True)
            for digest in ('0' * 64, False):
                with self.assertRaisesRegex(ValueError, 'recorded fixture'):
                    seal.check_fixtures({str(p): digest})
            seal.check_fixtures({})
            with self.assertRaisesRegex(ValueError, 'recorded fixture'):
                seal.check_fixtures({}, required=True)
            p.write_bytes(current + b'// unrelated')
            with self.assertRaisesRegex(ValueError, 'accepted fixture bytes'):
                seal.check_fixtures({str(p): seal.sha(p)})

    def test_build_fixture_exact_profile_delta(self):
        current = seal.BUILD_FIXTURE.read_bytes()
        accepted = current.decode().replace(seal.BUILD_FIXTURE_EDIT[1], seal.BUILD_FIXTURE_EDIT[0]).encode()
        p = self.root / 'build.sh'; p.write_bytes(current)
        old = b'historical build fixture\n'
        hashes = (seal.hashlib.sha256(old).hexdigest(), seal.sha(p))
        with patch.object(seal, 'BUILD_FIXTURE', p), patch.object(seal, 'FIXTURES', {p: hashes}), \
             patch.object(seal, 'original', return_value=old.decode()), \
             patch.object(seal, 'revision_source', return_value=accepted):
            seal.check_fixtures({str(p): hashes[1]}, fresh=True, required=True)
            p.write_bytes(current + b'\n# unrelated\n')
            with self.assertRaisesRegex(ValueError, 'accepted fixture bytes'):
                seal.check_fixtures({str(p): seal.sha(p)}, fresh=True, required=True)

    def buffer_fixture(self):
        current = seal.BUFFER_HOST.read_bytes()
        before, after = seal.BUFFER_GUARD_EDIT
        old = current.decode().replace(after, before).encode()
        self.assertEqual(seal.hashlib.sha256(old).hexdigest(), seal.BUFFER_HOST_HASHES[0])
        p = self.root / 'StarBufferHost.hpp'
        p.write_bytes(current)
        return p, old, current

    def test_buffer_historical_and_fresh_exact_receipts(self):
        p, old, current = self.buffer_fixture()
        with patch.object(seal, 'BUFFER_HOST', p), patch.object(seal, 'revision_source', return_value=old) as source:
            for digest in seal.BUFFER_HOST_HASHES:
                seal.check_buffer_host({str(p): digest}, required=True)
            seal.check_buffer_host({str(p): seal.sha(p)}, fresh=True, required=True)
            source.assert_called_with(p, '67ed3547')
            for digest in (seal.BUFFER_HOST_HASHES[0], '0' * 64, False):
                with self.assertRaisesRegex(ValueError, 'recorded Buffer host'):
                    seal.check_buffer_host({str(p): digest}, fresh=True, required=True)
            with self.assertRaisesRegex(ValueError, 'recorded Buffer host'):
                seal.check_buffer_host({str(p): '0' * 64})
            with self.assertRaisesRegex(ValueError, 'recorded Buffer host'):
                seal.check_buffer_host({}, required=True)
        with patch.object(seal, 'BUFFER_HOST', p), patch.object(seal, 'revision_source', return_value=old + b'// unrelated'):
            with self.assertRaisesRegex(ValueError, 'original Buffer host'):
                seal.check_buffer_host({str(p): seal.sha(p)})

    def test_buffer_rejects_header_drift_even_with_matching_receipt(self):
        p, old, current = self.buffer_fixture()
        text = current.decode()
        mutants = [text + '// unrelated header edit\n',
                   text.replace('ByteArrayNativeAccess::size(live)', 'ByteArrayNativeAccess::capacity(live)'),
                   text.replace('  if(c.param&&arrayOverlaps(*c.param))return false;\n', ''),
                   text.replace('  if(!out||a%alignof(uint64_t)||a>UINTPTR_MAX-sizeof(uint64_t))return false;\n', '')]
        with patch.object(seal, 'BUFFER_HOST', p), patch.object(seal, 'revision_source', return_value=old):
            for mutant in mutants:
                self.assertNotEqual(mutant, text)
                p.write_text(mutant)
                with self.subTest(mutant=mutant[-80:]), self.assertRaisesRegex(ValueError, 'only Buffer safeOutput'):
                    seal.check_buffer_host({str(p): seal.sha(p)}, fresh=True)

    def test_buffer_baseline_delta_preserves_other_input_rejection(self):
        p, old, current = self.buffer_fixture()
        other = self.root / 'other.hpp'
        other.write_text('unchanged')
        owned = [self.root / 'owned.cpp']
        owned[0].write_text('owned')
        baseline = dict(status='ACCEPTED_NATIVE_BEFORE_PRODUCTION_MUTATION',
                        owned_before={str(owned[0]): 'original'},
                        bindings={str(p): seal.BUFFER_HOST_HASHES[0], str(other): seal.sha(other)})
        fresh = {str(p): seal.sha(p), str(other): seal.sha(other), str(owned[0]): seal.sha(owned[0])}
        # Isolate unrelated existing contracts; exercise real rehash/subset and
        # guard reconstruction against temporary files, without any native tool.
        with patch.object(seal, 'BUFFER_HOST', p), patch.object(seal, 'revision_source', return_value=old), \
             patch.object(seal, 'OWNED', owned), patch.object(seal, 'NEW', []), \
             patch.object(seal, 'check_inventory_test'), patch.object(seal, 'check_fixtures'), \
             patch.object(seal, 'check_owned'), patch.object(seal, 'check_host'):
            seal.check_baseline(baseline, fresh)
            seal.rehash_compiler_bindings(fresh, fresh=True)
            with self.assertRaisesRegex(ValueError, 'recorded Buffer host'):
                seal.check_baseline(baseline, dict(fresh, **{str(p): seal.BUFFER_HOST_HASHES[0]}))
            with self.assertRaisesRegex(ValueError, 'recorded Buffer host'):
                seal.check_baseline(dict(baseline, bindings=dict(baseline['bindings'], **{str(p): '0' * 64})), fresh)
            with self.assertRaises(ValueError):
                seal.check_baseline(baseline, dict(fresh, **{str(other): '0' * 64}))
            other.write_text('drift')
            with self.assertRaisesRegex(ValueError, 'binding drift'):
                seal.check_baseline(baseline, fresh)
            with self.assertRaisesRegex(ValueError, 'binding drift'):
                seal.rehash_compiler_bindings(fresh, fresh=True)

    def test_own_source_and_test_bindings(self):
        code = seal.verifier_bindings()
        self.assertIn(str(Path(__file__).resolve()), code)
        self.assertIn(str(Path(seal.__file__).resolve()), code)
        seal.rehash(code)


if __name__ == '__main__':
    unittest.main()
