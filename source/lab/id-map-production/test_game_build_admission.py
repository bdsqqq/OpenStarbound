#!/usr/bin/env python3
"""Hermetic admission tests: no configure/build, real SDK walk or live-root prepare."""
import copy
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('id_map_admission_test_subject', HERE / 'game_build_admission.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.patch('ROOT', self.root)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.cmake = self.source / 'CMakeLists.txt'
        self.cmake.write_text('\n'.join('option(' + key + ' "fixture" OFF)' for key in a.SELECTORS))
        self.header = self.root / a.HEADER
        self.header.parent.mkdir(parents=True)
        self.header.write_text('// declared future dependency\n')
        for relative in ('scripts/build-id-map-behavior-lab.py', 'source/lab/behavior/build_provenance.py',
                         'source/client/StarClientApplication.cpp'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('// fixture\n')
        self.tools_dir = self.root / 'tools'
        self.tools_dir.mkdir()
        self.binary = self.tools_dir / 'native'
        self.binary.write_bytes(b'\xcf\xfa\xed\xfe' + b'fixture')
        self.binary.chmod(0o755)
        keys = ('CMAKE_EXECUTABLE CMAKE_C_COMPILER CMAKE_CXX_COMPILER CMAKE_AR CMAKE_RANLIB '
                'CMAKE_LINKER CMAKE_MAKE_PROGRAM STAR_CARGO_EXECUTABLE STAR_RUSTC_EXECUTABLE '
                'APPLE_TOOLCHAIN_SELECTOR').split()
        self.tools = {key: str(self.binary) for key in keys}
        self.sdk = self.root / 'sdk'
        self.sdk.mkdir()
        (self.sdk / 'header.h').write_text('fixture sdk')
        self.tool_plan = self.root / 'old-tool-plan.json'
        self.tool_plan.write_text(json.dumps(dict(tools=self.tools, sdk=str(self.sdk),
            witness={'files': {'DO_NOT_IMPORT': 'historical'}}, stage='EXPIRED_HISTORICAL')))
        self.tool_pin = a.sha(self.tool_plan)
        self.retirement = self.root / 'retirement.json'
        self.retirement.write_text('{}')
        self.retired = dict(manifest=str(self.retirement), sha256=a.sha(self.retirement), physical=str(self.retirement))
        self.output = self.root / 'admission'
        # Mock only repository-specific/resource gates. Membership and byte
        # closure, commands, profile checks, native checks and validate are real.
        self.old_bins = self.patch('check_no_old_bins', None, return_value=None)
        self.retirement_check = self.patch('check_retirement', None, return_value=self.retired)
        self.budget = self.patch('check_budget', None, return_value=dict(liveBytes=0, archiveBytes=0, newRootBytes=0))
        self.patch('source_roots', None, side_effect=lambda tools, sdk:
                   [str(self.source), str(self.root / 'scripts'), str(self.tools_dir), str(self.sdk)])
        self.patch('retained_objects', None, return_value=[])
        self.patch('auxiliary_tools', None, return_value=[self.binary])
        # The module under test itself is a tool input; pin its actual path but
        # never mutate it or traverse the repository SDK during fixture tests.
        self.real_closure = a.closure
        self.patch('closure', None, side_effect=self.fixture_closure)

    def patch(self, name, value, **kwargs):
        p = patch.object(a, name, value, **kwargs) if not kwargs else patch.object(a, name, **kwargs)
        result = p.start()
        self.addCleanup(p.stop)
        return result

    def fixture_closure(self, roots):
        witness = self.real_closure(roots)
        a._pin(witness, [HERE / 'game_build_admission.py'])
        return witness

    def prepare(self):
        return a.prepare(self.output, 'b' * 40, 1, self.retirement, self.retired['sha256'],
                         self.tool_plan, self.tool_pin)

    def assert_invalid(self, plan, message=None):
        with self.assertRaises((ValueError, AssertionError, FileNotFoundError)) as error:
            a.validate(plan)
        if message:
            self.assertIn(message, str(error.exception))

    def test_positive_prepare_validate_and_path_selection_only(self):
        plan = self.prepare()
        self.assertEqual(a.validate(plan), self.root / 'build/behavior/id-map-combined-r1')
        self.assertEqual(plan['profiles'], a.profiles())
        self.assertNotIn('DO_NOT_IMPORT', plan['witness']['files'])
        self.assertTrue((self.output / 'plan.json').is_file())
        self.assertEqual(plan['compiledHeader']['path'], str(self.header))
        self.assertIn('not yet compiled', plan['compiledHeader']['role'])

    def test_exact_real_source_selector_schema_read_only(self):
        # The only real repository-data test reads the source selector tuple.
        with patch.object(a, 'ROOT', HERE.parents[2]):
            a.check_source_selectors()
        self.assertEqual(len(a.SELECTORS), 29)
        self.assertEqual(set(a.SELECTORS), set(a._generic.SELECTORS) | {'STAR_USE_RUST_ID_MAP'})

    def test_wrong_id_map_profile(self):
        plan = self.prepare()
        plan['profiles']['candidate']['STAR_USE_RUST_ID_MAP'] = 'OFF'
        self.assert_invalid(plan, '29-selector')

    def test_line_query_must_remain_off(self):
        plan = self.prepare()
        plan['profiles']['candidate']['STAR_USE_RUST_LINE_QUERY'] = 'ON'
        self.assert_invalid(plan, '29-selector')

    def test_missing_29th_profile_selector(self):
        plan = self.prepare()
        del plan['profiles']['reference']['STAR_USE_RUST_ID_MAP']
        self.assert_invalid(plan, '29-selector')

    def test_source_missing_extra_duplicate_and_default_on(self):
        original = self.cmake.read_text()
        for text in (original.replace('option(STAR_USE_RUST_ID_MAP "fixture" OFF)', ''),
                     original + '\noption(STAR_USE_RUST_EXTRA "fixture" OFF)',
                     original + '\nOPTION ( STAR_USE_RUST_EXTRA "fixture" ${DEFAULT})',
                     original + '\noption(STAR_USE_RUST_ID_MAP "fixture" OFF)',
                     original.replace('STAR_USE_RUST_ID_MAP "fixture" OFF', 'STAR_USE_RUST_ID_MAP "fixture" ON')):
            with self.subTest(text=text[-80:]):
                self.cmake.write_text(text)
                with self.assertRaisesRegex(ValueError, '29 selectors'):
                    a.check_source_selectors()
        self.cmake.write_text(original)

    def test_new_source_member_is_rejected(self):
        plan = self.prepare()
        (self.source / 'extra.cpp').write_text('extra')
        self.assert_invalid(plan, 'membership')

    def test_new_sdk_or_tool_runtime_member_is_rejected(self):
        plan = self.prepare()
        for root in (self.sdk, self.tools_dir):
            member = root / 'new-input'
            member.write_text('new member')
            with self.subTest(root=root):
                self.assert_invalid(plan, 'membership')
            member.unlink()

    def test_archive_source_alias_rejected_before_output(self):
        copy_path = self.root / 'build/retained-source/header.hpp'
        copy_path.parent.mkdir(parents=True)
        copy_path.write_text(self.header.read_text())
        self.header.unlink()
        self.header.symlink_to(copy_path)
        with self.assertRaisesRegex(ValueError, 'cannot replace live source'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_actual_sdk_alias_change_is_rejected(self):
        plan = self.prepare()
        target = self.root / 'other-sdk'
        self.sdk.rename(target)
        self.sdk.symlink_to(target, target_is_directory=True)
        self.assert_invalid(plan, 'alias changed')

    def test_changed_source_bytes_are_rejected(self):
        plan = self.prepare()
        self.cmake.write_text(self.cmake.read_text() + '\n# byte drift')
        self.assert_invalid(plan, 'input drift')

    def test_expired_future_and_naive_creation(self):
        plan = self.prepare()
        now = dt.datetime.now(dt.timezone.utc)
        for created in (now - dt.timedelta(seconds=2101), now + dt.timedelta(seconds=60), now.replace(tzinfo=None)):
            with self.subTest(created=created):
                bad = copy.deepcopy(plan)
                bad['createdUTC'] = created.isoformat()
                self.assert_invalid(bad)

    def test_deadline_rechecked_after_expensive_witness(self):
        plan = self.prepare()
        def expire(_):
            plan['createdUTC'] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=2101)).isoformat()
        with patch.object(a, 'unchanged', side_effect=expire):
            self.assert_invalid(plan, 'deadline reached')

    def test_deadline_caps_checkpoint_and_generation_are_fixed(self):
        plan = self.prepare()
        for field, value in [('deadlines', dict(a.DEADLINES, maxAgeSeconds=2101)),
                             ('caps', dict(a.CAPS, newRootBytes=1)), ('sourceCheckpoint', 'short'),
                             ('checkpointRole', 'CURRENT'), ('generation', True), ('generation', 0)]:
            with self.subTest(field=field, value=value):
                bad = copy.deepcopy(plan)
                bad[field] = value
                self.assert_invalid(bad)

    def test_argv_drift_rejected(self):
        plan = self.prepare()
        plan['commands']['candidate']['build'][-1] = 'waived'
        self.assert_invalid(plan, 'argv drift')

    def test_commands_fix_tools_profiles_outputs_and_retained_depfiles(self):
        plan = self.prepare()
        for role in ('reference', 'candidate'):
            command = a.commands(plan, role)
            argv = command['configure']
            self.assertEqual(argv[:3], [str(self.binary), '--preset', 'macos-arm-release'])
            self.assertEqual(len([word for word in argv if word.startswith('-DSTAR_USE_RUST_')]), 29)
            for key, value in self.tools.items():
                if key not in a.EXCLUDED:
                    self.assertIn('-D' + key + '=' + value, argv)
            self.assertIn('-DSTAR_USE_RUST_LINE_QUERY=OFF', argv)
            self.assertIn('-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON', argv)
            self.assertIn('-DVCPKG_MANIFEST_INSTALL=OFF', argv)
            self.assertEqual(command['build'][-5:], ['--parallel', '6', '--', '-d', 'keepdepfile'])

    def test_gate_failures_precede_output_and_witness(self):
        for gate in (self.old_bins, self.retirement_check, self.budget):
            with self.subTest(gate=gate):
                gate.side_effect = ValueError('gate denied')
                with self.assertRaisesRegex(ValueError, 'gate denied'):
                    self.prepare()
                self.assertFalse(self.output.exists())
                a.closure.assert_not_called()
                gate.side_effect = None

    def test_missing_header_rejected_before_output(self):
        self.header.unlink()
        with self.assertRaises(FileNotFoundError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_missing_header_witness_pin_rejected(self):
        plan = self.prepare()
        del plan['witness']['files'][str(self.header)]
        self.assert_invalid(plan, 'unhashed')

    def test_tool_selection_pin_and_missing_tool_rejected(self):
        with self.assertRaisesRegex(ValueError, 'externally pinned'):
            a.selected_paths(self.tool_plan, '0' * 64)
        old = json.loads(self.tool_plan.read_text())
        del old['tools']['STAR_RUSTC_EXECUTABLE']
        self.tool_plan.write_text(json.dumps(old))
        with self.assertRaisesRegex(ValueError, 'complete selected'):
            a.selected_paths(self.tool_plan, a.sha(self.tool_plan))
        self.assertFalse(self.output.exists())

    def test_tool_bytes_and_sdk_alias_drift_rejected(self):
        plan = self.prepare()
        self.binary.write_bytes(b'\xcf\xfa\xed\xfechanged')
        self.assert_invalid(plan, 'native tool')
        self.binary.write_bytes(b'\xcf\xfa\xed\xfefixture')
        plan['sdkPhysical'] = '/unadmitted/sdk'
        self.assert_invalid(plan, 'alias changed')

    def test_retirement_uses_literal_original_pins(self):
        self.assertEqual(a.PRODUCT_PINS, dict(
            reference='57305ea18f2f11edff14826d8732bd5559115231673a19ebec0088302f44a09f',
            candidate='8ea903429572485ddc3afb253c19d08f52a7bc3209e217342234d77ada97790b'))
        protected = {self.root / a.OLD_BASE / role / 'bin/starbound': digest
                     for role, digest in a.PRODUCT_PINS.items()}
        bindings = {p: dict(path=str(p), sha256=h, size=2048) for p, h in protected.items()}
        with patch.object(a, 'retired_product_bindings', return_value=(bindings, 'c' * 64)) as verifier:
            result = ORIGINAL_RETIREMENT(self.retirement, 'c' * 64)
            verifier.assert_called_once_with(self.root, (self.retirement, 'c' * 64), protected)
            self.assertIn('UNAVAILABLE', result['originState'])

    def test_retirement_strict_reconstruction_and_missing_original(self):
        rows, pins = [], {}
        for role in ('reference', 'candidate'):
            payload = (role.encode() * (2 * 1024 ** 2 // len(role) + 1))[:2 * 1024 ** 2]
            digest = hashlib.sha256(payload).hexdigest()
            pins[role] = digest
            relative = a.OLD_BASE + '/' + role + '/bin/starbound'
            (self.root / relative).parent.mkdir(parents=True)
            blob = self.root / 'build/migration-evidence-archive/blobs' / digest[:2] / (digest + '.gz')
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(gzip.compress(payload))
            rows.append(dict(path=relative, sha256=digest, size=len(payload),
                             fingerprint=[1, 1, len(payload), 1, 1, 0o100755, 1]))
        manifest = self.root / 'build/migration-evidence-archive/runs/fixture/manifest.json'
        manifest.parent.mkdir(parents=True)
        data = dict(version=1, status='ARCHIVED_VERIFIED_PRUNED',
                    roots=[str(Path(row['path']).parent) for row in rows], min_bytes=2 * 1024 ** 2,
                    entries=rows, removed_bytes=sum(row['size'] for row in rows))

        def write_manifest(value):
            manifest.write_text(json.dumps(value))
            return a.sha(manifest)

        with patch.object(a, 'PRODUCT_PINS', pins):
            pin = write_manifest(data)
            self.assertEqual(len(ORIGINAL_RETIREMENT(manifest, pin)['products']), 2)
            original = self.root / rows[0]['path']
            original.write_bytes(b'live original')
            with self.assertRaisesRegex(ValueError, 'must be absent'):
                ORIGINAL_RETIREMENT(manifest, pin)
            original.unlink()
            for mutate in ('roots', 'entries', 'bound', 'pin'):
                bad = copy.deepcopy(data)
                if mutate == 'roots':
                    bad['roots'].append('build/other/bin')
                elif mutate == 'entries':
                    bad['entries'].pop()
                elif mutate == 'bound':
                    bad['entries'][0]['size'] -= 1
                    bad['entries'][0]['fingerprint'][2] -= 1
                else:
                    bad['entries'][0]['sha256'] = '0' * 64
                with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                    ORIGINAL_RETIREMENT(manifest, write_manifest(bad))
            pin = write_manifest(data)
            digest = rows[0]['sha256']
            blob = self.root / 'build/migration-evidence-archive/blobs' / digest[:2] / (digest + '.gz')
            blob.write_bytes(gzip.compress(gzip.decompress(blob.read_bytes()) + b'x'))
            with self.assertRaisesRegex(ValueError, 'exceed bound'):
                ORIGINAL_RETIREMENT(manifest, pin)

    def test_tool_selector_injection_and_archived_tool_copy_rejected(self):
        old = json.loads(self.tool_plan.read_text())
        old['tools']['STAR_USE_RUST_ID_MAP'] = str(self.binary)
        self.tool_plan.write_text(json.dumps(old))
        with self.assertRaisesRegex(ValueError, 'argument schema'):
            a.selected_paths(self.tool_plan, a.sha(self.tool_plan))
        del old['tools']['STAR_USE_RUST_ID_MAP']
        archived = self.root / 'build/copied-tool'
        archived.parent.mkdir()
        archived.write_bytes(self.binary.read_bytes())
        archived.chmod(0o755)
        old['tools']['CMAKE_EXECUTABLE'] = str(archived)
        self.tool_plan.write_text(json.dumps(old))
        with self.assertRaisesRegex(ValueError, 'cannot select tools'):
            a.selected_paths(self.tool_plan, a.sha(self.tool_plan))

    def configured_fixture(self, role='candidate'):
        plan = self.prepare()
        build = Path(plan['buildRoot']) / role / 'cmake'
        build.mkdir(parents=True)
        cache = build / 'CMakeCache.txt'
        cache.write_text('\n'.join(key + ':BOOL=' + value for key, value in a.profiles()[role].items()))
        (build / 'build.ninja').write_text('  FLAGS = -isysroot ' + str(self.sdk) + '\n')
        words = [self.tools['CMAKE_CXX_COMPILER'], '-isysroot', str(self.sdk)]
        words += ['-D' + key for key, value in a.profiles()[role].items() if value == 'ON']
        words += ['-o', 'client/StarClientApplication.cpp.o', '-c', str(self.source / 'client/StarClientApplication.cpp')]
        database = [dict(file=str(self.source / 'client/StarClientApplication.cpp'), directory=str(build), arguments=words)]
        (build / 'compile_commands.json').write_text(json.dumps(database))
        self.patch('selection', None, return_value=self.tools)
        return plan, build, database

    def test_configured_receipt_declares_object_depfile_not_compilation(self):
        plan, build, _ = self.configured_fixture()
        result = a.configured(plan, 'd' * 64, build)
        self.assertTrue(result['clientDepfile'].endswith('StarClientApplication.cpp.o.d'))
        self.assertIn('NOT yet compiled', result['scope'])
        self.assertTrue((build.parent / 'complete-tool-admission.json').is_file())
        self.assertEqual(a.configured(plan, 'd' * 64, build), result)

    def test_configured_duplicate_missing_extra_cache_selector(self):
        plan, build, _ = self.configured_fixture()
        cache = build / 'CMakeCache.txt'
        original = cache.read_text()
        for text in (original + '\nSTAR_USE_RUST_ID_MAP:BOOL=ON',
                     original.replace('STAR_USE_RUST_ID_MAP:BOOL=ON', ''),
                     original + '\nSTAR_USE_RUST_EXTRA:BOOL=ON'):
            with self.subTest(text=text[-80:]):
                cache.write_text(text)
                with self.assertRaisesRegex(ValueError, '29-selector'):
                    a.check_configured(plan, build)
        self.assertFalse((build.parent / 'complete-tool-admission.json').exists())

    def test_configured_macro_compiler_sdk_output_and_client_count(self):
        plan, build, rows = self.configured_fixture()
        original = copy.deepcopy(rows)
        bads = []
        wrong = copy.deepcopy(original)
        wrong[0]['arguments'].append('-DSTAR_USE_RUST_ID_MAP')
        bads.append(wrong)
        wrong = copy.deepcopy(original)
        wrong[0]['arguments'].append('-USTAR_USE_RUST_ID_MAP')
        bads.append(wrong)
        wrong = copy.deepcopy(original)
        wrong[0]['arguments'][-1] = str(self.source / 'client/Different.cpp')
        bads.append(wrong)
        wrong = copy.deepcopy(original)
        wrong[0]['arguments'][0] = '/wrong/compiler'
        bads.append(wrong)
        wrong = copy.deepcopy(original)
        wrong[0]['arguments'][2] = '/wrong/sdk'
        bads.append(wrong)
        wrong = copy.deepcopy(original)
        index = wrong[0]['arguments'].index('-o') + 1
        wrong[0]['arguments'][index] = '../outside.o'
        bads.append(wrong)
        bads.extend([[], original + original])
        for bad in bads:
            with self.subTest(bad=bad):
                (build / 'compile_commands.json').write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    a.check_configured(plan, build)
        self.assertFalse((build.parent / 'complete-tool-admission.json').exists())

    def test_reference_split_macro_selector_is_not_hidden(self):
        plan, build, rows = self.configured_fixture('reference')
        rows[0]['arguments'] += ['-D', 'STAR_USE_RUST_ID_MAP']
        (build / 'compile_commands.json').write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError, 'macro vector'):
            a.check_configured(plan, build)

    def test_configured_changed_tool_selection_rejected(self):
        plan, build, _ = self.configured_fixture()
        a.selection.return_value = dict(self.tools, EXTRA_TOOL=str(self.binary))
        with self.assertRaisesRegex(ValueError, 'executable selection'):
            a.check_configured(plan, build)

    def test_original_reference_object_membership_is_113(self):
        base = self.root / a.OLD_BASE / 'reference/cmake/core'
        base.mkdir(parents=True)
        for index in range(113):
            (base / (str(index) + '.o')).write_bytes(b'object fixture')
        self.assertEqual(len(ORIGINAL_OBJECTS()), 113)
        (base / 'extra.o').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, '113 reference'):
            ORIGINAL_OBJECTS()

    def test_actual_budget_math_fixed_caps_and_reservation(self):
        root = self.root / 'build/behavior/id-map-combined-r1'
        archive = self.root / 'build/migration-evidence-archive'
        build = self.root / 'build'
        original = ORIGINAL_BUDGET
        for counts, accepted in (({archive: 0, build: 2 * 1024 ** 3, root: 0}, True),
                                 ({archive: 0, build: 3 * 1024 ** 3, root: 0}, False),
                                 ({archive: 17 * 1024 ** 3, build: 17 * 1024 ** 3, root: 0}, False),
                                 ({archive: 0, build: 2 * 1024 ** 3, root: 2 * 1024 ** 3}, False)):
            with self.subTest(counts=counts), patch.object(a, 'allocated', side_effect=lambda p: counts[p]):
                if accepted:
                    self.assertEqual(original(root)['newRootBytes'], 0)
                else:
                    with self.assertRaises(ValueError):
                        original(root)


ORIGINAL_RETIREMENT = a.check_retirement
ORIGINAL_BUDGET = a.check_budget
ORIGINAL_OBJECTS = a.retained_objects

if __name__ == '__main__':
    unittest.main()
