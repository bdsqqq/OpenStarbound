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


def bounded_error(exc):
    return (type(exc).__name__ + ': ' + str(exc))[:512].encode('utf-8')[:512].decode('utf-8', errors='ignore')


def guard(argv, status_fd, token, source_sha, environment):
    pid = os.getpid()
    pgid, sid = os.getpgrp(), os.getsid(0)
    record = dict(schema=SCHEMA, token=token, sourceSha256=source_sha,
        guardianPID=pid, guardianPGID=pgid, guardianSID=sid,
        commandPID=None, returncode=None, commandReaped=False, launchError=None)
    try:
        if status_fd <= 2 or pid != pgid or pid != sid:
            raise ValueError('guardian must own a fresh session and private status descriptor')
        if hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest() != source_sha:
            raise ValueError('guardian source pin mismatch')
        # the actual command must not inherit the private protocol capability.
        os.set_inheritable(status_fd, False)
        # Python startup can coerce locale variables in its own environment;
        # launch with the parent's declared mapping, not that mutated copy.
        proc = subprocess.Popen(argv, env=environment, close_fds=True, pass_fds=())
        record['commandPID'] = proc.pid
    except BaseException as exc:
        record['launchError'] = bounded_error(exc)
        proc = None
    finally:
        # only the actual command owns copies of these pipe writers now.
        for fd in (1, 2):
            try:
                os.close(fd)
            except OSError:
                pass
    if proc is not None:
        try:
            record['returncode'] = proc.wait()
            record['commandReaped'] = True
        except BaseException as exc:
            record['launchError'] = bounded_error(exc)
    data = json.dumps(record, sort_keys=True, separators=(',', ':')).encode('utf-8')
    try:
        if len(data) > STATUS_BYTES:
            raise ValueError('guardian status exceeds protocol bound')
        while data:
            written = os.write(status_fd, data)
            if written <= 0:
                raise OSError('guardian status write made no progress')
            data = data[written:]
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
    parser.add_argument('argv', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
    guard(argv, args.status_fd, args.token, args.source_sha, json.loads(args.environment_json))


if __name__ == '__main__':
    main()
