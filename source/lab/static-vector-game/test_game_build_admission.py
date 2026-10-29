"""Pure guards; no tool invocation or actual game admission."""
import copy
import datetime as dt
import importlib.util
import inspect
import json
import os
import plistlib
import stat
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_sv_ad_test', HERE / 'game_build_admission.py')
ad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ad)
G = ad.allocation_root()
P = ad.build_root()


class AdmissionTests(unittest.TestCase):
    def test_finite_controller_destinations_and_logical_bound(self):
        outputs = ad.controller_outputs()
        self.assertEqual(len(outputs), 43)
        self.assertTrue(all(type(v) is int and v > 0 for v in outputs.values()))
        self.assertEqual(ad.controller_output_bound(), 2 * sum(outputs.values()))
        self.assertNotIn(P / 'reference/cargo.command.json', outputs)
        for path in (P / 'unknown.json', P / 'reference/build-inputs-unbounded.json',
                     P / 'another-attempt/plan.json', P / 'candidate/configure-extra.receipt.json'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                ad.controller_limit(path)

    def test_controller_dump_uses_real_bounded_publication(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            path = root / 'completion.json'
            value = {'unicode': '\u2603', 'state': ['complete', 3]}
            with patch.object(ad, 'build_root', return_value=root):
                result = ad.dump(path, value)
                self.assertEqual(path.read_bytes(), (json.dumps(value, indent=2, sort_keys=True) + '\n').encode())
                self.assertEqual(result, ad.identity(path))
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    ad.dump(path, value)
                self.assertFalse((root / '.completion.json.partial').exists())
                unknown = root / 'undeclared.json'
                with self.assertRaises(ValueError):
                    ad.dump(unknown, value)
                self.assertFalse(unknown.exists())

    def test_controller_overflow_retains_bounded_partial_and_blocks_retry(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            path = root / 'failure.json'
            with patch.object(ad, 'build_root', return_value=root):
                with self.assertRaisesRegex(ValueError, 'byte limit'):
                    ad.dump(path, {'error': 'x' * (64 * 1024)})
                partial = root / '.failure.json.partial'
                self.assertLessEqual(partial.stat().st_size, 64 * 1024)
                before = partial.read_bytes()
                with self.assertRaises(FileExistsError):
                    ad.dump(path, {'error': 'different attempt'})
                self.assertEqual(partial.read_bytes(), before)
                self.assertFalse(path.exists())

    def test_sidecar_supplement_is_pinned_and_preserves_compact_bytes(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            path = root / 'reference/bin/starbound.behavior-build.json'
            path.parent.mkdir(parents=True)
            path.write_text('{"schema": "synthetic"}')
            original = ad.identity(path)
            value = {'schema': 'synthetic', 'gameOrigin': {'status': 'fixture'}}
            with patch.object(ad, 'build_root', return_value=root):
                ad.supplement_sidecar(path, value, original)
                self.assertEqual(path.read_bytes(), json.dumps(value, sort_keys=True).encode())
                with self.assertRaisesRegex(ValueError, 'identity'):
                    ad.supplement_sidecar(path, value, original)
                with self.assertRaises(ValueError):
                    ad.supplement_sidecar(root / 'failure.json', value, original)

    def test_prepare_rejects_alternate_admission_before_input_acquisition(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            created = dt.datetime.now(dt.timezone.utc).isoformat()
            with patch.object(ad, 'build_root', return_value=root), patch.object(ad, 'current_inputs') as inputs:
                with self.assertRaisesRegex(ValueError, 'one canonical'):
                    ad.prepare(root / 'another-attempt', ad.CHECKPOINT, {}, root / 'forecast', 'x', created_utc=created)
                inputs.assert_not_called()
                self.assertEqual(list(root.iterdir()), [])
        self.assertNotIn('json.dump(', inspect.getsource(ad.prepare))

    def test_current30_profiles_and_source(self):
        ad.config.validate_source()
        self.assertEqual(len(ad.SELECTORS), 30)
        self.assertEqual(sum(v == 'ON' for v in ad.profiles()['candidate'].values()), 29)
        self.assertEqual(set(ad.profiles()['reference'].values()), {'OFF'})
        bad = dict(ad.profiles()['candidate'], STAR_USE_RUST_LINE_QUERY='ON')
        with self.assertRaises(ValueError):
            ad.config.validate_profile('candidate', bad)
        with self.assertRaises(ValueError):
            ad.config.validate_source('option(STAR_USE_RUST_STATIC_VECTOR "bad" ON)')

    def test_original_clock_no_renewal(self):
        now = dt.datetime(2026, 10, 29, tzinfo=dt.timezone.utc)
        plan = dict(createdUTC=now.isoformat(), deadlines=ad.DEADLINES)
        ad.check_deadline(plan, now + dt.timedelta(seconds=2099))
        for delta in (-1, 2100, 9000):
            with self.assertRaises(ValueError):
                ad.check_deadline(plan, now + dt.timedelta(seconds=delta))
        with self.assertRaises(ValueError):
            ad.check_deadline(dict(plan, deadlines={'maxAgeSeconds': 9999}), now)

    def test_explicit_metadata_and_fresh_roles(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            (root / 'observation.json').write_text('{}')
            self.assertEqual(len(ad.metadata_inventory(root)), 1)
            (root / 'candidate').mkdir()
            with self.assertRaises(ValueError):
                ad.metadata_inventory(root)

    def test_alias_and_native_metadata_rejected(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            (root / 'note').write_bytes(b'\xcf\xfa\xed\xfe')
            with self.assertRaises(ValueError):
                ad.metadata_inventory(root)
            (root / 'alias').symlink_to(root / 'note')
            with self.assertRaises(ValueError):
                ad.identity(root / 'alias')

    def test_exact_needed_old_pair_allowed_unexpected_rejected(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            behavior = root / 'build/behavior'
            for role in ad.profiles():
                path = behavior / 'id-map-combined-r2' / role / 'bin/starbound'
                path.parent.mkdir(parents=True)
                path.write_text(role)
            pins = {r: ad.sha(behavior / 'id-map-combined-r2' / r / 'bin/starbound') for r in ad.profiles()}
            with patch.object(ad, 'ROOT', root), patch.object(ad, 'PREDECESSORS', pins):
                self.assertEqual(len(ad.check_binaries()), 2)
                bad = behavior / 'surprise/reference/bin/starbound'
                bad.parent.mkdir(parents=True)
                bad.write_text('unowned')
                with self.assertRaises(ValueError):
                    ad.check_binaries()

    def test_missing_sdk_fails_current_path_selection(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            path = Path(temp) / 'selector.json'
            import json
            tools = {key: '/usr/bin/python3' for key in ('CMAKE_EXECUTABLE', 'CMAKE_C_COMPILER',
                'CMAKE_CXX_COMPILER', 'CMAKE_AR', 'CMAKE_RANLIB', 'CMAKE_LINKER', 'CMAKE_MAKE_PROGRAM',
                'STAR_CARGO_EXECUTABLE', 'STAR_RUSTC_EXECUTABLE', 'APPLE_TOOLCHAIN_SELECTOR')}
            path.write_text(json.dumps(dict(tools=tools, sdk='/missing/SDK')))
            with patch.object(ad.primitives, 'native'):
                with self.assertRaises(ValueError):
                    ad.primitives.selected_paths(path, ad.sha(path))

    def test_configure_candidate_has_separate_cargo(self):
        plan = dict(buildRoot=str(G), sdk='/SDK', tools={'CMAKE_EXECUTABLE': '/cmake'})
        commands = ad.commands(plan, 'candidate')
        self.assertIn('star_rust_engine_ffi_build', commands['cargo'])
        self.assertNotIn('starbound', commands['cargo'])
        self.assertIn('starbound', commands['build'])
        self.assertIsNone(ad.commands(plan, 'reference')['cargo'])

    def test_retention_covers_whole_generation_not_just_four_binaries(self):
        forecast = dict(schema='static-vector-product-retention-forecast-v1',
                        sourceCheckpoint=ad.CHECKPOINT, complete=True,
                        products={key: 1 for key in ad.RETENTION_PRODUCTS})
        budget = dict(archiveBytes=ad.CAPS['archiveBytes'] - len(ad.RETENTION_PRODUCTS))
        self.assertEqual(ad.check_retention(forecast, ad.CHECKPOINT, budget), len(ad.RETENTION_PRODUCTS))
        for missing in ad.RETENTION_PRODUCTS:
            with self.subTest(missing=missing):
                bad = dict(forecast, products={k: v for k, v in forecast['products'].items() if k != missing})
                with self.assertRaises(ValueError):
                    ad.check_retention(bad, ad.CHECKPOINT, budget)
        bad = dict(forecast, products={k: 1 for k in
                   ('predecessor-reference', 'predecessor-candidate', 'new-reference', 'new-candidate')})
        with self.assertRaisesRegex(ValueError, 'binaries alone'):
            ad.check_retention(bad, ad.CHECKPOINT, budget)

    def test_retention_rejects_underfunded_boolean_and_unknown_costs(self):
        forecast = dict(schema='static-vector-product-retention-forecast-v1',
                        sourceCheckpoint=ad.CHECKPOINT, complete=True,
                        products={key: 1 for key in ad.RETENTION_PRODUCTS})
        budget = dict(archiveBytes=ad.CAPS['archiveBytes'] - len(ad.RETENTION_PRODUCTS) + 1)
        with self.assertRaisesRegex(ValueError, 'headroom'):
            ad.check_retention(forecast, ad.CHECKPOINT, budget)
        for value in (True, 0, -1, 1.5):
            with self.subTest(value=value):
                bad = dict(forecast, products=dict(forecast['products'], **{'cargo-products': value}))
                with self.assertRaises(ValueError):
                    ad.check_retention(bad, ad.CHECKPOINT, dict(archiveBytes=0))
        bad = dict(forecast, products=dict(forecast['products'], surprise=1))
        with self.assertRaises(ValueError):
            ad.check_retention(bad, ad.CHECKPOINT, dict(archiveBytes=0))

    def test_wrong_base_rejected_before_inputs(self):
        plan = dict(stage=ad.STAGE, scope=ad.SCOPE, caps=ad.CAPS, sourceCheckpoint='0' * 40,
                    checkpointRole='BASE_ONLY; current working-tree bytes authoritative')
        with self.assertRaises(ValueError):
            ad.static_plan(plan)


class NamespaceTests(unittest.TestCase):
    def test_three_roots_and_allocation_cannot_be_narrowed(self):
        self.assertEqual(ad.enclosure_root(), G / 'current30-enclosure')
        self.assertEqual(P, G / 'current30-enclosure/products')
        with patch.object(ad.allocation, 'enforce', return_value={}) as enforce:
            ad.check_budget()
            ad.check_budget(G)
            self.assertEqual(enforce.call_args.args, (ad.ROOT, G))
            for bad in (P, ad.enclosure_root(), G / 'reference'):
                with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'whole allocation'):
                    ad.check_budget(bad)
            self.assertEqual(enforce.call_count, 2)
        self.assertTrue(all(path.is_relative_to(P) for path in ad.controller_outputs()))
        self.assertNotIn(G / 'current30-admission/plan.json', ad.controller_outputs())

    def test_missing_owner_fails_prepare_before_source_or_native_probes(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            with patch.object(ad, 'ROOT', root), \
                 patch.object(ad.config, 'validate_source', side_effect=AssertionError('source probe')), \
                 patch.object(ad.primitives, 'selected_paths', side_effect=AssertionError('tool probe')):
                with self.assertRaises((ValueError, OSError)):
                    ad.prepare(ad.build_root() / 'current30-admission', ad.CHECKPOINT,
                        {}, root / 'forecast', 'unused',
                        created_utc=dt.datetime.now(dt.timezone.utc).isoformat())
                self.assertEqual(list(root.iterdir()), [])

    def test_new_pair_allowed_but_old_namespace_does_not_qualify(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            with patch.object(ad, 'ROOT', root):
                old = root / 'build/behavior/id-map-combined-r2'
                pins = {}
                for role in ad.profiles():
                    for base in (old, ad.build_root()):
                        path = base / role / 'bin/starbound'
                        path.parent.mkdir(parents=True)
                        path.write_bytes(b'\xcf\xfa\xed\xfe' + role.encode())
                    pins[role] = ad.sha(old / role / 'bin/starbound')
                with patch.object(ad, 'PREDECESSORS', pins):
                    self.assertEqual(len(ad.check_binaries()), 2)
                    bad = ad.allocation_root() / 'reference/bin/starbound'
                    bad.parent.mkdir(parents=True)
                    bad.write_text('old namespace')
                    with self.assertRaisesRegex(ValueError, 'unexpected native game'):
                        ad.check_binaries()

    def test_mutable_filesystem_metadata_not_frozen_but_fully_scanned(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            metadata = root / '.fseventsd'
            metadata.mkdir()
            log = metadata / 'uuid'
            log.write_text('old mutable state')
            note = root / '.other-hidden'
            note.write_text('immutable')
            before = ad.metadata_inventory(root)
            self.assertEqual(set(before), {str(note)})
            log.write_text('changed OS state')
            self.assertEqual(ad.metadata_inventory(root), before)
            for name, data in [('native.a', b'plain'), ('native.o', b'plain'),
                    ('native.dylib', b'plain'), ('starbound', b'plain'),
                    ('uuid', b'\xcf\xfa\xed\xfe'), ('uuid', b'\x7fELF'), ('uuid', b'!<arch>\n')]:
                bad = metadata / name
                bad.write_bytes(data)
                with self.subTest(name=name, data=data), self.assertRaises(ValueError):
                    ad.metadata_inventory(root)
                bad.unlink()
            log.write_text('restored mutable state')
            alias = metadata / 'alias'
            alias.symlink_to(note)
            with self.assertRaises(ValueError):
                ad.metadata_inventory(root)
            alias.unlink()
            with patch.object(ad.os, 'scandir', side_effect=PermissionError('unreadable')):
                with self.assertRaises(PermissionError):
                    ad.metadata_inventory(root)
            # No generated-state or backing-image exclusion in the allocator.
            image = root / 'image.dmg'
            image.write_bytes(b'x' * 4096)
            paths = {path for path, _ in ad.allocation._entries(root)}
            self.assertTrue({log, image}.issubset(paths))

    def test_generated_classification_is_root_only_not_a_source_directory_waiver(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            nested = root / 'source/.fseventsd'
            nested.mkdir(parents=True)
            source = nested / 'input.cpp'
            source.write_text('immutable source, despite nested OS-like name')
            self.assertIn(str(source), ad.metadata_inventory(root))
            source.write_bytes(b'\x7fELF')
            with self.assertRaises(ValueError):
                ad.metadata_inventory(root)

    def test_lifecycle_files_selected_individually_not_cmake_definitions(self):
        with patch.object(ad.primitives, 'source_roots', return_value=['/source', '/rust']):
            roots = ad.source_roots({}, '/sdk')
        self.assertEqual(roots, ['/source', '/rust', '/usr/bin/hdiutil', '/usr/bin/sandbox-exec'])
        plan = dict(buildRoot=str(P), sdk='/SDK', tools={'CMAKE_EXECUTABLE': '/cmake'},
                    lifecycleTools=ad.LIFECYCLE_TOOLS)
        argv = ad.commands(plan, 'candidate')['configure']
        self.assertFalse(any('hdiutil' in value or 'sandbox-exec' in value for value in argv))


class EnclosureAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=G)
        self.addCleanup(self.temp.cleanup)
        self.g = Path(self.temp.name)
        self.e = self.g / 'current30-enclosure'
        self.p = self.e / 'products'
        self.p.mkdir(parents=True)
        self.image = self.e / 'image.dmg'
        self.image.write_bytes(b'fixture backing; mutable, never hashed')
        self.tool = self.e / 'tool'
        self.tool.write_bytes(b'fixture tool, never executed')
        self.host = self.e.stat().st_dev
        self.volume = self.host + 123
        self.mounted = True
        image = self.image.stat()
        self.owner = dict(root=str(self.e), image=dict(path=str(self.image),
            st_dev=image.st_dev, st_ino=image.st_ino, size=image.st_size, maxBytes=1024),
            mount=dict(path=str(self.p), st_dev=self.volume), device='/dev/disk41',
            volumeDevice='/dev/disk41s1', tool=dict(path=ad.er.TOOL, sha256=ad.sha(self.tool)),
            originalExperiment={'result': 'FAILED', 'clock': 'opaque original acquisition'})
        self.records = [dict(**{'image-path': str(self.image), 'system-entities': [
            {'dev-entry': '/dev/disk41'},
            {'dev-entry': '/dev/disk41s1', 'mount-point': str(self.p)}]})]
        physical = ad.er.physical
        original_stat = Path.stat
        def physical_fixture(value):
            if value == ad.er.TOOL:
                return self.tool
            if value == '/dev/disk41s1':
                return SimpleNamespace(stat=lambda: SimpleNamespace(st_mode=stat.S_IFBLK,
                                                                     st_rdev=self.volume))
            return physical(value)
        def stat_fixture(path, *args, **kwargs):
            actual = original_stat(path, *args, **kwargs)
            if path == self.p:
                fields = {name: getattr(actual, name) for name in dir(actual) if name.startswith('st_')}
                fields['st_dev'] = self.volume if self.mounted else self.host
                return SimpleNamespace(**fields)
            return actual
        for patcher in (patch.object(ad, 'allocation_root', return_value=self.g),
                        patch.object(ad.er, 'G', self.g),
                        patch.object(ad.er, 'physical', side_effect=physical_fixture),
                        patch.object(Path, 'stat', stat_fixture)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.write_records()

    def write_records(self):
        (self.e / 'owner.json').write_text(json.dumps(self.owner))
        (self.e / 'ownership-info.plist').write_bytes(plistlib.dumps({'images': self.records}))

    def test_owner_and_info_physical_bindings_original_retained_no_backing_hash(self):
        sha = ad.sha
        def guarded(path):
            self.assertNotEqual(Path(path), self.image, 'mutable image hashed')
            return sha(path)
        with patch.object(ad, 'sha', side_effect=guarded):
            state = ad.enclosure_state()
        self.assertEqual(state['owner'], self.owner)
        for key, name in [('ownerFile', 'owner.json'), ('infoFile', 'ownership-info.plist')]:
            self.assertEqual(state[key]['identity'], ad.identity(self.e / name))
            self.assertEqual(state[key]['physical'], ad.file_state(self.e / name))
        before = state['ownerFile']
        owner_file = self.e / 'owner.json'
        replacement = self.e / 'replacement'
        replacement.write_bytes(owner_file.read_bytes())
        replacement.replace(owner_file)
        self.assertNotEqual(ad.enclosure_state()['ownerFile'], before)

    def test_uncommitted_failed_or_releasing_setup_cannot_admit(self):
        # A valid owner file can survive a later setup/release failure. Physical
        # ownership alone must not turn that partial attempt into a new lease.
        for name in ('.setup-in-progress', 'setup-failure.json', 'release-evidence'):
            path = self.e / name
            path.write_bytes(b'bounded failed/in-progress evidence')
            try:
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'setup.*terminal|setup.*committed'):
                    ad.enclosure_state()
            finally:
                path.unlink()

    def test_unmounted_or_mutated_physical_owner_fails(self):
        self.mounted = False
        with self.assertRaises(ad.er.ReleaseError):
            ad.enclosure_state()
        self.mounted = True
        self.image.write_bytes(b'different size')
        with self.assertRaises(ad.er.ReleaseError):
            ad.enclosure_state()

    def test_owner_schema_and_strict_numeric_namespace_sanity_negatives(self):
        original = copy.deepcopy(self.owner)
        for section, key, value in [('image', 'st_dev', True), ('image', 'st_ino', 1.0),
                ('mount', 'st_dev', True), ('image', 'maxBytes', ad.CAPS['newRootBytes']),
                ('mount', 'path', str(self.g)), ('image', 'path', str(self.e / 'other.dmg'))]:
            self.owner = copy.deepcopy(original)
            self.owner[section][key] = value
            self.write_records()
            with self.subTest(section=section, key=key), self.assertRaises((ValueError, OSError)):
                ad.enclosure_state()
        self.owner = dict(original, unexpected=True)
        self.write_records()
        with self.assertRaises(ValueError):
            ad.enclosure_state()

    def test_device_info_unique_overlap_and_opaque_unrelated(self):
        self.records.append({'image-path': 'ram://2048', 'system-entities': [{'dev-entry': '/dev/disk99'}]})
        self.write_records()
        ad.enclosure_state()
        self.records[-1]['system-entities'][0]['dev-entry'] = '/dev/disk41'
        self.write_records()
        with self.assertRaisesRegex(ValueError, 'reused device'):
            ad.enclosure_state()
        self.records = [self.records[0], self.records[0]]
        self.write_records()
        with self.assertRaisesRegex(ValueError, 'unique image'):
            ad.enclosure_state()

    def test_ownership_files_bounded_unique_before_hash_or_read(self):
        for name in ('owner.json', 'ownership-info.plist'):
            path = self.e / name
            raw = path.read_bytes()
            for attack in ('oversize', 'hardlink', 'symlink'):
                with self.subTest(name=name, attack=attack):
                    if attack == 'oversize':
                        path.write_bytes(b'x' * (1024**2 + 1))
                    elif attack == 'hardlink':
                        os.link(path, self.e / 'alias')
                    else:
                        path.unlink()
                        path.symlink_to(self.tool)
                    # The other valid ownership file may be hashed first.
                    sha = ad.sha
                    def guarded(p):
                        self.assertNotEqual(Path(p), path, 'unsafe ownership hash')
                        return sha(p)
                    original_open = Path.open
                    def guarded_open(p, *args, **kwargs):
                        self.assertNotEqual(p, path, 'unsafe ownership read')
                        return original_open(p, *args, **kwargs)
                    with patch.object(ad, 'sha', side_effect=guarded), \
                         patch.object(Path, 'open', guarded_open), self.assertRaises(ValueError):
                        ad.enclosure_state()
                    if attack == 'hardlink':
                        (self.e / 'alias').unlink()
                    if attack == 'symlink':
                        path.unlink()
                    path.write_bytes(raw)

    def test_prepare_integrates_owner_products_budget_and_lifecycle_pins(self):
        forecast = dict(schema='static-vector-product-retention-forecast-v1',
            sourceCheckpoint=ad.CHECKPOINT, complete=True,
            products={key: 1 for key in ad.RETENTION_PRODUCTS})
        retention = self.p / 'retention.json'
        retention.write_text(json.dumps(forecast))
        metadata = ad.metadata_inventory(self.p)
        with patch.object(ad.config, 'validate_source'), \
             patch.object(ad, 'check_budget', return_value={'archiveBytes': 0}) as budget, \
             patch.object(ad.primitives, 'selected_paths', return_value=({'CMAKE_EXECUTABLE': '/cmake'}, '/SDK')), \
             patch.object(ad, 'physical', return_value='/SDK'), \
             patch.object(ad, 'source_roots', return_value=[]), \
             patch.object(ad, 'tree_members', return_value={}), \
             patch.object(ad.primitives, 'closure', return_value={'files': {}, 'aliases': {}}), \
             patch.object(ad.primitives, '_pin') as pin, \
             patch.object(ad, 'check_binaries', return_value={}), \
             patch.object(ad, 'current_inputs') as inputs:
            plan = ad.prepare(self.p / 'current30-admission', ad.CHECKPOINT,
                metadata, retention, ad.sha(retention),
                created_utc=dt.datetime.now(dt.timezone.utc).isoformat())
            self.assertEqual(plan['buildRoot'], str(self.p))
            self.assertEqual(plan['enclosure']['owner'], self.owner)
            self.assertEqual(plan['initialMetadata'], metadata)
            self.assertTrue(all(not call.args for call in budget.call_args_list))
            self.assertTrue(set(ad.LIFECYCLE_TOOLS.values()).issubset(pin.call_args.args[1]))
            self.assertNotIn('hdiutil', plan['tools'])
            self.assertTrue((self.p / 'current30-admission/plan.json').is_file())
            inputs.reset_mock()
            for section, field in [('image', 'st_ino'), ('image', 'size'), ('mount', 'st_dev')]:
                changed = copy.deepcopy(plan)
                changed['enclosure']['owner'][section][field] = float(
                    changed['enclosure']['owner'][section][field])
                with self.subTest(section=section, field=field), \
                     self.assertRaisesRegex(ValueError, 'ownership drift'):
                    ad.validate(changed)
                inputs.assert_not_called()
            self.owner['originalExperiment']['result'] = 'mutated'
            self.write_records()
            with self.assertRaisesRegex(ValueError, 'ownership drift'):
                ad.validate(plan)
            inputs.assert_not_called()

    def test_current_inputs_allows_os_state_change_but_not_hidden_native_or_frozen_state(self):
        generated = self.p / '.fseventsd'
        generated.mkdir()
        log = generated / 'uuid'
        log.write_text('initial OS state')
        retention = self.p / 'retention.json'
        retention.write_text('{}')
        plan = dict(toolPlan='mock', toolPlanSha256='mock', tools={}, sdk=str(self.e),
            sdkPhysical=str(self.e), sourceRoots=[], treeMembers={},
            witness={'files': {str(self.tool): ad.sha(self.tool)},
                     'aliases': {str(self.tool): str(self.tool)}},
            retention=ad.identity(retention), retentionForecast={}, python=str(self.tool),
            initialMetadata=ad.metadata_inventory(self.p), predecessors={},
            lifecycleTools=ad.LIFECYCLE_TOOLS,
            filesystemMetadataClassification={name: ad.FILESYSTEM_METADATA_CLASS
                                              for name in sorted(ad.FILESYSTEM_METADATA)})
        with patch.object(ad.config, 'validate_source'), \
             patch.object(ad.primitives, 'selected_paths', return_value=({}, str(self.e))), \
             patch.object(ad, 'source_roots', return_value=[]), \
             patch.object(ad, 'tree_members', return_value={}), \
             patch.object(ad.primitives, '_require_pin') as pin, \
             patch.object(ad, 'unchanged'), \
             patch.object(ad, 'check_binaries', return_value={}):
            log.write_text('changed UUID/log/OS state')
            ad.current_inputs(plan)
            self.assertEqual({call.args[1] for call in pin.call_args_list},
                             set(ad.LIFECYCLE_TOOLS.values()))
            log.write_bytes(b'\x7fELF')
            with self.assertRaisesRegex(ValueError, 'native input'):
                ad.current_inputs(plan)
            log.write_text('OS state again')
            plan['initialMetadata'][str(log)] = ad.identity(log)
            with self.assertRaisesRegex(ValueError, 'not immutable source'):
                ad.current_inputs(plan)
            del plan['initialMetadata'][str(log)]
            retention.write_text('{"changed": true}')
            with self.assertRaisesRegex(ValueError, 'retention proof drift'):
                ad.current_inputs(plan)

    def test_unmounted_prepare_fails_before_input_probes_or_writes(self):
        self.mounted = False
        before = set(self.p.iterdir())
        with patch.object(ad.config, 'validate_source', side_effect=AssertionError('source probe')), \
             patch.object(ad.primitives, 'selected_paths', side_effect=AssertionError('native probe')):
            with self.assertRaisesRegex(ValueError, 'mount host device|mount volume'):
                ad.prepare(self.p / 'current30-admission', ad.CHECKPOINT, {},
                    self.p / 'forecast', 'unused',
                    created_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        self.assertEqual(set(self.p.iterdir()), before)

    def test_duplicate_owner_keys_fail(self):
        path = self.e / 'owner.json'
        path.write_text('{"root":"wrong",' + path.read_text()[1:])
        with self.assertRaisesRegex(ValueError, 'duplicate owner'):
            ad.enclosure_state()


if __name__ == '__main__':
    unittest.main()
