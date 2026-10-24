#!/usr/bin/env python3
"""Source-gated native call traces; status/buffer controls are counterfactual."""
import argparse,gzip,hashlib,json,re,shlex,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(s,old,new,count):
 if s.count(old)!=count:raise ValueError('SOURCE_GATE '+repr(old))
 return s.replace(old,new)
def instrument(s):
 s=replace(s,'ZSTD_compressStream2(', 'labTraceCompress(',1)
 s=replace(s,'ZSTD_decompressStream(', 'labTraceDecompress(',1)
 return replace(s,'out.resize(', 'labTraceResize(out,',8)
def require_same(a,b):
 if a!=b:raise ValueError('COMPARISON ordered values/calls')
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--values',type=Path,required=True);a=p.parse_args()
 out=a.output.absolute();values=a.values.absolute();base=ROOT/'build/zstd-lab'
 if not out.is_relative_to(base) or out.exists() or any(x.is_symlink() for x in [out,*out.parents]):p.error('fresh nonsymlink owned output required')
 out.mkdir(parents=True);v=json.loads((values/'report.json').read_text())
 if v['status']!='VALUES_ONLY_NOT_QUALIFIED':raise ValueError('unqualified value acquisition required')
 for name,digest in v['bindings'].items():
  if sha(Path(name))!=digest:raise ValueError('VALUE_BINDING '+name)
 link=v['link'];cmds=[];receipts=[];generated=[];negative=[]
 def run(cmd,name):
  cmd=list(map(str,cmd));cmds.append(cmd);exe=Path(cmd[0]).resolve();before=sha(exe)
  r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=120)
  (out/(name+'.stderr')).write_bytes(r.stderr)
  # Initialized failure tails repeat heavily. Keep exact, lossless receipts
  # without several gigabytes of duplicate plain-text output per replay.
  stdout_path=out/(name+('.stdout.gz' if len(r.stdout)>1024*1024 else '.stdout'))
  if stdout_path.suffix=='.gz':
   with gzip.open(stdout_path,'wb',compresslevel=1) as stream:stream.write(r.stdout)
  else:stdout_path.write_bytes(r.stdout)
  if sha(exe)!=before:raise ValueError('executable drift')
  receipts.append(dict(name=name,command=cmd,returncode=r.returncode,executable_sha256=before,stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stdout_bytes=len(r.stdout),stdout_artifact=str(stdout_path),stdout_artifact_sha256=sha(stdout_path)))
  (out/'receipts.json').write_text(json.dumps(receipts,indent=2))
  if r.returncode:raise RuntimeError('command failed (NOT credited negative): '+name)
  return r.stdout
 raw=(HERE/'StarZSTDCompression.original.cpp').read_text();ref=(HERE/'StarZSTDCompression.reference.cpp').read_text()
 # A source gate is falsified independently before generated C++ compilation.
 try:instrument(raw.replace('out.resize(', 'out.resize (',1))
 except ValueError:negative.append('source-gate')
 else:raise RuntimeError('source gate escaped')
 lab=(HERE/'lab.cpp').read_text()
 lab=replace(lab,'if(argc!=2)return 2;','if(argc<2||argc>3)return 2;',1)
 lab=replace(lab,'error=Star::printException(e,false);','labTraceCaught(); error=Star::printException(e,false);',1)
 lab=replace(lab,'auto bytes=unhex','labTraceReset(argc==3?std::stoi(argv[2]):0); auto bytes=unhex',1)
 lab=replace(lab,"<<out.capacity()<<'\\n';","<<out.capacity()<<'\\t'<<labTraceSerialize()<<'\\n';",1)
 labpath=out/'lab-trace.cpp';labpath.write_text(lab);generated.append(labpath)
 sources={}
 for name,text in [('original',raw),('reference',ref)]:
  source=out/(name+'.cpp');source.write_text(instrument(text));sources[name]=source;generated.append(source)
 proto=(HERE/'host_contract.cpp').read_text()
 driver=proto.split('// All allocations,',1)[0].split('uint32_t run',1)[1]
 def opaque_gate(text):
  if re.search(r'\bContext\b|host\s*[!=]=|reinterpret_cast|static_cast<Context',text):raise ValueError('OPAQUE_CONTROLLER')
 opaque_gate(driver)
 try:opaque_gate(driver+' if(host==nativeHost) return static_cast<Context*>(opaque)->mode;')
 except ValueError:negative.append('opaque-controller-source-only')
 else:raise RuntimeError('opaque source guard escaped')
 proto=replace(proto,'ZSTD_compressStream2(','labTraceCompress(',1)
 proto=replace(proto,'ZSTD_decompressStream(','labTraceDecompress(',1)
 proto=replace(proto,'c.stream->resize(a);','labTraceResize(*c.stream,a);',1)
 proto=replace(proto,'c.result.resize(a);','labTraceResize(c.result,a);',1)
 proto_path=out/'host-instrumented.cpp';proto_path.write_text(proto);generated.append(proto_path)
 hosted=raw
 bodies=[
 ('void CompressionStream::compress(const char* in, size_t inLen, ByteArray& out)','ZstdLab::Context c(0,in,inLen,&out); c.compression=m_cStream; ZstdLab::invoke(c);'),
 ('void DecompressionStream::decompress(const char* in, size_t inLen, ByteArray& out)','ZstdLab::Context c(1,in,inLen,&out); c.decompression=m_dStream; ZstdLab::invoke(c);'),
 ('ByteArray ZstdCompression::compress(const char* in, size_t inLen, int compressionLevel)','return ZstdLab::oneShot(2,in,inLen,compressionLevel);'),
 ('ByteArray ZstdCompression::decompress(const char* in, size_t inLen)','return ZstdLab::oneShot(3,in,inLen);')]
 for signature,body in bodies:
  if hosted.count(signature+' {')!=1:raise ValueError('ADAPTER_SOURCE_GATE')
  start=hosted.index(signature+' {');end=hosted.index('\n}',start)+2
  hosted=hosted[:start]+signature+' {\n  '+body+'\n}'+hosted[end:]
 hosted_path=out/'hosted.cpp';hosted_path.write_text('#include "'+str(proto_path)+'"\n'+hosted);generated.append(hosted_path)
 fixture=values/'cases.tsv'
 small=out/'small.tsv';small.write_text('small small 2 0 2 0 616263\n')
 trunc=out/'truncated.tsv';trunc.write_text('trunc trunc 3 0 2 0 28b52ffd\n')
 faultcase=out/'fault.tsv';faultcase.write_text('fault persistent 2 0 2 0 616263\nlater persistent 2 0 2 0 646566\n')
 tracked=[HERE/'host_contract.cpp',HERE/'host_contract.hpp',HERE/'host_contract_test.cpp',faultcase,Path(__file__),HERE/'trace_shim.hpp',HERE/'trace_shim.cpp',HERE/'lab.cpp',HERE/'run.py',values/'report.json',values/'observations.tsv',fixture,small,trunc,*generated,Path(link['archive'])]
 # Native dependency bindings include compiler, all SDK/header leaves, real
 # vendor archive and native retained core objects from the independent values.
 tracked+=list(map(Path,v['bindings']))
 for n,source in enumerate([labpath,*sources.values(),hosted_path,HERE/'trace_shim.cpp']):
  dep=out/(str(n)+'.d')
  run([link['compiler'],*link['flags'],'-I'+str(HERE),'-include',HERE/'trace_shim.hpp','-M','-MF',dep,source],'deps'+str(n))
  tracked.extend(Path(x) if Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]))
 before={str(x.resolve()):sha(x.resolve()) for x in dict.fromkeys(tracked)}
 (out/'before.json').write_text(json.dumps(before,indent=2))
 def compile(name,source,reference=False):
  binary=out/name;source_before=sha(source)
  run([link['compiler'],*link['flags'],'-I'+str(HERE),'-include',HERE/'trace_shim.hpp',*(['-DLAB_REFERENCE=1'] if reference else []),labpath,source,HERE/'trace_shim.cpp',link['archive'],*link['libraries'],'-Wl,-dead_strip','-o',binary],name+'-compile')
  if sha(source)!=source_before:raise ValueError('generated source drift')
  return binary
 original=compile('original',sources['original']);reference=compile('reference',sources['reference'],True)
 hosted_binary=compile('hosted',hosted_path)
 normal=run([original,fixture],'normal');other=run([reference,fixture],'reference-normal');require_same(normal,other);require_same(normal,run([original,fixture],'repeat'))
 stripped=b'\n'.join(row.rsplit(b'\t',1)[0] for row in normal.splitlines())+b'\n'
 require_same(stripped,(values/'observations.tsv').read_bytes())
 require_same(normal,run([hosted_binary,fixture],'hosted-normal'))
 fault_original=run([original,faultcase,4],'fault-original')
 require_same(fault_original,run([reference,faultcase,4],'fault-reference'))
 require_same(fault_original,run([hosted_binary,faultcase,4],'fault-hosted'))
 # Ordinary trace receipts compare real steps/resize attempts, not only bytes.
 def reject(name,bad,good):
  try:require_same(bad,good)
  except ValueError:negative.append(name)
  else:raise RuntimeError('runtime trace control escaped '+name)
 for name,old,new in [
  ('prefix-clear','  size_t written = out.size();','  out.clear(); size_t written = out.size();'),
  ('premature-shrink','    written += outBuffer.pos;','    out.resize(written); written += outBuffer.pos;')]:
  if old not in raw:raise ValueError('mutant source missing')
  src=out/(name+'.cpp');src.write_text(instrument(raw).replace(old,new.replace('out.resize(','labTraceResize(out,')));generated.append(src)
  # Domain-gated mutation fixture: early shrink on a full-output/returning
  # facade can invalidate native spans. Do not execute such an unsafe mutant.
  # The literal nonfull step leaves the full real 8 MiB allocation live; its
  # extra resize is observable without reading undefined bytes or looping.
  target=small if name=='premature-shrink' else fixture
  good=run([original,target],name+'-safe-original') if target==small else normal
  if target==small:
   events=[[int(x) for x in e.split(':')] for e in good.splitlines()[0].rsplit(b'\t',1)[1].decode().split(';') if e]
   steps=[e for e in events if e[0]==1]
   if len(steps)!=1 or steps[0][2]>=steps[0][1] or steps[0][5:]!=[0,0]:raise ValueError('SAFE_MUTANT_DOMAIN')
  bad=run([compile(name,src),target],name);reject(name,bad,good)
 # Exact branches which ordinary codec/output equality did not distinguish.
 controls=[('compress-input-only','finished = ret == 0 && inBuffer.pos == inBuffer.size;','finished = inBuffer.pos == inBuffer.size;',small,1),
 ('drop-full-continue','      continue;','      /* dropped full-output continue */',small,2),
 ('decompress-require-ret0','finished = inBuffer.pos == inBuffer.size;','finished = ret == 0 && inBuffer.pos == inBuffer.size;',trunc,3)]
 for name,old,new,case,mode in controls:
  good=run([original,case,mode],name+'-original');require_same(good,run([reference,case,mode],name+'-reference'))
  require_same(good,run([hosted_binary,case,mode],name+'-hosted'))
  trace=good.splitlines()[0].rsplit(b'\t',1)[1].decode();events=[[int(x) for x in row.split(':')] for row in trace.split(';') if row]
  steps=[e for e in events if e[0] in (1,2)]
  expected=1 if mode==3 else 2
  if len(steps)!=expected:raise ValueError('CONTROL_PRECONDITION step count')
  if mode==1 and not (steps[0][5:]==[0,1] and steps[0][2]<steps[0][1] and steps[0][3]==steps[0][4]):raise ValueError('COUNTERFACTUAL status receipt')
  if mode==2 and not (steps[0][5:]==[0,0] and steps[0][1]==steps[0][2]==12 and steps[0][3]==steps[0][4]):raise ValueError('COUNTERFACTUAL exact span receipt')
  if mode==3 and not (steps[0][5]>0 and steps[0][3]==steps[0][4]):raise ValueError('NATIVE truncated receipt')
  src=out/(name+'.cpp');src.write_text(instrument(raw.replace(old,new)));generated.append(src)
  reject(name,run([compile(name,src),case,mode],name),good)
 # Wrong native host does a REAL additional codec step after pending.
 wrong=out/'host-extra-pending.cpp'
 wrong.write_text(replace(proto,'catch(...) {c.pending=std::current_exception(); return ZC_EXCEPTION;}','catch(...) {c.pending=std::current_exception(); if(c.mode==0 && c.compression && c.steps){labTraceCompress(c.compression,&c.out,&c.in,ZSTD_e_flush); ++c.steps;} return ZC_EXCEPTION;}',1));generated.append(wrong)
 wrong_adapter=out/'extra-pending-adapter.cpp';wrong_adapter.write_text(hosted_path.read_text().replace(str(proto_path),str(wrong)));generated.append(wrong_adapter)
 reject('real-step-after-pending',run([compile('extra-pending',wrong_adapter),faultcase,4],'extra-pending'),fault_original)
 # Observer-integrity negative still executes the real codec, drops ONLY receipt.
 src=out/'missing-receipt-shim.cpp';shim=(HERE/'trace_shim.cpp').read_text()
 src.write_text(replace(shim,'record({1,out->size,out->pos,in->pos,in->size,actual,result});','/* actual codec above still called; receipt deliberately missing */',1));generated.append(src)
 missing=out/'missing-receipt'
 run([link['compiler'],*link['flags'],'-I'+str(HERE),'-include',HERE/'trace_shim.hpp',labpath,sources['original'],src,link['archive'],*link['libraries'],'-Wl,-dead_strip','-o',missing],'missing-receipt-compile')
 reject('missing-real-step-receipt',run([missing,small],'missing-receipt'),run([original,small],'small-normal'))
 reject('verifier-tail',normal+b'bad',normal)
 # Independent literal anchor catches deliberately paired corrupt values even
 # when implementation equality is neutralized. No compression-byte golden.
 anchors=json.loads((values/'anchors.json').read_text());rows={r.split(b'\t')[0].decode():r.split(b'\t') for r in stripped.splitlines()}
 key=next(k for k,w in anchors.items() if w['output']=='616263');corrupt=list(rows[key]);corrupt[2]=b'616264'
 def anchor(row):
  if row[2].decode()!=anchors[key]['output']:raise ValueError('INDEPENDENT literal abc')
 try:anchor(corrupt)
 except ValueError:negative.append('paired-independent-literal')
 else:raise RuntimeError('paired corruption escaped')
 after={name:sha(Path(name)) for name in before};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after:raise ValueError('trace binding drift')
 report=dict(status='PASS_NATIVE_VALUES_AND_TRACE',cases=v['cases'],anchors=v['anchors'],value_sha256=v['ordered_sha256'],trace_sha256=hashlib.sha256(normal).hexdigest(),negative_controls=negative,native_zstd=v['native_zstd'],external_cli=v['external_cli'],bindings=before,generated_sources={str(x):sha(x) for x in generated},runtime_receipts=receipts,limits=['native calibration only, no Rust or gameplay qualification','mode1 return override is counterfactual, mode2 smaller output span is controlled not frozen-source natural buffer','mode3 bounds a genuinely extra-step mutant on actual truncated native frame; not normal-frame completion','resize sentinel after real codec progress is counterfactual, not actual OOM; persistent next call and same exception identity checked','no universal allocator timing, cross-platform, performance or actual Rust/game qualification'])
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['bindings','generated_sources','runtime_receipts']}))
if __name__=='__main__':main()
