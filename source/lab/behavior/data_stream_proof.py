"""Bind real packet/save/BTree consumers before projecting paths and ports.

Wire/save literals are derived from the native formats, not candidate output.
Counter scopes are nested controller graphs, not one-hot method observations.
"""
from copy import deepcopy
from pathlib import Path
from host_address_proof import same, integer

COLOR = [200, 112, 48, 255]
IMAGE = '/behaviorlab/datastream.png?multiply=c87030ff'
WIRE = '12120653545245414d0000'
SAVE = '5342564a30310d6461746173747265616d6c616201000000010604048310048160046004837e00000001010b73756256657273696f6e730700'
VALUE = {'id': 'datastreamlab', 'version': 1, 'content': COLOR, 'subVersions': {}}
METHODS = ['TcpPacketSocket::sendPackets(ChatSendPacket)',
           'TcpPacketSocket::writeData/readData/receivePackets',
           'VersionedJson::writeFile', 'VersionedJson::readFile',
           'VersionedJson::readSubVersioning(owned file bytes)',
           'BTreeSha256Database::open/insert/commit/close(memory)',
           'BTreeSha256Database::open/find/close(memory)',
           'BTreeSha256Database::open/insert/commit/close(file)',
           'BTreeSha256Database::open/find/close(file)',
           'VersionedJson::readSubVersioning(BTree value)']
# Native packet/header, VersionedJson and Json operator call graphs. These
# anchors are frozen before game execution; receive polling is not constant.
ANCHORS = {0: {0: 2, 5: 1, 7: 1, 13: 5, 34: 2, 35: 1, 46: 1, 50: 1},
           2: {0: 1, 10: 1, 13: 19, 17: 2, 34: 5, 35: 4, 46: 2, 50: 2},
           3: {0: 1, 8: 1, 22: 1, 25: 18, 29: 2, 37: 5, 38: 4,
               40: 5, 41: 4, 47: 2, 49: 2}}


def require(ok, message):
    if not ok:
        raise ValueError('data stream: ' + message)


def keys(value, names):
    require(type(value) is dict and set(value) == set(names.split()), 'schema')


def counters(value, backend):
    keys(value, 'attempt success exception')
    for row in value.values():
        require(type(row) is list and len(row) == 51 and all(integer(n) for n in row), 'counter shape/type')
    for a, s, e in zip(value['attempt'], value['success'], value['exception']):
        require(a == s + e and e == 0, 'successful native scope balance')
        if backend == 'cpp':
            require(a == 0, 'C++ consumer called Rust')


def binary(value):
    require(type(value) is str and len(value) % 2 == 0, 'hex shape')
    try:
        data = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError('data stream: invalid hex') from error
    require(data.hex() == value, 'noncanonical hex')
    return data


