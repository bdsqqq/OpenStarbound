"""Source-derived Buffer consumer literals, frozen before actual capture."""
from copy import deepcopy
import hashlib
from pathlib import Path
from host_address_proof import same, integer
from btree_padding import validate_pages

COLOR = [64, 144, 224, 255]
IMAGE = '/behaviorlab/buffer.png?multiply=4090e0ff'
LABEL = 'BUF-A|BUF-B'
PAYLOAD = ''.join(chr(97 + i % 26) for i in range(1537))
FRAME_A = bytes.fromhex('1210054255462d410000')
FRAME_B = bytes.fromhex('1210054255462d420000')
WIRE = (FRAME_A + FRAME_B).hex()
CHUNKS = [FRAME_A[:1], FRAME_A[1:5], FRAME_A[5:] + FRAME_B[:4], FRAME_B[4:]]
# SBVJ01, length9/id, present-u32 version1, JSON array5, four signed-VLQ
# integers, string length1537 (8c01), then the native sub-version trailer.
SAVE_BYTES = (bytes.fromhex('5342564a3031096275666665726c61620100000001060504810004822004834004837e058c01')
              + PAYLOAD.encode('ascii')
              + bytes.fromhex('00000001010b73756256657273696f6e730700'))
SAVE_HEX = SAVE_BYTES.hex()
SAVE_SHA256 = hashlib.sha256(SAVE_BYTES).hexdigest()
VALUE = {'id':'bufferlab', 'version':1, 'content':[*COLOR, PAYLOAD], 'subVersions':{}}


def require(ok, message):
    if not ok:
        raise ValueError('buffer: ' + message)


def keys(value, names):
    require(type(value) is dict and set(value) == set(names.split()), 'schema')


def counters(value, backend):
    keys(value, 'attempt success exception')
    for row in value.values():
        require(type(row) is list and len(row) == 50 and all(integer(n) for n in row), '50x3 counter shape/type')
    for a,s,e in zip(value['attempt'], value['success'], value['exception']):
        require(a == s + e and e == 0, 'successful native counter balance')
        if backend == 'cpp':
            require(a == 0, 'C++ consumer called Rust')


METHODS = [*(f'TcpPacketSocket::readData/receivePackets(stage{i})' for i in range(4)),
    'VersionedJson::writeFile', 'VersionedJson::readFile',
    'VersionedJson::readSubVersioning(owned file bytes)',
    'BTreeSha256Database::open/insert/commit/close(memory)',
    'BTreeSha256Database::open/find/close(memory)',
    'VersionedJson::readSubVersioning(memory BTree value)',
    'BTreeSha256Database::open/insert/commit/close(file)',
    'BTreeSha256Database::open/find/close(file)',
    'VersionedJson::readSubVersioning(BTree value)']
# Lower bounds follow actual native constructors/readers, not capture counts.
# Socket polling may add whole parser invocations. DataStreamDevices.cpp:130–147
# default-constructs ExternalBuffer then reset (NOT its pointer constructor),
# and its size() calls dataSize (43), NOT ExternalBuffer::size (41). File
# readFile is a direct DataStreamIODevice(File), with no Buffer call.
ANCHORS = {**{i: (31,33,35,36,43,46,49) for i in range(4)},
           4: (0,10,18,25,30), 6: (9,29), 9: (9,29), 12: (9,29)}


def binary(value):
    require(type(value) is str and len(value)%2 == 0, 'hex shape')
    try:
        data = bytes.fromhex(value)
    except ValueError as e:
        raise ValueError('buffer: invalid hex') from e
    require(data.hex() == value, 'canonical hex')
    return data


