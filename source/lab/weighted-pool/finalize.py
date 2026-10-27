#!/usr/bin/env python3
"""Compose already acquired immutable leaves. No native process is rerun.

The orthogonal outer producer failed decoding a linker map as UTF-8; the map
contains filesystem bytes. sdk_witness explicitly supports surrogateescape.
That failure is retained; this report never asserts a whole-producer pass.
"""
import json,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];BASE=ROOT/'build/weighted-pool-native-r1';OLD=BASE/'attempt2';OUT=BASE/'orthogonal'
sys.path.insert(0,str(HERE));import audit,run

def main():
    run.need(not (OUT/'report.json').exists(),'immutable report must not be overwritten')
    admission=json.loads((OUT/'admission.json').read_text())
    run.need(audit.sha(admission['base_admission'])==admission['base_admission_sha256'],'base admission exact')
    w=json.loads((OLD/'admission.json').read_text())['witness'];run.unchanged(w)
    for p,h in admission['delta'].items():run.need(audit.sha(p)==h,'orthogonal source drift')
    before=json.loads((OLD/'sdk-before.json').read_text());after=json.loads((OUT/'sdk-after.json').read_text());run.need(before==after,'SDK unchanged')
    paths=run.re.findall(r'^\[\s*\d+\] (.*\.tbd)$',(OLD/'native.map').read_text(errors='surrogateescape'),run.re.M)
    run.need(paths,'actual linked tbd list')
    run.dump(OUT/'sdk-consumed.json',run.sdk_witness.reconcile_consumed(before,paths,requested_root=before['requested_root'],expected_canonical_root=before['canonical_root']))
    r=audit.semantics();controls=audit.controls();run.need(json.loads((OUT/'controls.json').read_text())==controls,'original controls exact')
    r.update(status='PARTIAL_NATIVE_BASELINE; lifecycle observer gate UNRESOLVED; both monolithic producers and orthogonal outer producer FAILED; successful leaves composed read-only',controls=controls,failed_monolithic_attempts=2,orthogonal_outer_failure='UnicodeDecodeError in UTF-8 linker-map metadata decode AFTER all9 successful expected leaves; no native rerun',commands=['compile','link','real','diagnostics','nonprogress','lazy-negative','mutant-compile','mutant-link','mutant'],base_admission_sha256=audit.sha(OLD/'admission.json'),admission_sha256=audit.sha(OUT/'admission.json'),source_scope='ONLY new source/lab/weighted-pool and build/weighted-pool-native-r1; no production/Rust/header/CMake edits',definition_map='source/lab/weighted-pool/README.md',deadline=run.DEADLINE)
    r['products']={str(p):audit.sha(p) for p in BASE.rglob('*') if p.is_file() and p.name!='report.json'}
    r['products'].update({str(p):audit.sha(p) for p in HERE.glob('*') if p.is_file()})
    r['whole_root_bytes_before_report']=sum(p.stat().st_size for p in BASE.rglob('*') if p.is_file())
    run.need(r['whole_root_bytes_before_report']<64*1024*1024,'whole-root cap')
    run.dump(OUT/'report.json',r);print(audit.sha(OUT/'report.json'))
if __name__=='__main__':main()
