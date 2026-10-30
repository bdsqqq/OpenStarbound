"""SOURCE-only files and synthetic guardian wire. NO process/admission evidence."""
from contextlib import contextmanager, ExitStack
import copy
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

from PIL import Image
import static_vector_capture_protocol as q
import static_vector_capture as producer
import behavior_lab_static_vector as lab

G = q.ad.allocation_root()


@contextmanager
def namespace():
    G.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='capture-source-', dir=G) as temp, ExitStack() as stack:
        enclosure = Path(temp).resolve()
        products = enclosure / 'products'
        products.mkdir()
        owner = dict(root=str(enclosure), mount=dict(path=str(products), st_dev=products.stat().st_dev),
                     device='/dev/disk41', volumeDevice='/dev/disk41s1')
        original_identity = q.ad.identity
        def identity(path):
            if str(path) == q.ad.policy.TOOL:
                return dict(path=q.ad.policy.TOOL, sha256='a' * 64, size=123)
            return original_identity(path)
        stack.enter_context(mock.patch.object(q.ad, 'build_root', return_value=products))
        stack.enter_context(mock.patch.object(q.ad, 'enclosure_state', return_value={'owner': owner}))
        stack.enter_context(mock.patch.object(q.ad, 'identity', side_effect=identity))
        stack.enter_context(mock.patch.object(q.r, 'BUILD', products))
        stack.enter_context(mock.patch.object(lab, '_frontend_identity', return_value={'syntheticOnly': True}))
        stack.enter_context(mock.patch.object(lab, '_check_game_origin', return_value={
            'schema': 'static-vector-whole-game-origin-v1', 'syntheticOnly': True}))
        yield products


def fake_actor(argv, cwd, env, output, *, limits, validate, remaining_seconds, python,
               witness, write_record, check_output, scope, on_command_started, stdin):
    """Build the current exact record/wire, then notify before publishing completion."""
    assert stdin == producer.subprocess.DEVNULL and limits == q.LIMITS and scope == q.SCOPE
    actor_started = time.monotonic()
    remaining_seconds()
    validate()
    launcher = dict(python=q.b.identity(python), guardian=q.b.identity(q.b.GUARDIAN))
    token = 'b' * 64
    args = [str(python), '-B', str(q.b.GUARDIAN), '--status-fd', '14', '--token', token,
            '--source-sha', launcher['guardian']['sha256'], '--environment-json', json.dumps(env, sort_keys=True),
            '--notify-start', '--start-ack-fd', '15', '--', *argv]
    command = dict(argv=argv, launchArgv=args, launcher=launcher, guardianSchema=q.b.GUARDIAN_SCHEMA,
        statusBytes=q.b.STATUS_BYTES, cwd=str(cwd), environment=env, phase='process', outputLimits=limits,
        startedUTC=dt.datetime.now(dt.timezone.utc).isoformat(),
        inputsSha256=hashlib.sha256(json.dumps(witness, sort_keys=True).encode()).hexdigest(), scope=scope,
        observer='on_command_started', startSchema=q.b.COMMAND_START_SCHEMA,
        startAcknowledgment='nonce-lf-eof-v1', stdin='DEVNULL')
    write_record(output.with_suffix('.command.json'), command)
    start = dict(schema=q.b.COMMAND_START_SCHEMA, token=token, sourceSha256=launcher['guardian']['sha256'],
                 guardianPID=4242, guardianPGID=4242, guardianSID=4242, commandPID=4343)
    raw_start = json.dumps(start).encode()
    # The exact production parsers establish the synthetic frame's type contract.
    frame = q.b.command_start_status(raw_start, 4242, token, launcher['guardian']['sha256'])
    on_command_started(frame)
    status = dict(start, schema=q.b.GUARDIAN_SCHEMA, returncode=0, commandReaped=True, launchError=None)
    raw_end = json.dumps(status).encode()
    status = q.b.guardian_status(raw_end, 4242, token, launcher['guardian']['sha256'])
    wire = raw_start + b'\n' + raw_end
    for name in ('stdout', 'stderr'):
        path = check_output(output.with_suffix('.' + name))
        q.ad.bounded.write_bytes(path, b'', limits[name + 'Bytes'])
    receipt = dict(argv=argv, launchArgv=args, launcher=launcher,
        command=q.r.identity(output.with_suffix('.command.json')), phase='process', guardianStatus=status,
        guardianStatusBytes=len(wire), guardianStatusEOF=True, commandPID=4343, commandReaped=True,
        guardianReturncode=-9, outputLimits=limits,
        streams={name: dict(bytesRead=0, bytesWritten=0, eof=True, overflow=None) for name in ('stdout', 'stderr')},
        outputComplete=True, returncode=0, elapsedSeconds=time.monotonic() - actor_started, failure=None, cleanupFailure=None,
        pid=4242, pgid=4242, reaped=True, guardianReaped=True, reapedScope='DIRECT_GUARDIAN_ONLY',
        finishedUTC=dt.datetime.now(dt.timezone.utc).isoformat(), scope=scope, commandStart=start,
        startConsumed=True, callbackCompleted=True, startAcknowledged=True, guardianProtocolHex=wire.hex(),
        commandStartFrameHex=raw_start.hex(), stdin='DEVNULL')
    write_record(output.with_suffix('.receipt.json'), receipt)
    return receipt


