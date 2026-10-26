"""Finite File application receipt replay; never builds or acquires evidence.

prepare freezes expectations before observation; seal pins completed evidence;
replay requires the caller's seal digest. Neither preparation nor tests qualify
an application. Historical source bindings are deliberately never replayed.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
sys.dont_write_bytecode = True
import behavior_lab as lab
import build_provenance as provenance
import file_proof
import byte_array_proof
import io_device_proof
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'build/behavior'
OWN = BASE / 'file-qualification-tools-r1'
BUILD = BASE / 'file-combined-r1'
ARCHIVE = BUILD / 'candidate/cmake/rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a'
KERNEL = ROOT / 'build/file-rust/runner-worker-r1/cmake-production-r1/report.json'
RUNNER = ROOT / 'source/lab/file/production/runner.py'
ACTUAL = BASE / 'file-actual-report.json'
AUX = BASE / 'file-auxiliary-r1'
HISTORY = BASE / 'string-view-actual-report.json'
ACCEPTED = BASE / 'string-view-qualification-tools-r1/full-replay-r1/qualification.json'
ACCEPTED_SHA = '2b3143774f57a38b7b08c40b0349a7fe5b74e97f7ead0d657252d5c9305d5c6c'
ROLES = ('reference', 'reference-repeat', 'candidate')
REVISION = 'd3a1b6f5'
BYTE_ANCHORS = {**{i: (36,) for i in range(4)}, 4: (34,), 5: (34, 40), 6: (34, 40),
                7: (13,), 8: (34, 40), 9: (34, 40), 10: (13,), 11: (34, 40),
                12: (34, 40), 13: (6, 39, 41)}


def need(ok, message):
    if not ok:
        raise ValueError('File qualification: ' + message)


def keys(value, names):
    need(type(value) is dict and set(value) == set(names.split()), 'schema fields: ' + names)


def exact(value, expected, label):
    # Preserve scalar types inside embedded identities too, not only at the root.
    def same(a, b):
        if type(a) is not type(b):
            return False
        if type(a) is dict:
            return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
        if type(a) is list:
            return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        return a == b
    need(same(value, expected), label)


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda x: need(False, 'nonfinite JSON'))


def sha(path):
    with Path(path).open('rb') as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
        return h.hexdigest()


def digest(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'digest')
    return value


def path_domain(path, root):
    path, root = Path(path), Path(root).resolve()
    need(path.is_absolute() and path == path.resolve() and path.is_relative_to(root), 'path domain: ' + str(path))
    return path


def bind(path, bindings, expected=None):
    path = Path(path).resolve()
    value = sha(path)
    if expected is not None:
        need(value == digest(expected), 'binding drift: ' + str(path))
    need(str(path) not in bindings or bindings[str(path)] == value, 'changed during replay')
    bindings[str(path)] = value
    return value


def verify_bindings(pins, bindings):
    need(type(pins) is dict and bool(pins), 'missing bindings')
    for path, value in pins.items():
        need(type(path) is str and Path(path).is_absolute() and str(Path(path).resolve()) == path, 'binding path')
        bind(path, bindings, digest(value))


def write_new(path, data):
    path_domain(path, OWN)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write('\n')


def stages(scene):
    return ('ray-clear', 'ray-blocked', 'ray-restored') if scene == 'raycast-room' else ('lit-room', 'occluder-added', 'occluder-restored')


def matrix_root(scene):
    return BASE / ('file-actual-r1' if scene == 'buffer-room' else 'file-combined-' + scene + '-r1')


def rgba(path):
    with Image.open(path) as image:
        return list(image.size), hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest()


def historical(bindings):
    """Authenticate only accepted report/capture bytes, not old live source paths."""
    bind(ACCEPTED, bindings, ACCEPTED_SHA)
    accepted = load(ACCEPTED)
    exact(accepted['status'], 'FINITE_STRINGVIEW_APPLICATION_PASS', 'accepted history')
    pins = accepted['bindings']
    def old(path):
        need(str(path) in pins, 'historical binding missing: ' + str(path))
        bind(path, bindings, pins[str(path)])
        return load(path)
    report = old(HISTORY)
    exact(report['passed'], True, 'historical pass')
    exact(report['actualMatrices'], 20, 'historical count')
    rows = report['rows']
    need(len(rows) == 20 and {r['scene'] for r in rows} == set(lab.SCENARIOS), 'historical scenes')
    result = {}
    for row in rows:
        scene = row['scene']
        expected = BASE / ('string-view-actual-r1' if scene == 'stringview-room' else 'string-view-combined-' + scene + '-r1')
        exact(row['report'], str(expected / 'report.json'), 'historical role root')
        matrix = old(expected / 'report.json')
        exact(matrix['passed'], True, 'historical matrix')
        directory = expected / 'candidate/frames'
        manifest = old(directory / 'manifest.json')
        exact(matrix['comparison']['candidate'], str(directory), 'historical candidate role')
        need(matrix['comparison']['identities']['candidate'] == manifest, 'historical role association')
        need(set(manifest['frames']) == set(stages(scene)), 'historical stage inventory')
        frames = {}
        for index, name in enumerate(stages(scene)):
            png, receipt = directory / (name + '.png'), directory / (name + '.json')
            envelope = old(receipt)
            need(str(png) in pins, 'historical PNG missing binding')
            bind(png, bindings, pins[str(png)])
            exact(envelope['metadata']['scenario'], scene, 'historical scene association')
            exact(envelope['name'], name, 'historical sequence association')
            exact(envelope['metadata']['stage'], name, 'historical stage association')
            exact(envelope['metadata']['stageIndex'], index, 'historical stage ordinal')
            exact(envelope['metadata']['lightingBackend'], 'rust', 'historical candidate backend')
            exact(envelope['file'], name + '.png', 'historical PNG association')
            dimensions, pixels = rgba(png)
            entry = manifest['frames'][name]
            need(entry == dict(dimensions=dimensions, pngSha256=pins[str(png)],
                               receiptSha256=pins[str(receipt)], pixelsSha256=pixels), 'historical raw RGBA association')
            frames[name] = dict(entry, png=str(png), receipt=str(receipt))
        result[scene] = dict(root=str(expected), captureId=manifest['captureId'], frames=frames)
    return result


def independent_id(value, seen):
    need(type(value) is str and bool(value) and value not in seen, 'independent capture IDs')
    seen.add(value)


def frozen_tools(pins, bindings):
    need(set(pins) == {str(p.resolve()) for p in tool_paths()}, 'complete tool inventory')
    verify_bindings(pins, bindings)


def tool_paths():
    # Existing lab exclusion remains untouched; these are verifier inputs only.
    return sorted(set((ROOT / 'source/lab/behavior').glob('*.py')) |
                  set((ROOT / 'source/lab/file').rglob('*.py')) |
                  {Path(sys.executable).resolve(), AUX / 'replay.py', AUX / 'verify.py', AUX / 'test_tools.py'})


def prepare(output):
    bindings = {}
    history = historical(bindings)
    tools = {str(p.resolve()): sha(p) for p in tool_paths()}
    source = provenance.source_snapshot(ROOT)
    exact(len(source), 1492, 'game source inventory')
    data = dict(schema=1, status='PREPARED_NOT_APPLICATION_QUALIFIED', testedProduction=REVISION,
                history=history, historicalBindings=bindings, tools=tools, source=source,
                scenarios=sorted(lab.SCENARIOS), auxiliaryAPI='verify(freeze_path, acquisition_path)',
                auxiliaryVerifier=str(AUX / 'replay.py'))
    write_new(output, data)
    return sha(output)


def prepared(path, expected, bindings):
    bind(path, bindings, expected)
    data = load(path)
    keys(data, 'schema status testedProduction history historicalBindings tools source scenarios auxiliaryAPI auxiliaryVerifier')
    exact(data['schema'], 1, 'prepare schema')
    exact(data['status'], 'PREPARED_NOT_APPLICATION_QUALIFIED', 'prepare status')
    exact(data['testedProduction'], REVISION, 'production revision')
    exact(data['scenarios'], sorted(lab.SCENARIOS), 'scenario inventory')
    exact(data['auxiliaryAPI'], 'verify(freeze_path, acquisition_path)', 'auxiliary API')
    exact(data['auxiliaryVerifier'], str(AUX / 'replay.py'), 'auxiliary verifier domain')
    frozen_tools(data['tools'], bindings)
    exact(len(data['source']), 1492, 'source inventory')
    need(data['source'] == provenance.source_snapshot(ROOT), 'source snapshot drift')
    for rel, value in data['source'].items():
        bind(ROOT / rel, bindings, value)
    verify_bindings(data['historicalBindings'], bindings)
    need(historical(bindings) == data['history'], 'frozen historical expectations')
    return data


def validate_report(report, history):
    keys(report, 'passed actualMatrices historicalSequences testedProduction rows')
    exact(report['passed'], True, 'actual pass')
    exact(report['actualMatrices'], 20, 'actual matrix count')
    exact(report['historicalSequences'], 20, 'historical sequence count')
    exact(report['testedProduction'], REVISION, 'tested production')
    rows = report['rows']
    need(type(rows) is list and len(rows) == 20 and {r['scene'] for r in rows} == set(lab.SCENARIOS), 'exact twenty rows')
    for row in rows:
        keys(row, 'scene report previous frames')
        scene = row['scene']
        exact(row['report'], str(matrix_root(scene) / 'report.json'), 'actualRoot scene identity')
        exact(row['previous'], history[scene]['root'], 'historical root identity')
        wanted = [dict(name=name + '.png', dimensions=entry['dimensions'], decodedRgbaSha256=entry['pixelsSha256'])
                  for name, entry in sorted(history[scene]['frames'].items())]
        need(type(row['frames']) is list and sorted(row['frames'], key=lambda x: x['name']) == wanted, 'historical frame inventory')


def file_receipts(frames, scene, role):
    need(set(frames) == set(stages(scene)), 'exact three stages')
    wanted = 'rust' if role == 'candidate' else 'cpp'
    for index, name in enumerate(stages(scene)):
        receipt = frames[name]['receipt']
        exact(receipt['stage'], name, 'stage name')
        exact(receipt['stageIndex'], index, 'stage ordinal')
        exact(receipt['scenario'], scene, 'scene role')
        exact(receipt['lightingBackend'], wanted, 'lighting role backend')
        if scene != 'buffer-room':
            need('fileProof' not in receipt, 'File attribution outside five scopes')
            continue
        file_proof.validate(receipt)
        byte_array_proof.validate(receipt)
        io_device_proof.validate(receipt)
        for proof in (receipt['fileProof'], receipt['bufferProof'], receipt['bufferProof']['ioDevice'], receipt['bufferProof']['byteArray']):
            exact(proof['backend'], wanted, 'consumer role backend')
        if role == 'candidate':
            for index, modes in BYTE_ANCHORS.items():
                for mode in modes:
                    need(receipt['bufferProof']['byteArray']['scopes'][index]['calls']['success'][mode] > 0, 'ByteArray source mode')
        proof = receipt['fileProof']
        need(not any(proof['calls']['exception']), 'File exceptions in success scopes')
        for scope in proof['scopes']:
            need(not any(scope['calls']['exception']), 'File scope exception')
    if scene == 'buffer-room':
        file_proof.validate_snapshots([frames[name]['receipt']['fileProof'] for name in stages(scene)])
        for key in ('bufferProof',):
            snapshots = [frames[name]['receipt'][key] for name in stages(scene)]
            need(all(x == snapshots[0] for x in snapshots), 'frozen consumer counts')


def kernel_identity(report, archive_sha):
    exact(report['status'], 'FINITE_CURRENT_PRODUCTION_FILE_RUST_PASS', 'kernel status')
    exact(report['archive'], str(ARCHIVE), 'separate actual CMake archive path')
    exact(report['archive_sha256'], archive_sha, 'actual archive mismatch')
    exact(report['modes'], 34, 'kernel mode count')
    for group in ('bindings', 'artifacts'):
        need(type(report[group]) is dict and bool(report[group]), 'kernel missing bindings')


def builds(data, bindings):
    options = re.findall(r'^option\((STAR_USE_RUST_\w+) "[^"]+" (\w+)\)', (ROOT / 'source/CMakeLists.txt').read_text(), re.M)
    need(len(options) == 24 and len(dict(options)) == 24 and all(x == 'OFF' for _, x in options), '24 defaults OFF')
    result = {}
    for role in ('reference', 'candidate'):
        binary = BUILD / role / 'bin/starbound'
        proof = lab.verified_build(binary)
        need(proof['source_files'] == data['source'], 'build full source map')
        cache = proof['build_identity']['cache']
        for option, _ in options:
            exact(cache[option], 'ON' if role == 'candidate' and option != 'STAR_USE_RUST_LINE_QUERY' else 'OFF', 'selector ' + option)
        bind(binary, bindings, proof['binary_sha256'])
        bind(str(binary) + '.behavior-build.json', bindings)
        verify_bindings(proof['build_identity']['files'], bindings)
        need(bool(proof['build_identity']['tools']), 'build tools missing')
        for tool in proof['build_identity']['tools'].values():
            bind(tool['path'], bindings, tool['sha256'])
        ninja = BUILD / role / 'cmake/build.ninja'
        bind(ninja, bindings)
        lines = ninja.read_text().splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith('build ') and '/bin/starbound:' in line)
        link = next(line for line in lines[index:index + 18] if line.startswith('  LINK_LIBRARIES = '))
        archives = [token for token in link.split() if token.endswith('libstar_engine_ffi.a')]
        need(len(archives) == int(role == 'candidate'), 'sole linked aggregate')
        if archives:
            need((BUILD / role / 'cmake' / archives[0]).resolve() == ARCHIVE, 'linked actual archive')
        result[role] = proof
    return result


def strict_pair(report, root, role, manifests):
    exact(report['schema'], 1, 'pair schema')
    exact(report['passed'], True, 'partial pair')
    exact(report['errors'], [], 'pair errors')
    keys(report['gate'], 'maxError changedPixels')
    for value in report['gate'].values():
        exact(value, 0, 'zero tolerance')
    exact(report['reference'], str(root / 'reference/frames'), 'pair reference domain')
    exact(report['candidate'], str(root / role / 'frames'), 'pair candidate domain')
    exact(report['identities'], dict(reference=manifests['reference'], candidate=manifests[role]), 'pair inventory identity')
    need(set(report['frames']) == set(manifests[role]['frames']), 'partial pair stages')
    for row in report['frames'].values():
        exact(row['passed'], True, 'pair stage pass')
        exact(row['errors'], [], 'pair stage errors')
        for key in ('changedPixels', 'maxError'):
            exact(row[key], 0, 'exact pair pixels')


def matrix(scene, proofs, history, output, bindings, seen):
    root = matrix_root(scene)
    manifests = {}
    frames_by_role = {}
    for role in ROLES:
        directory = root / role / 'frames'
        path_domain(directory, root)
        frames, manifest = lab.validated(directory)
        file_receipts(frames, scene, role)
        for key, value in (('schema', 1), ('exitCode', 0)):
            exact(manifest[key], value, 'capture ' + key)
        cid = manifest['captureId']
        independent_id(cid, seen)
        expected = proofs['candidate' if role == 'candidate' else 'reference']
        exact(manifest['buildProvenance'], expected, 'capture source/binary identity')
        exact(manifest['binary'], lab.identity(Path(expected['binary'])), 'capture binary role')
        exact(manifest['overlayFiles'], lab.overlay_identity(scene), 'overlay inventory identity')
        for name, value in manifest['overlayFiles'].items():
            label, relative = name.split('/', 1)
            bind(lab.asset_overlays(scene)[label] / relative, bindings, value)
        for key in ('binary', 'assets', 'bootconfig', 'configuration'):
            item = manifest[key]
            exact(lab.identity(Path(item['path'])), item, 'capture input drift')
            if key in ('bootconfig', 'configuration'):
                exact(item['path'], str(root / role / ('sbinit.config' if key == 'bootconfig' else 'scenario.json')), 'capture input role domain')
            bind(item['path'], bindings, item['sha256'])
        for path in directory.iterdir():
            if path.is_file():
                bind(path, bindings)
        launch_path = root / role / 'launch.json'
        bind(launch_path, bindings)
        launch = load(launch_path)
        for key in ('binary', 'assets', 'bootconfig', 'configuration', 'buildProvenance', 'overlayFiles', 'command'):
            exact(launch[key], manifest[key], 'launch/capture identity: ' + key)
        need(manifest['command'] == [expected['binary'], '-bootconfig', str(root / role / 'sbinit.config')], 'capture literal argv')
        manifests[role], frames_by_role[role] = manifest, frames
    acquisition = load(root / 'report.json')
    exact(acquisition['passed'], True, 'partial matrix')
    bind(root / 'report.json', bindings)
    for role, key in (('reference-repeat', 'repeatability'), ('candidate', 'comparison')):
        saved = load(root / key / 'report.json')
        bind(root / key / 'report.json', bindings)
        exact(saved, acquisition[key], 'embedded pair mismatch')
        strict_pair(saved, root, role, manifests)
        rebuilt = lab.pair_compare(root / 'reference/frames', root / role / 'frames', output / key, same_backend=role == 'reference-repeat')
        strict_pair(rebuilt, root, role, manifests)
        exact(rebuilt, saved, 'pair replay mismatch')
    inspection_rows = []
    for name in stages(scene):
        current = frames_by_role['candidate'][name]
        old = history[scene]['frames'][name]
        need(current['dimensions'] == old['dimensions'] and current['pixelsSha256'] == old['pixelsSha256'], 'historical exact decoded RGBA')
        inspection_rows.append(dict(scene=scene, stage=name, captureId=manifests['candidate']['captureId'],
                                    png=str(root / 'candidate/frames' / (name + '.png')),
                                    pngSha256=current['pngSha256'], decodedRgbaSha256=current['pixelsSha256'],
                                    receiptSha256=current['receiptSha256'], dimensions=current['dimensions']))
    return inspection_rows


def inspection(report, expected):
    keys(report, 'schema inspectedBy allFramesViewed frames')
    exact(report['schema'], 1, 'inspection schema')
    exact(report['allFramesViewed'], True, 'inspection acknowledgment')
    need(type(report['inspectedBy']) is str and bool(report['inspectedBy'].strip()), 'inspection observer')
    need(type(report['frames']) is list and len(report['frames']) == 60, 'inspection sixty frames')
    exact(sorted(report['frames'], key=lambda x: (x['scene'], x['stage'])), sorted(expected, key=lambda x: (x['scene'], x['stage'])), 'inspection frame identity/hash')


def auxiliary(bindings, proofs, archive_sha):
    acquisition = AUX / 'acquisition-r1'
    freeze = AUX / 'freeze-r1/inputs.json'
    saved = load(acquisition / 'report.json')
    exact(saved['schema'], 1, 'auxiliary schema')
    exact(saved['status'], 'FINITE_CURRENT_FILE_PCM_AND_12_CLI_PASS', 'auxiliary status')
    exact(saved['sourceRevision'], REVISION, 'auxiliary production revision')
    need(saved['sourcearchive'] == dict(path=str(ARCHIVE), sha256=archive_sha), 'auxiliary archive')
    verify_bindings(saved['bindings'], bindings)
    script = AUX / 'replay.py'
    for path in (script, AUX / 'verify.py', freeze):
        need(str(path) in saved['bindings'], 'missing auxiliary verifier/freeze binding')
    need(saved['identity'] == dict(producer=sha(script), verifier=sha(AUX / 'verify.py')), 'auxiliary tool identity')
    for backend, role in (('cpp', 'reference'), ('rust', 'candidate')):
        proof = proofs[role]
        need(saved['bindings'].get(proof['binary']) == proof['binary_sha256'], 'auxiliary root binary')
        need(saved['buildsidecars'][backend] == proof, 'auxiliary build association')
        need(saved['sourceFiles'] == proof['source_files'], 'auxiliary full source map')
    need(len(saved['pcm']) == 2 and {r['backend'] for r in saved['pcm']} == {'cpp', 'rust'}, 'two PCM backends')
    names = {'help', 'help-with-error', 'unknown', 'missing', 'duplicate', 'end-markers'}
    need(len(saved['cli']) == 12 and {(r['backend'], r['case']) for r in saved['cli']} == {(b, n) for b in ('cpp', 'rust') for n in names}, 'twelve CLI cases')
    for row in saved['pcm']:
        for key, value in (('wavBytes', 60), ('pcmBytes', 16), ('conversionCalls', 17 if row['backend'] == 'rust' else 0)):
            exact(row[key], value, 'PCM ' + key)
    spec = importlib.util.spec_from_file_location('file_frozen_auxiliary', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rebuilt = module.verify(freeze, acquisition)
    # Preserve scalar types too: Python equality alone accepts bool/int aliases.
    need(json.dumps(rebuilt, sort_keys=True) == json.dumps(saved, sort_keys=True), 'auxiliary complete semantic replay')


def matrix_evidence_paths():
    """Pin acquired observations at seal time, not first during replay."""
    paths = set()
    for scene in lab.SCENARIOS:
        root = matrix_root(scene)
        paths.update(root / suffix for suffix in ('report.json', 'comparison/report.json', 'repeatability/report.json'))
        for role in ROLES:
            paths.update(root / role / suffix for suffix in ('launch.json', 'sbinit.config', 'scenario.json', 'process.log', 'frames/manifest.json'))
            for stage in stages(scene):
                paths.update(root / role / 'frames' / (stage + suffix) for suffix in ('.png', '.json'))
    return paths


def seal(preparation, preparation_sha, inspection_path, output):
    bindings = {}
    prepared(preparation, preparation_sha, bindings)
    # Fresh evidence can only be pinned after the parent acquires and inspects it.
    # This command does not bless its contents; replay performs every gate.
    for path in (*matrix_evidence_paths(), ACTUAL, KERNEL, ARCHIVE, AUX / 'acquisition-r1/report.json', AUX / 'freeze-r1/inputs.json', AUX / 'replay.py', AUX / 'verify.py', inspection_path):
        bind(path, bindings)
    data = dict(schema=1, status='SEALED_NOT_APPLICATION_QUALIFIED', preparation=str(preparation),
                preparationSha256=preparation_sha, inspection=str(inspection_path), bindings=bindings)
    write_new(output, data)
    return sha(output)


def replay(seal_path, seal_sha, output):
    path_domain(output, OWN)
    need(not output.exists(), 'fresh replay output required')
    bindings = {}
    bind(seal_path, bindings, seal_sha)
    sealed = load(seal_path)
    keys(sealed, 'schema status preparation preparationSha256 inspection bindings')
    exact(sealed['schema'], 1, 'seal schema')
    exact(sealed['status'], 'SEALED_NOT_APPLICATION_QUALIFIED', 'seal status')
    required = {str(p) for p in (ACTUAL, KERNEL, ARCHIVE, AUX / 'acquisition-r1/report.json', AUX / 'freeze-r1/inputs.json', AUX / 'replay.py', AUX / 'verify.py', Path(sealed['inspection']))}
    required.update(map(str, matrix_evidence_paths()))
    need(required <= set(sealed['bindings']), 'missing sealed evidence bindings')
    verify_bindings(sealed['bindings'], bindings)
    data = prepared(Path(sealed['preparation']), sealed['preparationSha256'], bindings)
    report = load(ACTUAL)
    validate_report(report, data['history'])
    archive_sha = bind(ARCHIVE, bindings)
    kernel = load(KERNEL)
    kernel_identity(kernel, archive_sha)
    # verify is the unmodified complete closure validator; NEVER run/acquire here.
    subprocess.run([sys.executable, '-B', str(RUNNER), 'verify', '--archive', str(ARCHIVE), '--output', str(KERNEL.parent)], cwd=ROOT, check=True)
    for group in ('bindings', 'artifacts'):
        verify_bindings(kernel[group], bindings)
    proofs = builds(data, bindings)
    rows, seen = [], set()
    for scene in data['scenarios']:
        rows.extend(matrix(scene, proofs, data['history'], output / scene, bindings, seen))
    inspection(load(sealed['inspection']), rows)
    auxiliary(bindings, proofs, archive_sha)
    verify_bindings(dict(bindings), {})
    result = dict(status='FINITE_FILE_APPLICATION_PASS', testedProduction=REVISION,
                  actualMatrices=20, pairReports=40, historicalSequences=20,
                  unchangedRgbaFrames=60, inspectedCandidateFrames=60,
                  actualArchiveSha256=archive_sha, bindings=bindings,
                  limits=['Finite local receipts only; no full-engine, OS deletion, audible mixer/Ogg, performance or universal ownership claim.',
                          'Inspection JSON records parent acknowledgment; software cannot prove a person looked.',
                          'Before/after hashes cannot detect transient edits reverted between observations.'])
    write_new(output / 'qualification.json', result)
    return sha(output / 'qualification.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('seal')
    p.add_argument('--preparation', type=Path, required=True); p.add_argument('--preparation-sha', required=True)
    p.add_argument('--inspection', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('replay')
    p.add_argument('--seal', type=Path, required=True); p.add_argument('--seal-sha', required=True); p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare': result = prepare(args.output)
    elif args.command == 'seal': result = seal(args.preparation, args.preparation_sha, args.inspection, args.output)
    else: result = replay(args.seal, args.seal_sha, args.output)
    print(result)


if __name__ == '__main__':
    main()
