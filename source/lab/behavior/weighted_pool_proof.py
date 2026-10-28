"""Source-derived normal treasure-route checks; logical fixtures are NOT game evidence.

TreasureDatabase descriptor deduplication is not WeightedPool.selectUniques.
Startup constructor/add calls are outside the per-phase counter bracket. Full
returned descriptor arrays (including unknown parameters) remain comparable.
"""
import re
from lru_proof import same, STAGES, ACTIONS

SELECTOR = 'STAR_USE_RUST_WEIGHTED_POOL'
CONSUMER = 'normal-root.createTreasure-TreasureDatabase-WeightedPool-ItemDatabase'
POOLS = ('behaviorWeightedRepeat', 'behaviorWeightedUnique', 'behaviorWeightedFiltered')
HEX64 = re.compile(r'[0-9a-f]{16}\Z')


def need(ok, message):
    if not ok:
        raise ValueError('WeightedPool ' + message)


def equal(a, b, message):
    need(same(a, b), message)


def counters(value):
    need(type(value) is list and len(value) == 19, 'counter mode extent')
    result = []
    for row in value:
        need(type(row) is list and len(row) == 4, 'counter stage extent')
        need(all(type(v) is str and HEX64.fullmatch(v) for v in row), 'canonical uint64 counters')
        result.append([int(v, 16) for v in row])
    return result


def descriptors(value, count):
    need(type(value) is list and len(value) == count, 'descriptor array count')
    for d in value:
        need(type(d) is dict, 'descriptor object')
        equal(d.get('name'), 'behaviorweightedtoken', 'descriptor name / fallback')
        equal(d.get('count'), 1, 'descriptor count')
        need(type(d.get('parameters')) is dict, 'descriptor parameters')
        equal(d['parameters'].get('tag'), 'kept', 'descriptor tag')
    # Do not drop/normalize extra fields: the observation retains them all.
    return value


def validate(receipt):
    p = receipt.get('weightedPoolProof')
    need(type(p) is dict and set(p) == set('version backend selector scopeThread phase countersBefore countersAfter visual consumer imageConsumer labelConsumer configuration'.split()), 'proof members')
    equal(p['version'], 1, 'version')
    need(p['backend'] in ('native', 'rust'), 'backend')
    equal(p['selector'], SELECTOR, 'selector')
    equal(p['scopeThread'], 'lua-calling-thread', 'counter thread')
    equal(p['consumer'], CONSUMER, 'consumer')
    equal(p['imageConsumer'], 'normal-Assets-WorldPainter', 'image consumer')
    equal(p['labelConsumer'], 'normal-Font-TextPainter', 'label consumer')
    need(type(p['configuration']) is dict and p['configuration'].get('scenario') == 'weighted-pool-room', 'configuration')
    phase = p['phase']
    need(type(phase) is int and phase in (0, 1, 2), 'phase')
    equal(receipt.get('stageIndex'), phase, 'capture phase')
    before, after = counters(p['countersBefore']), counters(p['countersAfter'])
    if p['backend'] == 'native':
        need(all(v == 0 for row in before + after for v in row), 'native OFF counters')
    else:
        calls, nonfiltered = ((3, 2) if phase == 1 else (4, 3))
        for mode, minimum in ((9, calls), (12, 3 * nonfiltered), (17, 3 * nonfiltered), (18, 3 * nonfiltered)):
            need((after[mode][0] - before[mode][0]) % 2**64 >= minimum, 'normal root minimum mode ' + str(mode))
    v = p['visual']
    need(type(v) is dict and set(v) == set('phase results selected selectedCount uniqueCount color label imagePath'.split()), 'visual members')
    equal(v['phase'], phase, 'Lua phase')
    results = v['results']
    schedule = [(POOLS[0], 2)] * (1 if phase == 1 else 2) + [(POOLS[1], 1), (POOLS[2], 0)]
    need(type(results) is list and len(results) == len(schedule), 'call schedule extent')
    for result, (pool, count) in zip(results, schedule):
        need(type(result) is dict and set(result) == {'pool', 'descriptors'}, 'result members')
        equal(result['pool'], pool, 'call schedule pool')
        descriptors(result['descriptors'], count)
    if phase != 1:
        equal(results[0]['descriptors'], results[1]['descriptors'], 'same-seed complete descriptors')
    selected = results[-2]['descriptors'] if phase == 1 else results[0]['descriptors']
    equal(v['selected'], selected, 'actual selected descriptors')
    selected_count = 1 if phase == 1 else 2
    equal(v['selectedCount'], selected_count, 'selected count')
    equal(v['uniqueCount'], 1, 'unique count')
    color = [selected_count * 70, 80, (phase + 1) * 70, 255]
    equal(v['color'], color, 'descriptor/phase color')
    equal(v['label'], f'Weighted {phase+1}/3 count={selected_count} tag=kept', 'Font label')
    equal(v['imagePath'], '/behaviorlab/weighted-white.png?multiply=' + bytes(color).hex(), 'Assets image')
    return p


def observation(receipt):
    p = validate(receipt)
    return {k: v for k, v in p.items() if k not in ('backend', 'countersBefore', 'countersAfter', 'configuration')}


def validate_snapshots(receipts):
    need(type(receipts) is list and len(receipts) == 3, 'three receipts required')
    first = validate(receipts[0])
    for phase, receipt in enumerate(receipts):
        p = validate(receipt)
        equal(p['phase'], phase, 'strict stage order')
        equal(p['backend'], first['backend'], 'backend switched')
        equal(p['configuration'], first['configuration'], 'configuration switched')
    # No invented full descriptor golden: compare all raw fields across phases.
    for index in (1, 2):
        equal(receipts[index]['weightedPoolProof']['visual']['results'][0]['descriptors'],
              first['visual']['results'][0]['descriptors'], 'cross-phase seeded repeat')
    return True


def visible(frame, receipt):
    p = validate(receipt)
    equal(receipt.get('cameraPosition'), [64, 48], 'camera position')
    equal(receipt.get('cameraPixelRatio'), 2, 'camera ratio')
    need(frame.width >= 200 and frame.height >= 200, 'viewport')
    x, y = frame.width // 2, frame.height // 2
    crop = frame.crop((x-32, y-32, x+32, y+32)).convert('RGBA')
    equal(crop.tobytes(), bytes(p['visual']['color']) * 64 * 64, 'WorldPainter pixels')
    label = frame.crop((x-100, y-100, x+200, y-40)).convert('RGBA')
    need(list(label.getdata()).count((255, 255, 255, 255)) >= 8, 'Font label absent')


def validate_sequence(frames, scene_fields=()):
    equal(set(frames), set(STAGES), 'frame names')
    receipts = [frames[s]['receipt'] for s in STAGES]
    validate_snapshots(receipts)
    for phase, receipt in enumerate(receipts):
        equal(receipt.get('stage'), STAGES[phase], 'stage')
        equal(receipt.get('action'), ACTIONS[phase], 'world action')
        equal(receipt.get('occluderPresent'), phase == 1, 'world occluder')
        equal(receipt.get('observedOccluderMaterial') == receipt.get('materialId'), phase == 1, 'world observed material')
    before, after = receipts[0], receipts[2]
    for field in set(scene_fields) - {'stageIndex', 'action', 'occluderPresent'}:
        equal(before.get(field), after.get(field), 'world restoration ' + field)
    equal(before.get('worldState', {}).get('declared'), after.get('worldState', {}).get('declared'), 'declared restoration')
    need(len({frames[s]['pixelsSha256'] for s in STAGES}) == 3, 'three discriminating images required')
