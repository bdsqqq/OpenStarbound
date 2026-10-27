"""Frozen source-derived TTL replay. Logical fixtures are NOT actual-game evidence.

Time reads bracket the untouched native operation: cleanup must admit ONE cutoff
for every entry, not a different guessed clock per key. Only after full raw replay
may arbitrary initial keys, timestamps and worker interleavings be projected out.
"""
import re
from lru_proof import same, STAGES, ACTIONS

SELECTOR = 'STAR_USE_RUST_TTL_CACHE'
KEY = 'behavior-ttl-a'
MISSING = 'behavior-ttl-unknown'
ERROR = f"(TenantException) No such tenant named '{MISSING}'"
HEX = re.compile(r'(?:[0-9a-f]{2})*\Z')
META = dict(name=KEY, priority=17, colonyTagCriteria={'behavior-ttl-proof': 3},
            tenants=[], labIndex=17, labLiteral='normal-tenant-constructor')


def need(ok, message):
    if not ok:
        raise ValueError('TTL ' + message)


def equal(a, b, message):
    need(same(a, b), message)


def integer(value):
    need(type(value) is int and -(2**63) <= value < 2**63, 'signed integer')
    return value


def bytehex(value, size=None):
    need(type(value) is str and HEX.fullmatch(value) is not None, 'canonical hex')
    need(size is None or len(value) == size * 2, 'hex extent')
    return bytes.fromhex(value)


def counters(value):
    need(type(value) is dict and set(value) == {'get', 'cleanup'}, 'counter members')
    return {k: int.from_bytes(bytehex(v, 8), 'big') for k, v in value.items()}


def snapshot(value):
    need(type(value) is dict and set(value) == {'entries', 'ttl', 'smear', 'update', 'maxHex'}, 'snapshot members')
    equal(value['ttl'], 10000, 'default TTL changed')
    equal(value['smear'], 1000, 'default smear changed')
    equal(value['update'], True, 'refresh disabled')
    equal(value['maxHex'], 'ffffffffffffffff', 'capacity changed')
    entries = value['entries']
    need(type(entries) is list, 'entries')
    seen = set()
    for e in entries:
        need(type(e) is dict and set(e) == {'keyHex', 'stamp'}, 'entry members')
        bytehex(e['keyHex'])
        need(e['keyHex'] not in seen, 'duplicate entry')
        seen.add(e['keyHex'])
        integer(e['stamp'])
    return [dict(e) for e in entries]