def validate(receipt):
    p = receipt.get('dataStreamProof')
    keys(p, 'version backend nativeObservedCalls scopes calls network save database visual')
    require(type(p['version']) is int and p['version'] == 1 and p['backend'] in ('cpp', 'rust'), 'version/backend')
    backend = p['backend']
    require(type(p['nativeObservedCalls']) is int and p['nativeObservedCalls'] == 10
            and type(p['scopes']) is list and len(p['scopes']) == 10, 'native caller scopes')
    counters(p['calls'], backend)
    for index, scope in enumerate(p['scopes']):
        keys(scope, 'method completed calls')
        require(scope['completed'] is True and scope['method'] == METHODS[index], 'native caller order')
        counters(scope['calls'], backend)
        if backend == 'rust':
            require(sum(scope['calls']['success']) > 0, 'native consumer bypassed Rust')
            if index in ANCHORS:
                wanted = [ANCHORS[index].get(mode, 0) for mode in range(51)]
                require(scope['calls']['success'] == wanted, 'source-derived controller graph')
    if backend == 'rust':
        for mode in range(51):
            require(p['calls']['success'][mode] >= sum(s['calls']['success'][mode] for s in p['scopes']), 'scope containment')
        # Scalar framing, strings, VLQ and bool participate in the real callers.
        for mode in (0, 10, 13, 17, 22, 25, 29, 34, 35, 37, 38, 40, 41, 46, 47, 49, 50):
            require(p['calls']['success'][mode] > 0, f'actual Rust controller {mode} absent')
    n = p['network']
    keys(n, 'transport inputEndpoint chosenPort ownedBindSucceeded rulesVersion streamEnabled universeHandshake expectedWireHex actualWireHex sendAttempts sendCompletions acceptedPeerAddress acceptedPeerPort acceptedPeerSource clientLocalOsAvailable clientLocalCachePort sentText receivedText sentMode receivedMode receivedData receivedPacketCount pending')
    port = n['chosenPort']
    require(integer(port, 40201, 40232) and n['inputEndpoint'] == f'127.0.0.1:{port}'
            and n['ownedBindSucceeded'] is True, 'owned numeric listener')
    require(n['transport'] == 'tcp' and type(n['rulesVersion']) is int and n['rulesVersion'] == 5
            and n['streamEnabled'] is False and n['universeHandshake'] is False, 'TCP framing contract')
    require(n['expectedWireHex'] == WIRE and n['actualWireHex'] == WIRE, 'independent actual wire')
    require(integer(n['sendAttempts'], 1) and type(n['sendCompletions']) is int
            and n['sendAttempts'] == n['sendCompletions'], 'actual send boundary')
    require(n['acceptedPeerAddress'] == '127.0.0.1' and integer(n['acceptedPeerPort'], 1, 65535)
            and n['acceptedPeerSource'] == 'OS-accept-sockaddr'
            and n['clientLocalOsAvailable'] is False and type(n['clientLocalCachePort']) is int
            and n['clientLocalCachePort'] == 0, 'OS/cache provenance')
    require(n['sentText'] == n['receivedText'] == 'STREAM' and type(n['sentMode']) is int
            and type(n['receivedMode']) is int and n['sentMode'] == n['receivedMode'] == 0
            and same(n['receivedData'], {}) and type(n['receivedPacketCount']) is int
            and n['receivedPacketCount'] == 1 and n['pending'] is False, 'typed received packet')
    s = p['save']
    keys(s, 'filename wireHex expectedWireHex value consumed atEnd')
    require(type(s['filename']) is str and Path(s['filename']).name == 'datastream-save.sbvj', 'save filename')
    require(s['wireHex'] == s['expectedWireHex'] == SAVE and same(s['value'], VALUE)
            and type(s['consumed']) is int and s['consumed'] == len(bytes.fromhex(SAVE))
            and s['atEnd'] is True, 'native save literal/schema/EOF')
    d = p['database']
    keys(d, 'filename key blockSize pagesHex foundHex memoryPagesHex memoryFoundHex value consumed atEnd')
    require(type(d['filename']) is str and Path(d['filename']).name == 'datastream-color.btree'
            and d['key'] == 'color' and type(d['blockSize']) is int and d['blockSize'] == 512, 'database identity')
    require(d['foundHex'] == d['memoryFoundHex'] == SAVE and same(d['value'], VALUE)
            and type(d['consumed']) is int and d['consumed'] == len(bytes.fromhex(SAVE))
            and d['atEnd'] is True, 'reopened database value/EOF')
    pages, memory = binary(d['pagesHex']), binary(d['memoryPagesHex'])
    # Memory backing is explicitly initialized before logical truncation;
    # native file extension supplies zeros. No uninitialized header bytes.
    for data in (pages, memory):
        require(1024 <= len(data) <= 8192 and len(data) % 512 == 0
                and data[:12] == b'BTreeDB5\x00\x00\x02\x00'
                and data[12:28] == b'datastreamlab\x00\x00\x00'
                and data[28:32] == b'\x00\x00\x00\x20'
                and bytes.fromhex(SAVE) in data, 'independent database header/value')
    require(pages == memory, 'native memory/file database bytes')
    require(same(p['visual'], {'imagePath': IMAGE, 'color': COLOR, 'sourceSize': [16, 16],
            'displaySize': [64, 64], 'scale': 4, 'label': 'STREAM'}), 'normal Assets/Font consumer')
    out = deepcopy(p)
    for key in ('backend', 'calls', 'scopes', 'nativeObservedCalls'):
        out.pop(key)
    # Counts are scheduling-dependent, but only after positive balanced calls.
    out['network']['sendAttempts'] = out['network']['sendCompletions'] = '<validated-send-count>'
    out['network']['chosenPort'] = '<owned-listener-port>'
    out['network']['inputEndpoint'] = '127.0.0.1:<owned-listener-port>'
    out['network']['acceptedPeerPort'] = '<accepted-ephemeral-port>'
    out['save']['filename'] = '<owned-storage>/datastream-save.sbvj'
    out['database']['filename'] = '<owned-storage>/datastream-color.btree'
    return out


def bind(receipt, configuration):
    """Run before path projection; compare actual owned file bytes, not names."""
    validate(receipt)
    storage = Path(configuration['storageDirectory']).resolve(strict=True)
    require(configuration['storageDirectory'] == str(storage), 'canonical sandbox storage')
    for name, filename, field in (('save', 'datastream-save.sbvj', 'wireHex'),
                                   ('database', 'datastream-color.btree', 'pagesHex')):
        p = Path(receipt['dataStreamProof'][name]['filename'])
        require(p == storage / filename and not p.is_symlink()
                and p.resolve(strict=True).parent == storage, 'owned file path')
        require(p.read_bytes().hex() == receipt['dataStreamProof'][name][field], 'owned file bytes')


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
