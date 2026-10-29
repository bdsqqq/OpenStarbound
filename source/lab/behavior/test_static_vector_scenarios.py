"""Synthetic dispatch and source-projection controls; no native/game evidence."""
import copy
import inspect
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import static_vector_scenarios as s
import behavior_lab_static_vector as lab


class RegistryTests(unittest.TestCase):
    def test_exact26_and_frozen(self):
        s.assert_frozen()
        self.assertEqual(s.SCENARIOS25, (*s.runner.SCENARIOS, 'id-map-room'))
        self.assertEqual(s.SCENARIOS, (*s.SCENARIOS25, 'static-vector-room'))
        self.assertEqual(len(set(s.SCENARIOS)), 26)

    def test_all25_decode_dispatch_only(self):
        for scenario in s.SCENARIOS25:
            fixture = {'synthetic': {'receipt': {'scenario': scenario}}}
            with self.subTest(scenario=scenario), mock.patch.object(s.runner, 'captures', return_value=fixture) as old24, \
                    mock.patch.object(s.id_decoder, 'captures', return_value=fixture) as old25:
                self.assertEqual(s.decode_old(Path('/synthetic-only'), scenario), fixture)
                self.assertEqual(old25.call_count, int(scenario == 'id-map-room'))
                self.assertEqual(old24.call_count, int(scenario != 'id-map-room'))
        with self.assertRaises(s.runner.LabError):
            s.decode_old(Path('/synthetic-only'), s.SCENARIO)
        with self.assertRaises(s.runner.LabError):
            s.require('unknown-room')

    def test_all26_overlay_projection(self):
        for scenario in s.SCENARIOS:
            expected = s.runner.asset_overlays(scenario)
            if scenario == 'id-map-room':
                expected['id-map-fixture'] = s.HERE / 'id-map-assets'
            self.assertEqual(s.asset_overlays(scenario), expected)
        self.assertEqual(s.asset_overlays(s.SCENARIO), s.runner.ASSET_OVERLAYS)

    def test_current30_profiles_bad_membership_and_values(self):
        for role, selectors in s.configuration.profiles().items():
            proof = {'build_identity': {'cache': selectors}}
            self.assertEqual(s.backend(proof), 'rust' if role == 'candidate' else 'native')
            for mutate in (lambda c: c.pop(s.configuration.STATIC_VECTOR),
                           lambda c: c.update(STAR_USE_RUST_LINE_QUERY='ON'),
                           lambda c: c.update(STAR_USE_RUST_FAKE='OFF'),
                           lambda c: c.update(STAR_USE_RUST_STATIC_VECTOR=True)):
                bad = copy.deepcopy(proof)
                mutate(bad['build_identity']['cache'])
                with self.assertRaises(ValueError):
                    s.backend(bad)

    def test_old_comparator_every_branch_is_exact_source_projection(self):
        old = inspect.getsource(s.runner.pair_compare)
        new = inspect.getsource(lab.pair_compare)
        start = '            if ref_meta["scenario"] == "buffer-room":'
        added_start = new.index('            if ref_meta["scenario"] in ("static-vector-room", "id-map-room"):')
        added_end = new.index('            elif ref_meta["scenario"] == "buffer-room":')
        new = new[:added_start] + start + new[added_end + len('            elif ref_meta["scenario"] == "buffer-room":'):]
        new = new.replace('"parityCertified": False, "inspectionRequired": True, ', '')
        self.assertEqual(old, new)
        # This includes Buffer IODevice/File/ByteArray and all exception/pixel paths.
        self.assertIn('ref_io', new)
        self.assertIn('ref_file', new)
        self.assertIn('ref_ba', new)

    def test_all26_comparator_dispatch_positive_and_wrong_backend(self):
        # Already-decoded fake data exercises comparator branch dispatch only.
        # The source projection above separately guards the complete old decoder.
        from PIL import Image
        routes = {
            'encoding-room': ('encodingProof',), 'sha256-room': ('sha256Proof', 'assets'),
            'vlq-room': ('vlqProof', 'assets'), 'bytes-room': ('bytesProof', 'assets'),
            'unicode-room': ('unicodeProof', 'assets'), 'shell-room': ('shellProof',),
            'jsonpath-room': ('jsonPathProof', 'assets'), 'assetpath-room': ('assetPathProof', 'assets'),
            'random-room': ('randomMwcProof',), 'jsonpatch-room': ('jsonPatchProof', 'assets'),
            'text-room': ('textScanProof',), 'zstd-room': ('zstdProof',),
            'option-parser-room': ('optionParserProof',), 'host-address-room': ('hostAddressProof',),
            'datastream-room': ('dataStreamProof',), 'buffer-room': ('bufferProof',),
            'stringview-room': ('stringViewProof',), 'path-embed-room': ('pathEmbedProof',),
            'lru-room': ('lruProof',), 'ttl-room': ('ttlProof',), 'weighted-pool-room': ('weightedPoolProof',),
            'id-map-room': ('idMapProof',), s.SCENARIO: ('staticVectorProof',),
        }
        native = {'path-embed-room', 'lru-room', 'ttl-room', 'weighted-pool-room', 'id-map-room', s.SCENARIO}
        def metadata(scene, candidate=False):
            wanted = 'rust' if candidate else 'native' if scene in native else 'cpp'
            row = dict(scenario=scene, inWorld=True, stage='synthetic-stage', worldState={'retainedInvisible': True},
                       lightingBackend='rust' if candidate and scene == 'lighting-room' else 'cpp')
            if scene in routes:
                node = row
                for key in routes[scene]:
                    node[key] = {}
                    node = node[key]
                node['backend'] = wanted
            elif scene == 'raycast-room':
                row['raycastState'] = {side: {'backend': wanted} for side in ('client', 'server')}
            elif scene == 'compression-room':
                row['compressionProof'] = {'operations': {key: {'backend': wanted} for key in ('embed', 'zlib', 'gzip')}}
            if scene == 'buffer-room':
                row['bufferProof'].update(ioDevice={'backend': wanted}, byteArray={'backend': wanted})
                row['fileProof'] = {'backend': wanted}
            return row
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'build').mkdir()
            ref, cand = root / 'ref', root / 'candidate'
            ref.mkdir()
            cand.mkdir()
            png = root / 'frame.png'
            Image.new('RGBA', (2, 2), (10, 20, 30, 255)).save(png)
            manifest = dict(captureId='ref', assets={'sha256': 'fake'}, binary={'sha256': 'fake'},
                            overlayFiles={}, semanticBootconfig={}, semanticConfiguration={})
            for scene in s.SCENARIOS:
                with self.subTest(scene=scene), mock.patch.object(s.runner, 'BUILD', root / 'build'), \
                        mock.patch.object(lab, 'check_owned', side_effect=lambda value: value):
                    ref_meta, cand_meta = metadata(scene), metadata(scene, True)
                    def decoded(path):
                        return ({'frame': dict(receipt=ref_meta if path == ref else cand_meta, png=png, dimensions=[2, 2])},
                                dict(manifest, captureId='ref' if path == ref else 'candidate'))
                    with mock.patch.object(lab, 'validated', side_effect=decoded):
                        result = lab.pair_compare(ref, cand, root / 'build' / (scene + '-positive'))
                        self.assertTrue(result['passed'], result['errors'])
                        # Replace the whole candidate metadata with the reference
                        # backend: every branch must refuse this false candidate.
                        cand_meta.clear()
                        cand_meta.update(metadata(scene))
                        self.assertFalse(lab.pair_compare(ref, cand, root / 'build' / (scene + '-bad'))['passed'])

    def test_old_receipt_config_and_weighted_source_checks(self):
        for scenario, key in (('weighted-pool-room', 'weightedPoolProof'), ('ttl-room', 'ttlProof'), ('id-map-room', 'idMapProof')):
            config = {'scenario': scenario}
            proof = {'build_identity': {'cache': s.configuration.profiles()['reference']},
                     'source_files': {k: 'a' * 64 for k in s.runner.build_provenance.WEIGHTED_POOL_SOURCES}}
            frames = {'stage': {'receipt': {key: {'backend': 'native', 'configuration': config}}}}
            s.bind_old(frames, scenario, proof, config)
            bad = copy.deepcopy(frames)
            bad['stage']['receipt'][key]['configuration'] = {'scenario': 'wrong'}
            with self.assertRaises(s.runner.LabError):
                s.bind_old(bad, scenario, proof, config)
            if scenario == 'weighted-pool-room':
                proof['source_files'].pop(next(iter(proof['source_files'])))
                with self.assertRaises(s.runner.LabError):
                    s.bind_old(frames, scenario, proof, config)


if __name__ == '__main__':
    unittest.main()
