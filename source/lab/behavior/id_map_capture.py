"""scene25 producer; local argv receipts do not independently attest OS parent argv.

receives the new frontend instead of importing it, keeping its private frozen
runner and the original 24 capture paths independent.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid


def capture(lab, executable: Path, assets: Path, directory: Path, timeout: float,
            frontend_argv: list[str]) -> Path:
    runner = lab._legacy
    error = lab.LabError
    if (type(frontend_argv) is not list or not frontend_argv
            or not all(type(arg) is str and '\0' not in arg for arg in frontend_argv)
            or runner.canonical(Path(frontend_argv[0])) != Path(lab.__file__).resolve()):
        raise error('IdMap actual new frontend argv required')
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= 180):
        raise error('timeout must be finite and positive, at most 180 seconds')
    lab._capture_arguments(frontend_argv, executable, assets, directory, timeout)
    binary_id, asset_id = runner.identity(executable), runner.identity(assets)
    if not os.access(binary_id['path'], os.X_OK):
        raise error('capture executable is not executable')
    binary = Path(binary_id['path'])
    proof = lab.verified_build(binary)
    origin = lab._check_game_origin(binary, proof)
    frontend = dict(identities=lab._frontend_identity(), argv=list(frontend_argv))
    overlays = runner.overlay_identity(lab.SCENARIO)
    directory = runner.create_owned(directory)
    frames = directory / 'frames'
    manifest_path = frames / 'manifest.json'
    process = None
    try:
        home = runner.create_owned(directory / 'home')
        frames = runner.create_owned(frames)
        storage = runner.create_owned(frames / 'storage')
        for name in ('data', 'config', 'cache'):
            runner.create_owned(home / name)
        configuration = directory / 'scenario.json'
        bootconfig = directory / 'sbinit.config'
        runner.dump(configuration, dict(outputDirectory=str(frames), storageDirectory=str(storage),
                    scenario=lab.SCENARIO, maxFrames=1800, platformWrites=False))
        runner.dump(bootconfig, dict(assetDirectories=[], assetSources=[asset_id['path'],
                    *(str(runner.canonical(path)) for path in lab.asset_overlays(lab.SCENARIO).values())],
                    storageDirectory=str(storage), logDirectory=str(storage), includeUGC=False,
                    defaultConfiguration=dict(includeUGC=False, vsync=False, windowedResolution=[960, 540],
                        fullscreen=False, maximized=False, borderless=False, sfxVol=0, musicVol=0,
                        instrumentVol=0, clearUniverseFiles=False, clientIPJoinable=False,
                        clientP2PJoinable=False, serverAdvertise=False, serverIP='127.0.0.1')))
        environment = dict(os.environ)
        for key in ('SteamAppId', 'SteamGameId', 'STAR_BEHAVIOR_LAB'):
            environment.pop(key, None)
        environment.update(STAR_BEHAVIOR_LAB=str(configuration), HOME=str(home),
                           XDG_DATA_HOME=str(home / 'data'), XDG_CONFIG_HOME=str(home / 'config'),
                           XDG_CACHE_HOME=str(home / 'cache'))
        command = [binary_id['path'], '-bootconfig', str(bootconfig)]
        boot_id, configuration_id = runner.identity(bootconfig), runner.identity(configuration)
        launch = dict(binary=binary_id, assets=asset_id, buildProvenance=proof, gameOrigin=origin,
                      overlayFiles=overlays, bootconfig=boot_id, configuration=configuration_id,
                      command=command, timeoutSeconds=timeout, frontend=frontend)
        runner.durable_dump(directory / 'launch.json', launch)
        launch_id = runner.identity(directory / 'launch.json')
        started, wall_started = time.monotonic(), time.time()
        with (directory / 'process.log').open('xb') as log:
            previous_handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
            interrupted = None
            waiting = False

            def interrupt_capture(signum, frame):
                nonlocal interrupted
                interrupted = signal.Signals(signum).name
                # Defer both signals while Popen acquires ownership and while
                # reaping; repeated SIGINT must not abandon descendants.
                if waiting:
                    raise error('capture interrupted by ' + interrupted)

            for signum in previous_handlers:
                signal.signal(signum, interrupt_capture)
            try:
                process = subprocess.Popen(command, cwd=directory, env=environment, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                process_start = None
                try:
                    start_identity, group = runner.process_identity(process.pid)
                    if group != process.pid:
                        raise error('capture process is not its private group leader')
                    process_start = dict(schema=1, pid=process.pid, pgid=group, osStart=start_identity,
                        status='started', command=command, binary=binary_id, configuration=configuration_id,
                        launch=launch_id, wallStarted=wall_started)
                    runner.durable_dump(directory / 'process-start.json', process_start)
                    waiting = True
                    if interrupted:
                        raise error('capture interrupted by ' + interrupted)
                    code = process.wait(timeout=timeout)
                finally:
                    waiting = False
                    # also reap descendants after a normal leader exit; never signal by name.
                    try:
                        runner.stop_process_group(process)
                    finally:
                        if process_start is not None and process.poll() is not None:
                            runner.durable_dump(directory / 'process-exit.json', dict(schema=1,
                                pid=process.pid, pgid=process_start['pgid'], osStart=process_start['osStart'],
                                status='reaped', exitCode=process.returncode,
                                startReceipt=runner.identity(directory / 'process-start.json'),
                                wallFinished=time.time()))
                if interrupted:
                    raise error('capture interrupted by ' + interrupted)
            finally:
                for signum, handler in previous_handlers.items():
                    signal.signal(signum, handler)
        active_elapsed, wall_elapsed = time.monotonic() - started, time.time() - wall_started
        runner.validate_capture_clock(active_elapsed, wall_elapsed)
        if code:
            raise error(f'client exited {code}; inspect {directory / "process.log"}')
        if (runner.identity(executable) != binary_id or runner.identity(assets) != asset_id
                or runner.identity(bootconfig) != boot_id or runner.identity(configuration) != configuration_id
                or runner.identity(directory / 'launch.json') != launch_id):
            raise error('binary/assets/config/launch changed while client ran')
        if lab.verified_build(binary) != proof or lab._check_game_origin(binary, proof) != origin:
            raise error('build provenance/game origin changed while client ran')
        if lab._frontend_identity() != frontend['identities']:
            raise error('frontend inputs changed while client ran')
        if runner.overlay_identity(lab.SCENARIO) != overlays:
            raise error('asset overlay changed while client ran')
        captured = lab.captures(frames)
        lab._restoration(frames)
        if len(captured) != 3 or any(frame['receipt']['scenario'] != lab.SCENARIO for frame in captured.values()):
            raise error('captured scenario differs from requested three-stage scenario')
        semantic_boot = runner.load(bootconfig)
        for field in ('storageDirectory', 'logDirectory'):
            semantic_boot[field] = '<isolated-storage>'
        semantic_config = runner.load(configuration)
        semantic_config.update(outputDirectory='<isolated-output>', storageDirectory='<isolated-storage>')
        manifest = dict(schema=1, captureId=uuid.uuid4().hex, binary=binary_id, assets=asset_id,
            buildProvenance=proof, overlayFiles=overlays, semanticBootconfig=semantic_boot,
            semanticConfiguration=semantic_config, bootconfig=boot_id, configuration=configuration_id,
            command=command, exitCode=code, processStart=runner.identity(directory / 'process-start.json'),
            processExit=runner.identity(directory / 'process-exit.json'), elapsedSeconds=active_elapsed,
            frames=runner.inventory(captured))
        runner.dump(manifest_path, manifest)
        runner.dump(directory / lab.BINDING, lab._binding(frames, manifest, origin, launch))
        lab.validated(frames)
        return frames
    except BaseException as failure:
        # retain rejected bytes, but never leave a success-named manifest on abort.
        if manifest_path.exists():
            manifest_path.rename(directory / 'rejected-manifest.json')
        runner.durable_dump(directory / 'failure.json', dict(reason=str(failure),
            exception=type(failure).__name__, timeoutSeconds=timeout,
            pid=process.pid if process is not None else None, log=str(directory / 'process.log')))
        raise
