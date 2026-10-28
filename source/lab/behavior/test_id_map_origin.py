"""SYNTHETIC ONLY: no actual admission, tool execution, SDK or game positive.

Native image parsing/emitted-code attestation and repository-specific tool path
selection/retirement are mocked. Current file hashes, source membership, generic
snapshots, raw dependency replay, command windows and Ninja links are real fixture
checks. No production bypass is introduced by these tests.
"""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('idmap_whole_origin_test', HERE / 'id_map_origin.py')
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)


class SyntheticOriginTests(unittest.TestCase):
    def patch(self, obj, name, *args, **kwargs):
        p = patch.object(obj, name, *args, **kwargs)
        result = p.start()
        self.addCleanup(p.stop)
        return result

    def put(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, dict) or isinstance(value, list):
            path.write_text(json.dumps(value, sort_keys=True))
        elif isinstance(value, bytes):
            path.write_bytes(value)
        else:
            path.write_text(value)
        return path

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.patch(o, 'ROOT', self.root)
        self.patch(o.ad, 'ROOT', self.root)
        self.patch(o.builder, 'ROOT', self.root)
        self.patch(o.bp.subprocess, 'run', side_effect=AssertionError('NO native/version probes allowed'))
        self.patch(o.bp.subprocess, 'Popen', side_effect=AssertionError('NO subprocess allowed'))
        self.patch(o.ad, 'validate', side_effect=AssertionError('NO current-age admission validation'))
        self.patch(o.ad, 'check_deadline', side_effect=AssertionError('NO renewed current clock'))
        self.native = self.put(self.root / 'tools/native', b'\xcf\xfa\xed\xfefixture')
        self.native.chmod(0o755)
        self.python = str(self.native)
        keys = ('CMAKE_EXECUTABLE CMAKE_C_COMPILER CMAKE_CXX_COMPILER CMAKE_AR CMAKE_RANLIB '
                'CMAKE_LINKER CMAKE_MAKE_PROGRAM STAR_CARGO_EXECUTABLE STAR_RUSTC_EXECUTABLE '
                'APPLE_TOOLCHAIN_SELECTOR').split()
        self.tools = {key: str(self.native) for key in keys}
        self.sdk = self.root / 'sdk'
        self.put(self.sdk / 'header.h', 'sdk fixture')
        self.put(self.root / 'source/CMakeLists.txt', '\n'.join(
            'option(' + key + ' "fixture" OFF)' for key in o.ad.SELECTORS))
        self.header = self.put(self.root / o.ad.HEADER, '// scene fixture')
        self.client = self.put(self.root / 'source/client/StarClientApplication.cpp', '// client fixture')
        for relative in ('scripts/build-id-map-behavior-lab.py', 'source/lab/behavior/build_provenance.py',
                         'source/lab/id-map-production/game_build_admission.py',
                         'source/lab/id-map-production/game_origin.py'):
            self.put(self.root / relative, '// fixture input, NEVER executed')
        self.tool_plan = self.put(self.root / o.ad.TOOL_PLAN, {'tools': self.tools, 'sdk': str(self.sdk)})
        self.retired = {'manifest': str(self.put(self.root / 'retirement.json', {})), 'sha256': 'b' * 64}
        self.objects = [str(self.put(self.root / ('retained/obj' + str(n) + '.o'), b'object')) for n in range(113)]
        self.roots = [str(self.root / name) for name in ('source', 'scripts', 'tools', 'sdk')]
        # Narrow repository-specific boundaries; no actual SDK/resource/output preparation.
        self.patch(o.ad, 'selected_paths', return_value=(self.tools, str(self.sdk)))
        self.patch(o.ad, 'selection', return_value=self.tools)
        self.patch(o.ad, 'source_roots', return_value=self.roots)
        self.patch(o.ad, 'retained_objects', return_value=self.objects)
        self.patch(o.ad, 'auxiliary_tools', return_value=[self.native])
        self.patch(o.ad, 'check_retirement', return_value=self.retired)
        self.image = SimpleNamespace(kind=2, symbols=[])
        self.patch(o.code._generic, 'MachO', return_value=self.image)
        self.emitted = dict(complete=True, blockers=[],
            game_sha256=o.code.sha(b'SYNTHETIC, NOT MACH-O'),
            archive_sha256=o.code.sha(b'fixture archive, NOT native'),
            functions=[dict(name_hex=name.hex(), synthetic=True) for name in o.code.NAMES],
            providers=[dict(name_hex=name.hex(), members=[{'synthetic': True}]) for name in o.code.NAMES],
            native_call_edges=[dict(owner_hex=o.code.OWNER.hex(), target_name_hex=o.code.NAMES[0].hex(), synthetic=True)])
        self.attest = self.patch(o.code, 'attest', return_value=self.emitted)
        self.pair = self.root / 'build/behavior/id-map-combined-r1'
        witness = o.ad.closure(list(map(Path, self.roots)))
        o.ad._pin(witness, self.objects + [self.native, self.tool_plan, Path(o.__file__)])
        self.plan = dict(stage=o.ad.STAGE, scope=o.ad.SCOPE, caps=o.ad.CAPS, deadlines=o.ad.DEADLINES,
            # Intentionally years old. Only original recorded execution matters.
            createdUTC='2020-01-01T00:00:00+00:00', sourceCheckpoint='a' * 40,
            checkpointRole=o.ad.CHECKPOINT_ROLE, generation=1, buildRoot=str(self.pair),
            profiles=o.ad.profiles(), tools=self.tools, sdk=str(self.sdk), sdkPhysical=str(self.sdk),
            toolPlan=str(self.tool_plan), toolPlanSha256=o.ad.TOOL_PLAN_SHA,
            toolPlanRole='PATH_SELECTION_ONLY; historical admission NOT reused', retirement=self.retired,
            sourceRoots=self.roots, treeMembers=o.ad.tree_members(self.roots), witness=witness,
            retainedReferenceObjects=self.objects, configureCwd=str(self.root / 'source'),
            compiledHeader=dict(path=str(self.header), physical=str(self.header), sha256=o.ad.sha(self.header),
                role='DECLARED_FUTURE_COMPILE_DEPENDENCY; not yet compiled'))
        self.plan['commands'] = {r: o.ad.commands(self.plan, r) for r in o.ROLES}
        self.plan_path = self.put(self.root / 'new-admission/plan.json', self.plan)
        self.pin = o.ad.sha(self.plan_path)
        self.proofs = {}
        for role in o.ROLES:
            self.make_role(role)
        self.complete()

    def complete(self):
        self.put(self.pair / 'completion.json', dict(status='ADMITTED_PAIR_BUILT_NOT_GAME_QUALIFIED',
            admissionSha256=self.pin, backends={r: o._identity(self.pair / r / 'id-map-build.json') for r in o.ROLES}))

    def make_role(self, role):
        side, build = self.pair / role, self.pair / role / 'cmake'
        binary = self.put(side / 'bin/starbound', b'SYNTHETIC, NOT MACH-O')
        cache = {**self.tools, **o.ad.profiles()[role]}
        self.put(build / 'CMakeCache.txt', '\n'.join(k + ':STRING=' + v for k, v in cache.items()))
        self.put(build / 'build.ninja', 'build ' + str(binary) + ': CXX_EXECUTABLE_LINKER fixture.o\n'
                 + '  FLAGS = -isysroot ' + str(self.sdk) + '\n  LINK_LIBRARIES = '
                 + (o.ARCHIVE if role == 'candidate' else '') + '\n')
        obj = build / 'client/CMakeFiles/starbound.dir/StarClientApplication.cpp.o'
        argv = [str(self.native), '-isysroot', str(self.sdk)]
        argv += ['-D' + k for k, v in o.ad.profiles()[role].items() if v == 'ON']
        argv += ['-o', str(obj), '-c', str(self.client)]
        self.put(build / 'compile_commands.json', [dict(file=str(self.client), directory=str(build), arguments=argv)])
        self.put(str(obj) + '.d', str(obj) + ': ' + str(self.client) + ' ' + str(self.header) + '\n')
        self.put(obj, b'fixture object after inputs')
        configured = o.ad.check_configured(self.plan, build)
        self.put(side / 'complete-tool-admission.json', dict(configured, planSha256=self.pin))
        sources = o.bp.source_snapshot(self.root)
        before = dict(schema=1, source_root=str(self.root), build_dir=str(build), source_files=sources)
        generic_cache = {k: v for k, v in cache.items() if k.startswith(('CMAKE_', 'VCPKG_', 'STAR_'))}
        identity = dict(kind='cmake', cache=generic_cache, files={str(build / name): o.ad.sha(build / name)
            for name in ('CMakeCache.txt', 'build.ninja', 'compile_commands.json')},
            tools={k: dict(path=v, sha256=o.ad.sha(v)) for k, v in cache.items() if k in (
                'CMAKE_COMMAND', 'CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_MAKE_PROGRAM',
                'CMAKE_AR', 'CMAKE_RANLIB', 'CMAKE_TOOLCHAIN_FILE', 'STAR_CARGO_EXECUTABLE', 'STAR_RUSTC_EXECUTABLE')})
        snapshot = dict(before, build_identity=identity, compile_source_files=o.bp._compile_source_inputs(build))
        self.put(side / 'inputs-before.json', before)
        self.put(side / 'build-inputs.json', snapshot)
        proof = dict(snapshot, binary=str(binary), binary_sha256=o.ad.sha(binary), limitations=o.bp.LIMITATIONS)
        self.proofs[role] = proof
        self.put(o.bp.sidecar(binary), proof)
        deps = o.builder.dependency_witness(self.plan, configured, snapshot)
        self.put(side / 'client-dependencies.json', deps)
        for index, phase in enumerate(o.PHASES):
            if phase in ('configure', 'compile'):
                args = o.ad.commands(self.plan, role)['configure' if phase == 'configure' else 'build']
            else:
                action = phase.removeprefix('provenance-')
                args = [self.python, str(self.root / 'source/lab/behavior/build_provenance.py'), action,
                        '--source-root', str(self.root)]
                if action == 'begin':
                    args += ['--build-dir', str(build)]
                if action != 'verify':
                    args += ['--snapshot', str(side / 'build-inputs.json')]
                if action in ('seal', 'verify'):
                    args += ['--binary', str(binary)]
            # Both roles consume one fixed original window, in actual pair order.
            second = (0 if role == 'reference' else 100) + index * 2
            start = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=second)
            self.put(side / (phase + '.command.json'), dict(argv=args, cwd=str(self.root / 'source'),
                environment=o.builder.environment(self.plan, role), startedUTC=start.isoformat()))
            self.put(side / (phase + '.receipt.json'), dict(argv=args, returncode=0, elapsedSeconds=1,
                failure=None, finishedUTC=(start + dt.timedelta(seconds=1)).isoformat(), pid=101))
            self.put(side / (phase + '.stdout'), proof if phase == 'provenance-verify' else '')
            self.put(side / (phase + '.stderr'), '')
        archive = self.put(build / o.ARCHIVE, b'fixture archive, NOT native') if role == 'candidate' else None
        record = dict(schema=1, backend=role, admission=o._identity(self.plan_path), admissionSha256=self.pin,
            binary=o._identity(binary), genericProof=o._identity(o.bp.sidecar(binary)),
            configured=o._identity(side / 'complete-tool-admission.json'),
            dependencies=o._identity(side / 'client-dependencies.json'),
            builder=o._identity(self.root / 'scripts/build-id-map-behavior-lab.py'),
            environment=o.builder.environment(self.plan, role), archive=o._identity(archive) if archive else None)
        self.put(side / 'id-map-build.json', record)

    def validate(self, role='candidate'):
        return o.validate_game_origin(self.pair / role / 'bin/starbound', self.proofs[role])

    def change(self, relative, mutate):
        path = self.pair / relative
        value = json.loads(path.read_text())
        mutate(value)
        self.put(path, value)

    def reject(self, text=None, role='candidate'):
        with self.assertRaises((ValueError, AssertionError, OSError, KeyError)) as caught:
            self.validate(role)
        if text:
            self.assertIn(text, str(caught.exception))

    def test_fixture_generic_snapshots_and_raw_dependency_invariants(self):
        for role in o.ROLES:
            side = self.pair / role
            configured = o._read(side / 'complete-tool-admission.json')
            configured.pop('planSha256')
            o._generic(self.plan, side, self.proofs[role], configured)
            self.assertEqual(o.builder.dependency_witness(self.plan, configured, self.proofs[role]),
                             o._read(side / 'client-dependencies.json'))
            o._link_archive(side, side / 'cmake' / o.ARCHIVE if role == 'candidate' else None)

    def test_synthetic_completed_original_window_is_deterministic_no_native(self):
        first = self.validate()
        self.assertEqual(first, self.validate())
        self.assertEqual(first['backend'], 'candidate')
        self.assertEqual(first['emittedCode'], self.emitted)
        self.assertIn('data-object', ' '.join(first['limitations']))

    def test_synthetic_reference_exact_no_rust(self):
        result = self.validate('reference')
        self.assertEqual(result['emittedCode']['status'], 'NO_RUST')
        self.attest.assert_not_called()

    def test_wrong_role_record(self):
        self.change('candidate/id-map-build.json', lambda x: x.update(backend='reference'))
        self.complete()
        self.reject('role/admission')

    def test_old_or_lab_path_and_traversal_and_symlink(self):
        for relative in ('build/behavior/weighted-pool-combined-r1/candidate/bin/starbound',
                         'source/lab/candidate/bin/starbound',
                         'build/behavior/id-map-combined-r0/candidate/bin/starbound'):
            path = self.put(self.root / relative, b'wrong')
            with self.assertRaises(ValueError):
                o.validate_game_origin(path, {})
        with self.assertRaises(ValueError):
            o.validate_game_origin(self.pair / 'candidate/bin/../bin/starbound', self.proofs['candidate'])
        path = self.root / 'alias'
        path.symlink_to(self.pair / 'candidate/bin/starbound')
        with self.assertRaises(ValueError):
            o.validate_game_origin(path, self.proofs['candidate'])

    def test_wrong_external_pin_and_tool_selection_pin(self):
        self.change('completion.json', lambda x: x.update(admissionSha256='f' * 64))
        self.reject('digest')
        self.complete()
        plan = copy.deepcopy(self.plan)
        plan['toolPlanSha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'e890'):
            o._static_plan(plan, self.pair)

    def test_command_deadline_expiry_naive_reversed_and_precreation(self):
        path = self.pair / 'candidate/compile.receipt.json'
        original = json.loads(path.read_text())
        for stamp in ('2020-01-01T00:35:01+00:00', '2020-01-01T00:00:00',
                      '2019-12-31T23:59:59+00:00'):
            self.put(path, dict(original, finishedUTC=stamp))
            self.reject()
        self.put(path, original)
        self.change('candidate/compile.command.json', lambda x: x.update(startedUTC='2019-01-01T00:00:00+00:00'))
        self.reject('window/order')

    def test_phase_set_and_cross_backend_command_order(self):
        side = self.pair / 'candidate'
        self.put(side / 'extra.command.json', {})
        self.reject('six supervised')
        (side / 'extra.command.json').unlink()
        path = side / 'provenance-begin.command.json'
        command = o._read(path)
        command['startedUTC'] = '2020-01-01T00:00:00+00:00'
        self.put(path, command)
        self.reject('preceded reference')

    def test_nonzero_failure_missing_phase_and_missing_output(self):
        path = self.pair / 'reference/configure.receipt.json'
        original = json.loads(path.read_text())
        for change in (dict(returncode=1), dict(failure='deadline')):
            self.put(path, dict(original, **change))
            self.reject('unsuccessful')
        self.put(path, original)
        (self.pair / 'reference/configure.stderr').unlink()
        self.reject()

    def test_wrong_stage_caps_checkpoint_and_29_profiles(self):
        for key, value in (('stage', 'OLD'), ('caps', {}), ('checkpointRole', 'REBOUND'),
                           ('profiles', {'reference': {}})):
            plan = copy.deepcopy(self.plan)
            plan[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                o._static_plan(plan, self.pair)

    def test_wrong_actual_argv_environment_and_interpreter(self):
        path = self.pair / 'candidate/provenance-seal.command.json'
        original = json.loads(path.read_text())
        for mutate in (lambda x: x['argv'].append('--skip'),
                       lambda x: x['environment'].update(RUSTFLAGS='bad'),
                       lambda x: x['argv'].__setitem__(0, '/unadmitted/python')):
            value = copy.deepcopy(original)
            mutate(value)
            self.put(path, value)
            self.reject()
        self.put(path, original)

    def test_root_failure_and_completion_status_and_other_backend_binding(self):
        self.put(self.pair / 'failure.json', {'status': 'FAILED'})
        self.reject('failed pair')
        (self.pair / 'failure.json').unlink()
        self.change('completion.json', lambda x: x.update(status='QUALIFIED'))
        self.reject('completion')
        self.complete()
        self.change('reference/id-map-build.json', lambda x: x.update(schema=9))
        self.reject('identity changed')

    def test_current_source_header_sdk_tool_and_member_drift(self):
        for path in (self.header, self.client, self.sdk / 'header.h', self.native):
            original = path.read_bytes()
            path.write_bytes(original + b'drift')
            self.reject()
            path.write_bytes(original)
        extra = self.put(self.sdk / 'added.h', 'new member')
        self.reject('membership')
        extra.unlink()

    def test_source_alias_to_archival_copy_cannot_be_rebound(self):
        archived = self.put(self.root / 'build/source-copy/header.hpp', self.header.read_bytes())
        self.header.unlink()
        self.header.symlink_to(archived)
        plan = copy.deepcopy(self.plan)
        plan['treeMembers'] = o.ad.tree_members(self.roots)
        with self.assertRaisesRegex(ValueError, 'cannot replace live source'):
            o._static_plan(plan, self.pair)

    def test_reference_dangling_rust_target_is_rejected(self):
        target = self.pair / 'reference/cmake/rust-engine-ffi'
        target.symlink_to(self.root / 'absent-archive-tree')
        self.reject('reference must have no Rust')

    def test_actual_configured_macro_and_object_witness_drift(self):
        side = self.pair / 'candidate'
        path = side / 'cmake/compile_commands.json'
        database = json.loads(path.read_text())
        database[0]['arguments'].remove('-DSTAR_USE_RUST_ID_MAP')
        self.put(path, database)
        with self.assertRaisesRegex(ValueError, 'macro vector'):
            o.ad.check_configured(self.plan, side / 'cmake')
        # Object bytes independently participate in the observed dependency witness.
        configured = o._read(side / 'complete-tool-admission.json')
        self.put(Path(configured['clientObject']), b'changed object')
        self.assertNotEqual(o.builder.dependency_witness(self.plan, configured, self.proofs['candidate']),
                            o._read(side / 'client-dependencies.json'))

    def test_declared_header_missing_or_changed(self):
        plan = copy.deepcopy(self.plan)
        plan['compiledHeader']['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'header changed'):
            o._static_plan(plan, self.pair)

    def test_archive_changed_or_unlinked_or_duplicate(self):
        archive = self.pair / 'candidate/cmake' / o.ARCHIVE
        archive.write_bytes(b'changed')
        self.reject('identity changed')
        archive.write_bytes(b'fixture archive, NOT native')
        side = self.pair / 'candidate'
        path = side / 'cmake/build.ninja'
        original = path.read_text()
        for link in ('', o.ARCHIVE + ' ' + o.ARCHIVE, '/unrelated/libstar_engine_ffi.a'):
            path.write_text(original.replace('LINK_LIBRARIES = ' + o.ARCHIVE, 'LINK_LIBRARIES = ' + link))
            with self.assertRaises((ValueError, FileNotFoundError)):
                o._link_archive(side, archive)
        path.write_text(original)

    def test_compiled_dependency_requires_observed_header_and_current_object(self):
        side = self.pair / 'candidate'
        configured = o._read(side / 'complete-tool-admission.json')
        dep = Path(configured['clientDepfile'])
        dep.write_text(str(configured['clientObject']) + ': ' + str(self.client) + '\n')
        # Rebind output metadata only: the independent raw parser must still reject.
        self.change('candidate/id-map-build.json', lambda x: x.update(dependencies=o._identity(side / 'client-dependencies.json')))
        self.complete()
        self.reject('consume admitted')

    def test_configured_cache_macros_snapshot_and_generic_proof_drift(self):
        proof = copy.deepcopy(self.proofs['candidate'])
        proof['compile_source_files'][str(self.client)] = 'f' * 64
        side = self.pair / 'candidate'
        self.put(o.bp.sidecar(side / 'bin/starbound'), proof)
        self.change('candidate/id-map-build.json', lambda x: x.update(genericProof=o._identity(o.bp.sidecar(side / 'bin/starbound'))))
        self.complete()
        self.proofs['candidate'] = proof
        self.reject('snapshot/proof')

    def test_duplicate_provider_missing_edge_and_incomplete_emitted_code(self):
        for change in (dict(complete=False), dict(native_call_edges=[]),
                       dict(functions=[dict(name_hex=o.code.NAMES[0].hex())] * 3),
                       dict(providers=[dict(name_hex=o.code.NAMES[0].hex(), members=[{}, {}])] * 3)):
            self.attest.return_value = dict(self.emitted, **change)
            self.reject('emitted-code')

    def test_native_reference_symbols_or_wrong_image_kind(self):
        self.image.symbols = [{'name': o.code.NAMES[0]}]
        self.reject('run/count', role='reference')
        self.image.symbols = []
        self.image.kind = 1
        self.reject('MH_EXECUTE')

    def test_unmodified_real_attester_rejects_synthetic_bytes(self):
        # This is a known-failure control against the actual byte attester,
        # separate from the whole-reader's mocked structural positive.
        real = o._load('idmap_actual_code_negative', HERE.parent / 'id-map-production/game_origin.py')
        self.assertFalse(real.attest(b'NOT MACH-O', b'NOT ARCHIVE')['complete'])


if __name__ == '__main__':
    unittest.main()
