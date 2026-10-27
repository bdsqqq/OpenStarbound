#!/usr/bin/env python3
"""Finite LRU evidence composition, without acquisition or child processes.

Historical semantic replays are NOT rerun as fresh identity attestations. The
resolver rechecks exact bytes and archive membership; selected retained captures
also receive direct Python semantic/image/PID checks. --compose is the only
writing mode. Normal verification and all falsifying controls are read-only.
"""
import argparse
import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
OWN = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'build/migration-evidence-archive'
ROLES = ('reference', 'reference-repeat', 'candidate')
STAGES = ('lit-room', 'occluder-added', 'occluder-restored')
MANIFESTS = {
    '20261027-legacy-large-r1': 'c90981fd2ab20952fca0c9afacd44f295aa15557a823999d2d9659c4215a7a34',
    '20261027-behavior-inactive-r1': '6130523118c7e3d66e826a4f9ba57c6cefc05c62b39338e6114989a98f5b98d2',
    '20261027-historical-rest-r1': 'ebb82310ef1165309bd9437010e269dfff31aeb1a81db62101fa989f24673db6',
    '20261027-historical-residual-r1': '49213441525521a5c40b51454c6c13d51a9dcce5eb25940793a544dad5ebbd22',
}
REPORTS = {
    'parentStreams': ('build/lru-parent-semantic-r1/report.json', 'be0e067027bf27ec1b51b9796f8ffa1123b51edc162f7fa779a456025c3b5f68'),
    'parentPid': ('build/lru-parent-semantic-r1/pid-report.json', 'ecbc8504b12a902585b4f30682e2d5ae9f7ab18354929eb360c120f3cf3af483'),
    'parentCompiled': ('build/lru-parent-semantic-r1/compiled-closure.json', '64c7fd721c1a6c3c4cdff563c07e6630febbd0db0086adee4fa97698b059348f'),
    'old21': ('build/lru-old-scenes-r1/final-r1/report.json', '7d60b88727156f086621b7f4747e275cd4ef58b2fcefd8087ae255531ef995d8'),
    'oldInspection': ('build/lru-game-build-r1/legacy-parent-inspection-complete-r1.json', 'b4996cd9c6e07f15ddc10fa30d467c11395d95fffb69f136aac2b453ef2f3e15'),
    'lruProcess': ('build/lru-game-pid-r3/report.json', 'd4c599fb4a3892c734c9c9b313b30303787798d38395c2c2d1d3b6962e531b41'),
    'lru': ('build/behavior/lru-actual-r3/report.json', '8fff584822f292082d7adf74e8ab5d8653508d62cfac3dd172e28eab71280dfa'),
    'lruInspection': ('build/lru-game-pid-r3/inspection.json', 'f79b9d8d203dffc84d1654b7329a79d80afb8bf1d79f4b482f4a3d1d07f4e89d'),
    'auxiliary': ('build/lru-auxiliary-r1/replay/report.json', '477ab5f111a7ec58e99491428852192702954b246bd0b6a07d72675a0cbc1d35'),
    'buffer': ('build/lru-game-build-r1/buffer-gates-r1/report.json', 'e805a2728453d1875eee870c86a9aa13fb58f417600b777dbbcd04add18844cf'),
    'runtime': ('build/lru-production-runtime-r1/acquisition-4/report.typed', 'beec45da25fec2ed9e5e052dd5dfc4b8c498a425debffd2a275afa59899ab41c'),
    'host': ('build/lru-production-runtime-r1/host-supplement/report.typed', 'ed77703f18987bcd970e8790c0ab1d578d6314016c3252ad1aa842054930fe96'),
    'rust': ('build/lru-rust-parity-r1/report.typed', '6d0735ce0efe4e12dd1e2f861cdaac5fac85729106b697352e416bee4785c0ed'),
    'unwind': ('build/lru-boundary-unwind-r1/after-r3/report.typed', '0255083fcd72c4d42da8b0a13d30531e891874bcfadcbea225cf74ee6e12a23b'),
    'native': ('build/lru-cache-recovery-r4/report.json', 'cc628816f80e77ecc592ad386ead816564d5c191c83b1ddb428a9dc219156b61'),
    'rejectedR1': ('build/lru-final-qualification-r1/qualification.json', '3c129dc529c518335bd6d2aae42dddfdecfc0995b180a4ff49449d49f8dc947a'),
}
BINARIES = {'reference': '474bf23fe963e18b493263fb064e788c84c1b2f4432f0b96bec2b9122cbc8c6a', 'candidate': '053f787a5e03589b5b9dea25b37be8e823cedc2254136b0792cd32baebaa7263'}
LIMITS = [
    'finite darwin arm64 fixtures; not full 39-module migration, universal equivalence, other platforms, OOM, sanitizer or performance qualification',
    'compiled production remains 5074db1a; defaults OFF; C++ key/value/map/lifetime leaves remain explicit; Rust LRU control-flow proof is an accepted historical claim',
    'historical native/Rust/unwind/runtime/host/auxiliary semantic replays remain historical; exact reported artifact bytes rechecked, not historical inode/ctime/live-path seals',
    'old21 aggregate previously passed but executes native version probes and Zstd; it is NOT rerun or called subprocess-free',
    'Zstd semantic decoder result is historical; current PNG/metadata byte bindings and frame equality rechecked without a decoder process',
    'lighting original outer exit UNKNOWN; independently accepted inner game receipts and historical replay do not invent an outer exit',
    'original Zstd exit2, rejected final r1, cancelled final r2 and previous failed acquisitions remain failed/unaccepted',
    'literal WAV/16PCM/12 early-exit CLI; not Ogg, mixer, device, general audio, player/world/ship save interchange or Universe handshake',
    'local integrity, not signatures, reproducible builds, loaded-framework attestation, transient race absence or fresh OS process-group attestation',
    'source/catalog/recipe membership differences recorded explicitly; historical source closures are not rebound to current source',
]


