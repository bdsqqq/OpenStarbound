#!/usr/bin/env python3
"""New small revision: reject fabricated borrow replies lacking a native leaf.
Single combined executable avoids a second pile of candidates under the same cap.
"""
import run as A
import json,shlex,re
H=A.H;OUT=A.OUT;ROOT=A.ROOT

def main():
 ad=json.loads((OUT/'admission.json').read_bytes());r=ad['recipe'];w=ad['witness'];old=str(H/'frame.hpp');ret=OUT/'frame-before-borrow-guard.hpp';A.need(A.sha(ret)==ad['delta'][old],'retained exact old tested frame');delta={str(p):A.sha(p)for p in [H/'frame.hpp',H/'combined.cpp',H/'hardening.py']};w['files'].update(delta)
 A.dump(OUT/'hardening-admission.json',dict(baseSha256=A.sha(OUT/'admission.json'),previousReportSha256=A.sha(OUT/'independent-report.json'),delta=delta,sourceVersion=dict(canonical=old,oldSha256=A.sha(ret),retained=str(ret)),reason='canonical BORROW result additionally requires a successful native borrow callback; no native object stored in policy',linkMap='omit symbol-heavy map to remain under same64MiB cap; actual -t SDK/provider trace retained'))
 live=dict(files={p:h for p,h in w['files'].items()if p in ad['delta']or p in delta or p in ad['tools']or p in r['objects']or p in r['libraries']},aliases={});mock=OUT/'mock.o';live['files'][str(mock)]=A.sha(mock);c=r['compiler'];flags=[*r['flags'],'-DWP_BOUNDARY_ON=1','-I'+str(H),'-I'+str(H.parent/'weighted-pool')];obj=OUT/'combined.o';dep=OUT/'combined.d';exe=OUT/'combined'
 A.command('compile-combined',[c,*flags,'-MD','-MF',dep,'-c',H/'combined.cpp','-o',obj],live);deps=shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]);A.subset(deps,w);live['files'][str(obj)]=A.sha(obj)
 A.command('link-combined',[c,*flags,*r['objects'],obj,mock,*r['libraries'],'-Wl,-dead_strip','-Wl,-t,-trace_implicit_libraries','-o',exe],live);live['files'][str(exe)]=A.sha(exe)
 A.command('combined-current',[exe],live);rows,expected=A.model.corpus();A.command('combined-corpus',[exe,'corpus'],live,stdin=rows.encode());A.need((OUT/'combined-corpus.stdout').read_bytes()==expected.encode(),'current27 corpus')
 data=(OUT/'combined-current.stdout').read_bytes();life=(OUT/'lifecycle-mock.stdout').read_bytes();A.need(data.startswith(life+life),'current eight lifecycle traces per implementation unchanged');A.need(b'PASS\tmissing-borrow-capability-rejected'in data,'fabricated borrow negative')
 paths=[p for p in(OUT/'link-combined.stdout').read_text(errors='surrogateescape').splitlines()if p.endswith('.tbd')and p.startswith('/')];sdk=json.loads((A.BASE/'sdk-before.json').read_bytes());requested=r['flags'][r['flags'].index('-isysroot')+1];A.dump(OUT/'hardening-sdk-consumed.json',A.sdk_witness.reconcile_consumed(sdk,paths,requested_root=requested,expected_canonical_root=requested))
 A.dump(OUT/'hardening-report.json',dict(status='CURRENT_NATIVE_MOCK_BORROW_GUARD_FINITE_PASS',admissionSha256=A.sha(OUT/'hardening-admission.json'),currentSource=delta,roots=19,stages=4,traceCount=8,corpusRows=27,limitations=['not actual Rust/production/game','generic private-friend range/access lookup remains review obligation','bounded finite optimized arithmetic only'],products={str(p):A.sha(p)for p in OUT.rglob('*')if p.is_file()and p.name not in ['hardening-report.json','hardening.stdout','hardening.stderr']}));print('REPORT',A.sha(OUT/'hardening-report.json'))
if __name__=='__main__':main()
