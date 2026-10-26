"""Source-derived IODevice receipts around real consumers; not a mock-device model."""
from copy import deepcopy
from host_address_proof import same

PNG_METHOD = 'Image::readPng(owned asset bytes)'


def require(ok, message):
    if not ok:
        raise ValueError('IODevice proof: ' + message)


def counters(value, backend):
    require(type(value) is dict and set(value) == {'attempt', 'success', 'exception'}, 'counter fields')
    for row in value.values():
        require(type(row) is list and len(row) == 22
                and all(type(n) is int and 0 <= n < 2**64 for n in row), 'typed 22-mode counts')
    for a, s, e in zip(value['attempt'], value['success'], value['exception']):
        require(a == (s + e) % 2**64, 'balanced actual routes')
    if backend == 'cpp':
        require(not any(n for row in value.values() for n in row), 'native backend with Rust counts')


def validate_fields(p):
    # Import lazily: Buffer's validator also validates this optional extension.
    from buffer_proof import METHODS
    require(type(p) is dict and set(p) == {'version', 'backend', 'scopeThread', 'captureExcluded', 'calls', 'scopes', 'png'}, 'fields')
    require(type(p['version']) is int and p['version'] == 1 and p['backend'] in ('cpp', 'rust'), 'version/backend')
    require(p['scopeThread'] == 'main' and p['captureExcluded'] is True, 'operation thread/capture boundary')
    backend = p['backend']
    counters(p['calls'], backend)
    require(type(p['scopes']) is list and len(p['scopes']) == 14, '14 actual scopes')
    methods = [*METHODS, PNG_METHOD]
    # These are inherited helpers in the source, not File/Buffer's overridden
    # absolute primitives. No base seek/restore receipt is invented for them.
    anchors = {0: (3,), 1: (3,), 2: (3,), 3: (3,), 4: (4,), 5: (3,), 6: (3,),
               7: (14,), 8: (13,), 9: (3,), 10: (14,), 11: (13,), 12: (3,), 13: (3,)}
    for index, scope in enumerate(p['scopes']):
        require(type(scope) is dict and set(scope) == {'method', 'completed', 'calls'}, 'scope fields')
        require(scope['method'] == methods[index] and scope['completed'] is True, 'scope identity/order')
        counters(scope['calls'], backend)
        if backend == 'rust':
            for mode in anchors[index]:
                require(scope['calls']['success'][mode] > 0, f'actual source mode {mode} absent in scope {index}')
    if backend == 'rust':
        require(p['scopes'][0]['calls']['exception'][3] > 0, 'incomplete header full-read exception')
        for event in ('attempt', 'success', 'exception'):
            for mode in range(22):
                require(p['calls'][event][mode] >= sum(s['calls'][event][mode] for s in p['scopes']), 'scope containment')
    require(same(p['png'], {'source': 'Root::assets()->bytes(/behaviorlab/buffer.png)',
                           'decoder': 'Image::readPng(Buffer)', 'sourceSize': [16, 16], 'color': [255, 255, 255, 255]}), 'actual PNG consumer')
    out = deepcopy(p)
    for key in ('backend', 'calls', 'scopes'):
        out.pop(key)
    return out


def validate(receipt):
    import buffer_proof
    p = receipt.get('bufferProof')
    require(type(p) is dict and 'ioDevice' in p, 'missing IODevice extension')
    io = validate_fields(p['ioDevice'])
    copy = deepcopy(receipt)
    copy['bufferProof'].pop('ioDevice')
    return {'consumer': buffer_proof.validate(copy), 'ioDevice': io}