def replay(events, backend):
    need(type(events) is list and events, 'raw history missing')
    previous = None
    expiry = []
    fg = []
    last_clock = None
    last_phase = 0
    for index, event in enumerate(events):
        need(type(event) is dict and set(event) == set('operation phase foreground keyHex before after clockBefore clockAfter countersBefore countersAfter producer errorHex index'.split()), 'event members')
        equal(event['index'], index, 'raw ordinal')
        need(type(event['phase']) is int and event['phase'] in (0, 1, 2), 'event phase')
        need(event['phase'] >= last_phase, 'raw phase history moved backward')
        last_phase = event['phase']
        need(type(event['foreground']) is bool, 'thread distinction')
        before, after = snapshot(event['before']), snapshot(event['after'])
        if previous is not None:
            equal(event['before'], previous, 'raw state history discontinuity')
        previous = event['after']
        lo, hi = integer(event['clockBefore']), integer(event['clockAfter'])
        need(lo <= hi and (last_clock is None or lo >= last_clock), 'clock order')
        last_clock = hi
        c0, c1 = counters(event['countersBefore']), counters(event['countersAfter'])
        operation = event['operation']
        need(operation in ('get', 'cleanup'), 'operation')
        if backend == 'native':
            need(all(v == 0 for v in (*c0.values(), *c1.values())), 'native OFF counters')
        else:
            # Global root counts can include unrelated cache users on other threads.
            need((c1[operation] - c0[operation]) % 2**64 >= 1, 'Rust root not entered')
        key = bytehex(event['keyHex'])
        if operation == 'cleanup':
            equal(key, b'', 'cleanup key')
            equal(event['producer'], None, 'cleanup producer')
            equal(event['errorHex'], None, 'cleanup error')
            # Native captures exactly ONE time for the entire removeWhere loop.
            survivors = {e['keyHex'] for e in after}
            need(survivors <= {e['keyHex'] for e in before}, 'cleanup inserted entry')
            cutoff_lo, cutoff_hi = lo, hi
            expected = []
            for e in before:
                boundary = e['stamp'] + 10000
                if e['keyHex'] in survivors:
                    cutoff_hi = min(cutoff_hi, boundary)
                    expected.append(e)
                else:
                    cutoff_lo = max(cutoff_lo, boundary + 1)
                    if e['keyHex'] == KEY.encode().hex() and lo > boundary:
                        expiry.append(dict(index=index, stamp=e['stamp'], clockBefore=lo))
            need(cutoff_lo <= cutoff_hi, 'strict cleanup expiry / common captured clock')
            equal(after, expected, 'cleanup modified retained stamp/order')
        else:
            need(event['foreground'], 'unexpected background tenant get (scope not proven)')
            need(key in (KEY.encode(), MISSING.encode()), 'unexpected tenant request')
            found = next((e for e in before if e['keyHex'] == event['keyHex']), None)
            produced = found is None
            producer = event['producer']
            equal(producer is not None, produced, 'wrong producer/hit')
            if produced:
                need(type(producer) is dict and set(producer) == {'state', 'clock'}, 'producer members')
                equal(producer['state'], event['before'], 'producer partial state')
                need(lo <= integer(producer['clock']) <= hi, 'producer clock')
            if key == MISSING.encode():
                need(produced, 'unknown key already cached')
                equal(bytehex(event['errorHex']), ERROR.encode(), 'native complete what message')
                equal(after, before, 'failed producer partial effects')
            else:
                equal(event['errorHex'], None, 'valid request failed')
                need(after and after[-1]['keyHex'] == event['keyHex'], 'get MRU/insertion')
                equal(after[:-1], [e for e in before if e['keyHex'] != event['keyHex']], 'get unrelated entry changed')
                stamp = after[-1]['stamp']
                earliest = producer['clock'] if producer is not None else lo
                need(earliest - 1000 <= stamp <= hi + 1000, 'native timestamp refresh bounds')
            fg.append(event)
    return fg, expiry