def fixture_process(parent, launch):
    """Create a synthetic actual-child/guardian binding; does NOT launch anything."""
    q.write_json(parent / 'launch.json', launch)
    def started(frame):
        q.write_json(parent / 'process-start.json', dict(schema=2, pid=4343, pgid=4242, guardianPID=4242,
            osStart='darwin-proc-bsdinfo:1000:123', status='started', binary=launch['binary'],
            configuration=launch['configuration'], command=launch['command'], launch=q.r.identity(parent / 'launch.json'),
            sourceClock=launch['sourceClock'], commandSource=q.r.identity(parent / 'process.command.json'),
            privateFrame=frame, wallStarted=time.time(), monotonicStarted=time.monotonic()))
    fake_actor(launch['command'], parent, launch['environment'], parent / 'process', limits=q.LIMITS,
        validate=lambda: None, remaining_seconds=lambda: 180, python=Path(sys.executable).resolve(),
        witness=q.witness(launch), write_record=q.write_json, check_output=q.destination, scope=q.SCOPE,
        on_command_started=started, stdin=producer.subprocess.DEVNULL)
    start = q.load(parent / 'process-start.json')
    end = dict(schema=2, pid=4343, pgid=4242, guardianPID=4242, osStart=start['osStart'],
        status='reaped-by-owned-guardian', exitCode=0, startReceipt=q.r.identity(parent / 'process-start.json'),
        actorReceipt=q.r.identity(parent / 'process.receipt.json'), sourceClock=launch['sourceClock'],
        wallFinished=time.time(), monotonicFinished=time.monotonic())
    q.write_json(parent / 'process-exit.json', end)
    return end