def need(ok, why):
    if not ok:
        raise ValueError(why)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def guard(event, args):
    # Fail closed even if a future imported semantic helper starts executing tools.
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork', 'os.forkpty', 'os.exec', 'pty.spawn'}:
        raise ValueError('process creation forbidden by qualification verifier')


sys.addaudithook(guard)
sys.path.insert(0, str(ROOT / 'source/lab'))
import native_evidence_json as typed
sys.path.insert(0, str(ROOT / 'source/lab/behavior'))
import behavior_lab as lab
import lru_proof
import buffer_proof
from PIL import Image


class Resolver:
    """Only current regular bytes or EXACT pinned path/hash archive membership.

    SDK/tool aliases are recorded as requested path -> actual canonical regular
    file, not silently represented as fresh regular acquisition products.
    No restore, fallback search by hash, subprocess or missing-source waiver.
    """
    def __init__(self):
        self.index = {}
        self.checked = {}
        self.origins = {}
        self.compiled_closures = {}
        self.source_snapshot = None
        summary = json.loads((ARCHIVE / 'cleanup-summary.json').read_bytes())
        authority = {row['path']: row['sha256'] for row in summary['rows']}
        for run, expected in MANIFESTS.items():
            p = ARCHIVE / 'runs' / run / 'manifest.json'
            need(authority.get(str(p.relative_to(ROOT))) == expected, 'archive authority pin')
            raw = p.read_bytes()
            need(digest(raw) == expected, 'archive manifest pin')
            m = json.loads(raw)
            for row in m['entries']:
                path = str(ROOT / row['path'])
                need(path not in self.index, 'duplicate archive path membership')
                self.index[path] = dict(row, manifest=run)

    def archive_entry(self, path, expected):
        row = self.index.get(str(path))
        need(row is not None and row['sha256'] == expected, 'exact archive path/hash membership: ' + str(path))
        return row

    def pin(self, path, expected, data=False):
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        name = str(p)
        need(re.fullmatch('[0-9a-f]{64}', expected) is not None, 'invalid expected SHA256')
        if name in self.checked:
            need(self.checked[name] == expected, 'conflicting required byte pin: ' + name)
            if not data:
                return
        if p.exists():
            actual = p.resolve(strict=True)
            need(stat.S_ISREG(actual.stat().st_mode), 'actual regular input required: ' + name)
            h = hashlib.sha256(); size = 0; chunks = []
            with actual.open('rb') as stream:
                for b in iter(lambda: stream.read(1048576), b''):
                    h.update(b); size += len(b)
                    if data:
                        chunks.append(b)
            need(h.hexdigest() == expected, 'current byte integrity: ' + name)
            self.origins[name] = dict(kind='current-regular', canonical=str(actual), size=size, sha256=expected)
        else:
            need(not p.is_symlink(), 'dangling input alias: ' + name)
            row = self.archive_entry(name, expected)
            blob = ARCHIVE / 'blobs' / expected[:2] / (expected + '.gz')
            need(blob.resolve() == blob.absolute() and stat.S_ISREG(blob.stat().st_mode), 'regular archive blob')
            h = hashlib.sha256(); size = 0; chunks = []
            with gzip.open(blob, 'rb') as stream:
                for b in iter(lambda: stream.read(1048576), b''):
                    h.update(b); size += len(b)
                    if data:
                        chunks.append(b)
            need(h.hexdigest() == expected and size == row['size'], 'archive decompressed byte integrity: ' + name)
            self.origins[name] = dict(kind='pinned-gzip', manifest=row['manifest'], blob=str(blob.relative_to(ROOT)), size=size, sha256=expected)
        self.checked[name] = expected
        if data:
            return b''.join(chunks)

    def load(self, path, expected=None):
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        expected = expected or self.checked.get(str(p))
        need(expected is not None, 'unbound JSON read: ' + str(p))
        raw = self.pin(p, expected, data=True)
        value = json.loads(raw)
        return typed.loads(raw.decode('ascii')) if value.get('format') == 'star-native-evidence-v1' else value

    def merge(self, bindings):
        for path, value in sorted(bindings.items()):
            self.pin(path, value['sha256'] if isinstance(value, dict) else value)

    def fresh(self, path):
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        need(p.resolve() == p.absolute() and stat.S_ISREG(p.lstat().st_mode), 'regular unaliased product')
        h = file_hash(p)
        self.pin(p, h)
        return h


