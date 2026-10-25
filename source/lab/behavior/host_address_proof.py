"""Validate the owned TCP consumer before projecting variable ports/counters.

Only the accepted peer comes from an OS sockaddr. The other socket addresses
are native caches; the client-local cache is never populated by connect().
"""
from copy import deepcopy

COLOR = [16, 192, 144, 255]
IMAGE = '/behaviorlab/host-address.png?multiply=10c090ff'
SOURCES = {'listenerLocal': 'cached-bind-input',
           'clientLocal': 'unpopulated-default-NOT-OS-getsockname',
           'clientRemote': 'cached-connect-input',
           'serverLocal': 'cached-listener-input',
           'serverRemote': 'OS-accept-sockaddr'}
MASK = (1 << 64) - 1


def require(ok, message):
    if not ok:
        raise ValueError('host address: ' + message)


def keys(value, names):
    require(type(value) is dict and set(value) == set(names.split()), 'schema')


def integer(value, low=0, high=MASK):
    return type(value) is int and low <= value <= high


def endpoint(port, zero=False):
    octets = [0, 0, 0, 0] if zero else [127, 0, 0, 1]
    h = 0
    for byte in octets:
        h = (h * 101 + byte) & MASK
    combined = (port * 2654435761 + 0x9e3779b9 + (h << 6) + (h >> 2)) & MASK
    text = '.'.join(map(str, octets))
    return {'mode': 0, 'bytes': octets, 'size': 4, 'isLocalHost': not zero,
            'isZero': zero, 'hash': h, 'text': text, 'port': port,
            'endpointText': f'{text}:{port}', 'endpointHash': h ^ combined}


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in b)
    if isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def counters(value, backend):
    keys(value, 'attempt success exception')
    for row in value.values():
        require(type(row) is list and len(row) == 27 and all(integer(n) for n in row), 'counter shape/type')
    for a, s, e in zip(value['attempt'], value['success'], value['exception']):
        require(a == s + e and e == 0, 'successful numeric consumer counter balance')
        if backend == 'cpp':
            require(a == 0, 'C++ consumer called Rust')


def validate(receipt):
    p = receipt.get('hostAddressProof')
    keys(p, 'version backend inputEndpoint chosenPort ownedBindSucceeded parsed listenerLocal clientLocal clientRemote serverLocal serverRemote addressSources clientLocalOsAvailable nativeObservedCalls scopes calls network visual')
    require(type(p['version']) is int and p['version'] == 1 and p['backend'] in ('cpp', 'rust'), 'version/backend')
    port = p['chosenPort']
    require(integer(port, 40169, 40200) and p['ownedBindSucceeded'] is True, 'owned listener')
    require(p['inputEndpoint'] == f'127.0.0.1:{port}', 'numeric input')
    require(same(p['addressSources'], SOURCES) and p['clientLocalOsAvailable'] is False, 'native cache/OS provenance')
    for name in ('parsed', 'listenerLocal', 'clientRemote', 'serverLocal'):
        require(same(p[name], endpoint(port)), name + ' identity/hash')
    require(same(p['clientLocal'], endpoint(0, True)), 'unpopulated client-local cache')
    peer = p['serverRemote']
    require(type(peer) is dict and integer(peer.get('port'), 1, 65535), 'accepted OS peer port')
    require(same(peer, endpoint(peer['port'])), 'accepted OS peer identity/hash')
    require(integer(p['nativeObservedCalls'], 4) and type(p['scopes']) is list
            and p['nativeObservedCalls'] == len(p['scopes']), 'actual call scopes')
    names = []
    for scope in p['scopes']:
        keys(scope, 'method completed calls')
        require(scope['completed'] is True and type(scope['method']) is str, 'completed native call')
        names.append(scope['method'])
        counters(scope['calls'], p['backend'])
    parse = 'HostAddressWithPort::HostAddressWithPort(String)'
    listen = 'TcpSocket::listen(parsed)'
    connect = 'TcpSocket::connectTo(parsed)'
    accept = 'TcpSocket::accept()'
    stream = 'operator<<(HostAddress accepted OS peer)'
    # Each parsed endpoint may encounter an occupied listener port. Failed
    # listen calls do not append a completed scope; connect follows OUR bind.
    require(names[0] == parse and names[-1] == stream and names.count(listen) == 1
            and names.count(connect) == 1 and names.count(accept) >= 1
            and all(n in (parse, listen, connect, accept, stream) for n in names), 'consumer call graph')
    li, ci = names.index(listen), names.index(connect)
    require(all(n == parse for n in names[:li]) and ci == li + 1
            and all(n == accept for n in names[ci + 1:-1]), 'bind-before-connect/accept order')
    counters(p['calls'], p['backend'])
    if p['backend'] == 'rust':
        # These source paths parse the endpoint, resolve its numeric host,
        # construct the accepted sockaddr, and stream the native peer.
        for mode in (1, 11, 12, 13, 16, 19, 21):
            require(p['calls']['success'][mode] > 0, f'actual Rust mode {mode} absent')
        require(p['scopes'][0]['calls']['success'][21] > 0, 'parsed endpoint bypass')
    require(same(p['network'], {'transport': 'tcp', 'rulesVersion': 5,
            'streamEnabled': False, 'universeHandshake': False, 'sentText': '127.0.0.1',
            'receivedText': '127.0.0.1', 'sendMode': 0, 'data': {}}), 'typed received packet')
    require(same(p['visual'], {'imagePath': IMAGE, 'color': COLOR, 'sourceSize': [16, 16],
            'displaySize': [64, 64], 'scale': 4, 'label': '127.0.0.1'}), 'normal image/Font source')
    normalized = deepcopy(p)
    for name in ('backend', 'calls', 'scopes', 'nativeObservedCalls'):
        normalized.pop(name)
    normalized['chosenPort'] = '<owned-listener-port>'
    normalized['inputEndpoint'] = '127.0.0.1:<owned-listener-port>'
    for name in ('parsed', 'listenerLocal', 'clientRemote', 'serverLocal', 'serverRemote'):
        role = '<accepted-ephemeral-port>' if name == 'serverRemote' else '<owned-listener-port>'
        normalized[name]['port'] = role
        normalized[name]['endpointText'] = '127.0.0.1:' + role
        normalized[name]['endpointHash'] = '<validated-native-port-hash>'
    return normalized


def visible(frame, receipt):
    validate(receipt)
    require(receipt.get('cameraPosition') == [64, 48] and receipt.get('cameraPixelRatio') == 2
            and min(frame.size) >= 200, 'camera/viewport')
    rgba = frame.convert('RGBA')
    x, y = frame.width // 2, frame.height // 2
    ink = [(i % rgba.width, i // rgba.width) for i, pixel in enumerate(rgba.getdata()) if pixel == tuple(COLOR)]
    require(len(ink) == 4096, 'normal64x64 image area')
    bounds = min(a for a, b in ink), min(b for a, b in ink), max(a for a, b in ink)+1, max(b for a, b in ink)+1
    require(bounds == (x-32, y-32, x+32, y+32), 'normal image geometry')
    label = frame.crop((x-100, y-100, x+100, y-40)).convert('RGBA')
    require(list(label.getdata()).count((255, 255, 255, 255)) >= 8, 'normal Font label absent')