def parser_events(events):
    """Validate each real cursor trace against the two literal 10-byte frames.

    Receive grouping/poll count is deliberately not assumed. Only after every
    event is checked may equivalent traces be projected to the four stages.
    """
    require(type(events) is list and 0 < len(events) <= 100000, 'parser events')
    total = pending = produced = index = 0
    last_stage = 0
    ends = {}
    kinds = set()
    totals = (1,5,14,20)
    counts = (0,0,1,2)
    while index < len(events):
        event = events[index]
        require(type(event) is dict and integer(event.get('stage'),0,3), 'event stage')
        stage = event['stage']
        require(last_stage <= stage <= last_stage+1, 'ordered event stages')
        last_stage = stage
        if event.get('kind') == 'receive':
            keys(event, 'stage kind bytes cumulativeBytes bufferSize')
            require(integer(event['bytes'],1,20), 'actual receive count')
            total += event['bytes']; pending += event['bytes']
            require(total <= totals[stage] and event['cumulativeBytes'] == total
                    and event['bufferSize'] == pending
                    and type(event['cumulativeBytes']) is int and type(event['bufferSize']) is int,
                    'actual receive/buffer extent')
            index += 1
            continue
        require(event.get('kind') == 'begin', 'unmatched parser checkpoint')
        size, pos, trim = pending, 0, 0
        wanted = [('begin',0,size,size,0)]
        while pos < size:
            left = size-pos
            if left == 1:
                pos += 1
                wanted.append(('incomplete-header',pos,size,size-pos,trim))
                break
            pos += 2
            if left < 10:
                wanted.append(('incomplete-payload',pos,size,size-pos,trim))
                break
            pos += 8; trim = pos; produced += 1
            wanted.append(('packet-complete',pos,size,size-pos,trim))
        wanted.append(('before-trim',pos,size,size-pos,trim))
        pending -= trim
        wanted.append(('after-trim',0,pending,pending,trim))
        for kind,p,s,r,c in wanted:
            require(index < len(events), 'truncated cursor trace')
            item = events[index]
            keys(item, 'stage kind pos size remaining consumed')
            require(same(item,dict(stage=stage,kind=kind,pos=p,size=s,remaining=r,consumed=c)),
                    'source-derived parser position/remaining/trim')
            kinds.add((stage,kind)); index += 1
        require(produced <= counts[stage], 'premature/extra typed packet')
        ends[stage] = (total,pending,produced)
    require(ends == {i:(totals[i],(1,5,4,0)[i],counts[i]) for i in range(4)}, 'four staged parser boundaries')
    require({(0,'incomplete-header'),(1,'incomplete-payload'),(2,'packet-complete'),
             (2,'incomplete-payload'),(3,'packet-complete')} <= kinds, 'fragment/coalescing coverage')
    return [list(ends[i]) for i in range(4)]