def process_binding(start, status, manifest, capture_id, game=None):
    need(type(start.get('pid')) is int and start['pid'] > 1 and type(start.get('pgid')) is int and type(status.get('pid')) is int and start['pid'] == start['pgid'] == status['pid'], 'actual game PID/PGID crossbinding')
    need(start['newSession'] is True and type(status['exitCode']) is int and status['exitCode'] == 0, 'actual game normal exit')
    need(start['argv'] == manifest['command'] and capture_id == manifest['captureId'], 'actual PID/capture/command binding')
    need(start['startedAt'] <= status['finishedAt'] and 0 <= status['elapsedSeconds'] <= 180, 'actual game time/deadline')
    if game is not None:
        need(start['pid'] == game['pid'] and start['startedAt'] == game['startedAt'] and status['finishedAt'] == game['finishedAt'], 'old21 game identity crossbinding')


def direct_frames(base, scene, role, resolver):
    """Reuse the frozen pure-Python oracles, except the native Zstd decoder.

    For Zstd only, keep accepted historical decoder semantics and independently
    check retained image/metadata/manifest/state bytes here. Never patch inflate.
    """
    directory = base / role / 'frames'
    manifest = resolver.load(directory / 'manifest.json')
    need(manifest['exitCode'] == 0 and manifest['schema'] == 1, 'capture normal manifest')
    source_role = 'candidate' if role == 'candidate' else 'reference'
    need(manifest['binary']['sha256'] == BINARIES[source_role], 'capture compiled binary')
    for key in ('binary', 'assets', 'bootconfig', 'configuration'):
        resolver.pin(manifest[key]['path'], manifest[key]['sha256'])
    proof = manifest['buildProvenance']
    need(proof['binary_sha256'] == BINARIES[source_role] and len(proof['source_files']) == 1499 and len(proof['compile_source_files']) == 472, 'compiled source/build identity')
    resolver.merge({str(ROOT / p): h for p, h in proof['source_files'].items()})
    resolver.merge(proof['compile_source_files'])
    if source_role not in resolver.compiled_closures:
        if resolver.source_snapshot is None:
            resolver.source_snapshot = lab.build_provenance.source_snapshot(ROOT)
        need(resolver.source_snapshot == proof['source_files'], 'exact compiled source membership')
        configured = lab.build_provenance._compile_source_inputs(Path(proof['build_dir']))
        need(configured == proof['compile_source_files'], 'exact configured source membership')
        sidecar = Path(proof['binary'] + '.behavior-build.json')
        resolver.fresh(sidecar)
        need(resolver.load(sidecar) == proof, 'physical binary source proof crossbinding')
        resolver.compiled_closures[source_role] = dict(sourceInputs=len(proof['source_files']), configuredInputs=len(configured), sourceMapSha256=digest(json.dumps(proof['source_files'], sort_keys=True).encode()), binarySha256=proof['binary_sha256'])
    selectors = {k: v for k, v in proof['build_identity']['cache'].items() if k.startswith('STAR_USE_RUST_')}
    need(len(selectors) == 26 and all(v == ('OFF' if source_role == 'reference' or k == 'STAR_USE_RUST_LINE_QUERY' else 'ON') for k, v in selectors.items()), '26 frozen production selectors')
    if scene != 'zstd-room':
        frames, reread = lab.validated(directory)
        need(reread == manifest, 'direct semantic manifest drift')
    else:
        frames = {}
        for stage, item in manifest['frames'].items():
            receipt = resolver.load(directory / (stage + '.json'))
            meta = receipt['metadata']
            png = resolver.pin(directory / (stage + '.png'), item['pngSha256'], data=True)
            with Image.open(io.BytesIO(png)) as image:
                pixels = image.convert('RGBA').tobytes(); dimensions = list(image.size)
            need(receipt['name'] == stage and meta['stage'] == stage and meta['scenario'] == scene and meta['inWorld'] is True, 'Zstd retained metadata stage')
            need(receipt['capture']['source'] == 'final-default-framebuffer' and receipt['capture']['stage'] == 'after-imgui-before-swap', 'Zstd final framebuffer')
            need(dimensions == item['dimensions'] and digest(pixels) == item['pixelsSha256'], 'Zstd retained decoded pixels')
            native = {field: meta[field] for field in lab.SCENE_FIELDS}
            meta = dict(meta, worldState={'declared': meta['worldState'], 'native': native})
            frames[stage] = dict(receipt=meta, pixelsSha256=digest(pixels), dimensions=dimensions, pngSha256=digest(png), receiptSha256=item['receiptSha256'])
        lab.validate_lighting_sequence(frames)
        need(lab.inventory(frames) == manifest['frames'], 'Zstd retained frame inventory')
    need(set(frames) == set(manifest['frames']) and len(frames) == 3, 'complete direct frame set')
    return frames, manifest


