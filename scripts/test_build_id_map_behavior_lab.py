"""Synthetic orchestration/dependency controls; NEVER invokes native tools."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

SPEC = importlib.util.spec_from_file_location('idmap_builder_under_test', Path(__file__).with_name('build-id-map-behavior-lab.py'))
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.scope = patch.object(b, 'ROOT', self.root)
        self.scope.start(); self.addCleanup(self.scope.stop)
        self.header = self.put('source/lab/behavior/id_map_scene.hpp', b'SYNTHETIC HEADER NOT A GAME')
        self.client = self.put('source/client/StarClientApplication.cpp', b'SYNTHETIC CLIENT')
        self.build = self.root / 'build/behavior/id-map-combined-r1'
        self.plan = dict(buildRoot=str(self.build), sdk='/SYNTHETIC-SDK', createdUTC='2000-01-01T00:00:00+00:00',
                         compiledHeader=dict(path=str(self.header), sha256=b.ad.sha(self.header)),
                         witness=dict(files={str(p): b.ad.sha(p) for p in (self.header, self.client)}))
        self.path = self.put('plan.json', json.dumps(self.plan).encode())
        self.pin = b.ad.sha(self.path)

    def put(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def dep_fixture(self, role='reference', extra=''):
        obj = self.put('build/behavior/id-map-combined-r1/' + role + '/cmake/client/client.o', b'SYNTHETIC OBJECT')
        dep = Path(str(obj) + '.d')
        dep.write_text('client/client.o: ' + str(self.client) + ' \\\n ' + str(self.header) + extra + '\n')
        return dict(backend=role, clientObject=str(obj), clientDepfile=str(dep))

    def test_make_escapes_and_continuation_not_shell_quotes(self):
        self.assertEqual(b.make_rule("out\\ file.o: /some\\ path/a\\#b\\:c$$d'quote.hpp \\\n tail.hpp"),
                         ('out file.o', ["/some path/a#b:c$d'quote.hpp", 'tail.hpp']))

    def test_malformed_make_rules(self):
        for text in ('', 'a.o:', 'a.o b.o: c.hpp', 'a.o: c\nb.o: d', 'a.o: $X', 'a.o: x#comment', 'a.o: x\\'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                b.make_rule(text)

    def test_actual_header_and_client_dependency(self):
        result = b.dependency_witness(self.plan, self.dep_fixture(), {'compile_source_files': {}})
        self.assertIn(str(self.header), result['dependencies'])
        self.assertIn('OBSERVED_COMPILER_DEPENDENCY', result['headerRole'])

    def test_relative_include_spelling_is_bound_to_physical_header(self):
        receipt = self.dep_fixture()
        dep = Path(receipt['clientDepfile'])
        spelling = str(self.root / 'source/client/../lab/behavior/id_map_scene.hpp')
        dep.write_text(dep.read_text().replace(str(self.header), spelling))
        result = b.dependency_witness(self.plan, receipt, {'compile_source_files': {}})
        self.assertIn(str(self.header), result['dependencies'])

    def test_owned_group_killed_even_when_leader_exits_on_term(self):
        proc = Mock(pid=123456, returncode=0)
        proc.wait.side_effect = [ValueError('SYNTHETIC DEADLINE'), 0, 0]
        with patch.object(b.subprocess, 'Popen', return_value=proc) as launch, \
             patch.object(b.os, 'killpg') as kill, \
             patch.object(b, 'remaining', return_value=5), \
             patch.object(b.ad, 'check_budget'), \
             self.assertRaisesRegex(ValueError, 'SYNTHETIC DEADLINE'):
            b.supervise(['SYNTHETIC NEVER EXECUTED'], self.root, {}, self.root / 'supervised', self.plan)
        self.assertTrue(launch.call_args.kwargs['start_new_session'])
        self.assertEqual([c.args[1] for c in kill.call_args_list], [b.signal.SIGTERM, b.signal.SIGKILL])
        self.assertTrue((self.root / 'supervised.receipt.json').is_file())

    def test_successful_leader_cannot_leave_background_descendants(self):
        proc = Mock(pid=123456, returncode=0)
        proc.wait.return_value = 0
        with patch.object(b.subprocess, 'Popen', return_value=proc), \
             patch.object(b.os, 'killpg') as kill, \
             patch.object(b, 'remaining', return_value=5), \
             patch.object(b.ad, 'check_budget'), patch.object(b.ad, 'check_deadline'):
            b.supervise(['SYNTHETIC NEVER EXECUTED'], self.root, {}, self.root / 'successful', self.plan)
        self.assertEqual([c.args[1] for c in kill.call_args_list], [b.signal.SIGKILL])
        command = json.loads((self.root / 'successful.command.json').read_text())
        receipt = json.loads((self.root / 'successful.receipt.json').read_text())
        self.assertEqual(receipt['pid'], proc.pid)
        self.assertLessEqual(b.dt.datetime.fromisoformat(command['startedUTC']),
                             b.dt.datetime.fromisoformat(receipt['finishedUTC']))

    def test_missing_compiled_header(self):
        receipt = self.dep_fixture()
        Path(receipt['clientDepfile']).write_text('client/client.o: ' + str(self.client))
        with self.assertRaisesRegex(ValueError, 'did not consume'):
            b.dependency_witness(self.plan, receipt, {'compile_source_files': {}})

    def test_wrong_object_target(self):
        receipt = self.dep_fixture()
        p = Path(receipt['clientDepfile'])
        p.write_text(p.read_text().replace('client/client.o:', 'client/other.o:'))
        with self.assertRaisesRegex(ValueError, 'target differs'):
            b.dependency_witness(self.plan, receipt, {'compile_source_files': {}})

    def test_unadmitted_and_changed_dependency(self):
        other = self.put('UNADMITTED.hpp', b'unknown')
        receipt = self.dep_fixture(extra=' ' + str(other))
        with self.assertRaisesRegex(ValueError, 'unadmitted/changed'):
            b.dependency_witness(self.plan, receipt, {'compile_source_files': {}})
        receipt = self.dep_fixture()
        self.header.write_bytes(b'CHANGED')
        with self.assertRaisesRegex(ValueError, 'unadmitted/changed'):
            b.dependency_witness(self.plan, receipt, {'compile_source_files': {}})

    def test_declared_but_not_compiled_is_not_enough(self):
        receipt = self.dep_fixture()
        Path(receipt['clientObject']).unlink()
        with self.assertRaisesRegex(ValueError, 'physical build product'):
            b.dependency_witness(self.plan, receipt, {'compile_source_files': {}})

    def test_external_pin_checked_before_validation_or_outputs(self):
        with patch.object(b.ad, 'validate') as validate, self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            b.build_pair(self.path, '0' * 64)
        validate.assert_not_called()
        self.assertFalse(self.build.exists())

    def test_admission_rejection_creates_no_candidate(self):
        with patch.object(b.ad, 'validate', side_effect=ValueError('old pair/reservation blocked')), self.assertRaisesRegex(ValueError, 'blocked'):
            b.build_pair(self.path, self.pin)
        self.assertFalse(self.build.exists())

    def test_environment_drops_shell_flag_and_search_overrides(self):
        with patch.dict('os.environ', {'RUSTFLAGS': 'bad', 'CFLAGS': 'bad', 'SDKROOT': '/bad'}):
            env = b.environment(self.plan, 'reference')
        self.assertEqual(env['SDKROOT'], '/SYNTHETIC-SDK')
        self.assertEqual(env['PATH'], '/usr/bin:/bin')
        self.assertNotIn('RUSTFLAGS', env)
        self.assertNotIn('CFLAGS', env)
        self.assertTrue(env['CARGO_HOME'].startswith(str(self.build)))
        self.assertNotEqual(env['CARGO_HOME'], env['HOME'] + '/.cargo')
        self.assertTrue(env['TMPDIR'].startswith(str(self.build)))

    def test_expired_admission_uses_original_deadline(self):
        with self.assertRaisesRegex(ValueError, 'original admission deadline'):
            b.remaining(self.plan)

    def orchestrate(self, fail=False):
        self.build.parent.mkdir(parents=True)
        configured = {}
        calls = []
        def configure(plan, pin, directory):
            role = directory.parent.name
            receipt = self.dep_fixture(role)
            configured[role] = receipt
            b.ad.dump(directory.parent / 'complete-tool-admission.json', receipt)
            return dict(receipt, planSha256=pin)
        def run(argv, cwd, env, output, plan):
            calls.append((argv, str(cwd), env))
            if fail:
                raise ValueError('SYNTHETIC FAILED CONFIGURE')
            if len(argv) > 2 and argv[1] == str(Path(b.bp.__file__).resolve()):
                phase = argv[2]
                if phase in ('begin', 'configured'):
                    path = Path(argv[argv.index('--snapshot') + 1])
                    path.write_text(json.dumps({'compile_source_files': {}}))
                elif phase == 'seal':
                    seal(Path(argv[argv.index('--binary') + 1]), None, None)
                elif phase == 'verify':
                    output.with_suffix('.stdout').write_text(json.dumps({'syntheticOnly': True}))
        def seal(binary, snapshot, root):
            self.put(str(binary.relative_to(self.root)), b'SYNTHETIC NOT A GAME')
            b.ad.dump(b.bp.sidecar(binary), {'syntheticOnly': True})
            if binary.parent.parent.name == 'candidate':
                self.put(str((binary.parent.parent / 'cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a').relative_to(self.root)), b'SYNTHETIC NOT AN ARCHIVE')
            return {'syntheticOnly': True}
        with patch.object(b.ad, 'validate', return_value=self.build), \
             patch.object(b.ad, 'commands', side_effect=lambda p, r: {'configure': ['SYNTHETIC-CONFIGURE', r], 'build': ['SYNTHETIC-BUILD', r]}), \
             patch.object(b.ad, 'configured', side_effect=configure), \
             patch.object(b.ad, 'check_configured', side_effect=lambda p, d: configured[d.parent.name]), \
             patch.object(b.bp, 'begin', side_effect=AssertionError('unsupervised begin')), \
             patch.object(b.bp, 'configured', side_effect=AssertionError('unsupervised native probe')), \
             patch.object(b.bp, 'seal', side_effect=AssertionError('unsupervised native probe')), \
             patch.object(b.bp, 'verify', side_effect=AssertionError('unsupervised native probe')):
            return b.build_pair(self.path, self.pin, run=run), calls

    def test_synthetic_complete_phase_order_and_receipts(self):
        root, calls = self.orchestrate()
        self.assertEqual([x[0] for x in calls if x[0][0].startswith('SYNTHETIC')],
                         [['SYNTHETIC-CONFIGURE', 'reference'], ['SYNTHETIC-BUILD', 'reference'],
                          ['SYNTHETIC-CONFIGURE', 'candidate'], ['SYNTHETIC-BUILD', 'candidate']])
        self.assertEqual([x[0][2] for x in calls if not x[0][0].startswith('SYNTHETIC')],
                         ['begin', 'configured', 'seal', 'verify'] * 2)
        self.assertTrue(all('CARGO_HOME' in x[2] for x in calls))
        result = json.loads((root / 'completion.json').read_text())
        self.assertEqual(result['status'], 'ADMITTED_PAIR_BUILT_NOT_GAME_QUALIFIED')
        self.assertFalse((root / 'failure.json').exists())
        native = json.loads((root / 'reference/id-map-build.json').read_text())
        self.assertIsNone(native['archive'])
        self.assertIn('NOT game', native['limitations'][0])

    def test_failed_phase_preserved_not_retried(self):
        with self.assertRaisesRegex(ValueError, 'SYNTHETIC FAILED'):
            self.orchestrate(fail=True)
        self.assertTrue((self.build / 'failure.json').is_file())
        self.assertFalse((self.build / 'completion.json').exists())
        with patch.object(b.ad, 'validate'), self.assertRaisesRegex(ValueError, 'fresh generation'):
            b.build_pair(self.path, self.pin, run=lambda *args: self.fail('must not run'))


if __name__ == '__main__':
    unittest.main()