class ProtocolTests(unittest.TestCase):
    def test_namespace_rejects_outside_arbitrary_backend_and_unowned_before_write(self):
        with namespace() as products:
            root = products / 'qualification' / lab.SCENARIO
            for path in (products / 'arbitrary', root / 'attempt2', products / 'qualification/unknown/reference'):
                with self.subTest(path=path), self.assertRaises(lab.LabError):
                    q.create_owned(path)
                self.assertFalse(path.exists())
            for role, backend in (('reference', 'rust'), ('repeat', 'rust'), ('candidate', 'native')):
                with self.assertRaisesRegex(lab.LabError, 'backend'):
                    q.capture_root(root / role, lab.SCENARIO, backend)
            with mock.patch.object(q.ad, 'enclosure_state', side_effect=ValueError('no owned mount')):
                with self.assertRaisesRegex(ValueError, 'no owned mount'):
                    q.create_owned(root / 'reference')
                self.assertFalse(root.exists())
            with self.assertRaises(lab.LabError):
                q.physical(Path(str(root / 'reference') + '/../candidate'))

    def test_bounded_png_exact_bytes_caps_partial_and_exclusive(self):
        with namespace() as products:
            root = products / 'qualification' / lab.SCENARIO / 'compare'
            q.create_owned(root)
            output = q.create_owned(root / 'comparison')
            frame = Image.new('RGBA', (2, 1), (1, 2, 3, 4))
            buffer = io.BytesIO()
            frame.save(buffer, format='PNG')
            path = output / 'lit-room-expected.png'
            q.write_png(path, frame)
            self.assertEqual(path.read_bytes(), buffer.getvalue())
            with self.assertRaises(ValueError):
                q.write_png(path, frame)
            overflow = output / 'lit-room-candidate.png'
            with mock.patch.object(q, 'PNG_LIMIT', 1), self.assertRaises(ValueError):
                q.write_png(overflow, frame)
            self.assertFalse(overflow.exists())
            # Raw input is checked before filesystem publication by write_bytes.
            self.assertFalse((output / ('.' + overflow.name + '.partial')).exists())
            with self.assertRaises(lab.LabError):
                q.write_png(output / 'arbitrary.png', frame)
            with mock.patch.object(q, 'JSON_LIMIT', 12), self.assertRaises(ValueError):
                q.write_json(output / 'report.json', {'wayTooLarge': 'x' * 30})
            self.assertTrue((output / '.report.json.partial').exists())
            self.assertFalse((output / 'report.json').exists())

    def test_single_link_bounded_unique_json_read_and_finite_sentinel(self):
        with namespace() as products:
            parent = q.create_owned(products / 'qualification' / lab.SCENARIO / 'reference')
            self.assertEqual((parent / q.r.SENTINEL).read_bytes(), b'behavior-lab-v1\n')
            with self.assertRaises(lab.LabError):
                q.create_owned(parent)
            for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
                path = parent / 'failure.json'
                path.write_bytes(raw)
                with self.assertRaises(lab.LabError):
                    q.load(path)
                path.unlink()
            original = parent / 'failure.json'
            original.write_text('{}')
            os.link(original, parent / 'hardlink')
            with self.assertRaises(lab.LabError):
                q.load(original)
            with self.assertRaises(lab.LabError):
                q.write_json(parent / 'not-declared.json', {})

    def test_rejected_manifest_exclusive_pinned_move_preserves_existing_data(self):
        with namespace() as products:
            parent = q.create_owned(products / 'qualification' / lab.SCENARIO / 'reference')
            frames = q.create_owned(parent / 'frames')
            q.write_json(frames / 'manifest.json', {'syntheticOnly': True})
            raw = (frames / 'manifest.json').read_bytes()
            q.write_json(parent / 'rejected-manifest.json', {'unrelatedExisting': True})
            existing = (parent / 'rejected-manifest.json').read_bytes()
            with self.assertRaises(FileExistsError):
                q.reject_manifest(frames)
            self.assertEqual((frames / 'manifest.json').read_bytes(), raw)
            self.assertEqual((parent / 'rejected-manifest.json').read_bytes(), existing)
        with namespace() as products:
            parent = q.create_owned(products / 'qualification' / lab.SCENARIO / 'reference')
            frames = q.create_owned(parent / 'frames')
            q.write_json(frames / 'manifest.json', {'syntheticOnly': True})
            before = (frames / 'manifest.json').stat()
            q.reject_manifest(frames)
            self.assertFalse((frames / 'manifest.json').exists())
            self.assertEqual((parent / 'rejected-manifest.json').stat().st_ino, before.st_ino)
            self.assertEqual((parent / 'rejected-manifest.json').stat().st_nlink, 1)
            self.assertEqual(q.load(parent / 'rejected-manifest.json'), {'syntheticOnly': True})

    def test_failure_record_cap_is_not_a_fabricated_receipt(self):
        with namespace() as products:
            parent = q.create_owned(products / 'qualification' / lab.SCENARIO / 'reference')
            with mock.patch.object(q, 'RECORD_LIMIT', 32), self.assertRaises(ValueError):
                q.write_json(parent / 'failure.json', dict(reason='x' * 100))
            self.assertFalse((parent / 'failure.json').exists())
            self.assertTrue((parent / '.failure.json.partial').exists())
            self.assertFalse((parent / 'process-exit.json').exists())


if __name__ == '__main__':
    unittest.main()
