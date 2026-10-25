"""Synthetic validator fixtures only; no game or framebuffer evidence."""
import unittest
from copy import deepcopy
import data_stream_proof as proof


def fixture(backend='rust'):
    def counts(values):
        row = [values.get(i, 0) for i in range(51)] if backend == 'rust' else [0] * 51
        return {'attempt': row[:], 'success': row[:], 'exception': [0] * 51}
    scopes = [{'method': name, 'completed': True, 'calls': counts(proof.ANCHORS.get(i, {25: 1}))}
              for i, name in enumerate(proof.METHODS)]
    totals = {event: [sum(s['calls'][event][i] for s in scopes) for i in range(51)]
              for event in ('attempt', 'success', 'exception')}
    pages = b'BTreeDB5\x00\x00\x02\x00datastreamlab\x00\x00\x00\x00\x00\x00\x20'
    pages = (pages + bytes.fromhex(proof.SAVE)).ljust(1024, b'\x00').hex()
    return {'dataStreamProof': {'version': 1, 'backend': backend, 'nativeObservedCalls': 10,
        'scopes': scopes, 'calls': totals,
        'network': {'transport': 'tcp', 'inputEndpoint': '127.0.0.1:40201', 'chosenPort': 40201,
            'ownedBindSucceeded': True, 'rulesVersion': 5, 'streamEnabled': False,
            'universeHandshake': False, 'expectedWireHex': proof.WIRE, 'actualWireHex': proof.WIRE,
            'sendAttempts': 1, 'sendCompletions': 1, 'acceptedPeerAddress': '127.0.0.1',
            'acceptedPeerPort': 51515, 'acceptedPeerSource': 'OS-accept-sockaddr',
            'clientLocalOsAvailable': False, 'clientLocalCachePort': 0, 'sentText': 'STREAM',
            'receivedText': 'STREAM', 'sentMode': 0, 'receivedMode': 0, 'receivedData': {},
            'receivedPacketCount': 1, 'pending': False},
        'save': {'filename': '/sandbox/datastream-save.sbvj', 'wireHex': proof.SAVE,
            'expectedWireHex': proof.SAVE, 'value': deepcopy(proof.VALUE),
            'consumed': len(bytes.fromhex(proof.SAVE)), 'atEnd': True},
        'database': {'filename': '/sandbox/datastream-color.btree', 'key': 'color', 'blockSize': 512,
            'pagesHex': pages, 'memoryPagesHex': pages, 'foundHex': proof.SAVE,
            'memoryFoundHex': proof.SAVE, 'value': deepcopy(proof.VALUE),
            'consumed': len(bytes.fromhex(proof.SAVE)), 'atEnd': True},
        'visual': {'imagePath': proof.IMAGE, 'color': proof.COLOR[:], 'sourceSize': [16, 16],
                   'displaySize': [64, 64], 'scale': 4, 'label': 'STREAM'}}}


class DataStreamProofTests(unittest.TestCase):
    def test_cpp_and_rust_project_only_validated_fields(self):
        self.assertEqual(proof.validate(fixture('cpp')), proof.validate(fixture()))

    def test_defined_port_scheduling_variation(self):
        receipt = fixture()
        n = receipt['dataStreamProof']['network']
        n.update(chosenPort=40202, inputEndpoint='127.0.0.1:40202', acceptedPeerPort=51516,
                 sendAttempts=2, sendCompletions=2)
        self.assertEqual(proof.validate(receipt), proof.validate(fixture()))

    def test_known_failures_reject_before_projection(self):
        mutations = [
            lambda p: p['network'].update(actualWireHex='00'),
            lambda p: p['network'].update(ownedBindSucceeded=False),
            lambda p: p['network'].update(acceptedPeerPort=True),
            lambda p: p['network'].update(acceptedPeerSource='cached-connect-input'),
            lambda p: p['network'].update(receivedText='hardcoded fallback'),
            lambda p: p['network'].update(sendCompletions=0),
            lambda p: p['save'].update(wireHex='00'),
            lambda p: p['save'].update(atEnd=False),
            lambda p: p['database'].update(memoryFoundHex='00'),
            lambda p: p['database'].update(memoryPagesHex='00'),
            lambda p: p['visual'].update(color=[0, 0, 0, 255]),
            lambda p: p.update(nativeObservedCalls=0),
            lambda p: p['scopes'][0]['calls']['success'].__setitem__(13, 0),
            lambda p: p['calls']['exception'].__setitem__(25, 1),
            lambda p: p['scopes'][0].update(method='fake decoder'),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                receipt = fixture()
                mutate(receipt['dataStreamProof'])
                with self.assertRaises(ValueError):
                    proof.validate(receipt)

    def test_balanced_value_equivalent_route_suppression_rejects(self):
        receipt = fixture()
        for field in ('attempt', 'success'):
            receipt['dataStreamProof']['scopes'][0]['calls'][field][13] -= 1
        with self.assertRaisesRegex(ValueError, 'source-derived controller graph'):
            proof.validate(receipt)

    def test_cpp_cannot_claim_rust_receipts(self):
        receipt = fixture('cpp')
        for field in ('attempt', 'success'):
            receipt['dataStreamProof']['calls'][field][0] = 1
        with self.assertRaisesRegex(ValueError, 'C\+\+ consumer'):
            proof.validate(receipt)


if __name__ == '__main__':
    unittest.main()
