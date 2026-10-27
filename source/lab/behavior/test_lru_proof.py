"""Deterministic LOGICAL fixtures only. These tests never execute/build the game."""
import copy
import json
from pathlib import Path
import unittest
from unittest import mock
from PIL import Image, ImageDraw
import lru_proof as p
import behavior_lab as lab


def fixture(backend='rust', phase=2, initial=(), mutant=None, origin=123):
    """Produce coherent alternate executions, not just broken report hashes."""
    keys = list(initial)
    events = []
    c = origin if backend == 'rust' else 0
    for index, requested in enumerate(p.requests()[:p.COUNTS[phase]]):
        n = p.MISSING if requested is None else p.name(requested)
        key = n.encode().hex()
        before = p.state(keys)
        # Mutants deliberately implement common *different* LRU semantics.
        if not ((mutant == 'hit-keeps-capacity' or
                 (mutant == 'warmup-hit-keeps-capacity' and index < 20)) and key in keys):
            while len(keys) > 19:
                keys.pop(0)
        produced = key not in keys or mutant == 'hit-produces' or (
            mutant == 'warmup-hit-produces' and index < 20)
        producer_state = p.state(keys) if produced else None
        if requested is None:
            if mutant == 'error-rolls-back':
                keys = before['keysHex'][:]
            status, error = 'error', dict(kind='std::exception',
                messageHex=f"(DungeonException) Unknown dungeon: '{n}'".encode().hex())
        else:
            if not (mutant == 'warmup-omit-promotion' and index == 0 and key in keys):
                if key in keys:
                    keys.remove(key)
                keys.append(key)
            status, error = 'ok', None
        after_c = (c + (backend == 'rust')) % 2**64
        if mutant == 'error-not-counted' and requested is None:
            after_c = c
        events.append(dict(operation='DungeonDefinitions.get', index=index, phase=p.phase_for(index),
            nameHex=key, before=before, after=p.state(keys), producerCalled=produced,
            producerState=producer_state, status=status, error=error,
            rootBeforeHex=c.to_bytes(8, 'big').hex(), rootAfterHex=after_c.to_bytes(8, 'big').hex()))
        c = after_c
    selected = (21, 1, 2)[phase]
    color = [selected*8, selected*4, (phase+1)*80, 255]
    results = []
    for index, requested in enumerate(p.requests()[:p.COUNTS[phase]]):
        if p.phase_for(index) != phase:
            continue
        if requested is None:
            results.append(dict(name=p.MISSING, ok=False, error=f"(DungeonException) Unknown dungeon: '{p.MISSING}'"))
        else:
            results.append(dict(name=p.name(requested), ok=True, metadata=p.metadata(requested)))
    visual = dict(phase=phase, results=results, continuation=True, selected=p.metadata(selected),
        color=color, label=f'LRU {phase+1}/3 metadata={selected:02d} continue=ok', scale=4,
        imagePath='/behaviorlab/lru-white.png?multiply='+bytes(color).hex())
    proof = dict(version=1, backend=backend, selector=p.SELECTOR, scopeThread='lua-calling-thread',
        phase=phase, events=events, visual=visual,
        consumer='normal-root.dungeonMetadata-Assets-DungeonDefinition',
        imageConsumer='normal-Assets-WorldPainter', labelConsumer='normal-Font-TextPainter')
    return dict(lruProof=proof, scenario='lru-room', cameraPosition=[64, 48], cameraPixelRatio=2,
        stageIndex=phase, stage=p.STAGES[phase], action=p.ACTIONS[phase], occluderPresent=phase == 1,
        materialId=1, observedOccluderMaterial=1 if phase == 1 else 0)


def frame(receipt):
    """Synthetic verifier sensitivity image, NEVER application evidence."""
    image = Image.new('RGBA', (400, 240), (21, 20, 19, 255))
    ImageDraw.Draw(image).rectangle((168, 88, 231, 151), fill=tuple(receipt['lruProof']['visual']['color']))
    ImageDraw.Draw(image).rectangle((165, 40, 234, 43), fill=(255, 255, 255, 255))
    return image