def validate(receipt):
    p = receipt.get('ttlProof')
    need(type(p) is dict and set(p) == set('version backend selector phase events visual deadline consumer imageConsumer labelConsumer configuration'.split()), 'proof members')
    equal(p['version'], 1, 'version')
    need(p['backend'] in ('native', 'rust'), 'backend')
    equal(p['selector'], SELECTOR, 'selector')
    equal(p['consumer'], 'normal-root.tenantConfig-TenantDatabase-Assets-Tenant', 'consumer')
    equal(p['imageConsumer'], 'normal-Assets-WorldPainter', 'image path')
    equal(p['labelConsumer'], 'normal-Font-TextPainter', 'Font path')
    need(type(p['configuration']) is dict and p['configuration'].get('scenario') == 'ttl-room', 'source/capture configuration')
    phase = p['phase']
    need(type(phase) is int and phase in (0, 1, 2), 'phase')
    equal(receipt.get('stageIndex'), phase, 'capture phase')
    fg, expiry = replay(p['events'], p['backend'])
    need(all(e['phase'] <= phase for e in p['events']), 'event ahead of capture stage')
    foreground_ops = [(e['phase'], e['operation'], bytehex(e['keyHex']).decode())
                      for e in p['events'] if e['foreground']]
    expected_ops = [(0, 'get', KEY), (0, 'get', KEY), (1, 'cleanup', ''),
                    (1, 'get', KEY), (2, 'get', MISSING), (2, 'get', KEY)]
    equal(foreground_ops, expected_ops[:(2, 4, 6)[phase]], 'all foreground operation schedule')
    expected = [(0, KEY), (0, KEY), (1, KEY), (2, MISSING), (2, KEY)][: (2, 3, 5)[phase]]
    equal([(e['phase'], bytehex(e['keyHex']).decode()) for e in fg], expected, 'foreground schedule')
    need(fg[1]['producer'] is None, 'phase-0 repeated access must hit')
    stamp0 = next(e['stamp'] for e in fg[1]['after']['entries'] if e['keyHex'] == KEY.encode().hex())
    equal(p['deadline'], stamp0 + 10001, 'actual observed expiry deadline')
    if phase >= 1:
        need(fg[2]['clockBefore'] >= p['deadline'], 'no actual expiry readiness')
        need(fg[2]['producer'] is not None, 'expired A not reconstructed')
        need(any(x['stamp'] == stamp0 and x['index'] < fg[2]['index'] for x in expiry), 'missing actual strict-expiry link')
        cleanups = [e for e in p['events'] if e['operation'] == 'cleanup' and e['foreground'] and e['phase'] == 1]
        need(len(cleanups) == 1 and cleanups[0]['clockBefore'] >= p['deadline'], 'normal foreground cleanup missing')
    visual = p['visual']
    need(type(visual) is dict and set(visual) == set('phase results selected continuation color label imagePath'.split()), 'visual members')
    equal(visual['phase'], phase, 'Lua phase')
    equal(visual['selected'], META, 'literal constructed Tenant metadata')
    equal(visual['continuation'], True, 'same Lua continuation')
    color = [136, 68, (phase + 1) * 80, 255]
    equal(visual['color'], color, 'metadata/phase color')
    equal(visual['label'], f'TTL {phase+1}/3 metadata=17 continue=ok', 'Font label')
    equal(visual['imagePath'], '/behaviorlab/ttl-white.png?multiply=' + bytes(color).hex(), 'Assets image')
    results = visual['results']
    expected_results = 2 if phase in (0, 2) else 1
    need(type(results) is list and len(results) == expected_results, 'Lua result count')
    for i, result in enumerate(results):
        if phase == 2 and i == 0:
            need(type(result) is dict and set(result) == {'name', 'ok', 'error'}, 'Lua failure members')
            equal(result['name'], MISSING, 'Lua unknown key')
            equal(result['ok'], False, 'pcall status')
            need(type(result['error']) is str, 'Lua diagnostics')
            first, newline, trace = result['error'].partition('\n')
            equal(first, ERROR, 'complete native/Lua first line')
            need(not newline or trace.startswith('Stack trace (most recent call first):\n'), 'Lua native diagnostic format')
        else:
            equal(result, dict(name=KEY, ok=True, metadata=META), 'normal tenantConfig result')
    return p


def observation(receipt):
    p = validate(receipt)
    visual = dict(p['visual'])
    visual['results'] = [dict(r, error=r['error'].partition('\n')[0]) if not r['ok'] else r for r in visual['results']]
    return dict(version=1, selector=SELECTOR, phase=p['phase'], visual=visual,
                consumer=p['consumer'], imageConsumer=p['imageConsumer'], labelConsumer=p['labelConsumer'],
                hitProven=True, expiryReproduced=p['phase'] >= 1, nativeErrorContinued=p['phase'] == 2)


def validate_snapshots(receipts):
    need(type(receipts) is list and len(receipts) == 3, 'three receipts required')
    previous = []
    backend = None
    for phase, receipt in enumerate(receipts):
        p = validate(receipt)
        equal(p['phase'], phase, 'frame ordering')
        if backend is not None:
            equal(p['backend'], backend, 'backend switched')
        backend = p['backend']
        equal(p['events'][:len(previous)], previous, 'raw history rewritten')
        previous = p['events']
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
    equal(before.get('worldState', {}).get('declared'), after.get('worldState', {}).get('declared'), 'declared world restoration')
    need(len({frames[s]['pixelsSha256'] for s in STAGES}) == 3, 'three discriminating images required')
