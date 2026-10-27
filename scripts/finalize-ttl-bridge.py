#!/usr/bin/env python3
"""Independently compose recorded successful TTL bridge commands after loader error.

No compiler, native binary, Cargo, subprocess, source edits or receipt rebinding.
The original outer producer failed; its missing PID remains unknown. Finite
inner-command parity can be accepted independently, never as whole-run success.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'source/lab/ttl-rust'
sys.path.insert(0, str(HERE))
import common as c
# common deliberately adds other helper directories. Resolve THIS verifier by
# physical filename, then prioritize its local sibling imports explicitly.
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('ttl_actual_independent_verifier', HERE / 'verify.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
OUT = c.OUT


def forbid(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork', 'os.forkpty', 'os.exec'}:
        raise ValueError('independent finalization/replay forbids process creation')


sys.addaudithook(forbid)


def archive_reconstruction():
    checked = []
    for name in ('provisional-canonical', 'provisional-toolchain', 'sealed-provisional-generated'):
        manifest_path = OUT / (name + '.json')
        manifest = json.loads(manifest_path.read_bytes())
        archive_path = OUT / (name + '.tar.gz')
        c.need(c.sha(archive_path) == manifest['archive_sha256'], 'historical archive bytes')
        with tarfile.open(archive_path, 'r:gz') as archive:
            c.need(set(archive.getnames()) == set(manifest['members']), 'exact historical archive membership')
            for path, row in manifest['members'].items():
                raw = archive.extractfile(path).read()
                c.need(len(raw) == row['size'] and hashlib.sha256(raw).hexdigest() == row['sha256'], 'historical member reconstruction')
        checked.append(dict(manifest=str(manifest_path), manifestSha256=c.sha(manifest_path), members=len(manifest['members'])))
    return checked


def compose():
    c.need(not (OUT / 'report.typed').exists(), 'never overwrite/rebind an existing report')
    error = OUT / 'actual-acquisition.stderr'
    c.need(b"AttributeError: module 'verify' has no attribute 'semantics'" in error.read_bytes(), 'preserved actual producer loader failure')
    c.need(not (OUT / 'semantic.typed').exists(), 'original producer did not finalize semantics')
    semantics = v.semantics(lambda p: Path(p).read_bytes())
    archives = archive_reconstruction()
    c.dump(OUT / 'semantic.typed', semantics)
    products = c.hashes(p for p in OUT.rglob('*') if p.is_file() and p.name not in ('report.typed', 'HANDOFF.md', 'acquisition.log') and 'audit' not in p.relative_to(OUT).parts)
    report = dict(status='FINITE_ACTUAL_RUST_TTL_BRIDGE_PASS',
                  inputs=c.load(OUT / 'inputs-before.typed'), products=products,
                  semantics=semantics, native_baseline_sha256=v.BASE_SHA,
                  canonical_archive_sha256=c.sha(v.canonical.ARCHIVE),
                  acceptanceMode='INDEPENDENT_COMPOSITION_AFTER_OUTER_PRODUCER_FAILURE',
                  originalProducer=dict(status='FAILED_PYTHON_MODULE_FINALIZER', observedExit=1,
                                        actualPid='UNKNOWN', wholeRunAccepted=False,
                                        stderr=str(error), stderrSha256=c.sha(error)),
                  finalizer=dict(path=str(Path(__file__).resolve()), sha256=c.sha(Path(__file__).resolve()),
                                 verifier=str(HERE / 'verify.py'), verifierSha256=c.sha(HERE / 'verify.py'),
                                 historicalArchives=archives),
                  limits='finite laboratory TTL Rust/native parity from durable successful inner-command records; original outer Python invocation remains failed/PID UNKNOWN; not production selection, game adoption, actual-clock exact boundary, OOM, arbitrary pointers, other platforms or universal equivalence')
    # Create an immutable producer candidate, then independently validate it.
    # Never overwrite it on failure: a failed check leaves an unaccepted candidate,
    # not permission to rebind receipts or change source/expectations.
    c.dump(OUT / 'report.typed', report)
    return v.verify(report)


def controls():
    original = c.load(OUT / 'report.typed')
    results = {}

    def reject(name, overlay, barrier):
        report = copy.deepcopy(original)
        # Coherently bind changed stdout to its actual command receipt, allowing
        # semantic falsifiers to reach the model/trace barrier, not just stdio SHA.
        for path, data in list(overlay.items()):
            if path.suffix == '.stdout':
                receipt = path.with_suffix('.receipt')
                if receipt.exists():
                    row = c.load(receipt)
                    row['stdout'] = hashlib.sha256(data).hexdigest()
                    overlay[receipt] = c.codec.dumps(row).encode('ascii')
        for path, data in overlay.items():
            for field in ('inputs', 'products'):
                if str(path) in report[field]:
                    report[field][str(path)] = hashlib.sha256(data).hexdigest()
        if report['inputs'] != original['inputs']:
            path = OUT / 'inputs-before.typed'
            overlay[path] = c.codec.dumps(report['inputs']).encode('ascii')
            report['products'][str(path)] = hashlib.sha256(overlay[path]).hexdigest()

        def read(path):
            path = Path(path)
            return overlay[path] if path in overlay else path.read_bytes()
        try:
            v.verify(report, read)
        except (ValueError, AssertionError) as error:
            c.need(barrier in str(error), 'wrong coherent control barrier ' + name + ': ' + str(error))
            results[name] = str(error)
        else:
            raise ValueError('coherent known failure escaped ' + name)

    path = OUT / 'ordered-0.stdout'
    rows = path.read_bytes().splitlines()
    fields = rows[10].split(b'\t'); fields[7] = b'wrong-result'; rows[10] = b'\t'.join(fields)
    reject('coherent-output-and-command-receipt-model', {path: b'\n'.join(rows) + b'\n'}, 'model stream barrier')
    path = OUT / 'lifecycle.stdout'
    reject('coherent-trace-and-command-receipt', {path: path.read_bytes().replace(b'producer-call', b'producer-wrong', 1)}, 'lifetime full native trace barrier')
    path = OUT / 'ordered-0.receipt'; row = c.load(path); row.update(pid=True, pgid=True)
    start_path = OUT / 'ordered-0.started'; start = c.load(start_path); start.update(pid=True, pgid=True)
    reject('coherent-boolean-pid-pair', {path: c.codec.dumps(row).encode('ascii'), start_path: c.codec.dumps(start).encode('ascii')}, 'typed owned group')
    path = OUT / 'fixture.map'; rows = path.read_bytes().splitlines()
    hits = [i for i, row in enumerate(rows) if row.endswith(b' _sb_ttl_run')]
    c.need(len(hits) == 1, 'unique provider corruption target')
    import re
    rows[hits[0]] = re.sub(rb'\[\s*\d+\]', b'[  1]', rows[hits[0]])
    reject('coherent-physical-controller-owner', {path: b'\n'.join(rows) + b'\n'}, 'provider')
    reject('coherent-frozen-kernel-source', {v.KERNEL: v.KERNEL.read_bytes() + b'\n// invalid source\n'}, 'frozen kernel source barrier')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose', action='store_true')
    parser.add_argument('--report-sha')
    parser.add_argument('--controls', action='store_true')
    args = parser.parse_args()
    if args.compose:
        result = compose()
    else:
        c.need(args.report_sha is not None and c.sha(OUT / 'report.typed') == args.report_sha, 'external composition report pin')
        result = v.verify()
    report = c.load(OUT / 'report.typed')
    c.need(report['acceptanceMode'] == 'INDEPENDENT_COMPOSITION_AFTER_OUTER_PRODUCER_FAILURE'
           and report['originalProducer']['wholeRunAccepted'] is False
           and report['originalProducer']['actualPid'] == 'UNKNOWN', 'failed outer invocation disposition')
    c.need(c.sha(Path(__file__).resolve()) == report['finalizer']['sha256'], 'finalizer source pin')
    c.need(c.sha(HERE / 'verify.py') == report['finalizer']['verifierSha256'], 'verifier source pin')
    result['retainedArchives'] = archive_reconstruction()
    if args.controls:
        result['coherentControls'] = controls()
        v.verify()  # Falsifiers did not mutate acquisition bytes.
    result['report_sha256'] = c.sha(OUT / 'report.typed')
    print(c.codec.dumps(result))


if __name__ == '__main__':
    main()
