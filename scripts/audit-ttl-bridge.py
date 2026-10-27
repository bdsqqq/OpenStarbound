#!/usr/bin/env python3
"""Supplemental read-only audit; immutable producer/finalizer failures stay failed.

Use the structured symbol-name column, not a suffix also matching an FDE label.
Coherent stdout/receipt/product overlays must reach actual semantic barriers.
"""
import argparse
import copy
import hashlib
import importlib.util
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ttl_frozen_finalizer', ROOT / 'scripts/finalize-ttl-bridge.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
c, v, OUT = f.c, f.v, f.OUT


def audit(pin):
    c.need(c.sha(OUT / 'report.typed') == pin, 'independent candidate pin')
    original = c.load(OUT / 'report.typed')
    c.need(c.sha(ROOT / 'scripts/finalize-ttl-bridge.py') == original['finalizer']['sha256'], 'frozen finalizer bytes')
    c.need(c.sha(v.HERE / 'verify.py') == original['finalizer']['verifierSha256'], 'frozen actual verifier bytes')
    c.need(original['originalProducer']['observedExit'] == 1 and original['originalProducer']['actualPid'] == 'UNKNOWN'
           and original['originalProducer']['wholeRunAccepted'] is False, 'outer failure must remain failed/unknown')
    positive = v.verify()
    archives = f.archive_reconstruction()
    results = {}

    def reject(name, overlay, barrier):
        report = copy.deepcopy(original)
        for path, raw in list(overlay.items()):
            if path.suffix == '.stdout':
                receipt = path.with_suffix('.receipt')
                row = c.load(receipt); row['stdout'] = hashlib.sha256(raw).hexdigest()
                overlay[receipt] = c.codec.dumps(row).encode('ascii')
        for path, raw in overlay.items():
            for field in ('inputs', 'products'):
                if str(path) in report[field]:
                    report[field][str(path)] = hashlib.sha256(raw).hexdigest()
        if report['inputs'] != original['inputs']:
            p = OUT / 'inputs-before.typed'
            overlay[p] = c.codec.dumps(report['inputs']).encode('ascii')
            report['products'][str(p)] = hashlib.sha256(overlay[p]).hexdigest()
        def read(p):
            p = Path(p)
            return overlay[p] if p in overlay else p.read_bytes()
        try:
            v.verify(report, read)
        except (ValueError, AssertionError) as error:
            c.need(barrier in str(error), 'wrong falsification barrier ' + name + ': ' + str(error))
            results[name] = str(error)
        else:
            raise ValueError('known corruption escaped ' + name)

    p = OUT / 'ordered-0.stdout'; rows = p.read_bytes().splitlines()
    fields = rows[10].split(b'\t'); fields[7] = b'wrong-result'; rows[10] = b'\t'.join(fields)
    reject('coherent-output-receipt-model', {p:b'\n'.join(rows)+b'\n'}, 'model stream barrier')
    p = OUT / 'lifecycle.stdout'
    reject('coherent-trace-receipt', {p:p.read_bytes().replace(b'producer-call', b'producer-wrong', 1)}, 'lifetime full native trace barrier')
    p = OUT / 'ordered-0.receipt'; row = c.load(p); row.update(pid=True, pgid=True)
    start = OUT / 'ordered-0.started'; before = c.load(start); before.update(pid=True, pgid=True)
    reject('coherent-boolean-pid-pair', {p:c.codec.dumps(row).encode('ascii'), start:c.codec.dumps(before).encode('ascii')}, 'typed owned group')
    p = OUT / 'fixture.map'; rows = p.read_bytes().splitlines()
    # Cross-check with the actual Mach-O/map verifier's parsed live symbol.
    symbol = v.evidence.native_symbols.unique_symbol(v.evidence.native_symbols.live_symbols(p.read_bytes()), b'_sb_ttl_run')
    indices = [i for i, row in enumerate(rows) if re.search(rb'\]\s+_sb_ttl_run$', row)]
    c.need(len(indices) == 1 and int(rows[indices[0]].split()[0],16) == symbol.address, 'exact live Rust symbol column')
    rows[indices[0]] = re.sub(rb'\[\s*\d+\]', b'[  1]', rows[indices[0]])
    reject('coherent-live-controller-provider', {p:b'\n'.join(rows)+b'\n'}, 'provider')
    reject('coherent-frozen-Rust-source', {v.KERNEL:v.KERNEL.read_bytes()+b'\n// invalid source\n'}, 'frozen kernel source barrier')
    v.verify()
    return dict(status='PARENT_ACCEPTED_FINITE_ACTUAL_RUST_TTL_COMPOSITION', reportSha256=pin,
                positive=positive, coherentControls=results, archives=archives,
                originalOuterInvocationAccepted=False, originalFinalizerControlInvocationAccepted=False,
                supplementalAuditSourceSha256=c.sha(Path(__file__).resolve()),
                limits='finite laboratory Rust/native parity from successful inner commands; original outer producer and first finalizer-control invocation remain failed; not production/game/whole-TTL adoption')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-sha', required=True)
    args = parser.parse_args()
    print(c.codec.dumps(audit(args.report_sha)))
