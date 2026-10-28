#!/usr/bin/env python3
"""Additional actual consumer typechecking, no game/object output or Cargo."""
import json,shlex,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H));import run as A
R=A.R;O=A.O;ad=A.load(O/'admission.json');cc=R/'build/behavior/ttl-cache-combined-r2/reference/cmake/compile_commands.json';rows=json.loads(cc.read_bytes());selected=[]
for name in ['StarTreasure.cpp','StarWeather.cpp','StarCelestialDatabase.cpp']:
 matches=[r for r in rows if Path(r['file']).name==name];A.need(len(matches)==1,'unique actual game source');row=matches[0];argv=shlex.split(row['command']);A.need(argv[0]==ad['recipe']['compiler'],'same preselected actual C++ compiler');A.need('-include-pch'not in argv and not any('cmake_pch'in x for x in argv),'native recipe already disables PCH');i=argv.index('-o');del argv[i:i+2];argv[argv.index('-c')]='-fsyntax-only';argv.extend(['-DSTAR_USE_RUST_WEIGHTED_POOL','-MD','-MF',str(O/(name+'.d'))]);selected.append(dict(name=name,source=row['file'],original=row,argv=argv))
base=ad['witness'];wide=A.closure([R/'source']);wide['files'].update(base['files']);wide['aliases'].update(base['aliases']);wide['files'][str(cc)]=A.sha(cc);wide['files'][str(Path(__file__).resolve())]=A.sha(Path(__file__));A.dump(O/'consumer-admission.json',dict(baseAdmissionSha256=A.sha(O/'admission.json'),commands=selected,witness=wide,sealedWallNs=time.time_ns(),procedureSha256=A.sha(Path(__file__)),purpose='same original native game compile flags, syntax-only plus sole new selector; not runtime/game/configure'))
for row in selected:
 A.command('consumer-'+row['name'],row['argv'],wide,ad['env']);dep=O/(row['name']+'.d');A.subset(shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]),wide)
A.dump(O/'consumer-report.json',dict(status='THREE_ACTUAL_PRODUCTION_CONSUMER_TUS_TYPECHECKED_ONLY',admissionSha256=A.sha(O/'consumer-admission.json'),sources=[r['source']for r in selected],receipts={r['name']:A.sha(O/('consumer-'+r['name']+'.receipt.json'))for r in selected}));print('CONSUMER REPORT',A.sha(O/'consumer-report.json'))
