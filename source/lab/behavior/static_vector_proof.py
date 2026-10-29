"""Independent scene26 receipt checks. Synthetic tests are not game evidence."""
import re

SCENARIO = 'static-vector-room'
SELECTOR = 'STAR_USE_RUST_STATIC_VECTOR'
ROUTE = 'WorldClient::render/tileEachTo/splitRect/StaticList/StaticVector'
STAGES = ('lit-room', 'occluder-added', 'occluder-restored')
EMPTY_MATERIAL = 65535  # source/game/StarMaterialTypes.hpp; tested against source.
U64 = (1 << 64) - 1
FIELDS = set(('version scenario stage backend selector frameSequence scopeId identityNotParity route worldSize '
              'clientWindow tileRange bufferTiles callsiteCalls splitCalls returnedRects splits countersBefore '
              'countersAfter tileMinPosition samples occluderColumns painterSubmitted configuration').split())


def need(ok, why):
    if not ok:
        raise ValueError(why)


def same_json(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(same_json(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(same_json(a, b) for a, b in zip(actual, expected))
    return actual == expected


def integer(value, minimum=0, maximum=U64):
    need(type(value) is int and minimum <= value <= maximum, 'bounded integer required')
    return value


def ints(value, size):
    need(type(value) is list and len(value) == size, 'integer tuple shape')
    for item in value:
        integer(item, -(1 << 31), (1 << 31) - 1)
    return value


def counters(value):
    need(type(value) is list and len(value) == 26, '26 counter modes required')
    result = []
    for mode in value:
        need(type(mode) is list and len(mode) == 2, 'two counter stages required')
        need(all(type(x) is str and re.fullmatch('[0-9a-f]{16}', x) for x in mode), 'canonical uint64 hex counter')
        result.append([int(x, 16) for x in mode])
    return result


def validate(receipt, *, stage, backend, configuration):
    integer(stage, 0, 2)
    need(backend in ('native', 'rust'), 'explicit backend required')
    need(type(configuration) is dict and configuration.get('scenario') == SCENARIO, 'trusted scenario configuration required')
    need(type(receipt) is dict and receipt.get('scenario') == SCENARIO and receipt.get('stage') == STAGES[stage]
         and type(receipt.get('stageIndex')) is int and receipt['stageIndex'] == stage, 'frame scenario/stage mismatch')
    p = receipt.get('staticVectorProof')
    need(type(p) is dict and set(p) == FIELDS, 'exact scene26 proof schema required')
    need(type(p['version']) is int and p['version'] == 1 and type(p['stage']) is int and p['stage'] == stage,
         'proof version/stage mismatch')
    need(p['scenario'] == SCENARIO and p['backend'] == backend and p['selector'] == SELECTOR and p['route'] == ROUTE,
         'actual route/backend/selector mismatch')
    need(same_json(p['configuration'], configuration), 'proof differs from admitted run configuration')
    seq = integer(p['frameSequence'], 1)
    need(type(p['scopeId']) is int and p['scopeId'] == seq, 'frame/scope association mismatch')
    identity = p['identityNotParity']
    need(type(identity) is dict and set(identity) == {'array', 'thread'}, 'exact native identity fields')
    need(type(identity['array']) is str and re.fullmatch('0x[0-9a-f]+', identity['array'])
         and int(identity['array'], 16) != 0, 'actual array identity required')
    need(type(identity['thread']) is str and re.fullmatch('[0-9]+', identity['thread']), 'calling thread identity required')
    need(ints(p['worldSize'], 2) == [128, 96] and ints(receipt.get('worldSize'), 2) == [128, 96], 'actual fixture world size')
    window, region = ints(p['clientWindow'], 4), ints(p['tileRange'], 4)
    buffer = integer(p['bufferTiles'], 0, 127)
    need(region == [window[0] - buffer, window[1] - buffer, window[2] + buffer, window[3] + buffer], 'actual padded window')
    x0, y0, x1, y1 = region
    width, height = x1 - x0, y1 - y0
    need(0 < width < 128 and height > 0 and -128 <= x0 and x1 <= 256 and x0 % 128 + width > 128,
         'actual capacity2 wrap route required')
    for field, expected in [('callsiteCalls', 1), ('splitCalls', 1), ('returnedRects', 2)]:
        need(type(p[field]) is int and p[field] == expected, 'exact scoped call count')
    start = x0 % 128
    offset = x0 - start
    expected_splits = [{'rect': [start, y0, 128, y1], 'xOffset': offset},
                       {'rect': [0, y0, start + width - 128, y1], 'xOffset': offset + 128}]
    need(type(p['splits']) is list and len(p['splits']) == 2, 'two actual split records required')
    for split in p['splits']:
        need(type(split) is dict and set(split) == {'rect', 'xOffset'}, 'exact split schema')
        ints(split['rect'], 4)
        integer(split['xOffset'], -(1 << 31), (1 << 31) - 1)
    need(p['splits'] == expected_splits, 'ordered actual split coverage/offset mismatch')
    need(ints(p['tileMinPosition'], 2) == [x0, y0] and p['occluderColumns'] == [126, 2], 'actual tile origin/owned columns')
    before, after = counters(p['countersBefore']), counters(p['countersAfter'])
    if backend == 'native':
        need(not any(x for rows in (before, after) for row in rows for x in row), 'native backend must record explicit zero counters')
    else:
        for mode, expected in [(0, 1), (13, 2), (19, 2)]:
            need((after[mode][0] - before[mode][0]) & U64 == expected, 'actual scoped constructor counter delta')
        need(all(after[m][1] == before[m][1] for m in range(26)), 'unexpected continuation in constructor scope')
    for field in ('lightingCompleted', 'inWorld', 'lightEntityReplicated', 'playerOutsideView', 'uiHidden'):
        need(receipt.get(field) is True, 'unsettled/incomplete ordinary frame')
    need(receipt.get('fullbright') is False and p['painterSubmitted'] is True, 'ordinary lit painter submission required')
    camera = receipt.get('cameraPosition')
    need(type(camera) is list and len(camera) == 2 and all(type(x) in (int, float) for x in camera)
         and camera[0] % 128 == 0 and camera[1] == 48 and receipt.get('cameraPixelRatio') == 2,
         'actual seam camera required')
    material = integer(receipt.get('materialId'), 0, 65533)
    need(receipt.get('material') == 'smoothmetal', 'actual seeded fixture material')
    need(type(p['samples']) is list and len(p['samples']) == 56, 'both columns and markers must be sampled')
    expected = {(x, y): (material if stage == 1 else EMPTY_MATERIAL)
                for x in (126, 2) for y in range(33, 60)}
    expected.update({(116, 48): EMPTY_MATERIAL, (12, 48): EMPTY_MATERIAL})
    seen = set()
    for sample in p['samples']:
        need(type(sample) is dict and set(sample) == {'world', 'renderIndex', 'worldForeground', 'worldBackground',
                                                     'renderedForeground', 'renderedBackground'}, 'exact tile sample schema')
        pos = tuple(ints(sample['world'], 2))
        need(pos in expected and pos not in seen, 'missing/duplicate/foreign tile sample')
        seen.add(pos)
        index = ints(sample['renderIndex'], 2)
        need(index == [(pos[0] - x0) % 128, pos[1] - y0] and 0 <= index[0] < width and 0 <= index[1] < height,
             'actual wrapped render index mismatch')
        for key in ('worldForeground', 'renderedForeground'):
            need(type(sample[key]) is int and sample[key] == expected[pos], 'actual foreground state mismatch')
        for key in ('worldBackground', 'renderedBackground'):
            need(type(sample[key]) is int and sample[key] == material, 'actual background state mismatch')
    need(seen == set(expected), 'both sides missing from real tile samples')
    return p


def observation(proof):
    # Only explicitly validated nondeterministic/diagnostic fields are excluded.
    omitted = {'backend', 'frameSequence', 'scopeId', 'identityNotParity', 'countersBefore', 'countersAfter', 'configuration'}
    return {key: value for key, value in proof.items() if key not in omitted}


def validate_sequence(receipts, restoration, *, backend, configuration, process_exit_code):
    need(type(process_exit_code) is int and process_exit_code == 0, 'successful owned process exit required')
    need(type(receipts) is list and len(receipts) == 3, 'three actual acknowledged states required')
    proofs = [validate(row, stage=i, backend=backend, configuration=configuration) for i, row in enumerate(receipts)]
    seq = [p['frameSequence'] for p in proofs]
    need(seq[0] < seq[1] < seq[2], 'stale/reused/nonmonotonic frame sequence')
    need(all(p['identityNotParity'] == proofs[0]['identityNotParity'] for p in proofs), 'calling thread/array identity changed')
    for key in ('worldSize', 'clientWindow', 'tileRange', 'bufferTiles', 'splits', 'tileMinPosition'):
        need(all(p[key] == proofs[0][key] for p in proofs), 'fixture viewport/split geometry drift')
    need(proofs[0]['samples'] == proofs[2]['samples'] and proofs[0]['samples'] != proofs[1]['samples'], 'actual add/remove tile restoration')
    expected = dict(version=1, scenario=SCENARIO, complete=True, ownedOccludersAbsent=True, occluderColumns=[126, 2],
                    yRange=[33, 59], observerDisarmed=True, lastStage=2, lastCapturedFrameSequence=seq[2], capture=STAGES[2])
    need(type(restoration) is dict and same_json(restoration, expected), 'acknowledged/disarmed authoritative restoration receipt required')
    ints(restoration['occluderColumns'], 2)
    ints(restoration['yRange'], 2)
    need(all(type(restoration[k]) is bool for k in ('complete', 'ownedOccludersAbsent', 'observerDisarmed'))
         and type(restoration['version']) is int and type(restoration['lastStage']) is int
         and type(restoration['lastCapturedFrameSequence']) is int, 'restoration scalar types')
    return [observation(p) for p in proofs]
