#!/usr/bin/env python3
"""Finite native-only OptionParser calibration; no production selectors or app starts."""
import argparse,hashlib,json,os,shlex,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;REV='0a428508'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def anchors(data):
 rows={}
 for l in data.decode().splitlines():
  i,k,v=l.split('\t');rows.setdefault(i,[]).append((k,bytes.fromhex(v)))
 def check(i,want):
  if rows.get(i)!=want:raise ValueError('literal anchor '+i+': '+repr(rows.get(i)))
 err=lambda s:('error',s.encode());done=('done',b'')
 check('unknown',[err("No such option '-wat'"),done]);check('missing',[err("Option '-p' must be followed by an argument"),done])
 check('duplicate',[('parameter',b'p'),('value',b'one'),('argument',b'tail'),err("Option with argument '-p' specified multiple times"),err('Too many positional arguments given, expected at most 0 got 1'),done])
 check('param-end',[('parameter',b'p'),('value',b'--'),err("No such option '-wat'"),done])
 check('switch',[('switch',b's'),done]);check('ends',[('argument',b'-s'),err('Too many positional arguments given, expected at most 0 got 1'),done])
 check('dash',[('switch',b'-help'),('switch',b''),done])
 check('required',[err("No such option '-wat'"),err("Missing required flag with argument '-z'"),err("Missing required flag with argument '-a'"),err('Too few positional arguments given, expected at least 1 got 0'),done])
 check('multiple-empty',[err('Too few positional arguments given, expected at least 1 got 0'),done]);check('multiple-many',[('argument',b'x'),('argument',b'y'),('argument',b'z'),done])
 base=b'cmd: sum\n\nCommand Line Usage: cmd [-verbose] -output <FILE> <target>\n  -verbose\t- v\n  -output <FILE>\t- out\n  <target>\t- tgt\n\nextra\n'
 check('help',[('help',base)])
 check('parameter-collisions',[('registration-error',b"(OptionParserException) Duplicate switch '-p' added"),('registration-error',b"(OptionParserException) Duplicate flag '-p' added"),('help',b'Command Line Usage: [-p <VALUE>]\n  -p <VALUE>\t- original\n'),('parameter',b'p'),('value',b'kept'),done])
 chunks=[b'cmd: sum\n\n',b'Command Line Usage: cmd [-verbose] -output <FILE> <target>\n',b'  -verbose\t- v\n',b'  -output <FILE>\t- out\n',b'  <target>\t- tgt\n',b'\nextra\n']
 if [v for k,v in rows['stream0'] if k=='trace']!=[('xsputn:'+str(len(c))+':'+c.hex()).encode() for c in chunks]:raise ValueError('format insertion chunk anchor')
 if [v for k,v in rows['stream0'] if k=='tie']!=[b'sync']*6:raise ValueError('tied stream sentries')
 for m in [3,5,11]:
  d=dict(rows['stream'+str(m)]);prefix=b''.join(chunks[:2])+(chunks[2][:-1] if m==3 else b'')
  if d['bytes']!=prefix:raise ValueError('late fault prefix')
 for m in [10,11]:
  if dict(rows['stream'+str(m)])['escaped']!=b'none':raise ValueError('exception mask suppression')
 for m in [12,13]:
  if dict(rows['stream'+str(m)])['bytes']!=b'........'+base:raise ValueError('right/internal alignment anchor')
 for m in range(4):check('metadata'+str(m),[('help',[b'Command Line Usage:\n',b'n:\n\nCommand Line Usage: n\n',b's\n\nCommand Line Usage:\n',b'n: s\n\nCommand Line Usage: n\n'][m])])
 for m in [0,1,2,3,4,5,9]:
  r=rows['stream'+str(m)]; d=dict(r)
  if d['escaped']!=(b'sentinel' if m in [4,5] else b'none'):raise ValueError('sentinel identity')
  if m==0 and d['bytes']!=base:raise ValueError('normal stream bytes')
  if m==1 and d['bytes']!=base.replace(b'cmd: sum\n\n',b'cmd: sum\n\n........',1):raise ValueError('width literal')
  if m==2 and d['bytes']!=b'cmd: sum\n':raise ValueError('short-write prefix')
  if m==4 and d['bytes']!=b'':raise ValueError('throw prefix')
  if m==9 and d['bytes']!=b'':raise ValueError('failed stream suppression')
 # Ordered option storage is std::list: append preserves the active iterator/end.
 if dict(rows['stream14'])['bytes']!=base.replace(b'  <target>',b'  -during\t- during-desc\n  <target>'):raise ValueError('active option-description insertion')
 # Positional vector append is restricted to before its own loop begins.
 d=dict(rows['stream6']);want=base.replace(b'Command Line Usage: cmd [-verbose] -output <FILE> <target>',b'Command Line Usage: NEW [-verbose] -output <FILE> [-early] <target> [<more>]');want=want.replace(b'  <target>',b'  -early\t- early-desc\n  <target>');want=want.replace(b'\nextra\n',b'  <more>\t- more-desc\n\nlate\n')
 if d['bytes']!=want:raise ValueError('header callback late-read anchor')
 d=dict(rows['stream7']);want=base.replace(b'  <target>',b'  -late\t- late-desc\n  <target>');want=want.replace(b'\nextra\n',b'  <latearg>\t- latearg-desc\n\nlate-extra\n')
 if d['bytes']!=want:raise ValueError('usage callback late definitions anchor')
 if dict(rows['stream8'])['nested']!=base:raise ValueError('nested help')
 return len(rows)
