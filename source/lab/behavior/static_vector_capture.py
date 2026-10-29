"""Typed current30 producer; never impersonates an acquired frontend module."""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
import sys
from pathlib import Path
import signal
import subprocess
import time
import uuid

import static_vector_scenarios as scenarios

r = scenarios.runner
ENV_KEYS = ('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR', 'DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY')


@dataclass(frozen=True)
class CaptureRequest:
    executable: Path
    assets: Path
    directory: Path
    timeout: float
    scenario: str
    frontend_argv: tuple[str, ...]


@dataclass(frozen=True)
class ProducerIdentity:
    files: dict


def boot_configuration(scenario, assets, storage):
    scenarios.require(scenario)
    defaults = dict(includeUGC=False, vsync=False, windowedResolution=[960, 540], fullscreen=False,
        maximized=False, borderless=False, sfxVol=0, musicVol=0, instrumentVol=0, clearUniverseFiles=False,
        clientIPJoinable=False, clientP2PJoinable=False, serverAdvertise=False, serverIP='127.0.0.1')
    if scenario == 'option-parser-room':
        defaults['optionParserProof'] = r.option_parser_proof.CONFIGURATION
    if scenario in ('encoding-room', 'vlq-room', 'bytes-room', 'compression-room', 'zstd-room', 'path-embed-room'):
        defaults['safe'] = {'allowRemoteAssets': True}
    return dict(assetDirectories=[], assetSources=[str(assets),
                *(str(r.canonical(p)) for p in scenarios.asset_overlays(scenario).values())],
                storageDirectory=str(storage), logDirectory=str(storage), includeUGC=False,
                defaultConfiguration=defaults)


def semantic_configuration(config):
    return dict(config, outputDirectory='<isolated-output>', storageDirectory='<isolated-storage>')


def semantic_boot(boot):
    return dict(boot, storageDirectory='<isolated-storage>', logDirectory='<isolated-storage>')


def environment(directory):
    home = directory / 'home'
    result = {k: os.environ[k] for k in ENV_KEYS if k in os.environ}
    result.update(STAR_BEHAVIOR_LAB=str(directory / 'scenario.json'), HOME=str(home),
                  XDG_DATA_HOME=str(home / 'data'), XDG_CONFIG_HOME=str(home / 'config'), XDG_CACHE_HOME=str(home / 'cache'))
    return result


def validate_timeout(timeout):
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 180:
        raise r.LabError('finite timeout in (0,180] required')


