"""Independent frozen PathEmbed text.frames, native image and TCP consumer proof.

Synthetic verifier tests are not application evidence. PNG rows are top-down;
StarImage.cpp:113 reverses them and Assets::loadImage flips frame bounds.
"""
import base64
import io
import json
from PIL import Image

FRAME_NAME = 'reserved%:?;/'
ESCAPED_NAME = 'reserved%%%c%q%s%b'
FRAMES = {'frameList': {FRAME_NAME: [16, 0, 32, 16], 'wrong': [0, 0, 16, 16]},
          'aliases': {'crop': FRAME_NAME}}
PARSED_FRAMES = {'file': '<embedded frames>', 'frames': FRAMES['frameList'], 'aliases': FRAMES['aliases']}
COLORS = ((240, 80, 40, 255), (40, 200, 120, 255), (40, 80, 240, 255), (240, 200, 40, 255))
MAX_PATH = 32768


def same(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(same(actual[k], expected[k]) for k in expected)
    if type(expected) is list:
        return len(actual) == len(expected) and all(same(a, b) for a, b in zip(actual, expected))
    return actual == expected


def keys(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError('invalid PathEmbed proof member set')


def require(actual, expected, message):
    if not same(actual, expected):
        raise ValueError('PathEmbed ' + message)


def pixels(crop=False, native=False):
    """Literal seed model; never read a candidate image to predict itself."""
    rows = []
    for y in range(16):
        row = bytearray()
        for x in range(16 if crop else 32):
            u = x % 16
            color = (224, 32, 176, 255)
            if crop or x >= 16:
                color = COLORS[(y // 8) * 2 + u // 8]
                if (u, y) == (1, 1):
                    color = (255, 255, 255, 255)
                if (u, y) == (14, 14):
                    color = (0, 0, 0, 255)
            row.extend(color)
        rows.append(bytes(row))
    return b''.join(reversed(rows) if native else rows)


def escape(text):
    substitutions = {'%': '%%', ':': '%c', '?': '%q', ';': '%s', '/': '%b'}
    return ''.join(substitutions.get(char, char) for char in text)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('PathEmbed duplicate raw frame member')
        result[key] = value
    return result


def counts(value):
    keys(value, 'selector escape')
    if any(type(n) is not int or not 0 <= n < 2**63 for n in value.values()):
        raise ValueError('PathEmbed completed counter is not an exact bounded integer')


def validate(receipt):
    if type(receipt) is not dict:
        raise ValueError('invalid PathEmbed receipt')
    p = receipt.get('pathEmbedProof')
    keys(p, 'version backend source parsedFrames images ownership network visual')
    require(p['version'], 1, 'version differs')
    backend = p['backend']
    if type(backend) is not str or backend not in ('native', 'rust'):
        raise ValueError('invalid PathEmbed backend')
    source = p['source']
    keys(source, 'version measurement basePath cropPath selectedAlias reservedFrameName seedSize selectedRect wrongRect')
    for key, expected in {'version': 1, 'selectedAlias': 'crop', 'reservedFrameName': FRAME_NAME,
                          'seedSize': [32, 16], 'selectedRect': [16, 0, 32, 16], 'wrongRect': [0, 0, 16, 16]}.items():
        require(source[key], expected, 'source ' + key + ' differs')
    path = source['basePath']
    if type(path) is not str or not 32 < len(path) <= MAX_PATH:
        raise ValueError('invalid PathEmbed base path extent')
    require(source['cropPath'], path + ':crop', 'alias path differs')
    parts = path.split(';')
    if len(parts) != 6 or parts[:2] != ['/opensb_data', 'image'] or parts[3:5] != ['frames', 'text']:
        raise ValueError('PathEmbed must use normal None/text image frames')
    encoded, escaped = parts[2], parts[5]
    try:
        png = base64.b64decode(encoded + '=' * (-len(encoded) % 4), altchars=b'-_', validate=True)
        if base64.urlsafe_b64encode(png).decode().rstrip('=') != encoded:
            raise ValueError('PathEmbed noncanonical URL base64')
        with Image.open(io.BytesIO(png)) as image:
            if image.format != 'PNG' or image.mode != 'RGBA' or image.size != (32, 16) or image.tobytes() != pixels():
                raise ValueError('PathEmbed producer PNG differs from literal seed')
    except (OSError, SyntaxError, base64.binascii.Error) as error:
        raise ValueError('invalid PathEmbed producer PNG/base64') from error
    m = source['measurement']
    keys(m, 'version backend scopeThread completed operationCount before after delta method framesMode path rawFrames escapedFrames')
    for key, expected in {'version': 1, 'backend': backend, 'scopeThread': 'lua-calling-thread',
                          'completed': True, 'operationCount': 1, 'method': 'None', 'framesMode': 'text',
                          'path': path, 'escapedFrames': escaped}.items():
        require(m[key], expected, 'normal embed measurement ' + key + ' differs')
    raw = m['rawFrames']
    if type(raw) is not str or not 1 <= len(raw) <= 2048:
        raise ValueError('invalid PathEmbed raw frames extent')
    try:
        parsed = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, TypeError, RecursionError) as error:
        raise ValueError('invalid PathEmbed raw frame JSON') from error
    require(parsed, FRAMES, 'raw frame names/alias/bounds differ')
    require(escaped, escape(raw), 'full literal escaped text differs')
    if escaped.count(ESCAPED_NAME) != 2:
        raise ValueError('PathEmbed independent escaped reserved name count differs')
    for name in ('before', 'after', 'delta'):
        counts(m[name])
    wanted = int(backend == 'rust')
    require(m['delta'], {'selector': wanted, 'escape': wanted}, 'completed operation deltas differ')
    for name in ('selector', 'escape'):
        if m['after'][name] - m['before'][name] != wanted or (backend == 'native' and m['before'][name] != 0):
            raise ValueError('PathEmbed stale/aliased executing-thread completed counters')
    require(p['parsedFrames'], PARSED_FRAMES, 'actual Assets text.frames/alias parser differs')
    keys(p['images'], 'base crop')
    for name, crop in (('base', False), ('crop', True)):
        require(p['images'][name], {'size': [16 if crop else 32, 16], 'layout': 'native-bottom-up-rgba8',
                'rgbaHex': pixels(crop=crop, native=True).hex()}, 'actual decoded ' + name + ' pixels/layout differ')
    require(p['ownership'], {'baseHeld': True, 'cropHeld': True, 'baseIdentityUnchanged': True,
            'cropIdentityUnchanged': True, 'distinctImages': True, 'baseAcquisitions': 1, 'cropAcquisitions': 1},
            'original base/crop render ownership differs')
    network = p['network']
    keys(network, 'transport address rulesVersion streamEnabled universeHandshake ownedBindSucceeded rounds')
    for name, value in {'transport': 'tcp', 'address': '127.0.0.1', 'rulesVersion': 5, 'streamEnabled': False,
                        'universeHandshake': False, 'ownedBindSucceeded': True}.items():
        require(network[name], value, 'normal TCP ' + name + ' differs')
    expected_rounds = [{'direction': 'a-to-b', 'sentText': text, 'receivedText': text,
                        'sendMode': 0, 'receivedData': {}} for text in (path, path + ':crop', 'PATHEMBED')]
    require(network['rounds'], expected_rounds, 'typed TCP base/crop/label delivery differs')
    require(p['visual'], {'imagePath': path + ':crop', 'basePath': path, 'scale': 4, 'displaySize': [64, 64],
            'center': [64, 48], 'fullbright': True, 'consumer': 'WorldPainter.foregroundOverlays', 'label': 'PATHEMBED'},
            'actual crop WorldPainter/Font submission differs')
    # Only completed counter snapshots and the explicit backend differ across
    # builds. All raw paths, text, decoded pixels and ownership remain compared.
    normalized_measurement = {k: v for k, v in m.items() if k not in ('backend', 'before', 'after', 'delta')}
    return {k: v for k, v in p.items() if k not in ('backend', 'source')} | {
        'source': source | {'measurement': normalized_measurement}}


def validate_snapshots(receipts):
    if type(receipts) is not list or len(receipts) != 3:
        raise ValueError('PathEmbed requires three stage snapshots')
    proofs = [validate(receipt) for receipt in receipts]
    if any(not same(proof, proofs[0]) for proof in proofs[1:]):
        raise ValueError('PathEmbed consumer observations changed across stages')
    # Normalization must not let a backend switch or stale counters hide within
    # an otherwise equal three-frame consumer proof.
    measurements = [r['pathEmbedProof']['source']['measurement'] for r in receipts]
    if any(not same(m, measurements[0]) for m in measurements[1:]):
        raise ValueError('PathEmbed measured operation changed across stages')
    return proofs[0]


def visible(frame, receipt):
    validate(receipt)
    camera = receipt.get('cameraPosition')
    if (type(camera) is not list or len(camera) != 2
            or any(type(v) not in (int, float) for v in camera) or camera != [64, 48]
            or type(receipt.get('cameraPixelRatio')) not in (int, float) or receipt['cameraPixelRatio'] != 2
            or min(frame.size) < 200):
        raise ValueError('invalid PathEmbed camera/viewport')
    x, y = frame.width // 2, frame.height // 2
    expected = Image.frombytes('RGBA', (16, 16), pixels(crop=True)).resize((64, 64), Image.Resampling.NEAREST)
    if frame.crop((x - 32, y - 32, x + 32, y + 32)).convert('RGBA').tobytes() != expected.tobytes():
        raise ValueError('PathEmbed visible crop pixels/orientation/geometry differ')
    label = frame.crop((x - 100, y - 100, x + 100, y - 40)).convert('RGBA')
    if list(label.getdata()).count((255, 255, 255, 255)) < 8:
        raise ValueError('PathEmbed normal Font label missing')