def frames(backend='rust', mutate=None, initial=()):
    directory = mock.Mock()
    pngs = [Path('/logical')/(stage+'.png') for stage in p.STAGES]
    paths = [path.with_suffix('.json') for path in pngs]
    directory.glob.side_effect = lambda pattern: pngs if pattern == '*.png' else paths
    envelopes, images = {}, {}
    for phase, path in enumerate(paths):
        r = {field: 'logical-stable-world' for field in lab.SCENE_FIELDS}
        r.update(fixture(backend, phase, initial=initial))
        r.update(inWorld=True, playerOutsideView=True, uiHidden=True, lightingCompleted=True,
            lightEntityReplicated=True, fullbright=False, replicatedSettledUpdates=90,
            lightingBackend='cpp', rustLightingCalls=0)
        if mutate:
            mutate(r, phase)
        images[pngs[phase]] = frame(r)
        envelopes[path] = dict(name=p.STAGES[phase], file=pngs[phase].name, width=400, height=240,
            metadata=r, capture=dict(source='final-default-framebuffer', stage='after-imgui-before-swap'))
    with mock.patch.object(lab, 'check_owned', side_effect=lambda x:x), \
         mock.patch.object(lab, 'load', side_effect=envelopes.__getitem__), \
         mock.patch.object(lab, 'image', side_effect=images.__getitem__), \
         mock.patch.object(lab, 'sha', return_value='0'*64):
        return lab.captures(directory)


def compare(reference, candidate, repeat=False):
    def manifest(identity):
        return dict(captureId=identity, assets=dict(sha256='0'*64), binary=dict(sha256='0'*64),
            overlayFiles={}, semanticBootconfig={}, semanticConfiguration={})
    with mock.patch.object(lab, 'create_owned', side_effect=lambda x:x), \
         mock.patch.object(lab, 'check_owned', side_effect=lambda x:x), \
         mock.patch.object(lab, 'validated', side_effect=[(reference, manifest('a')), (candidate, manifest('b'))]), \
         mock.patch.object(lab, 'dump'), mock.patch.object(lab, 'image', return_value=Image.new('RGBA',(400,240))), \
         mock.patch.object(Image.Image, 'save'):
        return lab.pair_compare(Path('/logical/a'), Path('/logical/b'), Path('/logical/output'), same_backend=repeat)


