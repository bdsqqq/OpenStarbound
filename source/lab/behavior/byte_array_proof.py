"""ByteArray route receipts for actual consumers; no all-mode coverage claim."""
from copy import deepcopy

EVENTS = ('attempt', 'success', 'exception')
MODE_COUNT = 56
U64 = 2**64


def require(ok, message):
    if not ok:
        raise ValueError('ByteArray proof: ' + message)


def counters(value, backend):
    require(type(value) is dict and set(value) == set(EVENTS), 'counter fields')
    for row in value.values():
        require(type(row) is list and len(row) == MODE_COUNT
                and all(type(n) is int and 0 <= n < U64 for n in row),
                'typed 56-mode u64 counts')
    for a, s, e in zip(value['attempt'], value['success'], value['exception']):
        require(a == (s + e) % U64, 'balanced actual routes')
    if backend == 'cpp':
        require(not any(n for row in value.values() for n in row),
                'native backend with Rust counts')


def validate_fields(p):
    # Buffer may validate this optional extension, so do not import it eagerly.
    from buffer_proof import METHODS
    from io_device_proof import PNG_METHOD
    require(type(p) is dict and set(p) == {
        'version', 'backend', 'scopeThread', 'captureExcluded', 'calls', 'scopes'}, 'fields')
    require(type(p['version']) is int and p['version'] == 1, 'version')
    require(type(p['backend']) is str and p['backend'] in ('cpp', 'rust'), 'backend')
    require(type(p['scopeThread']) is str and p['scopeThread'] == 'main'
            and p['captureExcluded'] is True, 'operation thread/capture boundary')
    backend = p['backend']
    counters(p['calls'], backend)
    require(type(p['scopes']) is list and len(p['scopes']) == 14, '14 actual scopes')
    for index, (scope, method) in enumerate(zip(p['scopes'], [*METHODS, PNG_METHOD])):
        require(type(scope) is dict and set(scope) == {'method', 'completed', 'calls'}, 'scope fields')
        require(type(scope['method']) is str and scope['method'] == method
                and scope['completed'] is True, 'scope identity/order/completion')
        counters(scope['calls'], backend)
        if backend == 'rust':
            require(any(scope['calls']['success']), f'actual success absent in scope {index}')
            if index < 4:
                # NetPacketSocket::readData appends actual received bytes (36).
                # Fixture observer arguments can still read size (41), so
                # any-success alone cannot establish receiver attribution.
                require(scope['calls']['success'][36] > 0, 'source receiver append absent')
    # Production TLS counters wrap. This tiny fixture uses ordinary bounded
    # containment, not modular sums that could conceal missing scope counts.
    for event in EVENTS:
        for mode in range(MODE_COUNT):
            require(p['calls'][event][mode] >= sum(s['calls'][event][mode] for s in p['scopes']),
                    'scope containment')
    out = deepcopy(p)
    for key in ('backend', 'calls', 'scopes'):
        out.pop(key)
    return out


def validate(receipt):
    import buffer_proof
    require(type(receipt) is dict, 'receipt fields')
    p = receipt.get('bufferProof')
    require(type(p) is dict and 'byteArray' in p, 'missing ByteArray extension')
    byte_array = validate_fields(p['byteArray'])
    copy = deepcopy(receipt)
    copy['bufferProof'].pop('byteArray')
    return {'consumer': buffer_proof.validate(copy), 'byteArray': byte_array}
