"""Strict finite consumer scaffold; validation alone is not native/application proof."""
from copy import deepcopy

EVENTS = ('attempt', 'success', 'exception')
MODE_COUNT = 58
U64 = 2**64
METHODS = ('AssetPath::split/Directives::parse/imageOperationFromString',
           'TextPainter::applyCommands')
REQUIRED = ((32, 33, 50), (33, 30, 47, 48, 50))
ASSET_PATH = '/behaviorlab/string-view.png?setcolor=123456'
INPUT = '^shadow=#123456,noshadow;VIEW'
SEED_RGBA = [[231, 17, 43, 0], [29, 197, 61, 64],
             [53, 79, 211, 128], [163, 107, 37, 255]]
# Literal expectations: never ask the parser under test to compute its oracle.
IMAGE = {'width': 2, 'height': 2, 'rgba': [
    [18, 52, 86, 0], [18, 52, 86, 64], [18, 52, 86, 128], [18, 52, 86, 255]]}
TRANSITIONS = [{'command': 'shadow', 'rgba': [18, 52, 86, 255]},
               {'command': 'noshadow', 'rgba': [0, 0, 0, 0]}]
FONT = {'input': INPUT, 'completed': True, 'valid': True,
        'events': [{'kind': 'command', 'hex': b'shadow=#123456,noshadow'.hex()},
                   {'kind': 'text', 'hex': b'VIEW'.hex()}],
        'glyphs': [{'codepoint': n, 'rgba': [255, 255, 255, 255]} for n in b'VIEW']}


def require(ok, message):
    if not ok:
        raise ValueError('StringView proof: ' + message)


def same(a, b):
    if type(a) is not type(b):
        return False
    if type(b) is dict:
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in b)
    if type(b) is list:
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def counters(value, backend):
    require(type(value) is dict and set(value) == set(EVENTS), 'counter fields')
    for row in value.values():
        require(type(row) is list and len(row) == MODE_COUNT
                and all(type(n) is int and 0 <= n < U64 for n in row), 'typed 58-mode u64 counts')
    for a, s, e in zip(*(value[k] for k in EVENTS)):
        require(a == (s + e) % U64, 'unbalanced calls')
    if backend == 'cpp':
        require(not any(n for row in value.values() for n in row), 'cpp Rust calls')


def validate_fields(p):
    require(type(p) is dict and set(p) == set('version backend active scopeThread captureExcluded '
        'valid overflow completed calls scopes transitions assetPath imageRead image font'.split()), 'fields')
    require(type(p['version']) is int and p['version'] == 1, 'version')
    require(type(p['backend']) is str and p['backend'] in ('cpp', 'rust'), 'backend')
    for key in ('active', 'captureExcluded', 'valid', 'completed'):
        require(p[key] is True, key)
    require(p['overflow'] is False and p['scopeThread'] == 'main', 'overflow/thread')
    require(same(p['assetPath'], ASSET_PATH), 'normal asset path')
    # This tag describes a read that MAY hit the processed-image cache. It does
    # not prove worker-local operation, fresh application, or worker execution.
    require(p['imageRead'] == 'normal-assets-cache-permitted', 'image read tag')
    require(same(p['image'], IMAGE), 'actual image RGB/alpha/dimensions')
    require(same(p['transitions'], TRANSITIONS), 'shadow state transitions')
    require(same(p['font'], FONT), 'separate normal foreground font evidence')
    counters(p['calls'], p['backend'])
    require(type(p['scopes']) is list and len(p['scopes']) == 2, 'two source scopes')
    for i, scope in enumerate(p['scopes']):
        require(type(scope) is dict and set(scope) == {'method', 'completed', 'calls'}, 'scope fields')
        require(same(scope['method'], METHODS[i]) and scope['completed'] is True, 'source scope completion/order')
        counters(scope['calls'], p['backend'])
        if p['backend'] == 'rust':
            for mode in REQUIRED[i]:
                require(scope['calls']['success'][mode] > 0, f'scope {i} missing consumer mode {mode}')
    for event in EVENTS:
        for mode in range(MODE_COUNT):
            require(p['calls'][event][mode] == sum(s['calls'][event][mode] for s in p['scopes']),
                    'exact source scope sum')
    out = deepcopy(p)
    for key in ('backend', 'calls', 'scopes'):
        out.pop(key)
    return out


def validate(receipt):
    require(type(receipt) is dict and 'stringViewProof' in receipt, 'missing consumer proof')
    return validate_fields(receipt['stringViewProof'])
