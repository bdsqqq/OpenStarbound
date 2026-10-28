"""Synthetic sensitivity fixtures only: NO game, native origin, or runtime proof.

Only the private game-origin checker is bypassed for synthetic positive inputs.
Generic build, process, config, image, state and manifest validators still run.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import behavior_lab_id_map as lab
from test_id_map_proof import fixture as proof_fixture, image as proof_image


class SyntheticFrontendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='id-map-frontend-synthetic-', dir=lab._legacy.BUILD)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.build = self.root / 'build'
        self.build.mkdir()
        patch = mock.patch.object(lab._legacy, 'BUILD', self.build)
        patch.start()
        self.addCleanup(patch.stop)
        origin = mock.patch.object(lab, '_check_game_origin', return_value={'syntheticOnly': True})
        self.origin = origin.start()
        self.addCleanup(origin.stop)
        self.origin_patch = origin

    def write(self, path, value):
        path.write_text(json.dumps(value, sort_keys=True))

    def fixture(self, label='fixture', backend='native'):
        runner = lab._legacy
        parent = runner.create_owned(self.build / label)
        frames = runner.create_owned(parent / 'frames')
        runner.create_owned(frames / 'storage')
        binary = parent / 'SYNTHETIC-NOT-A-GAME'
        binary.write_bytes(b'synthetic bytes, never executable or game-origin evidence')
        assets = parent / 'synthetic.pak'
        assets.write_bytes(b'synthetic assets')
        config = dict(scenario=lab.SCENARIO, outputDirectory=str(frames),
                      storageDirectory=str(frames / 'storage'), platformWrites=False, maxFrames=1800)
        runner.dump(parent / 'scenario.json', config)
        runner.dump(parent / 'sbinit.config', {'syntheticOnly': True})
        builddir = parent / 'synthetic-cmake'
        builddir.mkdir()
        cache = {key: 'ON' if backend == 'rust' and key != 'STAR_USE_RUST_LINE_QUERY' else 'OFF'
                 for key in lab.SELECTORS}
        (builddir / 'CMakeCache.txt').write_text(''.join(f'{k}:BOOL={v}\n' for k, v in cache.items()))
        source = builddir / 'synthetic.cpp'
        source.write_text('// never compiled\n')
        self.write(builddir / 'compile_commands.json', [dict(file=str(source), directory=str(builddir))])
        provenance = runner.build_provenance
        snapshot = provenance.configured(provenance.begin(build_dir=builddir))
        proof = provenance.seal(binary, snapshot)
        binary_id = runner.identity(binary)
        config_id = runner.identity(parent / 'scenario.json')
        command = [str(binary), '-bootconfig', str(parent / 'sbinit.config')]
        for index, name in enumerate(lab._proof.STAGES):
            receipt = proof_fixture(index, backend)
            receipt['idMapProof']['configuration'] = config
            receipt.update(scenario=lab.SCENARIO, inWorld=True,
                           worldState={'invisibleSyntheticWorldState': ['keep-me', index == 1]},
                           worldId='synthetic-world', worldSize=[128, 96], playerPosition=[12, 4],
                           playerOutsideView=True, uiHidden=True, stabilization={'synthetic': True},
                           lightingCompleted=True, fullbright=False, material='smoothmetal',
                           lightObject='behaviorlabconstantlight', lightEntityId=100,
                           lightPosition=[52.5, 33.5], lightColor=[1, 1, 1],
                           lightType='PointAsSpread', lightEntityReplicated=True,
                           changedTileMin=[62, 33], changedTileMax=[62, 59], seed=42,
                           replicatedSettledUpdates=90, lightingBackend='rust' if backend == 'rust' else 'cpp',
                           rustLightingCalls=1 if backend == 'rust' else 0)
            proof_image(receipt).save(frames / (name + '.png'))
            runner.dump(frames / (name + '.json'), dict(name=name, file=name + '.png', width=640, height=480,
                        capture=dict(source='final-default-framebuffer', stage='after-imgui-before-swap'),
                        metadata=receipt))
        runner.dump(frames / lab.RESTORATION, dict(version=1, scenario=lab.SCENARIO, stat='behaviorLabIdMap',
                    value=0, ownedCategoriesAbsent=True, lastPreparedStage=2))
        launch = dict(binary=binary_id, command=command, configuration=config_id,
                      frontend=dict(identities=lab._frontend_identity(), argv=[str(Path(lab.__file__).resolve()),
                                    'capture', '--synthetic-fixture-not-game']))
        runner.dump(parent / 'launch.json', launch)
        start = dict(schema=1, pid=12345, pgid=12345, osStart='SYNTHETIC-NOT-OS-PROCESS', status='started',
                     command=command, binary=binary_id, configuration=config_id,
                     launch=runner.identity(parent / 'launch.json'))
        runner.dump(parent / 'process-start.json', start)
        end = dict(schema=1, pid=start['pid'], pgid=start['pgid'], osStart=start['osStart'], status='reaped',
                   exitCode=0, startReceipt=runner.identity(parent / 'process-start.json'))
        runner.dump(parent / 'process-exit.json', end)
        manifest = dict(schema=1, captureId=label, binary=binary_id, assets=runner.identity(assets),
                        bootconfig=runner.identity(parent / 'sbinit.config'), configuration=config_id,
                        buildProvenance=proof, exitCode=0, command=command,
                        processStart=runner.identity(parent / 'process-start.json'),
                        processExit=runner.identity(parent / 'process-exit.json'),
                        frames=runner.inventory(lab.captures(frames)),
                        overlayFiles=runner.overlay_identity(lab.SCENARIO),
                        semanticBootconfig={'syntheticOnly': True},
                        semanticConfiguration=dict(config, outputDirectory='<isolated-output>',
                                                   storageDirectory='<isolated-storage>'))
        runner.dump(frames / 'manifest.json', manifest)
        runner.dump(parent / lab.BINDING, lab._binding(frames, manifest, self.origin.return_value, launch))
        return frames

    def mutate(self, frames, callback, stage=0):
        path = frames / (lab._proof.STAGES[stage] + '.json')
        envelope = lab._legacy.load(path)
        callback(envelope)
        self.write(path, envelope)

    def reseal_synthetic(self, frames):
        """Fixture rebinding is not a producer or an origin attestation."""
        runner = lab._legacy
        launch = runner.load(frames.parent / 'launch.json')
        start_path = frames.parent / 'process-start.json'
        start = runner.load(start_path)
        start['launch'] = runner.identity(frames.parent / 'launch.json')
        self.write(start_path, start)
        end_path = frames.parent / 'process-exit.json'
        end = runner.load(end_path)
        end['startReceipt'] = runner.identity(start_path)
        self.write(end_path, end)
        manifest_path = frames / 'manifest.json'
        manifest = runner.load(manifest_path)
        manifest.update(processStart=runner.identity(start_path), processExit=runner.identity(end_path),
                        frames=runner.inventory(lab.captures(frames)))
        self.write(manifest_path, manifest)
        self.write(frames.parent / lab.BINDING,
                   lab._binding(frames, manifest, self.origin.return_value, launch))

    def test_synthetic_positive_both_backends_generic_actual29_and_invisible_state(self):
        for backend in ('native', 'rust'):
            frames = self.fixture(backend, backend)
            captured, manifest = lab.validated(frames)
            self.assertEqual(len(captured), 3)
            self.assertEqual(len(manifest['buildProvenance']['build_identity']['cache']), 29)
            state = captured[lab._proof.STAGES[0]]['receipt']['worldState']
            self.assertEqual(state['declared']['invisibleSyntheticWorldState'], ['keep-me', False])
            self.assertIn('worldId', state['native'])
            self.assertIn('idMapProof', state)

    def test_synthetic_exact_compare_and_native_repeat(self):
        reference = self.fixture('ref')
        repeat = self.fixture('repeat')
        candidate = self.fixture('candidate', 'rust')
        # Baseline binary identities must match, just like independent real captures.
        self.assertTrue(lab.pair_compare(reference, repeat, self.build / 'repeat-report', True)['passed'])
        report = lab.pair_compare(reference, candidate, self.build / 'candidate-report')
        self.assertTrue(report['passed'], report)
        self.assertTrue(all(row['changedPixels'] == 0 for row in report['frames'].values()))

    def test_bad_proof_and_continuation_rejected_before_manifest(self):
        frames = self.fixture()
        self.mutate(frames, lambda e: e['metadata']['idMapProof']['visual'].update(value=True))
        with self.assertRaisesRegex(lab.LabError, 'stat readback'):
            lab.captures(frames)
        frames = self.fixture('rust', 'rust')
        self.mutate(frames, lambda e: e['metadata']['idMapProof']['countersAfter'][4].__setitem__(1, '0000000000000064'))
        with self.assertRaisesRegex(lab.LabError, 'minimum'):
            lab.captures(frames)

    def test_restore_missing(self):
        frames = self.fixture()
        (frames / lab.RESTORATION).unlink()
        with self.assertRaises(OSError):
            lab.validated(frames)

    def test_restore_exact_types_schema_and_final_stage(self):
        frames = self.fixture()
        path = frames / lab.RESTORATION
        original_bytes = path.read_bytes()
        original = lab._legacy.load(path)
        for key, value in (('version', True), ('value', False), ('value', 0.0),
                           ('ownedCategoriesAbsent', 1), ('lastPreparedStage', True),
                           ('lastPreparedStage', 1), ('stat', 'other'), ('extra', 0)):
            with self.subTest(key=key, value=value):
                self.write(path, dict(original, **{key: value}))
                with self.assertRaisesRegex(lab.LabError, 'restoration'):
                    lab.captures(frames)
        path.write_bytes(original_bytes)
        lab.validated(frames)

    def test_unknown_json_missing_png_and_missing_metadata(self):
        frames = self.fixture()
        unknown = frames / 'other-restoration.json'
        self.write(unknown, {})
        with self.assertRaisesRegex(lab.LabError, 'unknown JSON'):
            lab.captures(frames)
        unknown.unlink()
        png = frames / (lab._proof.STAGES[0] + '.png')
        data = png.read_bytes()
        png.unlink()
        with self.assertRaisesRegex(lab.LabError, 'three paired'):
            lab.captures(frames)
        png.write_bytes(data)
        self.mutate(frames, lambda e: e.pop('metadata'))
        with self.assertRaisesRegex(lab.LabError, 'metadata'):
            lab.captures(frames)

    def test_envelope_and_framebuffer_metadata_rejected(self):
        for index, mutation in enumerate((lambda e: e.update(width=True), lambda e: e.update(file='wrong.png'),
                                          lambda e: e['capture'].update(stage='before-world-render'))):
            frames = self.fixture(str(index))
            self.mutate(frames, mutation)
            with self.assertRaises(lab.LabError):
                lab.captures(frames)

    def test_wrong_backend_explicit_dispatch(self):
        reference = self.fixture('reference')
        wrong = self.fixture('wrong')
        report = lab.pair_compare(reference, wrong, self.build / 'wrong-report')
        self.assertFalse(report['passed'])
        self.assertIn('correct comparison backend', report['errors'][0])
        self.assertTrue((self.build / 'wrong-report/report.json').is_file())

    def test_config_binding(self):
        frames = self.fixture()
        self.mutate(frames, lambda e: e['metadata']['idMapProof']['configuration'].update(platformWrites=True))
        # Refreshing inventory cannot waive the proof/config equality check.
        manifest_path = frames / 'manifest.json'
        manifest = lab._legacy.load(manifest_path)
        # All stages must first agree, independently of manifest binding.
        for stage in (1, 2):
            self.mutate(frames, lambda e: e['metadata']['idMapProof']['configuration'].update(platformWrites=True), stage)
        manifest['frames'] = lab._legacy.inventory(lab.captures(frames))
        self.write(manifest_path, manifest)
        with self.assertRaisesRegex(lab.LabError, 'source/capture configuration'):
            lab.validated(frames)

    def test_selectors_missing_and_wrong_no_actual28_downgrade(self):
        for change in (lambda c: c.pop(lab._proof.SELECTOR),
                       lambda c: c.update(STAR_USE_RUST_LINE_QUERY='ON'),
                       lambda c: c.update(STAR_USE_RUST_LIGHTING='OFF'),
                       lambda c: c.update(STAR_USE_RUST_UNEXPECTED='OFF')):
            proof = {'build_identity': {'cache': {key: 'ON' if key != 'STAR_USE_RUST_LINE_QUERY' else 'OFF'
                                                 for key in lab.SELECTORS}}}
            change(proof['build_identity']['cache'])
            with self.assertRaises(lab.LabError):
                lab._check_selectors(proof, 'rust')

    def test_frozen_legacy_hash_negative(self):
        path = self.root / 'changed-legacy.py'
        path.write_bytes((lab.HERE / 'behavior_lab.py').read_bytes() + b'\n# changed\n')
        with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
            lab._load_legacy(path)
        self.assertEqual(lab._legacy.sha(lab.HERE / 'behavior_lab.py'), lab.LEGACY_SHA256)
        self.assertEqual(lab._legacy.sha(lab.HERE / 'test_native_scenario_contract.py'),
                         '67c8df97ee69a4d6f79c8b8afa934f83192fb5e25f9b09270447397d40653391')

    def test_old24_delegation_uses_original_functions(self):
        import behavior_lab as frozen
        self.assertIsNot(lab._legacy, frozen)
        self.assertEqual(len(frozen.SCENARIOS), 24)
        self.assertEqual(lab.SCENARIOS[:-1], frozen.SCENARIOS)
        for scenario in frozen.SCENARIOS:
            self.assertEqual(lab.asset_overlays(scenario), frozen.asset_overlays(scenario))
        # Reuse the frozen suite's synthetic fixture without changing its module.
        from test_behavior_lab import BehaviorLabTests
        fixture = BehaviorLabTests('test_ray_public_exact_compare_and_both_lighting_backends')
        fixture.root = self.build
        for hook in ('captures', 'validated'):
            self.assertEqual(lab._original[hook].__code__.co_code, getattr(frozen, hook).__code__.co_code)
        directory = fixture.fixture('old24')
        self.assertEqual(lab.captures(directory), frozen.captures(directory))
        self.assertEqual(lab.validated(directory), frozen.validated(directory))

    def test_visible_corruption_and_label_absence(self):
        from PIL import ImageDraw
        for label, corrupt in (('pixel', lambda image: image.putpixel((320, 240), (1, 2, 3, 255))),
                               ('label', lambda image: ImageDraw.Draw(image).rectangle((220, 140, 227, 140), fill='black'))):
            frames = self.fixture(label)
            path = frames / (lab._proof.STAGES[0] + '.png')
            image = lab._legacy.image(path)
            corrupt(image)
            image.save(path)
            with self.assertRaisesRegex(lab.LabError, 'pixels|Font label'):
                lab.captures(frames)

    def test_invisible_state_corruption_is_not_discarded(self):
        frames = self.fixture()
        self.mutate(frames, lambda e: e['metadata']['worldState'].update(invisibleSyntheticWorldState='changed'), 2)
        with self.assertRaisesRegex(lab.LabError, 'declared restoration'):
            lab.captures(frames)

    def test_process_exit_config_manifest_and_sidecar_tampering(self):
        for label, relative, change in (
            ('exit', 'process-exit.json', lambda p: p.update(exitCode=True)),
            ('process', 'process-start.json', lambda p: p.update(osStart='CHANGED')),
            ('config', 'scenario.json', lambda p: p.update(platformWrites=True)),
            ('binding', lab.BINDING, lambda p: p.update(gameOrigin={'unrelatedArchive': True})),
            ('tool', 'launch.json', lambda p: p['frontend']['argv'].__setitem__(0, str(lab.HERE / 'behavior_lab.py'))),
        ):
            frames = self.fixture(label)
            path = frames.parent / relative
            value = lab._legacy.load(path)
            change(value)
            self.write(path, value)
            with self.subTest(label=label), self.assertRaises(lab.LabError):
                lab.validated(frames)

    def test_restoration_bytes_bound_even_when_semantically_identical(self):
        frames = self.fixture()
        path = frames / lab.RESTORATION
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(lab.LabError, 'binding changed'):
            lab.validated(frames)

    def test_aborted_capture_never_passes(self):
        frames = self.fixture()
        self.write(frames.parent / 'failure.json', {'syntheticOnly': True})
        with self.assertRaisesRegex(lab.LabError, 'aborted capture'):
            lab.validated(frames)
        self.assertTrue((frames.parent / 'failure.json').exists())

    def test_rebound_old_tool_argv_still_rejected(self):
        frames = self.fixture()
        launch_path = frames.parent / 'launch.json'
        launch = lab._legacy.load(launch_path)
        launch['frontend']['argv'][0] = str(lab.HERE / 'behavior_lab.py')
        self.write(launch_path, launch)
        self.reseal_synthetic(frames)
        with self.assertRaisesRegex(lab.LabError, 'frontend tool identity/argv'):
            lab.validated(frames)

    def test_current_origin_changed_without_rebinding_sidecar(self):
        frames = self.fixture()
        self.origin.return_value = {'syntheticOnly': True, 'changedGameOrigin': True}
        with self.assertRaisesRegex(lab.LabError, 'binding changed'):
            lab.validated(frames)

    def test_exact_full_frame_corruption_outside_assertion_regions(self):
        reference = self.fixture('reference')
        candidate = self.fixture('candidate', 'rust')
        path = candidate / (lab._proof.STAGES[1] + '.png')
        image = lab._legacy.image(path)
        image.putpixel((0, 0), (1, 2, 3, 255))
        image.save(path)
        self.reseal_synthetic(candidate)
        lab.validated(candidate)
        output = self.build / 'full-frame-negative'
        report = lab.pair_compare(reference, candidate, output)
        self.assertFalse(report['passed'])
        row = report['frames'][lab._proof.STAGES[1]]
        self.assertEqual(row['changedPixels'], 1)
        self.assertIn('exact framebuffer gate failed', row['errors'])
        self.assertTrue((output / (lab._proof.STAGES[1] + '-diff.png')).is_file())

    def test_cli_requires_baseline_and_reports_diagnostic_only(self):
        reference = self.fixture('reference')
        repeat = self.fixture('repeat')
        candidate = self.fixture('candidate', 'rust')
        args = ['compare', '--reference', str(reference), '--candidate', str(candidate),
                '--output', str(self.build / 'cli-output')]
        self.assertEqual(lab.main(args), 2)
        self.assertFalse((self.build / 'cli-output').exists())
        self.assertEqual(lab.main(args + ['--repeat', str(repeat)]), 0)
        report = lab._legacy.load(self.build / 'cli-output/report.json')
        self.assertTrue(report['passed'])
        self.assertIs(report['parityCertified'], False)
        self.assertIs(report['inspectionRequired'], True)

    def test_successor25_matches_native_gate_without_rebinding_frozen24(self):
        from test_native_scenario_contract import check_native_scenarios
        source = (lab._legacy.ROOT / 'source/client/StarClientApplication.cpp').read_text()
        check_native_scenarios(source, lab.SCENARIOS)
        with self.assertRaisesRegex(ValueError, 'startup scenario allowlist'):
            check_native_scenarios(source, lab._legacy.SCENARIOS[:-1])
        clause = ' && scenario != "id-map-room"'
        self.assertEqual(source.count(clause), 1)
        with self.assertRaisesRegex(ValueError, 'startup scenario allowlist'):
            check_native_scenarios(source.replace(clause, '', 1), lab.SCENARIOS)

    def test_oversized_old24_image_writes_failure_and_cli_rejects(self):
        import struct
        import zlib
        from test_behavior_lab import BehaviorLabTests
        fixture = BehaviorLabTests('test_ray_public_exact_compare_and_both_lighting_backends')
        fixture.root = self.build
        frames = fixture.fixture('oversized-old24')
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
        header = struct.pack('>IIBBBBB', 10000, 10000, 8, 6, 0, 0, 0)
        png = next(frames.glob('*.png'))
        png.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(b'')) + chunk(b'IEND', b''))
        output = self.build / 'oversized-failure'
        report = lab.pair_compare(frames, frames, output, same_backend=True)
        self.assertFalse(report['passed'])
        self.assertTrue((output / 'report.json').is_file())
        self.assertEqual(lab.main(['verify', str(frames)]), 2)

    def test_origin_not_ready_and_capture_fail_closed_without_launch(self):
        frames = self.fixture()
        self.origin_patch.stop()
        with self.assertRaisesRegex(lab.LabError, 'origin|OriginNotReady'):
            lab.validated(frames)
        # Regardless of a parent-provided origin checker, launch producer is absent.
        self.origin_patch.start()
        output = self.build / 'must-not-launch'
        with self.assertRaisesRegex(lab.LabError, 'launch-admission producer'):
            lab.capture(frames.parent / 'SYNTHETIC-NOT-A-GAME', frames.parent / 'synthetic.pak', output, 1)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
