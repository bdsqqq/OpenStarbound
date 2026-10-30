"""Current30 capture plumbing, NOT game qualification or allocation accounting.

The trusted controller writes only finite owned leaves. The actual command is
confined by the existing products SBPL; its PID is NOT the guardian's PGID.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

import static_vector_scenarios as scenarios

r = scenarios.runner
HERE = Path(__file__).resolve().parent
b = scenarios.load_source('_sv_capture_actor', HERE.parents[2] / 'scripts/build-static-vector-behavior-lab.py')
ad = b.ad
SCOPE = 'CURRENT30_CAPTURE_V2_NOT_GAME_QUALIFICATION'
VERSION = 'current30-capture-process-v2'
JSON_LIMIT = 64 * 1024**2
RECORD_LIMIT = 64 * 1024
ACTOR_LIMIT = 256 * 1024
PNG_LIMIT = 80 * 1024**2
LIMITS = dict(stdoutBytes=4 * 1024**2, stderrBytes=2 * 1024**2,
              readChunkBytes=65536, overflowBytes=65536)
STAGES = ('lit-room', 'occluder-added', 'occluder-restored')
CAPTURE_FILES = {'scenario.json', 'sbinit.config', 'launch.json', 'process-start.json',
                 'process-exit.json', 'failure.json', 'rejected-manifest.json',
                 'static-vector-binding.json', 'process.command.json', 'process.receipt.json',
                 'process.stdout', 'process.stderr', 'process.stdout-overflow.bin', 'process.stderr-overflow.bin'}


def need(condition, message):
    if not condition:
        raise r.LabError(message)


def physical(path):
    spelling = os.fspath(path)
    path = Path(path)
    need(spelling == str(path) and path.is_absolute() and '..' not in path.parts and str(path) == os.path.abspath(path),
         'canonical absolute physical path required')
    for member in (path, *path.parents):
        need(not member.is_symlink(), 'path alias refused')
        if member.exists():
            info = member.lstat()
            need(stat.S_ISDIR(info.st_mode) or (member == path and stat.S_ISREG(info.st_mode)
                 and info.st_nlink == 1), 'physical directory or single-link regular file required')
    need(path.resolve() == path, 'noncanonical physical path')
    return path


def location(path):
    path = physical(path)
    root = physical(ad.build_root()) / 'qualification'
    need(path.is_relative_to(root), 'capture publication must be in current products qualification')
    parts = path.relative_to(root).parts
    need(len(parts) >= 2 and parts[0] in scenarios.SCENARIOS, 'finite known scenario required')
    scenario, role = parts[:2]
    need(role in ('reference', 'repeat', 'candidate', 'compare'), 'finite capture/compare role required')
    return path, scenario, role, parts[2:]


def current():
    state = ad.enclosure_state()
    need(type(state) is dict and state.get('owner', {}).get('mount', {}).get('path') == str(ad.build_root()),
         'current owned enclosure required')
    return state


def capture_root(path, scenario=None, backend=None):
    path, scene, role, tail = location(path)
    need(not tail and role in ('reference', 'repeat', 'candidate'), 'exact capture root required')
    need(scenario is None or scenario == scene, 'output scenario mismatch')
    need(backend is None or backend == ('rust' if role == 'candidate' else 'native'), 'capture role/backend mismatch')
    return path


def compare_root(path, *, bundle=False):
    path, scene, role, tail = location(path)
    need(role == 'compare' and (not tail if bundle else tail in (('repeatability',), ('comparison',))),
         'exact finite compare bundle/subdirectory required')
    return path


def create_owned(path):
    current()  # This MUST precede mkdir, including creation of intermediate parents.
    path, scene, role, tail = location(path)
    allowed = {(), ('home',), ('home', 'data'), ('home', 'config'), ('home', 'cache'),
               ('home', 'tmp'), ('frames',), ('frames', 'storage')}
    need(tail in ( {(), ('repeatability',), ('comparison',)} if role == 'compare' else allowed),
         'undeclared owned directory')
    need(not os.path.lexists(path), 'fresh path consumed forever; refusing existing output')
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    ad.bounded.write_bytes(path / r.SENTINEL, b'behavior-lab-v1\n', 64)
    return path


def destination(path):
    current()
    path, scene, role, tail = location(path)
    if role == 'compare':
        need(len(tail) in (1, 2), 'finite compare output required')
        if len(tail) == 2:
            need(tail[0] in ('repeatability', 'comparison'), 'finite comparison kind')
        name = tail[-1]
        allowed = {'report.json'}
        if len(tail) == 2:
            allowed |= {s + '-' + k + '.png' for s in STAGES for k in ('expected', 'candidate', 'diff')}
        need(name in allowed, 'undeclared comparison file')
    else:
        need((len(tail) == 1 and tail[0] in CAPTURE_FILES)
             or tail == ('frames', 'manifest.json'), 'undeclared capture controller file')
    need(path.parent.is_dir(), 'owned parent required')
    sentinel = path.parent / r.SENTINEL
    need(read_bytes(sentinel, 64) == b'behavior-lab-v1\n', 'owned parent sentinel required')
    return path


def file_limit(path):
    name = Path(path).name
    if name in ('process.command.json', 'process.receipt.json'):
        return ACTOR_LIMIT
    if name in ('process-start.json', 'process-exit.json', 'failure.json'):
        return RECORD_LIMIT
    return JSON_LIMIT


def write_json(path, value):
    path = destination(path)
    return ad.bounded.write_json(path, value, file_limit(path))


def write_png(path, image):
    path = destination(path)
    need(image.width * image.height <= r.MAX_PIXELS, 'decoded PNG pixel bound')
    # Encoding RAM is intentionally not claimed bounded by this file-size cap.
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return ad.bounded.write_bytes(path, buffer.getvalue(), PNG_LIMIT)


def reject_manifest(frames):
    """Exclusive move of pinned, already-bounded data; never replace a failure."""
    source = destination(Path(frames) / 'manifest.json')
    before = source.lstat()
    read_bytes(source, JSON_LIMIT)
    checked = source.lstat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
    need(all(getattr(before, key) == getattr(checked, key) for key in fields),
         'rejected manifest changed before move')
    target = destination(source.parent.parent / 'rejected-manifest.json')
    # link+unlink is the no-replace move available through Python's POSIX API.
    # Both names are finite controller paths; the final retained file has nlink=1.
    os.link(source, target, follow_symlinks=False)
    for path in (source, target):
        after = path.lstat()
        need((after.st_dev, after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns, after.st_nlink)
             == (before.st_dev, before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns, 2),
             'rejected manifest physical identity changed')
    source.unlink()


def read_bytes(path, limit):
    path = physical(path)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 <= info.st_size <= limit,
         'bounded regular single-link file required')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
        descriptor = os.fstat(stream.fileno())
    after = path.lstat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    need(len(raw) == info.st_size and all(getattr(info, k) == getattr(after, k)
         == getattr(descriptor, k) for k in fields),
         'file changed while reading')
    return raw


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise r.LabError('nonfinite JSON constant')
    return json.loads(read_bytes(path, file_limit(path)), object_pairs_hook=unique, parse_constant=invalid)


def image(path):
    read_bytes(path, PNG_LIMIT)
    return r.image(path)


def preflight_frames(directory):
    physical(directory)
    for path in directory.iterdir():
        if path.suffix == '.json':
            load(path)
        elif path.suffix == '.png':
            read_bytes(path, PNG_LIMIT)


def sandbox(binary, boot):
    state = current()
    tool = ad.identity(ad.policy.TOOL)
    binding = ad.policy.binding(state['owner'], tool)
    argv = ad.policy.wrap(str(ad.build_root()), [str(binary), '-bootconfig', str(boot)])
    ad.policy.validate_command(str(ad.build_root()), argv)
    return argv, binding


def witness(launch):
    return dict(frontend=launch['frontend']['identities'], binary=launch['binary'],
                configuration=launch['configuration'], sourceClock=launch['sourceClock'],
                nativeSandbox=launch['nativeSandbox'])


def keys(value, names, message):
    need(type(value) is dict and set(value) == set(names.split()), message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_clock(directory, launch, manifest, start=None, end=None):
    from static_vector_capture import environment, validate_timeout
    validate_timeout(launch['timeoutSeconds'])
    need(ad.policy.same(launch.get('processProtocol'), dict(cwd=str(directory), stdin='DEVNULL',
         startNewSession=True, clock='monotonic+wall-v1', binding=VERSION)), 'capture process protocol v2 required')
    env = launch.get('environment')
    expected = environment(directory)
    # Permitted inherited values are pinned in actor command; isolated paths are rederived.
    from static_vector_capture import ENV_KEYS
    need(type(env) is dict and not set(env) - set(expected) - set(ENV_KEYS)
         and all(type(v) is str and '\0' not in v for v in env.values())
         and all(env.get(k) == v for k, v in expected.items() if k not in ENV_KEYS), 'sanitized isolated environment differs')
    clock = launch.get('sourceClock')
    keys(clock, 'monotonic wall', 'source clock keys')
    start = load(directory / 'process-start.json') if start is None else start
    end = load(directory / 'process-exit.json') if end is None else end
    values = [clock['monotonic'], clock['wall'], start.get('monotonicStarted'), start.get('wallStarted'),
              end.get('monotonicFinished'), end.get('wallFinished')]
    need(all(number(v) for v in values), 'invalid process/source clocks')
    need(clock['monotonic'] <= start['monotonicStarted'] <= end['monotonicFinished']
         and clock['wall'] <= start['wallStarted'] <= end['wallFinished'], 'process/source clock order')
    active = end['monotonicFinished'] - clock['monotonic']
    r.validate_capture_clock(active, end['wallFinished'] - clock['wall'])
    need(active <= launch['timeoutSeconds'] + 6 and type(manifest.get('elapsedSeconds')) in (int, float)
         and manifest['elapsedSeconds'] == active, 'timeout/elapsed receipt differs')


def validate_process_binding(frames, manifest):
    """Reparse private start+final wire, never project guardian PID into game PID."""
    parent = capture_root(Path(frames).parent)
    need(Path(frames) == parent / 'frames', 'exact capture frames required')
    need(manifest.get('processBinding') == VERSION, 'explicit current30 process binding v2 required')
    launch = load(parent / 'launch.json')
    keys(launch, 'binary assets buildProvenance gameOrigin overlayFiles bootconfig configuration command nativeSandbox timeoutSeconds frontend environment sourceClock processProtocol', 'launch schema')
    from behavior_lab_static_vector import _frontend_identity
    keys(launch['frontend'], 'identities argv', 'frontend source schema')
    need(ad.policy.same(launch['frontend']['identities'], _frontend_identity()), 'current frontend source identity differs')
    keys(manifest, 'schema processBinding captureId binary assets buildProvenance overlayFiles semanticBootconfig semanticConfiguration bootconfig configuration command exitCode processStart processExit elapsedSeconds' + (' frames' if 'frames' in manifest else ''), 'manifest schema')
    need(type(manifest['schema']) is int and manifest['schema'] == 1
         and type(manifest['exitCode']) is int and manifest['exitCode'] == 0, 'successful typed manifest required')
    start, end = load(parent / 'process-start.json'), load(parent / 'process-exit.json')
    command, receipt = load(parent / 'process.command.json'), load(parent / 'process.receipt.json')
    keys(start, 'schema pid pgid guardianPID osStart status binary configuration command launch sourceClock commandSource privateFrame wallStarted monotonicStarted', 'start v2 schema')
    keys(end, 'schema pid pgid guardianPID osStart status exitCode startReceipt actorReceipt sourceClock wallFinished monotonicFinished', 'end v2 schema')
    keys(command, 'argv launchArgv launcher guardianSchema statusBytes cwd environment phase outputLimits startedUTC inputsSha256 scope observer startSchema startAcknowledgment stdin', 'actor command schema')
    keys(receipt, 'argv launchArgv launcher command phase guardianStatus guardianStatusBytes guardianStatusEOF commandPID commandReaped guardianReturncode outputLimits streams outputComplete returncode elapsedSeconds failure cleanupFailure pid pgid reaped guardianReaped reapedScope finishedUTC scope commandStart startConsumed callbackCompleted startAcknowledged guardianProtocolHex commandStartFrameHex stdin', 'actor receipt schema')
    need(type(start['schema']) is int and start['schema'] == 2 and type(end['schema']) is int and end['schema'] == 2,
         'typed process schema2 required')
    pid, pgid = start['pid'], start['pgid']
    need(type(pid) is int and type(pgid) is int and 0 < pid < 2**31 and 0 < pgid < 2**31 and pid != pgid
         and type(start['guardianPID']) is int and start['guardianPID'] == pgid, 'actual PID differs from guardian PGID')
    need(type(start['osStart']) is str and bool(start['osStart']) and start['status'] == 'started'
         and end['status'] == 'reaped-by-owned-guardian' and type(end['exitCode']) is int and end['exitCode'] == 0,
         'actual birth and successful owned-command completion required')
    for key in ('pid', 'pgid', 'guardianPID', 'osStart', 'sourceClock'):
        need(ad.policy.same(end[key], start[key]), 'start/end identity differs: ' + key)
    for field, filename in (('processStart', 'process-start.json'), ('processExit', 'process-exit.json')):
        need(ad.policy.same(manifest.get(field), r.identity(parent / filename)), 'manifest process identity differs')
    need(ad.policy.same(end['startReceipt'], manifest['processStart'])
         and ad.policy.same(end['actorReceipt'], r.identity(parent / 'process.receipt.json'))
         and ad.policy.same(start['launch'], r.identity(parent / 'launch.json'))
         and ad.policy.same(start['commandSource'], r.identity(parent / 'process.command.json'))
         and ad.policy.same(receipt['command'], start['commandSource']), 'process controller identities differ')
    for key in ('binary', 'configuration', 'command'):
        need(ad.policy.same(start[key], manifest[key]) and ad.policy.same(launch[key], manifest[key]), 'launch/process/manifest ' + key)
    need(ad.policy.same(start['sourceClock'], launch['sourceClock']), 'process source clock differs')
    argv, binding = sandbox(Path(manifest['binary']['path']), parent / 'sbinit.config')
    need(ad.policy.same(launch.get('nativeSandbox'), binding) and launch['command'] == argv, 'current sandbox binding/argv differs')
    launcher = dict(python=b.identity(Path(sys.executable).resolve(strict=True)), guardian=b.identity(b.GUARDIAN))
    need(ad.policy.same(command['launcher'], launcher) and ad.policy.same(receipt['launcher'], launcher),
         'current actor launcher identity differs')
    need(command['guardianSchema'] == b.GUARDIAN_SCHEMA and type(command['statusBytes']) is int
         and command['statusBytes'] == b.STATUS_BYTES and command['observer'] == 'on_command_started'
         and command['startSchema'] == b.COMMAND_START_SCHEMA
         and command['startAcknowledgment'] == 'nonce-lf-eof-v1', 'private start protocol differs')
    need(command['scope'] == receipt['scope'] == SCOPE and command['stdin'] == receipt['stdin'] == 'DEVNULL', 'capture actor scope/stdin differs')
    need(command['argv'] == receipt['argv'] == argv and command['cwd'] == str(parent)
         and ad.policy.same(command['environment'], launch['environment'])
         and command['phase'] == receipt['phase'] == 'process'
         and ad.policy.same(command['outputLimits'], LIMITS) and ad.policy.same(receipt['outputLimits'], LIMITS), 'actor command/limits differ')
    expected_sha = hashlib.sha256(json.dumps(witness(launch), sort_keys=True).encode()).hexdigest()
    need(command['inputsSha256'] == expected_sha, 'actor source witness differs')
    args = command['launchArgv']
    need(type(args) is list and all(type(v) is str for v in args) and args == receipt['launchArgv']
         and len(args) == 15 + len(argv), 'private launcher argv shape')
    need(args[:4] == [launcher['python']['path'], '-B', str(b.GUARDIAN), '--status-fd']
         and args[5] == '--token' and re.fullmatch('[0-9a-f]{64}', args[6])
         and args[7:10] == ['--source-sha', launcher['guardian']['sha256'], '--environment-json']
         and args[11:13] == ['--notify-start', '--start-ack-fd'] and args[14:] == ['--', *argv], 'private launcher argv differs')
    # args has 15 prefix words (0..14); keep FD checks separate and exact.
    need(re.fullmatch('[0-9]+', args[4]) and re.fullmatch('[0-9]+', args[13])
         and str(int(args[4])) == args[4] and str(int(args[13])) == args[13]
         and 2 < int(args[4]) < 2**31 and 2 < int(args[13]) < 2**31
         and int(args[4]) != int(args[13]), 'distinct private status/ACK descriptors')
    need(args[10] == json.dumps(launch['environment'], sort_keys=True), 'private environment differs')
    token = args[6]
    wire_hex = receipt['guardianProtocolHex']
    need(type(wire_hex) is str and re.fullmatch('[0-9a-f]*', wire_hex) and len(wire_hex) <= 2*b.STATUS_BYTES, 'private wire hex bound')
    wire = bytes.fromhex(wire_hex)
    need(wire.count(b'\n') == 1, 'exact start LF plus final status required')
    first, final = wire.split(b'\n')
    frame = b.command_start_status(first, pgid, token, launcher['guardian']['sha256'])
    status = b.guardian_status(final, pgid, token, launcher['guardian']['sha256'])
    need(ad.policy.same(frame, receipt['commandStart']) and ad.policy.same(frame, start['privateFrame'])
         and receipt['commandStartFrameHex'] == first.hex() and ad.policy.same(status, receipt['guardianStatus'])
         and status['commandPID'] == frame['commandPID'] == pid, 'private actual command identity differs')
    need(type(receipt['guardianStatusBytes']) is int and receipt['guardianStatusBytes'] == len(wire), 'wire byte count differs')
    for field in ('guardianStatusEOF', 'commandReaped', 'outputComplete', 'reaped', 'guardianReaped',
                  'startConsumed', 'callbackCompleted', 'startAcknowledged'):
        need(receipt[field] is True, 'actual complete/ACK/reap evidence required: ' + field)
    need(status['commandReaped'] is True and type(status['returncode']) is int and status['returncode'] == 0
         and type(receipt['returncode']) is int and receipt['returncode'] == 0
         and type(receipt['guardianReturncode']) is int and receipt['guardianReturncode'] == -9
         and receipt['failure'] is None and receipt['cleanupFailure'] is None
         and receipt['reapedScope'] == 'DIRECT_GUARDIAN_ONLY', 'successful direct guardian completion required')
    need(type(receipt['commandPID']) is int and receipt['commandPID'] == pid
         and type(receipt['pid']) is int and type(receipt['pgid']) is int
         and receipt['pid'] == receipt['pgid'] == pgid, 'actor actual/guardian pid differs')
    keys(receipt['streams'], 'stdout stderr', 'exact raw streams')
    for name in ('stdout', 'stderr'):
        row = receipt['streams'][name]
        keys(row, 'bytesRead bytesWritten eof overflow', 'stream schema')
        need(type(row['bytesRead']) is int and type(row['bytesWritten']) is int
             and 0 <= row['bytesRead'] == row['bytesWritten'] <= LIMITS[name + 'Bytes']
             and row['eof'] is True and row['overflow'] is None, 'complete nonoverflow raw stream required')
        need(len(read_bytes(parent / ('process.' + name), LIMITS[name + 'Bytes'])) == row['bytesWritten'], 'raw stream byte count differs')
        need(not os.path.lexists(parent / ('process.' + name + '-overflow.bin')), 'overflow evidence cannot qualify')
    need(number(receipt['elapsedSeconds']), 'actor elapsed clock')
    times = []
    for value in (command['startedUTC'], receipt['finishedUTC']):
        need(type(value) is str, 'typed UTC actor clock')
        parsed = dt.datetime.fromisoformat(value)
        need(parsed.utcoffset() == dt.timedelta(0) and parsed.isoformat() == value, 'canonical UTC actor clock')
        times.append(parsed.timestamp())
    began, finished = times
    need(launch['sourceClock']['wall'] <= began <= start['wallStarted'] <= finished <= end['wallFinished'], 'actor wall clock binding')
    need(end['wallFinished'] - finished <= 6
         and receipt['elapsedSeconds'] <= end['monotonicFinished'] - launch['sourceClock']['monotonic'],
         'actor completion clock binding')
    r.validate_capture_clock(receipt['elapsedSeconds'], finished - began)
    validate_clock(parent, launch, manifest, start, end)
    return start, end