def process_identity(pid):
    """Read the owned child's OS birth identity without spawning a probe process."""
    if sys.platform == 'darwin':
        import ctypes
        class BsdInfo(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint32) for name in
                        ('flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid', 'rgid', 'svuid', 'svgid', 'reserved')]
            _fields_ += [('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)]
            _fields_ += [(name, ctypes.c_uint32) for name in ('nfiles', 'pgid', 'pjobc', 'tdev', 'tpgid')]
            _fields_ += [('nice', ctypes.c_int32), ('startSeconds', ctypes.c_uint64), ('startMicroseconds', ctypes.c_uint64)]
        library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        library.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        library.proc_pidinfo.restype = ctypes.c_int
        info = BsdInfo()
        size = ctypes.sizeof(info)
        result = library.proc_pidinfo(pid, 3, 0, ctypes.byref(info), size)  # PROC_PIDTBSDINFO
        if result != size or info.pid != pid or info.startSeconds <= 0:
            raise r.LabError('owned child OS start identity unavailable')
        return f'darwin-proc-bsdinfo:{info.startSeconds}:{info.startMicroseconds}', info.pgid
    if sys.platform.startswith('linux'):
        stat = Path('/proc') / str(pid) / 'stat'
        fields = stat.read_text().rsplit(')', 1)[1].split()
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if not boot or not fields[19].isdigit():
            raise r.LabError('owned child OS start identity unavailable')
        return 'linux-proc-start:' + boot + ':' + fields[19], os.getpgid(pid)
    raise r.LabError('owned process birth reader unsupported on this platform')


def validate_launch_protocol(directory, launch, manifest):
    validate_timeout(launch['timeoutSeconds'])
    protocol = launch.get('processProtocol')
    if protocol != dict(cwd=str(directory), stdin='DEVNULL', startNewSession=True, clock='monotonic+wall-v1'):
        raise r.LabError('owned launch stdin/session/source-clock contract missing')
    env = launch.get('environment')
    expected = environment(directory)
    isolated = set(expected) - set(ENV_KEYS)
    if (type(env) is not dict or set(env) - set(ENV_KEYS) != isolated
            or any(env.get(k) != expected[k] for k in isolated)
            or any(type(v) is not str or '\0' in v for v in env.values())):
        raise r.LabError('sanitized isolated environment changed')
    start, end = r.load(directory / 'process-start.json'), r.load(directory / 'process-exit.json')
    clock = launch.get('sourceClock')
    if type(clock) is not dict or set(clock) != {'monotonic', 'wall'}:
        raise r.LabError('pre-Popen source clock required')
    values = [clock['monotonic'], clock['wall'], start.get('monotonicStarted'), start.get('wallStarted'),
              end.get('monotonicFinished'), end.get('wallFinished')]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        raise r.LabError('invalid actual source clock')
    if not (clock['monotonic'] <= start['monotonicStarted'] <= end['monotonicFinished']
            and clock['wall'] <= start['wallStarted'] <= end['wallFinished']):
        raise r.LabError('process/source clock order differs')
    active, wall = end['monotonicFinished'] - clock['monotonic'], end['wallFinished'] - clock['wall']
    r.validate_capture_clock(active, wall)
    if active > launch['timeoutSeconds'] + 6 or manifest.get('elapsedSeconds') != active:
        raise r.LabError('capture timeout/elapsed receipt differs')


def capture(request: CaptureRequest, producer: ProducerIdentity) -> Path:
    import behavior_lab_static_vector as frontend
    if not isinstance(request, CaptureRequest) or not isinstance(producer, ProducerIdentity):
        raise r.LabError('typed capture request/producer required')
    scenarios.require(request.scenario)
    validate_timeout(request.timeout)
    frontend._capture_arguments(list(request.frontend_argv), request.executable, request.assets,
                                request.directory, request.timeout, request.scenario)
    if producer.files != frontend._frontend_identity():
        raise r.LabError('actual producer/frontend identities differ')
    binary_id, asset_id = r.identity(request.executable), r.identity(request.assets)
    if not os.access(binary_id['path'], os.X_OK):
        raise r.LabError('capture binary not executable')
    binary = Path(binary_id['path'])
    proof = frontend.verified_build(binary)
    origin = frontend._check_game_origin(binary, proof)
    overlays = scenarios.overlay_identity(request.scenario)
    directory = r.create_owned(request.directory)
    frames, process = directory / 'frames', None
    manifest_path = frames / 'manifest.json'
    try:
        home = r.create_owned(directory / 'home')
        for name in ('data', 'config', 'cache'):
            r.create_owned(home / name)
        frames = r.create_owned(frames)
        storage = r.create_owned(frames / 'storage')
        config_path, boot_path = directory / 'scenario.json', directory / 'sbinit.config'
        config = dict(scenario=request.scenario, outputDirectory=str(frames), storageDirectory=str(storage),
                      maxFrames=1800, platformWrites=False)
        boot = boot_configuration(request.scenario, asset_id['path'], storage)
        r.dump(config_path, config)
        r.dump(boot_path, boot)
        boot_id, config_id = r.identity(boot_path), r.identity(config_path)
        command = [binary_id['path'], '-bootconfig', str(boot_path)]
        env = environment(directory)
        source_clock = dict(monotonic=time.monotonic(), wall=time.time())
        launch = dict(binary=binary_id, assets=asset_id, buildProvenance=proof, gameOrigin=origin,
            overlayFiles=overlays, bootconfig=boot_id, configuration=config_id, command=command,
            timeoutSeconds=request.timeout, frontend=dict(identities=producer.files, argv=list(request.frontend_argv)),
            environment=env, sourceClock=source_clock,
            processProtocol=dict(cwd=str(directory), stdin='DEVNULL', startNewSession=True, clock='monotonic+wall-v1'))
        r.durable_dump(directory / 'launch.json', launch)
        launch_id = r.identity(directory / 'launch.json')
        with (directory / 'process.log').open('xb') as log:
            handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
            interrupted, waiting = None, False

            def interrupt(signum, frame):
                nonlocal interrupted
                interrupted = signal.Signals(signum).name
                if waiting:
                    raise r.LabError('capture interrupted by ' + interrupted)

            for sig in handlers:
                signal.signal(sig, interrupt)
            try:
                process = subprocess.Popen(command, cwd=directory, env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                start = None
                try:
                    os_start, pgid = process_identity(process.pid)
                    if pgid != process.pid:
                        raise r.LabError('native child must own private process group')
                    start = dict(schema=1, pid=process.pid, pgid=pgid, osStart=os_start, status='started',
                        binary=binary_id, configuration=config_id, command=command, launch=launch_id,
                        wallStarted=time.time(), monotonicStarted=time.monotonic())
                    r.durable_dump(directory / 'process-start.json', start)
                    waiting = True
                    if interrupted:
                        raise r.LabError('capture interrupted by ' + interrupted)
                    remaining = request.timeout - (time.monotonic() - source_clock['monotonic'])
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, request.timeout)
                    code = process.wait(timeout=remaining)
                finally:
                    waiting = False
                    try:
                        r.stop_process_group(process)
                    finally:
                        if start is not None and process.poll() is not None:
                            end = dict(schema=1, pid=process.pid, pgid=start['pgid'], osStart=start['osStart'],
                                status='reaped', exitCode=process.returncode,
                                startReceipt=r.identity(directory / 'process-start.json'),
                                wallFinished=time.time(), monotonicFinished=time.monotonic())
                            r.durable_dump(directory / 'process-exit.json', end)
                if interrupted:
                    raise r.LabError('capture interrupted by ' + interrupted)
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
        if code != 0:
            raise r.LabError('native client exited ' + str(code) + '; inspect process.log')
        for path, before in ((request.executable, binary_id), (request.assets, asset_id), (config_path, config_id),
                             (boot_path, boot_id), (directory / 'launch.json', launch_id)):
            if r.identity(path) != before:
                raise r.LabError('capture input changed while client ran: ' + str(path))
        if (frontend.verified_build(binary) != proof or frontend._check_game_origin(binary, proof) != origin
                or frontend._frontend_identity() != producer.files or scenarios.overlay_identity(request.scenario) != overlays):
            raise r.LabError('source/frontend/origin/overlay changed while client ran')
        active = end['monotonicFinished'] - source_clock['monotonic']
        manifest = dict(schema=1, captureId=uuid.uuid4().hex, binary=binary_id, assets=asset_id,
            buildProvenance=proof, overlayFiles=overlays, semanticBootconfig=semantic_boot(boot),
            semanticConfiguration=semantic_configuration(config), bootconfig=boot_id, configuration=config_id,
            command=command, exitCode=code, processStart=r.identity(directory / 'process-start.json'),
            processExit=r.identity(directory / 'process-exit.json'), elapsedSeconds=active)
        # Process binding precedes sequence validation; no synthetic successful exit.
        r.validate_process_binding(frames, manifest)
        validate_launch_protocol(directory, launch, manifest)
        decoded = frontend.captures(frames, config, scenarios.backend(proof), code)
        scenarios.bind_old(decoded, request.scenario, proof, config)
        manifest['frames'] = r.inventory(decoded)
        r.dump(manifest_path, manifest)
        r.dump(directory / frontend.BINDING, frontend._binding(frames, manifest, origin, launch))
        frontend.validated(frames)
        return frames
    except BaseException as failure:
        if manifest_path.exists():
            manifest_path.rename(directory / 'rejected-manifest.json')
        r.durable_dump(directory / 'failure.json', dict(reason=str(failure), exception=type(failure).__name__,
            timeoutSeconds=request.timeout, pid=process.pid if process is not None else None,
            log=str(directory / 'process.log')))
        raise
