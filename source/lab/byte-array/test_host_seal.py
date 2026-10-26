"""Synthetic artifact sensitivity only; these tests execute no native program."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import host_seal as seal


class HostSealTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def recipes(self):
        return [dict(object=f'/configured/{i}.o', compiler='/compiler', flags=['-DFAKE'],
                     source='/source/StarByteArray.cpp' if i == 48 else f'/source/unit{i}.c')
                for i in range(113)]

    def native_recipe(self):
        return Path('/compiler'), ['-DFAKE'], [], []

    def command(self):
        exe = self.root / 'compiler'
        exe.write_bytes(b'synthetic compiler image; never executed')
        argv = [str(exe), '-ivfsoverlay', str(self.root / 'overlay.json'), '-c', 'probe.cpp']
        row = dict(name='compile-probe', command=argv, executable=str(exe), before=seal.sha(exe),
                   after=seal.sha(exe), returncode=0)
        for ext in ('stdout', 'stderr'):
            p = self.root / ('compile-probe.' + ext)
            p.write_bytes(b'')
            row[ext] = seal.sha(p)
        seal.stage.dump(self.root / 'compile-probe.command.json', row)
        return row, [('compile-probe', argv)]

    def test_positive_command_and_exact_247_configured_sequence(self):
        row, expected = self.command()
        seal.check_commands(self.root, [row], expected)
        with patch.object(seal.stage, 'recipe', return_value=self.native_recipe()):
            jobs, commands = seal.jobs_and_commands(self.root, self.recipes())
        self.assertEqual(len(jobs), 119)
        self.assertEqual(len(commands), 247)
        self.assertEqual(len(set(n for n, _ in commands)), 247)

    def test_missing_compile(self):
        _, expected = self.command()
        with self.assertRaisesRegex(ValueError, 'sequence'):
            seal.check_commands(self.root, [], expected)

    def test_missing_overlay_argument(self):
        row, expected = self.command()
        bad = copy.deepcopy(row)
        del bad['command'][1:3]
        with self.assertRaisesRegex(ValueError, 'exact configured command'):
            seal.check_commands(self.root, [bad], expected)

    def test_unlisted_execution_receipt(self):
        row, expected = self.command()
        seal.stage.dump(self.root / 'native-probe.command.json', {'command': ['lab']})
        with self.assertRaisesRegex(ValueError, 'command mirrors'):
            seal.check_commands(self.root, [row], expected)

    def test_unknown_command(self):
        row, expected = self.command()
        row['name'] = 'unrecorded-command'
        with self.assertRaisesRegex(ValueError, 'sequence'):
            seal.check_commands(self.root, [row], expected)

    def test_native_probe_in_compiler_phase(self):
        row, expected = self.command()
        row['command'] = [str(self.root / 'lab')]
        with self.assertRaisesRegex(ValueError, 'exact configured command'):
            seal.check_commands(self.root, [row], expected)

    def test_bool_exit_is_not_integer_zero(self):
        row, expected = self.command()
        row['returncode'] = False
        with self.assertRaisesRegex(ValueError, 'integer zero'):
            seal.check_commands(self.root, [row], expected)

    def test_bool_scope_is_not_integer_count(self):
        bad = dict(seal.SCOPE, native_executions=False)
        with self.assertRaises(ValueError):
            seal.equal(bad, seal.SCOPE, 'typed count')

    def test_parent_binding_removed(self):
        with self.assertRaisesRegex(ValueError, 'parent'):
            seal.subset({'/parent': '0' * 64}, {}, 'parent closure')

    def test_transitive_dependency_removed(self):
        dep = self.root / 'probe.d'
        dep.write_text('probe.o: /transitive/header.hpp\n')
        paths = seal.dependency_paths(dep)
        self.assertEqual(paths, ['/transitive/header.hpp'])
        with self.assertRaisesRegex(ValueError, 'dependency'):
            seal.check_dependencies(self.root, [['compiler', [], 'probe.cpp', 'probe']], {})

    def test_missing_abi_member_despite_equal_helper_count(self):
        original = b''.join(b'000 T Star::ByteArray::m' + str(i).encode() + b'()\n' for i in range(33))
        seal.host_diagnostic.required_abi(original, original + b'000 T Star::ByteArrayHost::extra()\n')
        wrong = b'\n'.join(original.splitlines()[1:]) + b'\n000 T Star::ByteArrayHost::extra()\n'
        with self.assertRaisesRegex(ValueError, 'missing original'):
            seal.host_diagnostic.required_abi(original, wrong)

    def test_source_route_gap(self):
        header = 'class ByteArray {\n};'
        body = ''.join('execute(%d, x);' % i for i in range(56))
        seal.check_routes(header, body, header)
        with self.assertRaisesRegex(ValueError, '56 source routes'):
            seal.check_routes(header, body.replace('execute(55, x);', ''), header)

    def archive(self):
        data = b'!<arch>\n'
        names = []
        for i in range(113):
            name = str(i) + '.o'
            names.append(name.encode())
            payload = ('object %d' % i).encode()
            (self.root / name).write_bytes(payload)
            header = (f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(payload):<10}`\n').encode()
            self.assertEqual(len(header), 60)
            data += header + payload + (b'\n' if len(payload) % 2 else b'')
        (self.root / 'prototype-core.a').write_bytes(data)
        (self.root / 'archive-table.stdout').write_bytes(b'\n'.join(names) + b'\n')

    def test_archive_object_bytes(self):
        self.archive()
        seal.check_archive(self.root)
        (self.root / '42.o').write_bytes(b'wrong object bytes')
        with self.assertRaisesRegex(ValueError, 'member bytes'):
            seal.check_archive(self.root)

    def write_map(self, objects):
        data = b'# Object files:\n' + b''.join(b'[%d] ' % i + p + b'\n' for i, p in enumerate(objects)) + b'# Sections:\n'
        (self.root / 'lab.map').write_bytes(data)

    def test_legacy_and_wrong_map_routes(self):
        good = [str(self.root / p).encode() for p in ('lab.o', 'controller.o', 'prototype-core.a(48.o)')]
        with patch.object(seal, 'configured_recipes', return_value=self.recipes()), \
             patch.object(seal.stage, 'recipe', return_value=self.native_recipe()):
            self.write_map(good)
            seal.check_map(self.root, 'lab')
            for bad in (good + [b'/old/native-core.a(StarByteArray.cpp.o)'],
                        [good[0], str(self.root / 'signed.o').encode(), good[2]]):
                self.write_map(bad)
                with self.assertRaises(ValueError):
                    seal.check_map(self.root, 'lab')

    def test_verifier_binds_own_source_and_tests(self):
        bindings = seal.verifier_bindings()
        self.assertIn(str(Path(seal.__file__).resolve()), bindings)
        self.assertIn(str(Path(__file__).resolve()), bindings)
        seal.rehash(bindings)


if __name__ == '__main__':
    unittest.main()