class LruProofTests(unittest.TestCase):
    def test_baseline_candidate_normalize_without_masking_semantics(self):
        for phase in range(3):
            self.assertEqual(p.validate(fixture('native', phase)), p.validate(fixture('rust', phase)))
            p.visible(frame(fixture(phase=phase)), fixture(phase=phase))
        p.validate_snapshots([fixture(phase=i) for i in range(3)])

    def test_initial_actual_cache_is_observed_not_assumed_empty(self):
        for size in (0, 1, 19, 20):
            for initial in ([f'{i:02x}ff00' for i in range(size)],
                            [p.name(i+1).encode().hex() for i in range(size)]):
                with self.subTest(size=size, initial=initial):
                    p.validate(fixture(initial=initial))
        # opaque non-UTF8 keys survive in the evidence without symbol decoding.
        result = p.validate(fixture(initial=['fffe0080']))
        self.assertEqual(result['events'][0]['before']['keysHex'], ['fffe0080'])

    def test_convergence_observation_for_every_initial_occupancy(self):
        for size in range(21):
            opaque = [(b'\xff\x00' + bytes([i])).hex() for i in range(size)]
            forward = [p.name(i+1).encode().hex() for i in range(size)]
            reverse = [p.name(21-i).encode().hex() for i in range(size)]
            mixed = [forward[i] if i % 2 else opaque[i] for i in range(size)]
            unknown = [p.MISSING.encode().hex()] + opaque[1:] if size else []
            for initial in (opaque, forward, reverse, mixed, unknown):
                for backend in ('native', 'rust'):
                    for phase in range(3):
                        with self.subTest(size=size, initial=initial, backend=backend, phase=phase):
                            receipt = fixture(backend, phase, initial=initial)
                            original = copy.deepcopy(receipt)
                            self.assertEqual(p.observation(receipt), p.observation(fixture('native', phase)))
                            self.assertEqual(receipt, original, 'raw evidence must remain untouched')
                            self.assertEqual(p.validate(receipt)['events'][0]['before'], p.state(initial))

    def test_warmup_defects_reject_before_projection_even_if_they_converge(self):
        first = p.name(1).encode().hex()
        opaque = [bytes([i, 255]).hex() for i in range(19)]
        cases = [('warmup-hit-produces', [first]),
                 ('warmup-hit-keeps-capacity', opaque + [first]),
                 ('warmup-omit-promotion', [first, 'ff00'])]
        for mutant, initial in cases:
            r = fixture(initial=initial, mutant=mutant)
            self.assertEqual(r['lruProof']['events'][20]['after'], fixture()['lruProof']['events'][20]['after'])
            with self.subTest(mutant=mutant), self.assertRaises(ValueError):
                p.observation(r)
        for index in (19, 20):
            r = fixture(); r['lruProof']['events'][index]['after']['keysHex'].reverse()
            with self.subTest(index=index), self.assertRaises(ValueError):
                p.observation(r)

    def test_raw_initial_history_cannot_be_rewritten_between_frames(self):
        rs = [fixture(phase=i, initial=['ff00']) for i in range(3)]
        changed = copy.deepcopy(rs); changed[2] = fixture(phase=2, initial=['fe00'])
        self.assertEqual(p.observation(rs[2]), p.observation(changed[2]))
        with self.assertRaisesRegex(ValueError, 'history'):
            p.validate_snapshots(changed)

    def test_common_comparator_relates_different_valid_initial_inputs(self):
        opaque = ['ff00', 'fe00']
        occupied = [p.name(i).encode().hex() for i in range(20, 0, -1)]
        native = frames('native', initial=opaque)
        for backend, repeat in (('native', True), ('rust', False)):
            self.assertTrue(compare(native, frames(backend, initial=occupied), repeat)['passed'])

    def test_deterministic_error_bytes_remain_exact_after_projection(self):
        original = fixture('native', phase=1)
        changed = copy.deepcopy(original)
        changed['lruProof']['events'][23]['error']['messageHex'] += b' extra'.hex()
        changed['lruProof']['visual']['results'][1]['error'] += ' extra'
        p.validate(changed)  # individually recognizable error, different exact bytes
        self.assertNotEqual(p.observation(original), p.observation(changed))
        def mutate(r, phase):
            if phase >= 1:
                r['lruProof']['events'][23]['error']['messageHex'] += b' extra'.hex()
                if phase == 1:
                    r['lruProof']['visual']['results'][1]['error'] += ' extra'
        result = compare(frames('native'), frames('rust', mutate=mutate))
        self.assertFalse(result['passed'])

    def test_raw_lua_backtrace_is_diagnostic_not_native_message(self):
        a = fixture(phase=1)
        b = copy.deepcopy(a)
        a['lruProof']['visual']['results'][1]['error'] += '\nStack trace (most recent call first):\n#0 0x123 native-frame'
        b['lruProof']['visual']['results'][1]['error'] += '\nStack trace (most recent call first):\n#0 0x456 rust-frame'
        raw = copy.deepcopy(a)
        self.assertEqual(p.observation(a), p.observation(b))
        self.assertEqual(a, raw, 'full raw diagnostic must stay recorded')
        b['lruProof']['visual']['results'][1]['error'] = 'different message'
        with self.assertRaisesRegex(ValueError, 'message mismatch'):
            p.observation(b)
        b = fixture(phase=1)
        b['lruProof']['visual']['results'][1]['error'] += '\nnot a recognized backtrace'
        with self.assertRaisesRegex(ValueError, 'diagnostic format'):
            p.observation(b)

    def test_required_members_fail_closed(self):
        original = fixture()
        paths = [(), ('events', 0), ('events', 0, 'before'), ('events', 23, 'error'),
                 ('visual',), ('visual', 'selected'), ('visual', 'results', 0),
                 ('visual', 'results', 1)]
        def at(root, path):
            for key in path:
                root = root[key]
            return root
        for path in paths:
            for key in at(original['lruProof'], path):
                r = copy.deepcopy(original)
                at(r['lruProof'], path).pop(key)
                with self.subTest(path=path, key=key), self.assertRaises(ValueError):
                    p.validate(r)
            r = copy.deepcopy(original)
            at(r['lruProof'], path)['extra'] = False
            with self.subTest(path=path, extra=True), self.assertRaises(ValueError):
                p.validate(r)

    def test_counter_bits_wrap_exactly(self):
        p.validate(fixture(origin=2**64-5))
        r = fixture()
        r['lruProof']['events'][0]['rootBeforeHex'] = 123
        with self.assertRaisesRegex(ValueError, 'hex'):
            p.validate(r)

    def test_coherent_different_cache_algorithms_rejected(self):
        for mutant in ('hit-keeps-capacity', 'hit-produces', 'error-rolls-back', 'error-not-counted'):
            with self.subTest(mutant=mutant), self.assertRaises(ValueError):
                p.validate(fixture(mutant=mutant))

    def test_wrong_partial_effects_and_continuation_rejected(self):
        mutations = [
            lambda q: q['events'][21].update(producerCalled=True, producerState=q['events'][21]['before']),
            lambda q: q['events'][23].update(status='ok', error=None),
            lambda q: q['events'][23]['after']['keysHex'].reverse(),
            lambda q: q['events'][23]['after'].update(size=20),
            lambda q: q['events'][24].update(producerCalled=True),
            lambda q: q['events'][24].update(status='error'),
            lambda q: q['visual'].update(continuation=False),
            lambda q: q['visual']['selected'].update(labIndex=21),
            lambda q: q['visual']['results'][-1].update(ok=False),
            lambda q: q['events'][0]['before'].update(max=19),
            lambda q: q['events'][0]['before'].update(size=False),
            lambda q: q['events'][24].update(rootAfterHex=q['events'][24]['rootBeforeHex']),
        ]
        for mutate in mutations:
            r = fixture()
            mutate(r['lruProof'])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                p.validate(r)

    def test_missing_extra_and_rewritten_frames_rejected(self):
        rs = [fixture(phase=i) for i in range(3)]
        for bad in (rs[:2], rs+[rs[0]], [rs[0], rs[0], rs[2]]):
            with self.assertRaises(ValueError):
                p.validate_snapshots(bad)
        # Both snapshots individually valid, but the later prefix was rewritten.
        changed = copy.deepcopy(rs)
        changed[2] = fixture(phase=2, origin=999)
        p.validate(changed[2])
        with self.assertRaisesRegex(ValueError, 'history'):
            p.validate_snapshots(changed)

    def test_wrong_visible_result_and_missing_label_rejected(self):
        r = fixture()
        image = frame(r)
        image.putpixel((200, 120), (0, 0, 0, 255))
        with self.assertRaisesRegex(ValueError, 'WorldPainter'):
            p.visible(image, r)
        image = frame(r)
        ImageDraw.Draw(image).rectangle((100,20,399,79), fill=(0,0,0,255))
        with self.assertRaisesRegex(ValueError, 'Font'):
            p.visible(image, r)

    def test_fixture_assets_are_literal_normal_constructor_inputs(self):
        root = Path(__file__).parent/'lru-assets/behaviorlab'
        files = sorted((root/'dungeons').glob('*.dungeon'))
        self.assertEqual(len(files), 21)
        for i, path in enumerate(files, 1):
            self.assertEqual(json.loads(path.read_text()), dict(metadata=p.metadata(i), parts=[]))
        with Image.open(root/'lru-white.png') as image:
            self.assertEqual(image.size, (16,16))
            self.assertEqual(image.tobytes(), b'\xff'*(16*16*4))

    def test_evaluated_cmake_selector_must_match_observed_backend(self):
        fs = frames()
        proof = dict(schema=1, binary='/logical/bin', binary_sha256='0'*64,
                     source_files={'source.cpp':'0'*64}, build_identity=dict(cache={p.SELECTOR:'ON'}))
        manifest = dict(schema=1, exitCode=0, frames=lab.inventory(fs), buildProvenance=proof,
            binary=dict(path='/logical/bin', sha256='0'*64), assets=dict(sha256='0'*64),
            bootconfig=dict(sha256='0'*64), configuration=dict(sha256='0'*64))
        with mock.patch.object(lab, 'captures', return_value=fs), mock.patch.object(lab, 'load', return_value=manifest):
            lab.validated(Path('/logical'))
            for value in ('OFF', None, True, '1'):
                proof['build_identity']['cache'][p.SELECTOR] = value
                with self.subTest(value=value), self.assertRaisesRegex(lab.LabError, 'selector'):
                    lab.validated(Path('/logical'))

    def test_scene_overlay_is_issue_scoped_and_old_order_retained(self):
        self.assertEqual(lab.SCENARIOS[-1], 'lru-room')
        self.assertEqual(lab.SCENARIOS[20], 'path-embed-room')
        self.assertEqual(len(lab.SCENARIOS), 22)
        for scene in lab.SCENARIOS:
            self.assertEqual('lru-fixture' in lab.asset_overlays(scene), scene == 'lru-room')

    def test_common_capture_and_repeat_candidate_plumbing(self):
        native, rust = frames('native'), frames('rust')
        self.assertTrue(compare(native, native, repeat=True)['passed'])
        self.assertTrue(compare(native, rust)['passed'])
        for ref, cand, repeat in ((native, native, False), (rust, rust, False), (native, rust, True)):
            result = compare(ref, cand, repeat)
            self.assertFalse(result['passed'])
            self.assertIn('LRU backend', str(result))

    def test_capture_checks_real_sequence_membership_and_world_observation(self):
        for mutate in (lambda r,i:r.update(occluderPresent=False),
                       lambda r,i:r['lruProof']['visual'].update(continuation=False),
                       lambda r,i:r['lruProof']['events'][-1].update(producerCalled=True)):
            with self.assertRaises(lab.LabError):
                frames(mutate=mutate)
        f = frames()
        for bad in ({k:v for k,v in f.items() if k != p.STAGES[2]}, f | {'extra':f[p.STAGES[0]]}):
            with self.assertRaisesRegex(ValueError, 'membership'):
                p.validate_sequence(bad)


if __name__ == '__main__':
    unittest.main()
