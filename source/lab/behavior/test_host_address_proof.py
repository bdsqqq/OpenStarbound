"""Synthetic verifier fixtures, NOT evidence of TCP execution or rendering."""
import unittest
from copy import deepcopy
import host_address_proof as p


def fixture(backend='cpp', port=40169, peer=50001):
    def counts(modes=()):
        row = [int(i in modes) if backend == 'rust' else 0 for i in range(27)]
        return {'attempt': row[:], 'success': row[:], 'exception': [0]*27}
    names = ['HostAddressWithPort::HostAddressWithPort(String)', 'TcpSocket::listen(parsed)',
             'TcpSocket::connectTo(parsed)', 'TcpSocket::accept()',
             'operator<<(HostAddress accepted OS peer)']
    proof = dict(version=1, backend=backend, inputEndpoint=f'127.0.0.1:{port}',
                 chosenPort=port, ownedBindSucceeded=True, addressSources=deepcopy(p.SOURCES),
                 clientLocalOsAvailable=False, nativeObservedCalls=5,
                 scopes=[{'method': name, 'completed': True,
                          'calls': counts((21,) if i == 0 else ())} for i, name in enumerate(names)],
                 calls=counts((1, 11, 12, 13, 16, 19, 21)),
                 clientLocal=p.endpoint(0, True), serverRemote=p.endpoint(peer),
                 network=dict(transport='tcp', rulesVersion=5, streamEnabled=False,
                              universeHandshake=False, sentText='127.0.0.1', receivedText='127.0.0.1',
                              sendMode=0, data={}),
                 visual=dict(imagePath=p.IMAGE, color=p.COLOR[:], sourceSize=[16,16],
                             displaySize=[64,64], scale=4, label='127.0.0.1'))
    proof.update({name: p.endpoint(port) for name in ('parsed', 'listenerLocal', 'clientRemote', 'serverLocal')})
    return {'hostAddressProof': proof}


class HostAddressProofTests(unittest.TestCase):
    def test_validated_projection(self):
        self.assertEqual(p.validate(fixture()), p.validate(fixture('rust', 40170, 60000)))

    def test_known_failures(self):
        changes = [lambda x: x.update(chosenPort=40000),
                   lambda x: x.update(ownedBindSucceeded=False),
                   lambda x: x['serverRemote'].update(port=0),
                   lambda x: x.update(clientLocal=p.endpoint(50001)),
                   lambda x: x['addressSources'].update(clientLocal='OS-getsockname'),
                   lambda x: x['parsed'].update(endpointHash=0),
                   lambda x: x['network'].update(receivedText='expected fallback'),
                   lambda x: x['network'].update(universeHandshake=True),
                   lambda x: x['visual'].update(color=[16,192,145,255]),
                   lambda x: x.update(nativeObservedCalls=True),
                   lambda x: x['scopes'].reverse(),
                   lambda x: x['parsed'].update(mode=False)]
        for mutate in changes:
            receipt = fixture()
            mutate(receipt['hostAddressProof'])
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                p.validate(receipt)

    def test_rust_bypass_and_counter_types(self):
        for mode in (1, 11, 12, 13, 16, 19, 21):
            receipt = fixture('rust')
            for key in ('attempt', 'success'):
                receipt['hostAddressProof']['calls'][key][mode] = 0
            with self.assertRaises(ValueError):
                p.validate(receipt)
        receipt = fixture('rust')
        receipt['hostAddressProof']['calls']['attempt'][0] = True
        with self.assertRaises(ValueError):
            p.validate(receipt)


if __name__ == '__main__':
    unittest.main()
