#!/usr/bin/env python3
"""Build isolated diagnostics only, using the recorded native compiler configuration."""
import json, shlex, subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parents[4]
out=root/'build/lighting-fp';out.mkdir(parents=True,exist_ok=True)
entries=json.loads((root/'build/behavior/reference/cmake/compile_commands.json').read_text())
entry=next(e for e in entries if e['file'].endswith('/StarCellularLightArray.cpp'))
a=shlex.split(entry['command']);a=a[:a.index('-o')]
commands=[]
def run(cmd):
 commands.append(cmd);subprocess.run(cmd,cwd=root,check=True)
source='source/lab/lighting/diagnostic/fp_sites.cpp'
for name,opts in [('fast',[]),('precise',['-fno-fast-math','-ffp-contract=off']),('nofma',['-ffp-contract=off']),('contract',['-fno-fast-math','-ffp-contract=fast'])]:
 for mode,ext in [('-S','.s'),('-dynamiclib','.dylib')]:
  run(a+opts+['-DPROBE='+name,mode,source,'-o',str(out/(name+ext))])
run(['rustc','-O','--crate-type','cdylib','source/lab/lighting/diagnostic/policy.rs','-o',str(out/'policy.dylib')])
for name in ('StarCellularLightArray.cpp','StarCellularLighting.cpp'):
 e=next(e for e in entries if e['file'].endswith('/'+name));cmd=shlex.split(e['command']);cmd=cmd[:cmd.index('-o')]
 run(cmd+['-S',e['file'],'-o',str(out/('production-'+name+'.s'))])
(out/'commands.json').write_text(json.dumps(commands,indent=2))
run([sys.executable,'source/lab/lighting/diagnostic/probe.py'])
