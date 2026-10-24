#!/usr/bin/env python3
"""Selected production wiring negatives; successful executables, byte comparison."""
import argparse,gzip,hashlib,json,os,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--values',required=True,type=Path);args=parser.parse_args()
OUT=args.output.absolute();V=args.values.absolute();base=ROOT/'build/zstd-lab'
if not OUT.is_relative_to(base) or OUT==base or OUT.exists() or any(p.is_symlink() for p in [OUT,*OUT.parents]):parser.error('fresh owned nonsymlink output required')
OUT.mkdir(parents=True)
v=json.loads((V/'report.json').read_text());link=v['link'];rust=ROOT/'build/zstd-rust/target/release/libstar_engine_ffi.a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for p,h in v['bindings'].items():
 if sha(Path(p))!=h:raise RuntimeError('binding drift '+p)
fixture=OUT/'cases.tsv';fixture.write_text('empty empty 0 0 2 0 -\nstream stream 2 0 2 0 616263\nbad bad 3 0 2 0 67617262616765\n')
raw=(ROOT/'source/core/StarZSTDCompression.cpp').read_text();host=(ROOT/'source/core/StarZstdHost.hpp').read_text();lab=(HERE/'lab.cpp').read_text().replace('if(delta!=expected)throw std::runtime_error("Rust per-call receipt mismatch");','(void)expected;')
labpath=OUT/'lab.cpp';labpath.write_text(lab)
results=[];commands=[];generated=[]
def invoke(name,source,fixture_lab,selected=True):
 binary=OUT/name;tls=OUT/(name+'.tls.tsv');cmd=[link['compiler'],*link['flags'],'-I'+str(ROOT/'source/core'),'-I'+str(HERE),*(['-DSTAR_USE_RUST_ZSTD=1','-DLAB_RUST=1'] if selected else []),str(fixture_lab),str(source),link['archive'],str(rust),*link['libraries'],'-Wl,-dead_strip','-o',str(binary)]
 commands.append(cmd);r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=90);(OUT/(name+'.compile.log')).write_bytes(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError('compile failure NOT credited '+name)
 env=os.environ.copy();env['ZSTD_RECEIPTS']=str(tls);r=subprocess.run([binary,fixture],cwd=ROOT,env=env,capture_output=True,timeout=30)
 (OUT/(name+'.stderr')).write_bytes(r.stderr)
 with gzip.open(OUT/(name+'.stdout.gz'),'wb') as f:f.write(r.stdout)
 if r.returncode:raise RuntimeError('runtime failure NOT credited '+name)
 result=(r.stdout,tls.read_bytes());results.append(dict(name=name,binary_sha256=sha(binary),stdout_sha256=hashlib.sha256(result[0]).hexdigest(),tls_sha256=sha(tls)))
 return result
production=ROOT/'source/core/StarZSTDCompression.cpp';good=invoke('good',production,labpath)
for name,src,labtext,selected in [
 ('dispatch',raw,lab,False),
 ('empty-bypass',raw.replace('  ZstdHost::NativeContext context(ZC_ONESHOT_COMPRESS,in,inLen);','  if(inLen==0)return ByteArray();\n  ZstdHost::NativeContext context(ZC_ONESHOT_COMPRESS,in,inLen);'),lab,True),
 ('receipt-suppression',raw,lab.replace('star_zstd_call_count(m,e)','uint64_t(0)'),True),
 ('pending-route',raw.replace('#include "StarZstdHost.hpp"','#include "'+str(OUT/'pending-host.hpp')+'"'),lab,True)]:
 if name=='pending-route':
  p=OUT/'pending-host.hpp';p.write_text(host.replace('std::rethrow_exception(c.pending);','throw StarException("wrong pending route");'));generated.append(p)
 p=OUT/(name+'.cpp');p.write_text(src);l=OUT/(name+'-lab.cpp');l.write_text(labtext);generated.extend([p,l])
 bad=invoke(name,p,l,selected)
 if good==bad:raise RuntimeError('COMPARISON escaped '+name)
for p,h in v['bindings'].items():
 if sha(Path(p))!=h:raise RuntimeError('after drift '+p)
report=dict(status='PASS_SELECTED_WIRING_NEGATIVES',controls=results,commands=commands,generated={str(p):sha(p) for p in [fixture,labpath,*generated]},bindings=v['bindings'])
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