def current_source_matches(ext, src, current):
 if ext=='hpp':return current==src
 if current==src:return True
 # Only the unique top-level selector's fallback may carry the original body.
 depth=0;starts=[];ends=[];offset=0
 for line in current.splitlines(keepends=True):
  directive=line.strip().split(maxsplit=1)[0] if line.strip() else b''
  if directive in (b'#if',b'#ifdef',b'#ifndef'):depth+=1
  elif directive==b'#else':
   if depth<=0:return False
   if depth==1:starts.append(offset+len(line))
  elif directive==b'#endif':
   if depth<=0:return False
   if depth==1:ends.append(offset)
   depth-=1
  offset+=len(line)
 if depth or len(starts)!=1 or len(ends)!=1:return False
 prefix,body=src.split(b'namespace Star {',1)
 fallback=current[starts[0]:ends[0]]
 return (b'STAR_USE_RUST_OPTION_PARSER' in current[:starts[0]] and
         current.startswith(prefix) and current[ends[0]:]==b'#endif\n' and
         fallback==b'namespace Star {'+body)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path);ap.add_argument('--identity-manifest',type=Path,default=ROOT/'build/zstd-lab/cpp-postbuild-r1/before.json');a=ap.parse_args();out=a.output.absolute();base=ROOT/'build/option-parser-lab'
 if out==base or not out.is_relative_to(base) or out.exists() or any(p.is_symlink() for p in [out,*out.parents]):ap.error('fresh owned nonsymlink output required')
 out.mkdir(parents=True);commands=[];receipts=[];controls=[]
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(shlex.join(cmd));exe=Path(cmd[0]).resolve();e=sha(exe);r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=80);(out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
  if sha(exe)!=e:raise RuntimeError('executable changed')
  receipts.append(dict(name=name,command=cmd,returncode=r.returncode,executable_sha256=e,stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_sha256=hashlib.sha256(r.stderr).hexdigest()))
  (out/'receipts.json').write_text(json.dumps(receipts,indent=2))
  if r.returncode:raise RuntimeError(name+' failed; not a successful negative control')
  return r.stdout
 def gate(ext,raw,ref):
  src=subprocess.check_output(['git','show',REV+':source/core/StarOptionParser.'+ext],cwd=ROOT);want=src.replace(b'namespace Star {',b'namespace OptionReference {\nusing namespace Star;')
  if ext=='cpp':want=want.replace(b'"StarOptionParser.hpp"',b'"StarOptionParser.reference.hpp"')
  if raw!=src or ref!=want or not current_source_matches(ext,src,(ROOT/('source/core/StarOptionParser.'+ext)).read_bytes()):raise ValueError('source provenance mismatch')
 for ext in ['cpp','hpp']:
  raw=(HERE/('StarOptionParser.original.'+ext)).read_bytes();ref=(HERE/('StarOptionParser.reference.'+ext)).read_bytes();gate(ext,raw,ref)
  try:gate(ext,raw+b' ',ref)
  except ValueError:controls.append('source-provenance-'+ext)
  else:raise RuntimeError('provenance verifier failed')
  try:gate(ext,raw,ref+b' ')
  except ValueError:controls.append('reference-provenance-'+ext)
  else:raise RuntimeError('reference provenance verifier failed')
 cm=ROOT/'build/behavior/reference/cmake';db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarOptionParser.cpp'));recipe=shlex.split(entry['command']);flags=[];skip=False
 for x in recipe[1:]:
  if skip:skip=False;continue
  if x=='-o':skip=True
  elif x not in ['-c',entry['file']]:flags.append(x)
 if any('STAR_USE_RUST' in x for x in flags):raise RuntimeError('non-native recipe')
 lines=(cm/'build.ninja').read_text().splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('build ') and '/bin/starbound:' in l)
 objs=[cm/x for x in shlex.split(lines[i].split(': ',1)[1])[1:] if x.endswith('.o') and x.startswith(('core/','extern/')) and not x.endswith('/StarOptionParser.cpp.o')]
 libs=shlex.split(next(l.split(' = ',1)[1] for l in lines[i+1:i+15] if l.startswith('  LINK_LIBRARIES = ')));libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
 identity=[db,cm/'build.ninja',Path(recipe[0]).resolve(),*objs,*[Path(x) for x in libs if x.endswith('.a')]];sealed=json.loads(a.identity_manifest.read_text())
 supplementary=ROOT/'build/shell-lab/cpp-final-r2/before.json';old=json.loads(supplementary.read_text());zp=(cm/'core/CMakeFiles/star_core.dir/StarZSTDCompression.cpp.o').resolve();sealed[str(zp)]=old[str(zp)]
 for p in identity:
  if sealed.get(str(p.resolve()))!=sha(p):raise RuntimeError('native sealed identity drift '+str(p))
 tracked=[ROOT/'source/core/StarOptionParser.cpp',ROOT/'source/core/StarOptionParser.hpp',Path(__file__),HERE/'lab.cpp',a.identity_manifest,supplementary,Path(sys.executable).resolve(),Path('/usr/bin/ar').resolve(),*identity,*[HERE/('StarOptionParser.'+k+'.'+e) for k in ['original','reference'] for e in ['cpp','hpp']]]
 for n,s in enumerate([HERE/'lab.cpp',HERE/'StarOptionParser.original.cpp',HERE/'StarOptionParser.reference.cpp']):
  dep=out/(str(n)+'.d');run([recipe[0],*flags,'-I'+str(HERE),'-M','-MF',dep,s],'deps'+str(n));tracked += [Path(x) if Path(x).is_absolute() else ROOT/x for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1])]
 tracked=list(dict.fromkeys(p.resolve() for p in tracked));before={str(p):sha(p) for p in tracked};(out/'before.json').write_text(json.dumps(before,indent=2));archive=out/'native-core.a';run(['/usr/bin/ar','rcs',archive,*objs],'archive');archive_sha=sha(archive);binaries={};generated={}
 def compile(name,source,reference=False):
  binary=out/name;generated[str(source)]=sha(source);run([recipe[0],*flags,'-I'+str(HERE),*(['-DLAB_REFERENCE=1'] if reference else []),HERE/'lab.cpp',source,archive,*libs,'-Wl,-dead_strip','-o',binary],name+'-compile');binaries[str(binary)]=sha(binary);(out/'artifacts.json').write_text(json.dumps(dict(generated=generated,binaries=binaries),indent=2));return binary
 original=compile('original',HERE/'StarOptionParser.original.cpp');reference=compile('reference',HERE/'StarOptionParser.reference.cpp',True);candidate=compile('candidate',ROOT/'source/core/StarOptionParser.cpp')
 baseline=run([original],'original');count=anchors(baseline)
 for exe,name in [(original,'repeat'),(reference,'reference'),(candidate,'candidate')]:
  got=run([exe],name);anchors(got)
  if got!=baseline:raise ValueError('whole ordered stream mismatch '+name)
 # Known bad isolated output fixture validates the literal checker itself.
 broken=baseline.replace(b"4e6f2073756368206f7074696f6e20272d77617427",b"626164",1);(out/'known-bad.stdout').write_bytes(broken)
 try:anchors(broken)
 except ValueError:controls.append('isolated-known-bad')
 else:raise RuntimeError('literal verifier failed')
 source=(HERE/'StarOptionParser.original.cpp').read_text();mutants={
 'endflags':source.replace('if (arg == "--")','if (!endOfFlags && arg == "--")'),
 'consume':source.replace('String val = it.next();','String val;').replace('result.parameters[std::move(flag)].append(std::move(val));','val = it.next();\n        result.parameters[std::move(flag)].append(std::move(val));'),
 'dedup':source.replace('parameter.requirementMode != Multiple && result.parameters.contains(flag)','false'),
 'required':source.replace('na.requirementMode == Required &&','false &&'),
 'minimum':source.replace('if (argument.requirementMode == Required)','if (false)'),
 'error-order':source.replace('errors.append(strf("Missing required flag', 'errors.insertAt(0, strf("Missing required flag'),
 'one-dash':source.replace('String flag = arg.substr(1);','String flag = arg.substr(2);'),
 'stream-suppression':source.replace('void OptionParser::printHelp(std::ostream& os) const {','void OptionParser::printHelp(std::ostream& os) const {\n os.clear();'),
 'enum3':source.replace('else\n      cmdLineText += strf(" [<{}>...]", p.argumentName);','else if (p.requirementMode == Multiple)\n      cmdLineText += strf(" [<{}>...]", p.argumentName);'),
 'description-snapshot':source.replace('  for (auto const& p : m_options) {\n    if (p.second.is<Switch>()) {\n      auto const& sw', '  auto frozenOptions=m_options;\n  for (auto const& p : frozenOptions) {\n    if (p.second.is<Switch>()) {\n      auto const& sw'),
 'late-read':source.replace('void OptionParser::printHelp(std::ostream& os) const {','void OptionParser::printHelp(std::ostream& os) const {\n  auto m_commandName=this->m_commandName; auto m_summary=this->m_summary; auto m_additionalHelp=this->m_additionalHelp; auto m_options=this->m_options; auto m_arguments=this->m_arguments;'),
 }
 for name,body in [('write','auto s=strf(f,args...);os.write(s.data(),s.size());'),('fragment','auto s=strf(f,args...);for(char c:s) os << c;')]:
  helper='template<typename... T> void labformat(std::ostream& os,fmt::format_string<T...> f,T&&... args){'+body+'}\n'
  mutants[name]=source.replace('namespace Star {','namespace Star {\n'+helper).replace('format(os,','labformat(os,')
 for name,text in mutants.items():
  fixture=out/(name+'.cpp');fixture.write_text(text);exe=compile(name,fixture);got=run([exe],name)
  if got==baseline:raise RuntimeError('compiled mutant escaped '+name)
  controls.append(name)
 # Paired corruption defeats only comparison, never the independent anchors.
 paired=out/'paired-corruption.cpp';paired.write_text(mutants['required']);exe=compile('paired-corruption',paired);wrong=run([exe],'paired-corruption')
 paired_exe=compile('paired-corruption-candidate',paired);paired_wrong=run([paired_exe],'paired-corruption-candidate')
 if wrong!=paired_wrong:raise RuntimeError('paired corruption did not neutralize comparison')
 try:anchors(wrong)
 except ValueError:controls.append('paired-corruption-literal')
 else:raise RuntimeError('paired wrong source escaped literal anchor')
 after={str(p):sha(p) for p in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
 if before!=after or sha(archive)!=archive_sha or any(sha(Path(p))!=h for p,h in {**generated,**binaries}.items()):raise RuntimeError('bound artifact drift')
 report=dict(status='FINITE_NATIVE_CALIBRATION_PASS',revision=REV,cases=count,controls=controls,ordered_sha256=hashlib.sha256(baseline).hexdigest(),bindings=before,generated=generated,binaries=binaries,archive_sha256=archive_sha,commands=commands,receipts=receipts,link=dict(compiler=recipe[0],flags=flags,libraries=libs,archive=str(archive)),limits=['No Rust, production integration, application startup, screenshots, OOM, allocator, timing, resource or platform universality claim','Finite public-state and ostream observations; no private object layout inspection','Invalid UTF8 only in native String constructor domain; native errors preserved','RequirementMode 3 within representable 0..3 range; no arbitrary out-of-range enum values','No iterator-invalidating active positional vector append; defined active list-backed option insertion is tested','Streambuf traces observable writes/sentries, not suppressed internal format function entry attempts; no allocation or destruction timing proof'])
 (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ['status','cases','controls','ordered_sha256']}))
if __name__=='__main__':main()