def verify_old21(report, inspection, resolver):
    need(report['behavioralPassed'] is True and report['strictSupervisoryComplete'] is False and report['supervisorStatusUnverifiedScenes'] == ['lighting-room'], 'historical old21 scope')
    need(report['counts'] == dict(candidateFrames=63, captureIds=63, comparisonEdges=42, historicalExactRgbaFrames=63, pngReceiptStagePairs=189, sceneMatrices=21), 'old21 counts')
    need([r['scene'] for r in report['rows']] == list(lab.SCENARIOS[:-1]), '21 frozen scenes')
    resolver.merge(report['bindings']); resolver.merge(inspection['bindings'])
    inspected = {(f['scene'], f['stage']): f for f in inspection['frames']}
    need(len(inspected) == len(inspection['frames']) == 63, 'old21 inspected coverage')
    captures = []; trees = set()
    # Receipts are looked up by their EXACT pinned path, not PID guessed filenames.
    starts = [(p, resolver.load(p)) for p in report['bindings'] if Path(p).name == 'started.json']
    for row in report['rows']:
        scene = row['scene']; stage = row['roles']['candidate']['frameNames'][0]
        base = Path(inspected[(scene, stage)]['original']).parents[2]
        values = {}; manifests = {}
        for role in ROLES:
            frames, manifest = direct_frames(base, scene, role, resolver)
            values[role] = frames; manifests[role] = manifest
            identity = row['roles'][role]; game = next(g for g in row['gameProcesses'] if g['role'] == role)
            need(file_hash(base / role / 'frames/manifest.json') == identity['manifestSha256'], 'old21 manifest pin')
            matches = [(p, s) for p, s in starts if s.get('argv') == manifest['command']]
            need(len(matches) == 1, 'exact old21 actual game receipt')
            p, start = matches[0]; status = resolver.load(Path(p).with_name('status.json'))
            process_binding(start, status, manifest, identity['captureId'], game)
            need(identity['pid'] == start['pid'] and identity['frameNames'] == sorted(frames), 'old21 role/PID/stage binding')
            captures.append(dict(scene=scene, role=role, captureId=manifest['captureId'], pid=start['pid'], startedAt=start['startedAt'], stages=sorted(frames), startedReceipt=p, statusReceipt=str(Path(p).with_name('status.json'))))
            trees.add(str(base / role))
        need(row['gameProcesses'][0]['finishedAt'] <= row['gameProcesses'][1]['startedAt'] and row['gameProcesses'][1]['finishedAt'] <= row['gameProcesses'][2]['startedAt'], 'old21 native repeat BEFORE Rust')
        for stage in values['reference']:
            a, b, c = (values[r][stage] for r in ROLES)
            need(a['pixelsSha256'] == b['pixelsSha256'] == c['pixelsSha256'], 'old21 exact pixel edge')
            need(a['receipt']['worldState'] == b['receipt']['worldState'] == c['receipt']['worldState'], 'old21 semantic edge')
            f = inspected[(scene, stage)]
            need(c['pngSha256'] == f['pngSha256'] and c['receiptSha256'] == f['receiptSha256'] and c['pixelsSha256'] == f['rgbaSha256'], 'old21 inspection/capture binding')
            oldpng = resolver.pin(f['historicalPng'], f['historicalPngSha256'], data=True)
            with Image.open(io.BytesIO(oldpng)) as image:
                need(digest(image.convert('RGBA').tobytes()) == c['pixelsSha256'] == f['historicalRgbaSha256'], 'old21 historical exact RGBA')
    return captures, trees


