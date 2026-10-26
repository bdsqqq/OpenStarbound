"""Synthetic validator cases, not actual IODevice consumer evidence."""
from copy import deepcopy
import unittest
import buffer_proof
import io_device_proof as p
from test_buffer_proof import fixture as buffer_fixture


def fixture(backend='rust'):
    q = buffer_fixture(backend)
    methods = [*buffer_proof.METHODS, p.PNG_METHOD]
    anchors = {0:3,1:3,2:3,3:3,4:4,5:3,6:3,7:14,8:13,9:3,10:14,11:13,12:3,13:3}
    scopes = []
    for i, method in enumerate(methods):
        calls = {k:[0]*22 for k in ('attempt','success','exception')}
        if backend == 'rust':
            calls['attempt'][anchors[i]] = calls['success'][anchors[i]] = 1
            if i == 0:
                calls['exception'][3] = 1
                calls['attempt'][3] += 1
        scopes.append(dict(method=method,completed=True,calls=calls))
    totals = {k:[sum(s['calls'][k][i] for s in scopes) for i in range(22)] for k in ('attempt','success','exception')}
    q['bufferProof']['ioDevice'] = dict(version=1,backend=backend,scopeThread='main',captureExcluded=True,
        calls=totals,scopes=scopes,png=dict(source='Root::assets()->bytes(/behaviorlab/buffer.png)',
        decoder='Image::readPng(Buffer)',sourceSize=[16,16],color=[255]*4))
    return q


class IODeviceProofTests(unittest.TestCase):
    def test_native_and_rust_normalize_after_validation(self):
        self.assertEqual(p.validate(fixture('cpp')),p.validate(fixture()))
        self.assertEqual(buffer_proof.validate(fixture('cpp')),buffer_proof.validate(fixture()))

    def test_old_buffer_contract_remains_strict(self):
        q=fixture();q['bufferProof']['network']['actualWireHex']='00'
        with self.assertRaises(ValueError):p.validate(q)

    def test_balanced_missing_source_route_still_rejected(self):
        q=fixture();v=q['bufferProof']['ioDevice']
        for event in ('attempt','success'):
            v['scopes'][7]['calls'][event][14]=0
            v['calls'][event][14]-=1
        with self.assertRaisesRegex(ValueError,'source mode'):p.validate(q)

    def test_balanced_missing_pending_header_rejected(self):
        q=fixture();v=q['bufferProof']['ioDevice']
        v['scopes'][0]['calls']['exception'][3]=0
        v['scopes'][0]['calls']['attempt'][3]-=1
        v['calls']['exception'][3]-=1;v['calls']['attempt'][3]-=1
        with self.assertRaisesRegex(ValueError,'incomplete header'):p.validate(q)

    def test_scope_type_png_capture_and_thread_corruptions_rejected(self):
        changes=[lambda v:v.update(captureExcluded=False),lambda v:v.update(scopeThread='worker-all'),
                 lambda v:v['png'].update(color=[0,0,0,255]),lambda v:v['png'].update(decoder='mock'),
                 lambda v:v['scopes'][0].update(completed=1),lambda v:v['scopes'].pop(),
                 lambda v:v['calls']['attempt'].__setitem__(0,True),
                 lambda v:v['scopes'][13].update(method='evidence writePng')]
        for change in changes:
            q=fixture();change(q['bufferProof']['ioDevice'])
            with self.assertRaises(ValueError):p.validate(q)


if __name__=='__main__':unittest.main()