def validate(receipt):
    p = receipt.get('bufferProof')
    byte_array = None
    if type(p) is dict and 'byteArray' in p:
        from byte_array_proof import validate_fields
        byte_array = validate_fields(p['byteArray'])
        p = deepcopy(p)
        p.pop('byteArray')
    io = None
    if type(p) is dict and 'ioDevice' in p:
        from io_device_proof import validate_fields
        io = validate_fields(p['ioDevice'])
        p = deepcopy(p)
        p.pop('ioDevice')
    keys(p, 'version backend nativeObservedCalls scopes calls network save database visual')
    require(type(p['version']) is int and p['version']==1 and p['backend'] in ('cpp','rust'), 'version/backend')
    backend = p['backend']
    require(type(p['nativeObservedCalls']) is int and p['nativeObservedCalls']==13
            and type(p['scopes']) is list and len(p['scopes'])==13, 'native scopes')
    counters(p['calls'],backend)
    for i,scope in enumerate(p['scopes']):
        keys(scope, 'method completed calls')
        require(scope['method']==METHODS[i] and scope['completed'] is True, 'native scope order')
        counters(scope['calls'],backend)
        if backend=='rust':
            for mode in ANCHORS.get(i,()):
                require(scope['calls']['success'][mode]>0, f'source controller {mode} missing in scope {i}')
            if i==5:
                require(not any(scope['calls']['attempt']), 'direct File reader mislabeled as Buffer')
    if backend=='rust':
        for mode in range(50):
            require(p['calls']['success'][mode]>=sum(s['calls']['success'][mode] for s in p['scopes']), 'scope containment')
    n=p['network']
    keys(n, 'transport producer inputEndpoint chosenPort ownedBindSucceeded rulesVersion streamEnabled universeHandshake expectedWireHex actualWireHex sentWireHex sendAttempts stages parserEvents acceptedPeerAddress acceptedPeerPort acceptedPeerSource clientLocalOsAvailable receivedTexts receivedPacketCount')
    require(integer(n['chosenPort'],40233,40264) and n['inputEndpoint']==f"127.0.0.1:{n['chosenPort']}"
            and n['ownedBindSucceeded'] is True, 'owned numeric listener')
    require(n['transport']=='tcp' and n['producer']=='independent-literal-raw-sender'
            and type(n['rulesVersion']) is int and n['rulesVersion']==5
            and n['streamEnabled'] is False and n['universeHandshake'] is False, 'native typed framing contract')
    require(n['expectedWireHex']==n['actualWireHex']==n['sentWireHex']==WIRE
            and integer(n['sendAttempts'],4), 'independent actual sent/received bytes')
    require(n['acceptedPeerAddress']=='127.0.0.1' and integer(n['acceptedPeerPort'],1,65535)
            and n['acceptedPeerSource']=='OS-accept-sockaddr' and n['clientLocalOsAvailable'] is False, 'OS/cache provenance')
    require(same(n['receivedTexts'],['BUF-A','BUF-B']) and type(n['receivedPacketCount']) is int
            and n['receivedPacketCount']==2, 'typed decoded messages')
    require(same(n['stages'],[dict(stage=i,sentBytes=t,receivedBytes=t,packetCount=c)
            for i,(t,c) in enumerate(zip((1,5,14,20),(0,0,1,2)))]), 'four stage counts')
    normalized = parser_events(n['parserEvents'])
    s=p['save'];keys(s,'filename wireHex expectedWireHex value consumed atEnd')
    require(type(s['filename']) is str and Path(s['filename']).name=='buffer-save.sbvj'
            and s['wireHex']==s['expectedWireHex']==SAVE_HEX and same(s['value'],VALUE)
            and type(s['consumed']) is int and s['consumed']==1594 and s['atEnd'] is True, 'independent native save/EOF')
    d=p['database'];keys(d,'filename key blockSize pagesHex foundHex memoryPagesHex memoryFoundHex memoryValue memoryConsumed memoryAtEnd value consumed atEnd')
    require(type(d['filename']) is str and Path(d['filename']).name=='buffer-payload.btree'
            and d['key']=='buffer-payload' and type(d['blockSize']) is int and d['blockSize']==512, 'database identity')
    require(d['foundHex']==d['memoryFoundHex']==SAVE_HEX and same(d['value'],VALUE) and same(d['memoryValue'],VALUE)
            and type(d['consumed']) is int and d['consumed']==1594 and d['atEnd'] is True
            and type(d['memoryConsumed']) is int and d['memoryConsumed']==1594 and d['memoryAtEnd'] is True, 'multi-block reopened value/EOF')
    pages,memory=binary(d['pagesHex']),binary(d['memoryPagesHex'])
    for data in (pages,memory):
        validate_pages(data)
        require(2560<=len(data)<=8192 and len(data)%512==0 and data[:12]==b'BTreeDB5\x00\x00\x02\x00'
                and data[12:28]==b'bufferlab'+bytes(7) and data[28:32]==b'\x00\x00\x00\x20'
                and hashlib.sha256(b'buffer-payload').digest() in data
                and PAYLOAD[:208].encode() in data, 'independent multi-block header/key/payload')
    require(pages==memory, 'initialized memory/file page bytes')
    require(same(p['visual'],dict(imagePath=IMAGE,color=COLOR,sourceSize=[16,16],displaySize=[64,64],scale=4,label=LABEL)), 'normal Assets/Font consumer')
    out=deepcopy(p)
    for key in ('backend','calls','scopes','nativeObservedCalls'):out.pop(key)
    out['network']['parserEvents']=normalized
    out['network']['sendAttempts']='<validated-partial-send-count>'
    out['network']['chosenPort']='<owned-listener-port>'
    out['network']['inputEndpoint']='127.0.0.1:<owned-listener-port>'
    out['network']['acceptedPeerPort']='<accepted-ephemeral-port>'
    out['save']['filename']='<owned-storage>/buffer-save.sbvj'
    out['database']['filename']='<owned-storage>/buffer-payload.btree'
    if io is not None:
        out['ioDevice'] = io
    if byte_array is not None:
        out['byteArray'] = byte_array
    return out


def bind(receipt,configuration):
    validate(receipt)
    storage=Path(configuration['storageDirectory']).resolve(strict=True)
    require(configuration['storageDirectory']==str(storage), 'canonical storage')
    for name,filename,field in (('save','buffer-save.sbvj','wireHex'),('database','buffer-payload.btree','pagesHex')):
        path=Path(receipt['bufferProof'][name]['filename'])
        require(path==storage/filename and not path.is_symlink() and path.resolve(strict=True).parent==storage, 'owned path')
        require(path.read_bytes().hex()==receipt['bufferProof'][name][field], 'actual owned file bytes')


def visible(frame,receipt):
    validate(receipt)
    require(receipt.get('cameraPosition')==[64,48] and receipt.get('cameraPixelRatio')==2
            and min(frame.size)>=200, 'camera/viewport')
    rgba=frame.convert('RGBA');x,y=frame.width//2,frame.height//2
    ink=[(i%rgba.width,i//rgba.width) for i,pixel in enumerate(rgba.getdata()) if pixel==tuple(COLOR)]
    require(len(ink)==4096,'normal image area')
    require((min(a for a,b in ink),min(b for a,b in ink),max(a for a,b in ink)+1,max(b for a,b in ink)+1)==(x-32,y-32,x+32,y+32),'normal image geometry')
    label=frame.crop((x-100,y-100,x+100,y-40)).convert('RGBA')
    require(list(label.getdata()).count((255,255,255,255))>=8,'normal Font label absent')