def verify_r3(report, inspection, producer, resolver):
    need(report['status'] == 'FRESH_LRU_THREE_ACTUAL_PID_RECEIPTS_PASS' and report['compiledRevision'] == '5074db1a' and report['originalR2WasNotRetagged'] is True, 'R3 accepted process scope')
    need(producer['passed'] is True and producer['parityCertified'] is False, 'R3 immutable producer inspection status')
    need(inspection['process_report_sha256'] == REPORTS['lruProcess'][1] and inspection['producer_report_sha256'] == REPORTS['lru'][1], 'R3 inspection report crossbinding')
    resolver.merge(report['frozenBindings']); resolver.merge(inspection['processBindings'])
    base = Path(report['output']); captures = []; framesets = {}
    need([g['role'] for g in report['games']] == list(ROLES), 'mandatory THREE R3 game receipts')
    need(len(inspection['frames']) == 9, 'R3 nine inspected frames')
    for row in report['games']:
        role = row['role']
        # These are mandatory even though a matching semantic manifest exists.
        for key in ('startedReceipt', 'statusReceipt'):
            resolver.fresh(row[key])
        start = resolver.load(row['startedReceipt']); status = resolver.load(row['statusReceipt'])
        need(start == row['start'] and status == row['status'], 'R3 actual receipt/report crossbinding')
        resolver.fresh(base / role / 'frames/manifest.json')
        for f in inspection['frames']:
            if f['role'] == role:
                resolver.pin(f['png'], f['png_sha256'])
                resolver.pin(Path(f['png']).with_suffix('.json'), f['receipt_sha256'])
        frames, manifest = direct_frames(base, 'lru-room', role, resolver)
        process_binding(start, status, manifest, row['captureId'])
        need(start['observerOnly'] is True and start['timeoutSeconds'] == 180, 'R3 nonmutating observer')
        for phase, stage in enumerate(STAGES):
            f = next(f for f in inspection['frames'] if f['role'] == role and f['stage'] == stage)
            need(f['phase'] == phase and f['operations'] == len(frames[stage]['receipt']['lruProof']['events']) == (22, 25, 27)[phase], 'R3 actual operation/inspection binding')
        framesets[role] = frames
        captures.append(dict(scene='lru-room', role=role, captureId=manifest['captureId'], pid=start['pid'], startedAt=start['startedAt'], stages=sorted(frames), startedReceipt=row['startedReceipt'], statusReceipt=row['statusReceipt']))
    a, b, c = report['games']
    need(a['status']['finishedAt'] <= b['start']['startedAt'] and b['status']['finishedAt'] <= c['start']['startedAt'], 'R3 native repeat BEFORE Rust')
    for stage in STAGES:
        a, b, c = (framesets[r][stage] for r in ROLES)
        need(a['pixelsSha256'] == b['pixelsSha256'] == c['pixelsSha256'], 'R3 exact pixel edge')
        need(a['receipt']['worldState'] == b['receipt']['worldState'] == c['receipt']['worldState'], 'R3 exact semantic edge')
    return captures, {str(base / role) for role in ROLES}, framesets


