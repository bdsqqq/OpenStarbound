"""Synthetic/immutable-receipt controls only; NEVER acquisition or qualification."""
import copy
import json
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch
import file_qualification as q
from test_file_proof import synthetic, totals
from test_byte_array_proof import fixture


class QualifierTests(unittest.TestCase):
    def frames(self, backend='rust'):
        receipt = fixture(backend)
        if backend == 'rust':
            b = receipt['bufferProof']['byteArray']
            for i, modes in q.BYTE_ANCHORS.items():
                for mode in modes:
                    for event in ('attempt', 'success'):
                        b['scopes'][i]['calls'][event][mode] = 1
            for event in ('attempt', 'success', 'exception'):
                b['calls'][event] = [sum(s['calls'][event][i] for s in b['scopes']) for i in range(56)]
        receipt.update(scenario='buffer-room', lightingBackend=backend, fileProof=synthetic(backend))
        frames = {}
        for i, name in enumerate(q.stages('buffer-room')):
            r = copy.deepcopy(receipt); r.update(stage=name, stageIndex=i)
            frames[name] = dict(receipt=r)
        return frames

    def test_synthetic_scopes(self):
        for role in q.ROLES:
            q.file_receipts(self.frames('rust' if role == 'candidate' else 'cpp'), 'buffer-room', role)

    def test_file_corruptions(self):
        mutations = [lambda r: r.pop('fileProof'),
                     lambda r: r['fileProof'].update(mainThread=1),
                     lambda r: r['fileProof'].update(backend='cpp'),
                     lambda r: r['fileProof'].update(foundHex='00'),
                     lambda r: r['fileProof']['scopes'].pop(),
                     lambda r: r.update(stageIndex=False),
                     lambda r: r.update(scenario='stringview-room')]
        for mutate in mutations:
            frames = self.frames(); mutate(frames['lit-room']['receipt'])
            with self.subTest(mutate=mutate), self.assertRaises((ValueError, KeyError)):
                q.file_receipts(frames, 'buffer-room', 'candidate')

    def test_exception_balanced_and_snapshot_drift(self):
        frames = self.frames()
        p = frames['lit-room']['receipt']['fileProof']
        p['scopes'][0]['calls']['attempt'][0] = p['scopes'][0]['calls']['exception'][0] = 1
        totals(p)
        with self.assertRaisesRegex(ValueError, 'exception'):
            q.file_receipts(frames, 'buffer-room', 'candidate')
        p['scopes'][0]['calls']['exception'][0] = 0
        p['scopes'][0]['calls']['success'][0] = 1; totals(p)
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            q.file_receipts(frames, 'buffer-room', 'candidate')

    def test_required_modes(self):
        for i, modes in enumerate(q.file_proof.REQUIRED):
            for mode in modes:
                frames = self.frames()
                p = frames['lit-room']['receipt']['fileProof']
                for event in q.file_proof.EVENTS: p['scopes'][i]['calls'][event][mode] = 0
                totals(p)
                with self.assertRaises(ValueError): q.file_receipts(frames, 'buffer-room', 'candidate')

    def test_prior_bytearray_anchor(self):
        frames = self.frames()
        for frame in frames.values():
            p = frame['receipt']['bufferProof']['byteArray']
            for event in ('attempt', 'success'):
                p['scopes'][13]['calls'][event][39] = 0
                p['calls'][event][39] -= 1
        with self.assertRaisesRegex(ValueError, 'ByteArray source mode'):
            q.file_receipts(frames, 'buffer-room', 'candidate')

    def test_partial_stages_and_false_attribution(self):
        frames = self.frames(); frames.pop('occluder-added')
        with self.assertRaises(ValueError): q.file_receipts(frames, 'buffer-room', 'candidate')
        frames = self.frames()
        for f in frames.values(): f['receipt']['scenario'] = 'lighting-room'
        with self.assertRaisesRegex(ValueError, 'attribution'):
            q.file_receipts(frames, 'lighting-room', 'candidate')

    def pair(self):
        root = q.matrix_root('buffer-room')
        manifests = {r: dict(captureId=r, frames={n: {} for n in q.stages('buffer-room')}) for r in q.ROLES}
        report = dict(schema=1, passed=True, errors=[], gate=dict(maxError=0, changedPixels=0),
                      reference=str(root / 'reference/frames'), candidate=str(root / 'candidate/frames'),
                      identities=dict(reference=manifests['reference'], candidate=manifests['candidate']),
                      frames={n: dict(passed=True, errors=[], maxError=0, changedPixels=0) for n in q.stages('buffer-room')})
        return root, manifests, report

    def test_pair_partial_alias_bool_and_roles(self):
        root, manifests, good = self.pair()
        q.strict_pair(good, root, 'candidate', manifests)
        mutations = [lambda p: p.update(schema=True), lambda p: p.update(passed=1),
                     lambda p: p['gate'].update(maxError=False),
                     lambda p: p['frames'].pop('lit-room'),
                     lambda p: p.update(candidate=str(root / 'reference-repeat/frames')),
                     lambda p: p['identities']['candidate'].update(captureId='wrong'),
                     lambda p: p['frames']['lit-room'].update(changedPixels=True),
                     lambda p: p.update(errors=['partial'])]
        for mutate in mutations:
            bad = copy.deepcopy(good); mutate(bad)
            with self.assertRaises(ValueError): q.strict_pair(bad, root, 'candidate', manifests)

    def test_nested_pair_identity_preserves_scalar_types(self):
        root, manifests, report = self.pair()
        manifests['candidate'].update(schema=1, exitCode=0)
        q.strict_pair(report, root, 'candidate', manifests)
        for field, alias in [('schema', True), ('exitCode', False)]:
            bad = copy.deepcopy(report)
            bad['identities']['candidate'][field] = alias
            with self.assertRaises(ValueError): q.strict_pair(bad, root, 'candidate', manifests)
        with self.assertRaises(ValueError):
            q.exact({'nested': [0, 1]}, {'nested': [False, True]}, 'nested aliases')

    def test_seal_pins_every_matrix_role_before_replay(self):
        required = q.matrix_evidence_paths()
        self.assertEqual(len(required), 720)
        for scene in q.SCENARIOS:
            root = q.matrix_root(scene)
            for role in q.ROLES:
                self.assertIn(root / role / 'launch.json', required)
                self.assertIn(root / role / 'frames/manifest.json', required)
                for stage in q.stages(scene):
                    self.assertIn(root / role / 'frames' / (stage + '.png'), required)
                    self.assertIn(root / role / 'frames' / (stage + '.json'), required)
        recorded = {}
        def bind(path, bindings, expected=None):
            bindings[str(path)] = 'a' * 64
        with patch.object(q, 'prepared'), patch.object(q, 'bind', side_effect=bind), \
                patch.object(q, 'write_new', side_effect=lambda path, data: recorded.update(data)), \
                patch.object(q, 'sha', return_value='b' * 64):
            q.seal(q.OWN / 'preparation.json', 'c' * 64, q.OWN / 'inspection.json', q.OWN / 'seal.json')
        self.assertTrue(set(map(str, required)) <= set(recorded['bindings']))

    def test_future_live_scenes_do_not_expand_the_finite_file_oracle(self):
        original = q.matrix_evidence_paths()
        with patch.object(q.lab, 'SCENARIOS', (*q.SCENARIOS, 'future-room')):
            self.assertEqual(q.matrix_evidence_paths(), original)
        self.assertEqual(len(q.SCENARIOS), 20)
        self.assertEqual(len(original), 720)

    def test_kernel_archive_and_missing_bindings(self):
        good = dict(status='FINITE_CURRENT_PRODUCTION_FILE_RUST_PASS', archive=str(q.ARCHIVE),
                    archive_sha256='a'*64, modes=34, bindings={'a':'b'}, artifacts={'c':'d'})
        q.kernel_identity(good, 'a'*64)
        for values in (dict(archive_sha256='b'*64), dict(archive=str(q.ROOT/'build/file-rust/aggregate-r1/release/libstar_engine_ffi.a')),
                       dict(bindings={}), dict(artifacts={}), dict(modes=True)):
            with self.assertRaises(ValueError): q.kernel_identity(dict(good, **values), 'a'*64)

    def test_inspection_missing_negative_hash_and_duplicate(self):
        rows = [dict(scene=scene, stage=stage, pngSha256='a'*64) for scene in q.SCENARIOS for stage in q.stages(scene)]
        good = dict(schema=1, inspectedBy='parent', allFramesViewed=True, frames=rows)
        q.inspection(good, rows)
        for mutate in (lambda d: d.update(allFramesViewed=1), lambda d: d['frames'].pop(),
                       lambda d: d['frames'][0].update(pngSha256='b'*64),
                       lambda d: d['frames'].__setitem__(0, d['frames'][1]), lambda d: d.update(schema=True)):
            bad = copy.deepcopy(good); mutate(bad)
            with self.assertRaises(ValueError): q.inspection(bad, rows)

    def test_report_partial_and_domain(self):
        history = {s: dict(root='/frozen/'+s, frames={n: dict(dimensions=[1,1], pixelsSha256='a'*64) for n in q.stages(s)}) for s in q.SCENARIOS}
        rows = [dict(scene=s, report=str(q.matrix_root(s)/'report.json'), previous=history[s]['root'],
                     frames=[dict(name=n+'.png', dimensions=[1,1], decodedRgbaSha256='a'*64) for n in sorted(q.stages(s))]) for s in q.SCENARIOS]
        good = dict(passed=True, actualMatrices=20, historicalSequences=20, testedProduction=q.REVISION, rows=rows)
        q.validate_report(good, history)
        for mutate in (lambda d: d.update(actualMatrices=True), lambda d: d['rows'].pop(),
                       lambda d: d['rows'][0].update(report='/tmp/report.json'),
                       lambda d: d['rows'][0]['frames'].pop(), lambda d: d.update(passed=1),
                       lambda d: d['rows'].__setitem__(0, d['rows'][1])):
            bad=copy.deepcopy(good); mutate(bad)
            with self.assertRaises(ValueError): q.validate_report(bad, history)
        with self.assertRaises(ValueError): q.path_domain(q.OWN/'../escape', q.OWN)
        with self.assertRaises(ValueError): q.verify_bindings({}, {})

    def test_binding_drift_and_duplicate_json_no_repair(self):
        directory=q.OWN/('synthetic-'+uuid.uuid4().hex); directory.mkdir(parents=True)
        p=directory/'receipt.json'; p.write_text('{"x":1}')
        pins={str(p): q.sha(p)}; q.verify_bindings(pins, {})
        p.write_text('{"x":1,"x":2}')
        changed=p.read_bytes()
        with self.assertRaises(ValueError): q.verify_bindings(pins, {})
        with self.assertRaises(ValueError): q.load(p)
        self.assertEqual(p.read_bytes(), changed)
        with self.assertRaises(FileNotFoundError): q.verify_bindings({str(directory/'absent'): 'a'*64}, {})

    def test_missing_tool_and_reused_capture(self):
        with patch.object(q, 'tool_paths', return_value=[q.OWN/'required-tool.py']):
            with self.assertRaisesRegex(ValueError, 'tool inventory'): q.frozen_tools({}, {})
        seen=set()
        for value in ('reference', 'repeat', 'candidate'): q.independent_id(value, seen)
        for value in ('reference', True, 1, ''):
            with self.assertRaises(ValueError): q.independent_id(value, seen)

    def test_auxiliary_declared_api_synthetic_only(self):
        from types import SimpleNamespace
        proofs={r: dict(binary='/synthetic/'+r, binary_sha256='a'*64, source_files={'synthetic':'b'*64}) for r in ('reference','candidate')}
        paths=[q.AUX/'replay.py',q.AUX/'verify.py',q.AUX/'freeze-r1/inputs.json']
        data=dict(schema=1,status='FINITE_CURRENT_FILE_PCM_AND_12_CLI_PASS',sourceRevision=q.REVISION,
                  sourcearchive=dict(path=str(q.ARCHIVE),sha256='c'*64),
                  bindings={**{str(p):'a'*64 for p in paths},**{p['binary']:p['binary_sha256'] for p in proofs.values()}},
                  identity=dict(producer='a'*64,verifier='a'*64),sourceFiles={'synthetic':'b'*64},
                  buildsidecars=dict(cpp=proofs['reference'],rust=proofs['candidate']),
                  pcm=[dict(backend=b,wavBytes=60,pcmBytes=16,conversionCalls=17 if b=='rust' else 0) for b in ('cpp','rust')],
                  cli=[dict(backend=b,case=n) for b in ('cpp','rust') for n in ('help','help-with-error','unknown','missing','duplicate','end-markers')])
        called=[]
        def verify(freeze, acquisition):
            called.append((freeze,acquisition)); return copy.deepcopy(data)
        module=SimpleNamespace(verify=verify)
        spec=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda m: None))
        with patch.object(q,'load',return_value=data), patch.object(q,'sha',return_value='a'*64), patch.object(q,'verify_bindings'), patch.object(q.importlib.util,'spec_from_file_location',return_value=spec), patch.object(q.importlib.util,'module_from_spec',return_value=module):
            q.auxiliary({},proofs,'c'*64)
            self.assertEqual(called,[(q.AUX/'freeze-r1/inputs.json',q.AUX/'acquisition-r1')])
            data['pcm'][0]['conversionCalls']=False
            with self.assertRaises(ValueError): q.auxiliary({},proofs,'c'*64)

    def test_missing_auxiliary_is_not_optional(self):
        with patch.object(q, 'AUX', q.OWN/'absent-auxiliary'):
            with self.assertRaises(FileNotFoundError): q.auxiliary({}, {}, 'a'*64)


if __name__ == '__main__':
    unittest.main()
