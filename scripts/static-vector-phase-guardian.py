#!/usr/bin/env python3
"""keep the owned session leader live until its parent finishes group cleanup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess

SCHEMA = 'static-vector-phase-guardian-v1'
STATUS_BYTES = 4096
START_SCHEMA = 'static-vector-command-start-v1'


def write_status(status_fd, data):
    while data:
        written = os.write(status_fd, data)
        if written <= 0:
            raise OSError('guardian status write made no progress')
        data = data[written:]


def await_start_ack(fd, token):
    """Hold the actual child's wait/reap until its observer durably returns."""
    expected = token.encode('ascii') + b'\n'
    if not 1 < len(expected) <= 256:
        raise ValueError('start acknowledgment nonce bound')
    data = bytearray()
    while True:
        part = os.read(fd, len(expected) + 1 - len(data))
        if not part:
            break
        data.extend(part)
        if len(data) > len(expected):
            raise ValueError('start acknowledgment overflow')
    if bytes(data) != expected:
        raise ValueError('start acknowledgment missing or changed')


def bounded_error(exc):
    return (type(exc).__name__ + ': ' + str(exc))[:512].encode('utf-8')[:512].decode('utf-8', errors='ignore')


def guard(argv, status_fd, token, source_sha, environment, notify_start=False, start_ack_fd=None):
    pid = os.getpid()
    pgid, sid = os.getpgrp(), os.getsid(0)
    record = dict(schema=SCHEMA, token=token, sourceSha256=source_sha,
        guardianPID=pid, guardianPGID=pgid, guardianSID=sid,
        commandPID=None, returncode=None, commandReaped=False, launchError=None)
    proc = None
    start_bytes = 0
    acknowledged = not notify_start
    ack_owned = False
    try:
        if status_fd <= 2 or pid != pgid or pid != sid:
            raise ValueError('guardian must own a fresh session and private status descriptor')
        if hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest() != source_sha:
            raise ValueError('guardian source pin mismatch')
        # the actual command must not inherit the private protocol capability.
        os.set_inheritable(status_fd, False)
        if notify_start:
            if type(start_ack_fd) is not int or start_ack_fd <= 2 or start_ack_fd == status_fd:
                raise ValueError('private start acknowledgment descriptor required')
            ack_owned = True
            os.set_inheritable(start_ack_fd, False)
        elif start_ack_fd is not None:
            raise ValueError('unexpected start acknowledgment descriptor')
        # Python startup can coerce locale variables in its own environment;
        # launch with the parent's declared mapping, not that mutated copy.
        proc = subprocess.Popen(argv, env=environment, close_fds=True, pass_fds=())
        record['commandPID'] = proc.pid
    except BaseException as exc:
        record['launchError'] = bounded_error(exc)
    else:
        if notify_start:
            row = {key: record[key] for key in ('token', 'sourceSha256', 'guardianPID',
                   'guardianPGID', 'guardianSID', 'commandPID')}
            row['schema'] = START_SCHEMA
            data = json.dumps(row, sort_keys=True, separators=(',', ':')).encode('utf-8') + b'\n'
            start_bytes = len(data)
            try:
                if start_bytes > STATUS_BYTES:
                    raise ValueError('guardian start exceeds protocol bound')
                write_status(status_fd, data)
                await_start_ack(start_ack_fd, token)
                acknowledged = True
            except BaseException as exc:
                # Keep the spawned PID, but do NOT wait/reap before a successful
                # observer acknowledgment. The parent cancels this live group.
                record['launchError'] = bounded_error(exc)
    finally:
        if ack_owned:
            try:
                os.close(start_ack_fd)
            except BaseException as exc:
                acknowledged = False
                record['launchError'] = bounded_error(exc)
        # only the actual command owns copies of these pipe writers now.
        for fd in (1, 2):
            try:
                os.close(fd)
            except OSError:
                pass
    if proc is not None and acknowledged:
        try:
            record['returncode'] = proc.wait()
            record['commandReaped'] = True
        except BaseException as exc:
            record['launchError'] = bounded_error(exc)
    data = json.dumps(record, sort_keys=True, separators=(',', ':')).encode('utf-8')
    try:
        if start_bytes + len(data) > STATUS_BYTES:
            raise ValueError('guardian status exceeds protocol bound')
        write_status(status_fd, data)
    except BaseException:
        if not notify_start:
            raise
        # The parent still owns this live PGID even if its private reader failed.
    finally:
        os.close(status_fd)
    # do not exit after reporting: a LIVE session leader avoids Darwin's
    # zombie-only killpg EPERM and pins PGID until the parent's final signal.
    while True:
        signal.pause()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status-fd', type=int, required=True)
    parser.add_argument('--token', required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--environment-json', required=True)
    parser.add_argument('--notify-start', action='store_true')
    parser.add_argument('--start-ack-fd', type=int)
    parser.add_argument('argv', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
    guard(argv, args.status_fd, args.token, args.source_sha, json.loads(args.environment_json),
          **({'notify_start': args.notify_start, 'start_ack_fd': args.start_ack_fd}
             if args.notify_start or args.start_ack_fd is not None else {}))


if __name__ == '__main__':
    main()