def historical_replays(rejected, resolver):
    """R1's rejection is retained; only its individual accepted replay receipts transfer."""
    accepted = {}
    for label in ('production', 'host', 'old21', 'auxiliary'):
        row = rejected['replays'][label]
        root = ROOT / 'build/lru-final-qualification-r1/commands' / label
        for name in ('started.json', 'status.json'):
            resolver.fresh(root / name)
        start = resolver.load(root / 'started.json'); status = resolver.load(root / 'status.json')
        need(start == row['start'] and status == row['status'], 'historical replay receipt binding')
        need(start['pid'] == start['pgid'] == status['pid'] and status['exitCode'] == 0 and status['timedOut'] is False and status['groupGone'] is True and status['reaped'] is True, 'historical replay exit')
        for name in ('stdout', 'stderr'):
            resolver.pin(root / name, status[name + 'Sha256'])
        accepted[label] = dict(historical=True, startReceipt=str(root / 'started.json'), statusReceipt=str(root / 'status.json'), stdoutSha256=status['stdoutSha256'], subprocessFree=False if label == 'old21' else 'not newly asserted')
    return accepted


def collect():
    r = Resolver()
    reports = {label: r.load(path, h) for label, (path, h) in REPORTS.items()}
    for label in ('parentStreams', 'parentPid'):
        r.merge(reports[label]['bindings'])
    for label in ('runtime', 'host'):
        r.merge(reports[label]['inputs']); r.merge(reports[label]['artifacts'])
    # Earlier source closures deliberately differ from production adoption. Only
    # their accepted historical claims + exact artifact bytes participate, not a
    # fictitious fresh replay against changed production headers.
    for label in ('rust', 'unwind', 'native'):
        r.merge(reports[label]['artifacts'])
    auxiliary_inputs = ROOT / 'build/lru-auxiliary-r1/r2/inputs.json'
    r.fresh(auxiliary_inputs); r.merge(r.load(auxiliary_inputs)['bindings'])
    r.merge(reports['buffer']['bindings'])
    replays = historical_replays(reports['rejectedR1'], r)
    captures, trees = verify_old21(reports['old21'], reports['oldInspection'], r)
    extra, more, framesets = verify_r3(reports['lruProcess'], reports['lruInspection'], reports['lru'], r)
    captures += extra; trees |= more
    need(len(captures) == len({c['captureId'] for c in captures}) == len({(c['pid'], c['startedAt']) for c in captures}) == 66, '66 actual game identities')
    buffer_values = []
    for role in ROLES:
        base = ROOT / 'build/behavior/lru-regression-r1-buffer-room' / role
        configuration = r.load(base / 'sbinit.config')
        for stage in STAGES:
            metadata = r.load(base / 'frames' / (stage + '.json'))['metadata']
            buffer_values.append(buffer_proof.validate(metadata))
            buffer_proof.bind(metadata, configuration)
    need(len(buffer_values) == 9 and all(v == buffer_values[0] for v in buffer_values), 'TCP/save/BTree exact normalized semantics')
    # Physical membership is frozen anew, never called a renewed old inode seal.
    trees |= {str(ROOT / 'build/lru-auxiliary-r1/r2'), str(ROOT / 'build/lru-game-pid-r3')}
    products = {}
    for tree in sorted(trees):
        for p in sorted(Path(tree).rglob('*')):
            s = p.lstat()
            need(not stat.S_ISLNK(s.st_mode), 'aliased selected product')
            if stat.S_ISDIR(s.st_mode):
                continue
            need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and p.resolve() == p.absolute(), 'regular unique selected product')
            products[str(p)] = r.fresh(p)
    # Verifier modules are separately pinned, including the unchanged model and
    # pure Python helper closure. They are not acquisition source substitutions.
    verifier_pins = {}
    for p in [*OWN.glob('*.py'), *sorted((ROOT / 'source/lab/behavior').glob('*.py')), ROOT / 'source/lab/native_evidence_json.py']:
        verifier_pins[str(p)] = r.fresh(p)
    disposition = ROOT / 'build/lru-final-qualification-r1/review-disposition.json'
    r.fresh(disposition)
    need(r.load(disposition)['status'] == 'NOT_ACCEPTED_PENDING_PROCESS_EVIDENCE_REPAIR', 'rejected r1 disposition')
    r2 = ROOT / 'build/lru-final-qualification-r2'
    for p in sorted(r2.rglob('*')):
        if p.is_file() and p.name != '.DS_Store':
            r.fresh(p)
    need(not (r2 / 'qualification.json').exists(), 'cancelled r2 cannot become accepted')
    # Do not mistake selective dependency membership for a whole-repository
    # inventory. Operational additions below were outside the frozen acquisition
    # input closure; the actual 1499-file game-source closure is checked above.
    operational = {}
    for p in [ROOT / 'scripts/cleanup-migration-artifacts.py', ROOT / 'scripts/test_cleanup_migration_artifacts.py', *sorted(OWN.glob('*.py'))]:
        operational[str(p)] = dict(currentSha256=r.fresh(p), presentInHistoricalRuntimeInputs=str(p) in reports['runtime']['inputs'], classification='post-freeze operational evidence/retention code; not compiled production')
    aux = reports['auxiliary']['acquisition']
    need(len(aux['cli']) == 12 and len(aux['pcm']) == 2 and aux['sourceRevision'] == '5074db1a', 'historical PCM/12CLI coverage')
    need([x['result']['receipts'][4] for x in aux['pcm']] == [0, 17] and all(x['wavBytes'] == 60 and x['pcmBytes'] == 16 for x in aux['pcm']), 'historical actual WAV/PCM conversion')
    need(reports['parentStreams']['status'] == 'DIRECT_PRODUCTION_STREAM_AND_FULL_LIFETIME_MODEL_RECHECK_PASS' and len(reports['parentStreams']['runs']) == 8 and reports['parentStreams']['trace_pairs'] == 8 and reports['parentStreams']['protocol_controls'] == 40, 'parent independent production semantic evidence')
    result = dict(
        status='FINITE_LRU_QUALIFIED_COMPOSED_HISTORICAL_AND_DIRECT_EVIDENCE',
        component='Star::LruCache', compiledRevision='5074db1a', binaryHashes=BINARIES,
        counts=dict(sceneMatrices=22, captureIds=66, selectedPngReceiptPairs=198, exactEdges=44, inspectedCandidateFrames=66, inspectedR3AllRoles=9, actualGameIdentities=66),
        captures=captures, reportPins={k: dict(path=p, sha256=h) for k, (p, h) in REPORTS.items()},
        historicalReplays=replays, directChecks=dict(nonZstdOldScenes=20, zstdPixelMetadataHistoricalDecode=True, lruOperations=[22,25,27], tcpSaveBtreeReceipts=9),
        historicalProofScope={k: dict(status=reports[k]['status'], mode='accepted historical semantics; exact reported artifact bytes rechecked; source identity seals NOT renewed') for k in ('rust','unwind','native','runtime','host','auxiliary')},
        originalLightingOuterExit='UNKNOWN', originalLightingOuterAccepted=False, originalZstdAttemptExit=2, originalZstdAttemptPassed=False, rejectedR1Accepted=False, cancelledR2Accepted=False,
        fullEngineComplete=False, universeHandshakeQualified=False, archiveManifestPins=MANIFESTS,
        physicalBindings=dict(sorted(r.origins.items())), productTrees=sorted(trees), products=products, verifierPins=verifier_pins,
        compiledClosures=resolver_closures(r), operationalSourceClosureAdditions=operational,
        sourceClosureDifferenceExplanation='compiled closure unchanged at 5074db1a; operational retention/verifier additions above were not in historical acquisition inputs. Catalog membership refresh belongs to parent and its bytes are not a compiled input. Historical pre-production Rust/unwind/native closures remain historical, not rebound; their exact report/artifact bytes are checked, not all historical input paths against changed production headers.',
        auxiliaryCounts=dict(cli=12, wavBytes=60, pcmBytes=16, samples=8, rustConversionCalls=17),
        limits=LIMITS)
    return result, r, reports, framesets


