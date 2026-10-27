#!/usr/bin/env python3
"""Expected negative compile identifies a real generic access-context gap."""
import run as A,json,shlex
H=A.H;O=A.OUT
ad=json.loads((O/'admission.json').read_bytes());ha=json.loads((O/'hardening-admission.json').read_bytes());w=ad['witness'];w['files'].update(ha['delta']);delta={str(p):A.sha(p)for p in [H/'friend.cpp',H/'generic_gap.py']};w['files'].update(delta);A.dump(O/'generic-gap-admission.json',dict(baseSha256=A.sha(O/'admission.json'),currentHardeningAdmissionSha256=A.sha(O/'hardening-admission.json'),delta=delta,expectation='original friend-context container parses; std::begin-based lab continuation rejects private-friend-only begin/end; production adapter remains blocked on this context'))
r=ad['recipe'];live=dict(files={p:h for p,h in w['files'].items()if p in ad['delta']or p in ha['delta']or p in delta or p in ad['tools']},aliases={});flags=[*r['flags'],'-DWP_BOUNDARY_ON=1','-I'+str(H)]
for name,on,expected in [('friend-original',1,0),('friend-boundary',0,1)]:
 dep=O/(name+'.d');A.command('syntax-'+name,[r['compiler'],*flags,'-DWP_FRIEND_ORIGINAL='+str(on),'-fsyntax-only','-MD','-MF',dep,H/'friend.cpp'],live,expected=expected)
 if dep.exists():A.subset(shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]),w)
A.need(b'begin'in(O/'syntax-friend-boundary.stderr').read_bytes(),'specific begin lookup diagnostic');A.dump(O/'generic-gap-report.json',dict(status='EXPECTED_GENERIC_ADAPTER_GAP_REPRODUCED',originalSyntaxPass=True,boundaryPrivateFriendSyntaxPass=False,admissionSha256=A.sha(O/'generic-gap-admission.json'),productionGenericTemplateQualification=False));print('GAP_REPORT',A.sha(O/'generic-gap-report.json'))
