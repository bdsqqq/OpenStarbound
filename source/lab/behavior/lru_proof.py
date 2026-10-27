"""Actual DungeonDefinitions receipts: independent native pre-evict semantics.

Logical fixtures test this verifier, NOT the application. Cache/symbol/error bytes
remain hex, and u64 counters remain eight big-endian bytes, never JSON doubles.
"""
import re

SELECTOR = 'STAR_USE_RUST_LRU_CACHE'
STAGES = ('lit-room', 'occluder-added', 'occluder-restored')
ACTIONS = ('room-populated', 'foreground-occluder-added', 'foreground-occluder-removed')
COUNTS = (22, 25, 27)
MISSING = 'behavior-lru-unknown'
HEX = re.compile(r'(?:[0-9a-f]{2})*\Z')


def same(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def need(condition, message):
    if not condition:
        raise ValueError('LRU ' + message)


def equal(actual, expected, message):
    need(same(actual, expected), message)


def members(value, names):
    need(type(value) is dict and set(value) == set(names.split()), 'member set: ' + names)


def byte_hex(value, length=None):
    need(type(value) is str and HEX.fullmatch(value) is not None, 'noncanonical byte hex')
    need(length is None or len(value) == length * 2, 'byte extent')
    return bytes.fromhex(value)


def counter(value):
    return int.from_bytes(byte_hex(value, 8), 'big')


def name(i):
    return f'behavior-lru-{i:02d}'


def requests():
    return list(range(1, 22)) + [21, 1, None, 1, 2, 2]


def phase_for(index):
    return 0 if index < 22 else 1 if index < 25 else 2


def metadata(i):
    return dict(name=name(i), displayName=f'LRU definition {i}', species='human', anchor=[],
                maxParts=i, maxRadius=100, protected=i % 2 == 0, gravity=10+i,
                breathable=True, labIndex=i)


def state(keys):
    return dict(size=len(keys), max=20, keysHex=keys[:])


def snapshot(value):
    members(value, 'size max keysHex')
    need(type(value['size']) is int and 0 <= value['size'] <= 20, 'cache size')
    equal(value['max'], 20, 'capacity changed')
    keys = value['keysHex']
    need(type(keys) is list and len(keys) == value['size'], 'cache key membership/size')
    for key in keys:
        byte_hex(key)
    need(len(set(keys)) == len(keys), 'duplicate cache keys')
    return keys[:]


def validate(receipt):
    need(type(receipt) is dict, 'receipt type')
    p = receipt.get('lruProof')
    members(p, 'version backend selector scopeThread phase events visual consumer imageConsumer labelConsumer')
    equal(p['version'], 1, 'version')
    need(type(p['backend']) is str and p['backend'] in ('native', 'rust'), 'backend')
    equal(p['selector'], SELECTOR, 'selector')
    equal(p['scopeThread'], 'lua-calling-thread', 'executing thread')
    equal(p['consumer'], 'normal-root.dungeonMetadata-Assets-DungeonDefinition', 'consumer')
    equal(p['imageConsumer'], 'normal-Assets-WorldPainter', 'image consumer')
    equal(p['labelConsumer'], 'normal-Font-TextPainter', 'label consumer')
    phase = p['phase']
    need(type(phase) is int and phase in (0, 1, 2), 'phase')
    equal(receipt.get('stageIndex'), phase, 'frame/phase mismatch')
    events = p['events']
    need(type(events) is list and len(events) == COUNTS[phase], 'operation count')
    for event in events:
        members(event, 'operation index phase nameHex before after producerCalled producerState status error rootBeforeHex rootAfterHex')
    keys = snapshot(events[0]['before'])
    normalized = []
    previous = None
    for index, (event, requested) in enumerate(zip(events, requests())):
        members(event, 'operation index phase nameHex before after producerCalled producerState status error rootBeforeHex rootAfterHex')
        equal(event['operation'], 'DungeonDefinitions.get', 'operation')
        equal(event['index'], index, 'operation ordinal')
        op_phase = phase_for(index)
        equal(event['phase'], op_phase, 'operation phase')
        n = MISSING if requested is None else name(requested)
        key = n.encode('ascii').hex()
        equal(event['nameHex'], key, 'actual request name bytes')
        snapshot(event['before'])
        equal(event['before'], state(keys), 'before state/order drift')
        # Native get pre-evicts before *any* lookup, even an MRU hit/error.
        while len(keys) > 19:
            keys.pop(0)
        produced = key not in keys
        equal(event['producerCalled'], produced, 'hit/producer status')
        equal(event['producerState'], state(keys) if produced else None, 'producer-time pre-eviction')
        if requested is None:
            equal(event['status'], 'error', 'unknown name status')
            members(event['error'], 'kind messageHex')
            equal(event['error']['kind'], 'std::exception', 'error kind')
            message = byte_hex(event['error']['messageHex'])
            need(b'Unknown dungeon:' in message and MISSING.encode() in message, 'actual unknown-name error bytes')
        else:
            equal(event['status'], 'ok', 'valid definition status')
            equal(event['error'], None, 'unexpected error')
            if not produced:
                keys.remove(key)
            keys.append(key)
        snapshot(event['after'])
        equal(event['after'], state(keys), 'after state/eviction order/partial effect')
        before, after = counter(event['rootBeforeHex']), counter(event['rootAfterHex'])
        delta = 1 if p['backend'] == 'rust' else 0
        need((after - before) % 2**64 == delta, 'actual Rust root-get counter delta')
        if p['backend'] == 'native':
            need(before == after == 0, 'native OFF baseline counter')
        if previous is not None and op_phase == phase_for(index-1):
            need(before == previous, 'within-phase root-get progression')
        previous = after
        normalized.append({k: v for k, v in event.items() if k not in ('rootBeforeHex', 'rootAfterHex')})
    final = ([name(i) for i in range(3, 22)] if phase == 0 else
             [name(i) for i in range(4, 22)] + [name(1)] if phase == 1 else
             [name(i) for i in range(5, 22)] + [name(1), name(2)])
    equal(keys, [n.encode().hex() for n in final], 'explicit terminal membership')
    visual = p['visual']
    members(visual, 'phase results continuation selected color label scale imagePath')
    equal(visual['phase'], phase, 'Lua phase')
    equal(visual['continuation'], True, 'continued Lua after error')
    selected = (21, 1, 2)[phase]
    equal(visual['selected'], metadata(selected), 'normal constructed metadata')
    color = [selected*8, selected*4, (phase+1)*80, 255]
    equal(visual['color'], color, 'metadata/phase-derived color')
    equal(visual['label'], f'LRU {phase+1}/3 metadata={selected:02d} continue=ok', 'Font label')
    equal(visual['scale'], 4, 'display scale')
    equal(visual['imagePath'], '/behaviorlab/lru-white.png?multiply=' + bytes(color).hex(), 'normal Assets image path')
    current = [r for index, r in enumerate(requests()[:COUNTS[phase]]) if phase_for(index) == phase]
    results = visual['results']
    need(type(results) is list and len(results) == len(current), 'Lua results count')
    for result, requested in zip(results, current):
        if requested is None:
            members(result, 'name ok error')
            equal(result['name'], MISSING, 'Lua unknown name')
            equal(result['ok'], False, 'Lua pcall error')
            need(type(result['error']) is str and MISSING in result['error'] and 'Unknown dungeon:' in result['error'], 'Lua error propagation')
        else:
            equal(result, dict(name=name(requested), ok=True, metadata=metadata(requested)), 'Lua metadata result')
    return {k: v for k, v in p.items() if k not in ('backend', 'events')} | {'events': normalized}


def validate_snapshots(receipts):
    need(type(receipts) is list and len(receipts) == 3, 'requires exactly three frames')
    need(all(type(r) is dict and type(r.get('stageIndex')) is int for r in receipts), 'frame ordinal type')
    by_phase = {r.get('stageIndex'): r for r in receipts}
    need(set(by_phase) == {0, 1, 2}, 'missing/duplicate frame phase')
    validate(by_phase[0])
    backend = by_phase[0]['lruProof']['backend']
    previous = []
    for phase in range(3):
        receipt = by_phase[phase]
        validate(receipt)
        equal(receipt['lruProof']['backend'], backend, 'backend switched within sequence')
        events = receipt['lruProof']['events']
        equal(events[:len(previous)], previous, 'observed history/counters rewritten across frames')
        previous = events
    return True


def visible(frame, receipt):
    validate(receipt)
    camera = receipt.get('cameraPosition')
    need(type(camera) is list and len(camera) == 2
         and all(type(v) in (int, float) for v in camera) and camera == [64, 48], 'camera position')
    need(type(receipt.get('cameraPixelRatio')) in (int, float) and receipt['cameraPixelRatio'] == 2, 'camera ratio')
    need(frame.width >= 200 and frame.height >= 200, 'viewport')
    x, y = frame.width//2, frame.height//2
    color = tuple(receipt['lruProof']['visual']['color'])
    crop = frame.crop((x-32, y-32, x+32, y+32)).convert('RGBA')
    need(crop.tobytes() == bytes(color)*64*64, 'visible WorldPainter metadata/phase color or geometry')
    label = frame.crop((x-100, y-100, x+200, y-40)).convert('RGBA')
    need(list(label.getdata()).count((255, 255, 255, 255)) >= 8, 'normal Font label missing')


def validate_sequence(frames, scene_fields=()):
    need(type(frames) is dict and set(frames) == set(STAGES), 'frame membership/count')
    receipts = [frames[s]['receipt'] for s in STAGES]
    validate_snapshots(receipts)
    for phase, r in enumerate(receipts):
        equal(r.get('stage'), STAGES[phase], 'frame stage')
        equal(r.get('action'), ACTIONS[phase], 'world action')
        equal(r.get('occluderPresent'), phase == 1, 'world occluder state')
        occupied = r.get('observedOccluderMaterial') == r.get('materialId')
        equal(occupied, phase == 1, 'world material observation')
    before, after = receipts[0], receipts[2]
    stable = set(scene_fields) - {'stageIndex', 'action', 'occluderPresent'}
    need(all(same(before.get(field), after.get(field)) for field in stable), 'world restoration state drift')
    equal(before.get('worldState', {}).get('declared'), after.get('worldState', {}).get('declared'),
          'declared world restoration state drift')
    # These three images MUST differ: the restored world carries later cache
    # state, unlike old lighting fixtures whose restoration pixels stay exact.
    need(len({frames[s]['pixelsSha256'] for s in STAGES}) == 3, 'phase images did not change')