def controls(r, reports, framesets):
    results = []
    def reject(name, action, barrier):
        try:
            action()
        except (ValueError, lab.LabError) as error:
            need(barrier in str(error), 'wrong falsification barrier for ' + name + ': ' + str(error))
            results.append(dict(name=name, rejected=True, barrier=str(error)))
        else:
            raise AssertionError('known failure escaped: ' + name)
    row = reports['lruProcess']['games'][0]
    manifest = r.load(Path(reports['lruProcess']['output']) / 'reference/frames/manifest.json')
    process_binding(row['start'], row['status'], manifest, row['captureId'])
    badstart = copy.deepcopy(row['start']); badstatus = copy.deepcopy(row['status'])
    # Coherently change PID in BOTH receipts: the selected acquisition identity
    # still must match the independently bound report/manifest.
    badstart['pid'] += 1; badstart['pgid'] += 1; badstatus['pid'] += 1
    reject('coherent-PID-pair-wrong-old-identity', lambda: process_binding(badstart, badstatus, manifest, row['captureId'], dict(pid=row['start']['pid'], startedAt=row['start']['startedAt'], finishedAt=row['status']['finishedAt'])), 'game identity crossbinding')
    badmanifest = copy.deepcopy(manifest); badmanifest['captureId'] = 'coherently-wrong-capture'
    reject('wrong-capture-with-valid-command', lambda: process_binding(row['start'], row['status'], badmanifest, row['captureId']), 'PID/capture/command')
    meta = copy.deepcopy(framesets['candidate']['lit-room']['receipt'])
    lru_proof.validate(meta)
    meta['lruProof']['visual']['selected']['metadata'] = -1
    reject('semantic-metadata-not-top-hash', lambda: lru_proof.validate(meta), 'normal constructed metadata')
    frame = framesets['candidate']['lit-room']
    with Image.open(frame['png']) as image:
        image = image.convert('RGBA'); image.putpixel((image.width//2, image.height//2), (1,2,3,255))
        reject('decoded-LRU-marker-pixel', lambda: lru_proof.visible(image, frame['receipt']), 'visible WorldPainter')
    bp = r.load(ROOT / 'build/behavior/lru-regression-r1-buffer-room/candidate/frames/lit-room.json')['metadata']
    bad = copy.deepcopy(bp)
    for name in ('actualWireHex', 'expectedWireHex', 'sentWireHex'):
        bad['bufferProof']['network'][name] = '00' * 20
    reject('coherently-wrong-all-TCP-wire-copies', lambda: buffer_proof.validate(bad), 'actual sent/received bytes')
    # Resolver controls execute the real path->sha->gzip and source barriers.
    archived = next((p, row) for p, row in r.origins.items() if row['kind'] == 'pinned-gzip')
    p, entry = archived
    r.archive_entry(p, entry['sha256'])
    reject('archive-wrong-path-same-valid-blob', lambda: r.archive_entry(p + '.not-a-member', entry['sha256']), 'exact archive path/hash')
    reject('archive-right-path-wrong-hash', lambda: r.archive_entry(p, '0'*64), 'exact archive path/hash')
    source = str(ROOT / 'source/rust/ffi/src/lru_cache.rs')
    fresh_resolver = copy.copy(r)
    fresh_resolver.checked = {p: h for p, h in r.checked.items() if p != source}
    reject('source-actual-byte-barrier-not-summary', lambda: fresh_resolver.pin(source, '0'*64), 'current byte integrity')
    boolean_start = copy.deepcopy(row['start']); boolean_status = copy.deepcopy(row['status'])
    boolean_start.update(pid=True, pgid=True); boolean_status['pid'] = True
    reject('coherent-boolean-PID-copies', lambda: process_binding(boolean_start, boolean_status, manifest, row['captureId']), 'actual game PID/PGID')
    missing = copy.deepcopy(reports['lruProcess']); missing['games'].pop()
    reject('omitted-third-mandatory-R3-game', lambda: verify_r3(missing, reports['lruInspection'], reports['lru'], r), 'mandatory THREE')
    # The audit hook is tested by its handler, never by launching a child.
    reject('process-creation-guard', lambda: guard('subprocess.Popen', ()), 'process creation forbidden')
    return dict(positiveActualSemanticPidCaptureArchive=True, negativeControls=results)


def resolver_closures(resolver):
    return dict(sorted(resolver.compiled_closures.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--compose', type=Path)
    group.add_argument('--certificate', type=Path)
    parser.add_argument('--controls', action='store_true')
    args = parser.parse_args()
    result, resolver, reports, framesets = collect()
    if args.controls:
        result['controls'] = controls(resolver, reports, framesets)
    if args.compose:
        allowed = ROOT / 'build/lru-final-qualification-r3'
        need(args.compose.absolute().parent == allowed, 'composition writable scope')
        allowed.mkdir(parents=True, exist_ok=True)
        with args.compose.open('x') as f:
            json.dump(result, f, sort_keys=True, indent=2); f.write('\n')
        action = 'COMPOSED'
    else:
        expected = json.loads(args.certificate.read_bytes())
        need(result == expected, 'certificate differs from independently reconstructed evidence')
        action = 'VERIFIED_READ_ONLY'
    print(json.dumps(dict(action=action, status=result['status'], counts=result['counts'], physicalBindings=len(resolver.origins), selectedProducts=len(result['products']), archivedBindings=sum(v['kind']=='pinned-gzip' for v in resolver.origins.values()), controls=len(result.get('controls', {}).get('negativeControls', []))), sort_keys=True))


if __name__ == '__main__':
    main()
