"""Logical verifier fixtures only: no game acquisition and no synthetic green claim."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from PIL import Image
import ttl_proof as p
import behavior_lab as lab


def hx(s):
    return s.encode().hex()


def state(entries):
    return dict(entries=[dict(keyHex=hx(k), stamp=t) for k, t in entries],
                ttl=10000, smear=1000, update=True, maxHex='ffffffffffffffff')


def fixture(backend='native', initially_cached=False, worker=True):
    """Independent scripted observations, with unrelated future-stamped key.

    Includes worker expiry between phase-0 capture and foreground phase 1.
    The phase-0 prefix is immutable; snapshots are intentionally NOT empty.
    """
    events = []
    current = [('unrelated-bootstrap', 50000)]
    if initially_cached:
        current.insert(0, (p.KEY, -50000))
    counts = dict(get=0, cleanup=0)

    def event(op, time, phase, foreground=True, key='', stamp=None):
        nonlocal current
        before = state(current)
        cb = {k: f'{v:016x}' for k, v in counts.items()}
        counts[op] += backend == 'rust'
        producer = None
        error = None
        if op == 'get':
            found = any(k == key for k, _ in current)
            if not found:
                producer = dict(state=copy.deepcopy(before), clock=time)
            if key == p.MISSING:
                error = hx(p.ERROR)
            else:
                current = [(k, t) for k, t in current if k != key] + [(key, stamp if stamp is not None else time)]
        else:
            current = [(k, t) for k, t in current if time - t <= 10000]
        e = dict(operation=op, phase=phase, foreground=foreground, keyHex=hx(key),
                 before=before, after=state(current), clockBefore=time, clockAfter=time,
                 countersBefore=cb, countersAfter={k: f'{v:016x}' for k, v in counts.items()},
                 producer=producer, errorHex=error, index=len(events))
        events.append(e)

    receipts = []
    for phase in range(3):
        if phase == 0:
            event('get', 1000, 0, key=p.KEY)
            event('get', 1001, 0, key=p.KEY)
        elif phase == 1:
            if worker:
                event('cleanup', 11002, 0, foreground=False)
            event('cleanup', 11003, 1)
            event('get', 11004, 1, key=p.KEY)
        else:
            event('get', 11005, 2, key=p.MISSING)
            event('get', 11006, 2, key=p.KEY)
        good = dict(name=p.KEY, ok=True, metadata=copy.deepcopy(p.META))
        results = ([copy.deepcopy(good), copy.deepcopy(good)] if phase == 0 else
                   [copy.deepcopy(good)] if phase == 1 else
                   [dict(name=p.MISSING, ok=False, error=p.ERROR + '\nStack trace (most recent call first):\nlogical only'), good])
        color = [136, 68, (phase + 1) * 80, 255]
        proof = dict(version=1, backend=backend, selector=p.SELECTOR, phase=phase,
                     events=copy.deepcopy(events), deadline=11002,
                     consumer='normal-root.tenantConfig-TenantDatabase-Assets-Tenant',
                     imageConsumer='normal-Assets-WorldPainter', labelConsumer='normal-Font-TextPainter',
                     configuration=dict(scenario='ttl-room'),
                     visual=dict(phase=phase, results=results, selected=copy.deepcopy(p.META),
                                 continuation=True, color=color,
                                 label=f'TTL {phase+1}/3 metadata=17 continue=ok',
                                 imagePath='/behaviorlab/ttl-white.png?multiply=' + bytes(color).hex()))
        receipts.append(dict(ttlProof=proof, stageIndex=phase, cameraPosition=[64, 48], cameraPixelRatio=2))
    return receipts


class TtlModel(unittest.TestCase):
    def test_frozen_matrix_and_native_rust_projection(self):
        for cached in (False, True):
            for worker in (False, True):
                native, rust = fixture(initially_cached=cached, worker=worker), fixture('rust', cached, worker)
                self.assertTrue(p.validate_snapshots(native))
                self.assertTrue(p.validate_snapshots(rust))
                self.assertEqual([p.observation(r) for r in native], [p.observation(r) for r in rust])
        self.assertEqual(p.observation(fixture(worker=True)[2]), p.observation(fixture(worker=False)[2]))

    def reject(self, mutate, phase=2, regex='TTL'):
        r = fixture()[phase]
        mutate(r['ttlProof'])
        with self.assertRaisesRegex(ValueError, regex):
            p.validate(r)

    def test_wrong_greater_equal_boundary_rejected(self):
        def change(proof):
            e = proof['events'][2]
            e['clockBefore'] = e['clockAfter'] = 11001  # exact TTL boundary: MUST retain
        self.reject(change, regex='strict cleanup')

    def test_no_refresh_rejected_when_source_bounds_discriminate(self):
        r = fixture(initially_cached=True)[0]
        r['ttlProof']['events'][0]['after']['entries'][-1]['stamp'] = -50000
        with self.assertRaisesRegex(ValueError, 'refresh bounds'):
            p.validate(r)

    def test_wrong_expiry_and_producer_rejected(self):
        self.reject(lambda proof: proof['events'][2]['after']['entries'].append(dict(keyHex=hx(p.KEY), stamp=1001)))
        self.reject(lambda proof: proof['events'][4].__setitem__('producer', None), regex='producer')
        self.reject(lambda proof: proof['events'][1].__setitem__('producer', dict(state=proof['events'][1]['before'], clock=1001)), regex='producer')

    def test_wrong_error_and_partial_effects_rejected(self):
        self.reject(lambda proof: proof['events'][-2].__setitem__('errorHex', hx(p.ERROR + ' extra')), regex='complete what')
        self.reject(lambda proof: proof['events'][-2]['after']['entries'].clear(), regex='partial effects')
        self.reject(lambda proof: proof['visual']['results'][0].__setitem__('error', p.ERROR + ' extra'), regex='first line')
        self.reject(lambda proof: proof['visual'].__setitem__('continuation', False), regex='continuation')

    def test_raw_history_rewrite_rejected_even_if_each_replay_valid(self):
        receipts = fixture()
        # A harmless within-bracket timing change still rewrites sealed history.
        e = receipts[2]['ttlProof']['events'][0]
        e['clockAfter'] += 1
        p.validate(receipts[2])
        with self.assertRaisesRegex(ValueError, 'history rewritten'):
            p.validate_snapshots(receipts)

    def test_wrong_backend_and_u64_types_rejected(self):
        self.reject(lambda proof: proof.__setitem__('backend', 'rust'), regex='root not entered')
        self.reject(lambda proof: proof['events'][0]['countersAfter'].__setitem__('get', True), regex='hex')
        self.reject(lambda proof: proof['events'][2].__setitem__('phase', 2), regex='phase')
        self.reject(lambda proof: proof['events'][2].__setitem__('foreground', True), regex='foreground operation')
        r = fixture('rust')[2]
        r['ttlProof']['backend'] = 'native'
        with self.assertRaisesRegex(ValueError, 'OFF counters'):
            p.validate(r)

    def test_coherent_whole_cleanup_boundary_brackets(self):
        e = fixture()[1]['ttlProof']['events'][2]
        e.update(index=0, before=state([('a', 0), ('b', 1)]),
                 after=state([('a', 0), ('b', 1)]), clockBefore=10000, clockAfter=10000)
        p.replay([e], 'native')  # exactly TTL retains a; b is younger
        e.update(after=state([('b', 1)]), clockBefore=10001, clockAfter=10001)
        p.replay([e], 'native')  # one common exact cutoff removes a, retains b
        e['clockBefore'] = 10000
        p.replay([e], 'native')  # bracket permits that same SINGLE internal cutoff
        e['after'] = state([])
        with self.assertRaisesRegex(ValueError, 'strict cleanup'):
            p.replay([e], 'native')  # b cannot expire anywhere in the bracket

    def test_single_cleanup_clock_not_per_key(self):
        # Impossible: keep the older key but remove the newer one at ANY cutoff.
        e = fixture()[1]['ttlProof']['events'][2]
        e['before'] = state([('old', 0), ('new', 10)])
        e['after'] = state([('old', 0)])
        e['clockBefore'], e['clockAfter'] = 10000, 10011
        e['index'] = 0
        with self.assertRaisesRegex(ValueError, 'common captured clock'):
            p.replay([e], 'native')

    def test_pixels_fixture_not_actual_game_evidence(self):
        r = fixture()[2]
        image = Image.new('RGBA', (640, 400), (0, 0, 0, 255))
        image.paste(tuple(r['ttlProof']['visual']['color']), (288, 168, 352, 232))
        image.paste((255, 255, 255, 255), (225, 105, 235, 106))
        p.visible(image, r)
        image.putpixel((320, 200), (0, 0, 0, 255))
        with self.assertRaisesRegex(ValueError, 'WorldPainter pixels'):
            p.visible(image, r)

    def test_static_source_wiring_and_original_full_expression(self):
        root = Path(__file__).resolve().parents[3]
        cpp = (root / 'source/game/StarTenantDatabase.cpp').read_text()
        self.assertIn('return m_tenantCache.get(name,\n        [this]', cpp)
        self.assertIn('TtlCacheLab::producer();', cpp)
        barrier = cpp.split('Json TenantDatabase::ttlLabHistory', 1)[1].split('TenantPtr TenantDatabase::getTenant', 1)[0]
        self.assertIn('MutexLocker locker(m_cacheMutex);', barrier)
        self.assertLess(barrier.index('TtlCacheLab::stop()'), barrier.index('TtlCacheLab::history()'))
        self.assertNotIn('[this,', cpp)
        self.assertLess(cpp.index('MutexLocker locker(m_cacheMutex);'), cpp.index('TtlCacheLab::Scope scope'))
        helper = (root / 'source/base/StarTtlCacheLab.hpp').read_text()
        inspection = helper.split('namespace TtlCacheLab {', 1)[0]
        for forbidden in ('.keys()', '.values()', '.ptr(', '.get(', '.clear()', 'cache.currentSize()'):
            self.assertNotIn(forbidden, inspection)
        self.assertIn('cache.m_cache.m_map', helper)
        self.assertIn('std::atomic<bool> watching', helper)
        self.assertIn('std::lock_guard<std::mutex>', helper)
        client = (root / 'source/client/StarClientApplication.cpp').read_text()
        self.assertIn('const_cast<TenantDatabase&>(*Root::singleton().tenantDatabase()).cleanup()', client)
        self.assertIn('entry.getInt("stamp") + last.get("after").getInt("ttl") + 1', client)
        self.assertEqual(lab.SCENARIOS[22], 'ttl-room')
        for scenario in lab.SCENARIOS:
            self.assertEqual('ttl-fixture' in lab.asset_overlays(scenario), scenario == 'ttl-room')
        self.assertEqual(json.loads((root / 'source/lab/behavior/newttl-assets/tenants/behavior-ttl-a.tenant').read_text()), p.META)


class TtlComparisonPlumbing(unittest.TestCase):
    def frames(self, backend='native', mutate=None):
        directory = mock.Mock()
        pngs = [Path('/logical') / (name + '.png') for name in p.STAGES]
        paths = [path.with_suffix('.json') for path in pngs]
        directory.glob.side_effect = lambda pattern: pngs if pattern == '*.png' else paths
        envelopes, images = {}, {}
        receipts = fixture(backend)
        for phase, (name, r) in enumerate(zip(p.STAGES, receipts)):
            base = {field: 'logical-stable-world' for field in lab.SCENE_FIELDS}
            base.update(r)
            base.update(scenario='ttl-room', inWorld=True, playerOutsideView=True, uiHidden=True,
                lightingCompleted=True, lightEntityReplicated=True, fullbright=False,
                replicatedSettledUpdates=90, lightingBackend='cpp', rustLightingCalls=0)
            base.update(worldState={'declared': {'logical': True}})
            base.update(stage=name, action=p.ACTIONS[phase], occluderPresent=phase == 1,
                observedOccluderMaterial=7 if phase == 1 else 0, materialId=7)
            if mutate:
                mutate(base, phase)
            image = Image.new('RGBA', (640, 400), (0, 0, 0, 255))
            image.paste(tuple(base['ttlProof']['visual']['color']), (288, 168, 352, 232))
            image.paste((255, 255, 255, 255), (225, 105, 235, 106))
            images[pngs[phase]] = image
            envelopes[paths[phase]] = dict(name=name, file=pngs[phase].name, width=640, height=400,
                metadata=base, capture=dict(source='final-default-framebuffer', stage='after-imgui-before-swap'))
        with mock.patch.object(lab, 'check_owned', side_effect=lambda x:x), \
                mock.patch.object(lab, 'load', side_effect=envelopes.__getitem__), \
                mock.patch.object(lab, 'image', side_effect=images.__getitem__), \
                mock.patch.object(lab, 'sha', return_value='0'*64):
            return lab.captures(directory)

    def test_generic_compare_branches_and_wrong_backend(self):
        from test_lru_proof import compare
        native, rust = self.frames(), self.frames('rust')
        self.assertTrue(compare(native, native, repeat=True)['passed'])
        self.assertTrue(compare(native, rust)['passed'])
        wrong = compare(native, native)
        self.assertFalse(wrong['passed'])
        self.assertIn('TTL backend', str(wrong))
        def mutate(receipt, phase):
            if phase == 2:
                receipt['ttlProof']['visual']['selected']['priority'] = 18
        with self.assertRaisesRegex(lab.LabError, 'literal constructed'):
            self.frames('rust', mutate=mutate)

    def test_selector_binding_rejects_before_process_receipt_access(self):
        fs = self.frames()
        proof = dict(schema=1, binary_sha256='0'*64, binary='/logical/bin', source_files={'x':'y'},
                     build_identity=dict(cache={p.SELECTOR:'ON'}))
        manifest = dict(schema=1, exitCode=0, frames=lab.inventory({k: dict(v,
            pngSha256='0'*64, receiptSha256='0'*64) for k,v in fs.items()}))
        fs = {k: dict(v, pngSha256='0'*64, receiptSha256='0'*64) for k,v in fs.items()}
        manifest.update(buildProvenance=proof, binary=dict(path='/logical/bin', sha256='0'*64),
                        assets=dict(sha256='0'*64), bootconfig=dict(sha256='0'*64), configuration=dict(sha256='0'*64))
        with mock.patch.object(lab, 'captures', return_value=fs), mock.patch.object(lab, 'load', return_value=manifest):
            with self.assertRaisesRegex(lab.LabError, 'TTL selector'):
                lab.validated(Path('/logical'))


class ProcessReceipts(unittest.TestCase):
    def test_durable_receipt_and_coherent_negative_bindings(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp).resolve()
            frames = parent / 'frames'
            frames.mkdir()
            lab.dump(parent / 'launch.json', {})
            start = dict(pid=123, pgid=123, osStart='logical-only-start', status='started',
                         binary={}, configuration={}, command=['logical'], launch=lab.identity(parent / 'launch.json'))
            lab.durable_dump(parent / 'process-start.json', start)
            end = dict(pid=123, pgid=123, osStart=start['osStart'], status='reaped', exitCode=0,
                       startReceipt=lab.identity(parent / 'process-start.json'))
            lab.durable_dump(parent / 'process-exit.json', end)
            manifest = dict(processStart=lab.identity(parent / 'process-start.json'),
                            processExit=lab.identity(parent / 'process-exit.json'), binary={}, configuration={}, command=['logical'])
            lab.validate_process_binding(frames, manifest)
            for field, value in (('pid', True), ('pid', 124), ('osStart', 'other'), ('exitCode', False)):
                wrong = copy.deepcopy(end)
                wrong[field] = value
                (parent / 'process-exit.json').write_text(json.dumps(wrong))
                manifest['processExit'] = lab.identity(parent / 'process-exit.json')
                with self.assertRaisesRegex(lab.LabError, 'process start/exit/manifest'):
                    lab.validate_process_binding(frames, manifest)


if __name__ == '__main__':
    unittest.main()
