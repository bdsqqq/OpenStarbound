"""Finite normal-status consumer checks; synthetic fixtures are NOT game evidence.

Stat reads may be JSON int or float (Lua F64), but never bool. Exact binary
integer values require neither tolerance nor rounding. Category removal uses
native BaseMap::remove: this scene does not exercise IdMap.clear.
"""
import re
from lru_proof import same, STAGES, ACTIONS

SELECTOR = 'STAR_USE_RUST_ID_MAP'
CONSUMER = 'normal-status.addPersistentEffects-StatusController-StatCollection-StatSet-IdMap'
READS = ((8, 12, 16, 18), (2,), (34,))
VALUES = (18, 2, 34)
MINIMA = (2, 0, 1)
HEX64 = re.compile(r'[0-9a-f]{16}\Z')


def need(ok, message):
    if not ok:
        raise ValueError('IdMap ' + message)


def equal(actual, expected, message):
    need(same(actual, expected), message)


def members(value, names):
    need(type(value) is dict and set(value) == set(names.split()), 'members: ' + names)


def stat_value(actual, expected):
    need(type(actual) in (int, float) and actual == expected, 'exact stat readback')


def counters(value):
    need(type(value) is list and len(value) == 10, 'counter mode extent')
    result = []
    for row in value:
        need(type(row) is list and len(row) == 2, 'counter stage extent')
        need(all(type(v) is str and HEX64.fullmatch(v) for v in row), 'canonical uint64 counters')
        result.append([int(v, 16) for v in row])
    return result


def validate(receipt):
    need(type(receipt) is dict, 'receipt type')
    p = receipt.get('idMapProof')
    members(p, 'version backend selector scopeThread phase countersBefore countersAfter visual consumer imageConsumer labelConsumer configuration')
    equal(p['version'], 1, 'version')
    need(type(p['backend']) is str and p['backend'] in ('native', 'rust'), 'backend')
    equal(p['selector'], SELECTOR, 'selector')
    equal(p['scopeThread'], 'lua-calling-thread', 'counter thread')
    equal(p['consumer'], CONSUMER, 'consumer')
    equal(p['imageConsumer'], 'normal-Assets-WorldPainter', 'image consumer')
    equal(p['labelConsumer'], 'normal-Font-TextPainter', 'label consumer')
    # The parent owns the complete shared runner configuration, not this schema.
    need(type(p['configuration']) is dict and p['configuration'].get('scenario') == 'id-map-room', 'configuration')
    phase = p['phase']
    need(type(phase) is int and phase in (0, 1, 2), 'phase')
    equal(receipt.get('stageIndex'), phase, 'capture phase')
    before, after = counters(p['countersBefore']), counters(p['countersAfter'])
    if p['backend'] == 'native':
        need(all(v == 0 for row in before + after for v in row), 'native OFF counters')
    else:
        for mode in (2, 4):
            for stage in (0, 1):
                need((after[mode][stage] - before[mode][stage]) % 2**64 >= MINIMA[phase],
                     f'normal root/continue minimum mode {mode} stage {stage}')
    v = p['visual']
    members(v, 'phase observations value color label imagePath')
    equal(v['phase'], phase, 'Lua phase')
    reads = v['observations']
    need(type(reads) is list and len(reads) == len(READS[phase]), 'readback schedule extent')
    for actual, expected in zip(reads, READS[phase]):
        stat_value(actual, expected)
    stat_value(v['value'], VALUES[phase])
    color = [VALUES[phase] * 4, 40, (phase + 1) * 60, 255]
    equal(v['color'], color, 'stat/phase color')
    equal(v['label'], f'IdMap {phase+1}/3 stat={VALUES[phase]}', 'Font label')
    equal(v['imagePath'], '/behaviorlab/id-map-white.png?multiply=' + bytes(color).hex(), 'Assets image')
    return p


def observation(receipt):
    p = validate(receipt)
    return {k: v for k, v in p.items()
            if k not in ('backend', 'countersBefore', 'countersAfter', 'configuration')}


def validate_snapshots(receipts):
    need(type(receipts) is list and len(receipts) == 3, 'three receipts required')
    first = validate(receipts[0])
    for phase, receipt in enumerate(receipts):
        p = validate(receipt)
        equal(p['phase'], phase, 'strict stage order')
        equal(p['backend'], first['backend'], 'backend switched')
        equal(p['configuration'], first['configuration'], 'configuration switched')
    return True


def visible(frame, receipt):
    p = validate(receipt)
    camera = receipt.get('cameraPosition')
    need(type(camera) is list and len(camera) == 2
         and all(type(v) in (int, float) for v in camera) and camera == [64, 48], 'camera position')
    need(type(receipt.get('cameraPixelRatio')) in (int, float)
         and receipt['cameraPixelRatio'] == 2, 'camera ratio')
    need(frame.width >= 200 and frame.height >= 200, 'viewport')
    x, y = frame.width // 2, frame.height // 2
    crop = frame.crop((x-32, y-32, x+32, y+32)).convert('RGBA')
    equal(crop.tobytes(), bytes(p['visual']['color']) * 64 * 64, 'WorldPainter pixels')
    label = frame.crop((x-100, y-100, x+200, y-40)).convert('RGBA')
    need(list(label.getdata()).count((255, 255, 255, 255)) >= 8, 'Font label absent')


def validate_sequence(frames, scene_fields=()):
    need(type(frames) is dict, 'frame mapping')
    equal(set(frames), set(STAGES), 'frame names')
    need(all(type(f) is dict and 'receipt' in f and type(f.get('pixelsSha256')) is str
             for f in frames.values()), 'frame members')
    receipts = [frames[s]['receipt'] for s in STAGES]
    validate_snapshots(receipts)
    for phase, receipt in enumerate(receipts):
        equal(receipt.get('stage'), STAGES[phase], 'stage')
        equal(receipt.get('action'), ACTIONS[phase], 'world action')
        equal(receipt.get('occluderPresent'), phase == 1, 'world occluder')
        need(type(receipt.get('materialId')) is int
             and type(receipt.get('observedOccluderMaterial')) is int, 'world material types')
        equal(receipt['observedOccluderMaterial'] == receipt['materialId'], phase == 1, 'world observed material')
    before, after = receipts[0], receipts[2]
    for field in set(scene_fields) - {'stageIndex', 'action', 'occluderPresent'}:
        need(field in before and field in after, 'missing world restoration ' + field)
        equal(before[field], after[field], 'world restoration ' + field)
    need(type(before.get('worldState', {})) is dict and type(after.get('worldState', {})) is dict,
         'world state type')
    equal(before.get('worldState', {}).get('declared'), after.get('worldState', {}).get('declared'), 'declared restoration')
    need(len({frames[s]['pixelsSha256'] for s in STAGES}) == 3, 'three discriminating images required')
