"""Five-scope File scaffold. Validation is NOT application/runtime proof.

Mode IDs follow file/source-map.json StarFile.cpp (34 source-order entries).
Native prefix initialization in modes 0/2/3/4/5/7/33 precedes controller entry.
Filesystem containment belongs to the caller; leaf labels prove no path domain.
"""
from copy import deepcopy

MODE_COUNT = 34
U64 = 1 << 64
EVENTS = ('attempt', 'success', 'exception')
METHODS = ('VersionedJson::writeFile', 'VersionedJson::readFile', 'File::readFile',
           'BTreeSha256Database::open/insert/commit/close(file)',
           'BTreeSha256Database::open/find/close(file)')
# VersioningDatabase.cpp:15-40 -> native overwrite(raw) -> writeFile -> writeFull.
# BTreeDatabase.cpp:103-169, 887-904, 1043-1062, 1130-1135 -> IODevice full loops.
# Fresh write phase can read its uncommitted cache: do NOT require readAbsolute.
REQUIRED = ((10, 7, 3, 30, 22, 31), (3, 30, 21, 20), (4, 3, 21, 20),
            (3, 30, 19, 28, 24, 29), (3, 30, 19, 23))
# Independently literal SBVJ01/id=bufferlab/version=1/array(64,144,224,255,
# 1537 ASCII cycling letters)/subVersions trailer; no serializer under test.
SAVE_HEX = ('5342564a3031096275666665726c61620100000001060504810004822004834004837e058c01'
            + bytes(97 + i % 26 for i in range(1537)).hex()
            + '00000001010b73756256657273696f6e730700')


def require(ok, message):
    if not ok:
        raise ValueError('File proof: ' + message)


def keys(value, names):
    require(type(value) is dict and set(value) == set(names.split()), 'fields')


def counters(value, backend):
    keys(value, 'attempt success exception')
    for row in value.values():
        require(type(row) is list and len(row) == MODE_COUNT
                and all(type(n) is int and 0 <= n < U64 for n in row), '34-mode u64 counts')
    for a, s, e in zip(*(value[k] for k in EVENTS)):
        require(a == (s + e) % U64, 'counter balance')
    if backend == 'cpp':
        require(not any(n for row in value.values() for n in row), 'cpp Rust counts')


def validate_fields(p):
    keys(p, 'version backend scopeThread mainThread captureExcluded valid overflow completed '
            'calls scopes saveFile databaseFile saveHex foundHex')
    require(type(p['version']) is int and p['version'] == 1, 'version')
    require(type(p['backend']) is str and p['backend'] in ('cpp', 'rust'), 'backend')
    for k in ('mainThread', 'captureExcluded', 'valid', 'completed'):
        require(p[k] is True, k)
    require(p['overflow'] is False, 'overflow')
    require(type(p['scopeThread']) is str and p['scopeThread'] == 'main', 'thread')
    for k, expected in (('saveFile', 'buffer-save.sbvj'), ('databaseFile', 'buffer-payload.btree'),
                        ('saveHex', SAVE_HEX), ('foundHex', SAVE_HEX)):
        require(type(p[k]) is str and p[k] == expected, k)
    counters(p['calls'], p['backend'])
    require(type(p['scopes']) is list and len(p['scopes']) == 5, 'five scopes')
    for i, scope in enumerate(p['scopes']):
        keys(scope, 'method started completed mainThread calls')
        require(type(scope['method']) is str and scope['method'] == METHODS[i], 'scope order')
        for k in ('started', 'completed', 'mainThread'):
            require(scope[k] is True, 'scope ' + k)
        counters(scope['calls'], p['backend'])
        if p['backend'] == 'rust':
            for mode in REQUIRED[i]:
                require(scope['calls']['success'][mode] > 0, f'scope {i} mode {mode}')
    for event in EVENTS:
        for mode in range(MODE_COUNT):
            require(p['calls'][event][mode] == sum(s['calls'][event][mode] for s in p['scopes']) % U64,
                    'scope sum')
    out = deepcopy(p)
    for k in ('backend', 'calls', 'scopes'):
        out.pop(k)
    return out


def validate(receipt):
    require(type(receipt) is dict and 'fileProof' in receipt, 'missing proof')
    return validate_fields(receipt['fileProof'])


def validate_snapshots(proofs):
    """Parent supplies the three acknowledged frames; this does not prove ACKs."""
    require(type(proofs) is list and len(proofs) == 3, 'three acknowledged snapshots')
    for proof in proofs:
        validate_fields(proof)
    require(all(p == proofs[0] for p in proofs[1:]), 'snapshot drift')
    return validate_fields(proofs[0])
