"""literal auxiliary contracts and read-only artifact reconstruction; never launches tools."""
import ast
import hashlib
import io
import json
import os
import shlex
import struct
import sys
import wave
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OWN = ROOT/'build/lru-auxiliary-r1'
OUT = OWN/'r2'
BASE = ROOT/'build/behavior/lru-cache-combined-r1'
AUDIO = ROOT/'source/lab/bytes/audio.cpp'
CLI = ROOT/'source/lab/behavior/option_parser_cli.py'
sys.path.insert(0, str(ROOT/'source/lab/behavior'))
import build_provenance as bp
WAV = bytes.fromhex('524946463400000057415645666d74201000000001000100401f0000803e00000200100064617461100000000080c7cfffff000001003930ff7f0000')
PCM = [-32768,-12345,-1,0,1,12345,32767,0]
NAMES = ('help','help-with-error','unknown','missing','duplicate','end-markers')
HASHES = {'reference':'474bf23fe963e18b493263fb064e788c84c1b2f4432f0b96bec2b9122cbc8c6a','candidate':'053f787a5e03589b5b9dea25b37be8e823cedc2254136b0792cd32baebaa7263'}
BADERR = b'COMPARISON pcm/metadata/end/seek/receipt mismatch\n'
def need(ok, why):
    if not ok: raise ValueError(why)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()
def read(p): return json.loads(Path(p).read_bytes())
def write(p,v):
    p=Path(p); need(p.is_relative_to(OWN) or p.is_relative_to(HERE),'write outside ownership')
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f: json.dump(v,f,indent=2,sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
def same(a,b):
    if type(a) is not type(b): return False
    if type(a) is dict: return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    if type(a) is list: return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b
def exact(a,b,label): need(same(a,b),label)
def snapshot(paths): return {str(Path(p).absolute()):sha(p) for p in sorted(set(map(str,paths)))}
def independent_wave():
    with wave.open(io.BytesIO(WAV)) as w:
        exact([w.getnchannels(),w.getframerate(),w.getsampwidth(),w.getnframes()],[1,8000,2,8],'independent stdwave metadata')
        exact(list(struct.unpack('<8h',w.readframes(8))),PCM,'independent stdwave samples')
    return dict(wavBytes=len(WAV),pcmBytes=16,channels=1,rate=8000,samples=PCM)
def literals():
    ns={}; tree=ast.parse(CLI.read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('PREAMBLE','HELP','ERRORS') for t in n.targets)]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<source-cli-literals>','exec'),ns)
    return ns

def cli_expected(name):
    ns=literals(); good=name in NAMES[:2]
    return (0 if good else 1,ns['PREAMBLE']+(ns['HELP'] if good else ('Error: '+ns['ERRORS'][name]+'\n\n').encode()+ns['HELP']),b'')
def cli_args(name,d): return {'help':['-help'],'help-with-error':['-help','-wat'],'unknown':['-wat'],'missing':['-loglevel'],'duplicate':['-bootconfig',str(d/'unselected.config')],'end-markers':['--','--','-wat']}[name]
def cli_config(d): return dict(assetDirectories=[],assetSources=[],storageDirectory=str(d/'storage'),logDirectory=str(d/'storage'),includeUGC=False)
def pcm_expected(side,bad=False): return dict(channels=1,rate=8000,samples=8,read=8,eof=0,end=8,pcm=PCM,receipts=[0,0,0,0,17,0] if side=='candidate' else [0]*6,seek_verified=not bad)
def archive_members(path):
    data=Path(path).read_bytes(); need(data[:8]==b'!<arch>\n','archive magic'); at=8; result=[]
    while at<len(data):
        h=data[at:at+60]; need(len(h)==60 and h[58:60]==b'`\n','archive header')
        size=int(h[48:58]); body=data[at+60:at+60+size]; need(len(body)==size,'archive truncation')
        name=h[:16].decode().strip(); start=at+60
        if name.startswith('#1/'):
            n=int(name[3:]); name=body[:n].rstrip(b'\0').decode(); body=body[n:]; start+=n
        else: name=name.rstrip('/')
        if name not in ('__.SYMDEF','__.SYMDEF SORTED',''):
            result.append(dict(name=name,headerOffset=at,payloadOffset=start,size=len(body),sha256=hashlib.sha256(body).hexdigest()))
        at+=60+size+(size%2)
    exact(at,len(data),'archive end'); return result

def archive_index(path):
    """BSD ranlib offsets name physical members without decoding newer LLVM bitcode."""
    data=Path(path).read_bytes(); need(data[:8]==b'!<arch>\n','archive index magic')
    h=data[8:68]; size=int(h[48:58]); body=data[68:68+size]; name=h[:16].decode().strip()
    if name.startswith('#1/'):
        n=int(name[3:]); name=body[:n].rstrip(b'\0').decode(); body=body[n:]
    need(name in ('__.SYMDEF','__.SYMDEF SORTED'),'BSD archive symbol table')
    n=struct.unpack_from('<I',body)[0]; need(n%8==0 and 8+n<=len(body),'ranlib size')
    count=struct.unpack_from('<I',body,4+n)[0]; strings=body[8+n:8+n+count]; exact(len(strings),count,'ranlib strings')
    members={m['headerOffset']:m for m in archive_members(path)}; result={}
    for at in range(4,4+n,8):
        offset,member=struct.unpack_from('<II',body,at); need(member in members and offset<len(strings),'physical ranlib provider')
        end=strings.index(b'\0',offset); symbol=strings[offset:end].decode(); result.setdefault(symbol,[]).append(members[member])
    return result

def recipe(side):
    cm=BASE/side/'cmake'; proof=read(BASE/side/'bin/starbound.behavior-build.json'); initial=read(BASE/side/'build-inputs.json')
    exact(proof['binary'],str(BASE/side/'bin/starbound'),'game path')
    exact(sha(proof['binary']),HASHES[side],'fresh game SHA'); exact(proof['binary_sha256'],HASHES[side],'sidecar SHA')
    sources=bp.source_snapshot(ROOT); exact(len(sources),1499,'source count'); exact(proof['source_files'],sources,'source seal'); exact(initial['source_files'],sources,'configured source seal')
    configured=bp._compile_source_inputs(cm); exact(len(configured),472,'configured count'); exact(proof['compile_source_files'],configured,'configured sources'); exact(initial['compile_source_files'],configured,'prebuild configured sources')
    exact(proof['build_identity'],initial['build_identity'],'prebuild identity')
    for p,h in proof['build_identity']['files'].items(): exact(sha(p),h,'recipe identity')
    for row in proof['build_identity']['tools'].values(): exact(sha(row['path']),row['sha256'],'build tool')
    selectors={k:v for k,v in proof['build_identity']['cache'].items() if k.startswith('STAR_USE_RUST_') and not k.endswith('-ADVANCED')}
    exact(len(selectors),26,'selectors count')
    for k,v in selectors.items(): exact(v,'OFF' if side=='reference' or k=='STAR_USE_RUST_LINE_QUERY' else 'ON','selector '+k)
    db=read(cm/'compile_commands.json'); entry=next(e for e in db if e['file'].endswith('/StarAudio.cpp')); command=shlex.split(entry['command']); flags=[]; it=iter(command[1:])
    for x in it:
        if x=='-o': next(it)
        elif x not in ('-c',entry['file']): flags.append(x)
    need('-O3' in flags and '-ffast-math' in flags,'production flags')
    lines=(cm/'build.ninja').read_text().splitlines(); i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
    objects=[str(cm/t) for t in shlex.split(lines[i].split(': ',1)[1])[1:] if t.endswith('.o') and t.startswith(('core/','extern/'))]
    exact(len(objects),113,'fresh object count'); exact(len(set(objects)),113,'unique objects')
    libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+16] if x.startswith('  LINK_LIBRARIES = ')))
    libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
    aggregates=[x for x in libs if x.endswith('libstar_engine_ffi.a')]
    exact(aggregates,[str(cm/'rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a')] if side=='candidate' else [],'actual singleton aggregate')
    return dict(cm=str(cm),compiler=command[0],flags=flags,objects=objects,libs=libs,sourceFiles=sources,configuredSources=configured,tools=proof['build_identity']['tools'],cache=proof['build_identity']['cache'])

def dep_paths(raw,cm,objects):
    files=[]; seen=[]; obj=None
    for line in raw.decode().splitlines():
        if not line: continue
        if not line.startswith('    '):
            need('deps ' in line and '(VALID)' in line,'stale/missing dependency block')
            obj=cm/line.split(': #deps',1)[0]; seen.append(str(obj))
        else:
            p=Path(line.strip()); p=p if p.is_absolute() else cm/p
            need(obj.stat().st_mtime_ns>=p.stat().st_mtime_ns,'dependency newer than object: '+str(p)); files.append(p)
    exact(seen,objects,'exact object dependencies'); return files

def make_deps(raw,cwd):
    tokens=shlex.split(raw.decode().replace('\\\n',' ').split(':',1)[1]); need(tokens,'empty compile dependency closure')
    return [Path(t) if Path(t).is_absolute() else cwd/t for t in tokens]

def command_plan(side,r):
    d=OUT/'acquisition'/side; a=d/'native-core-extern.a'; o=d/'audio.o'; exe=d/'audio'; mp=d/'audio.map'
    compile=[r['compiler'],*r['flags'],'-MD','-MF',str(d/'audio.d'),'-c',str(AUDIO),'-o',str(o)]
    link=[r['compiler'],*r['flags'],str(o),str(a),*r['libs'],'-Wl,-dead_strip','-Wl,-map,'+str(mp),'-o',str(exe)]
    return dict(archive=[r['tools']['CMAKE_AR']['path'],'rcs',str(a),*r['objects']],compile=compile,link=link,decode=[str(exe)],repeat=[str(exe)],negative=[str(exe),'corrupt-expected-pcm'])

def check_receipt(d,name,argv,expected_code=None):
    p=d/(name+'.json'); row=read(p); start=read(d/(name+'.start.json'))
    exact({k:v for k,v in row.items() if k!='products'},read(d/(name+'.status.json')),'durable status consistency')
    exact(start['argv'],argv,'argv'); exact(row['start'],start,'durable launch consistency'); exact(start['cwd'],str(d),'cwd')
    need(type(start['pid']) is int and start['pid']>1 and start['pgid']==start['pid'],'actual PID/PGID')
    need(type(start['startedWallNs']) is int and type(start['startedMonotonicNs']) is int,'start clocks')
    exact(start['stdin'],dict(kind='PIPE',bytes=0,closed=True),'empty owned PIPE stdin')
    need(start['deadlineSeconds'] in (10,30,90),'explicit bounded deadline')
    exact(start['executableSha256'],sha(Path(argv[0]).resolve()),'executed tool/binary')
    exact(row['executableAfter'],start['executableSha256'],'tool drift')
    need(row['reaped'] is True and row['groupGone'] is True and row['timedOut'] is False and row['unexpectedStartup'] is False,'normal process completion')
    need(row['endedMonotonicNs']>=start['startedMonotonicNs'],'end clock')
    need(row['endedMonotonicNs']-start['startedMonotonicNs']<=start['deadlineSeconds']*1_000_000_000,'deadline exceeded')
    if expected_code is not None: exact(row['exitCode'],expected_code,'normal exit')
    for suffix in ('stdout','stderr'): exact(row[suffix+'Sha256'],sha(d/(name+'.'+suffix)),'stdio hash')
    return row

def verify(freeze=None):
    f=read(OUT/'inputs.json') if freeze is None else freeze
    independent_wave(); exact(f['independentWave'],independent_wave(),'independent WAV')
    for p,h in f['bindings'].items(): exact(sha(p),h,'frozen source/artifact: '+p)
    required=set(str(p) for p in HERE.glob('*.py'))|{str(AUDIO),str(CLI),str(ROOT/'source/lab/behavior/build_provenance.py'),str(Path(sys.executable).resolve())}
    need(required<=set(f['bindings']),'omitted mandatory input binding')
    rows=[]; clirows=[]
    for side in ('reference','candidate'):
        r=recipe(side); exact(r,f['recipes'][side],'fresh recipe reconstruction'); cm=Path(r['cm']); d=OUT/'acquisition'/side
        required.update(str(ROOT/p) for p in r['sourceFiles']); required.update(r['configuredSources']); required.update(r['objects'])
        required.update(str(BASE/side/n) for n in ('build-inputs.json','bin/starbound','bin/starbound.behavior-build.json'))
        required.update(str(cm/n) for n in ('CMakeCache.txt','build.ninja','compile_commands.json','.ninja_deps'))
        required.update(row['path'] for row in r['tools'].values()); required.update(x for x in r['libs'] if x.endswith('.a'))
        depscmd=[r['cache']['CMAKE_MAKE_PROGRAM'],'-C',str(cm),'-t','deps',*[str(Path(p).relative_to(cm)) for p in r['objects']]]
        check_receipt(OUT/'preflight'/side,'ninja-deps',depscmd,0)
        required.update(map(str,dep_paths((OUT/'preflight'/side/'ninja-deps.stdout').read_bytes(),cm,r['objects'])))
        required.update(map(str,make_deps((OUT/'preflight'/side/'helper-deps.stdout').read_bytes(),OUT/'preflight'/side)))
        pre=OUT/'preflight'/side
        check_receipt(pre,'helper-deps',[r['compiler'],*r['flags'],'-M','-MT','audio-helper',str(AUDIO)],0)
        check_receipt(pre,'compile-driver',[r['compiler'],*r['flags'],'-###','-c',str(AUDIO),'-o',str(d/'audio.o')],0)
        check_receipt(d,'link-driver',[r['compiler'],'-###',*command_plan(side,r)['link'][1:]],0)
        toolroot=Path(r['compiler']).parents[1]
        check_receipt(d,'physical-providers',[str(toolroot/'bin/nm'),'-g',str(d/'native-core-extern.a')],0)
        check_receipt(d,'runtime-libraries',[str(toolroot/'bin/otool'),'-L',str(d/'audio')],0)
        bl=read(d/'before-link.json')
        exact(bl['bindings'],snapshot([*f['bindings'],d/'audio.o',d/'native-core-extern.a']),'prelink inputs')
        exact(bl['physicalArchive'],archive_members(d/'native-core-extern.a'),'prelink archive physical members')
        indexes={str(d/'native-core-extern.a'):archive_index(d/'native-core-extern.a')}
        if side=='candidate':
            agg=next(x for x in r['libs'] if x.endswith('libstar_engine_ffi.a')); indexes[agg]=archive_index(agg)
            for symbol in ('_star_bytes_transform','_star_bytes_call_count','_rust_eh_personality'):
                exact(len(indexes[agg].get(symbol,[])),1,'singleton physical provider '+symbol)
        exact(bl['physicalSymbolIndexes'],indexes,'prelink physical symbol providers')
        exact(bl['expandedDriverSha256'],sha(d/'link-driver.stderr'),'expanded linker bytes')
        expanded=(d/'link-driver.stderr').read_text()
        need(str(toolroot/'lib/libLTO.dylib') in expanded and str(toolroot/'bin/ld') in expanded,'expanded compiler linker/libLTO')
        expected_members={p:archive_members(p) for p in dict.fromkeys(x for x in r['libs'] if x.endswith('.a'))}
        exact(f['physicalArchives'][side],expected_members,'physical input archive payloads/providers')
        commands=command_plan(side,r)
        for name,argv in commands.items():
            check_receipt(d,name,argv,1 if name=='negative' else 0)
            receipt=read(d/(name+'.json'))
            outputs={'archive':[d/'native-core-extern.a'],'compile':[d/'audio.o',d/'audio.d'],'link':[d/'audio',d/'audio.map']}.get(name,[])
            exact(receipt['products'],snapshot(outputs),'immediate produced products')
        members=archive_members(d/'native-core-extern.a')
        exact([(m['name'],m['sha256']) for m in members],[(Path(p).name,sha(p)) for p in r['objects']],'113 physical object payloads')
        for p in make_deps((d/'audio.d').read_bytes(),d): exact(f['bindings'].get(str(p)),sha(p),'unfrozen helper dependency')
        exact((d/'literal.wav').read_bytes(),WAV,'literal fixture')
        for name in ('decode','repeat','negative'):
            exact(read(d/(name+'.stdout')),pcm_expected(side,name=='negative'),'literal PCM metadata/seek/end/counters')
            exact((d/(name+'.stderr')).read_bytes(),BADERR if name=='negative' else b'','PCM stderr')
        mp=(d/'audio.map').read_text(); need('StarAudio.cpp.o' in mp and 'Audio' in mp,'production Audio map origin')
        if side=='candidate': need('libstar_engine_ffi.a(' in mp and 'star_bytes' in mp,'actual singleton Rust conversion provider')
        rows.append(dict(backend=side,binarySha256=sha(d/'audio'),archiveSha256=sha(d/'native-core-extern.a'),result=read(d/'decode.stdout'),wavBytes=60,pcmBytes=16))
        for name in NAMES:
            q=OUT/'cli'/side/name; exact(read(q/'sbinit.config'),cli_config(q),'sandbox bootconfig')
            cmd=[str(BASE/side/'bin/starbound'),'-bootconfig',str(q/'sbinit.config'),*cli_args(name,q)]
            code,out,err=cli_expected(name); row=check_receipt(q,'run',cmd,code)
            environment=row['start']['environment']
            for k,v in dict(HOME=str(q/'home'),XDG_DATA_HOME=str(q/'home/data'),XDG_CONFIG_HOME=str(q/'home/config'),XDG_CACHE_HOME=str(q/'home/cache'),SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy').items(): exact(environment.get(k),v,'CLI isolated '+k)
            need(all(k not in environment for k in ('SteamAppId','SteamGameId','STAR_BEHAVIOR_LAB')),'CLI ambient game environment')
            exact((q/'run.stdout').read_bytes(),out,'literal HELP/error stdout'); exact((q/'run.stderr').read_bytes(),err,'CLI stderr')
            need(not list((q/'storage').rglob('*')),'CLI unexpectedly wrote storage')
            clirows.append(dict(backend=side,case=name,exitCode=row['exitCode'],stdoutSha256=row['stdoutSha256'],pid=row['start']['pid']))
    # Membership is reconstructed, not inferred from the report's input keys.
    r=f['recipes']['reference']; compiler=Path(r['compiler']); toolroot=compiler.parents[1]
    sdk=Path(r['flags'][r['flags'].index('-isysroot')+1])
    sdkfiles=[*sorted(sdk.rglob('*.tbd')),sdk/'SDKSettings.json',sdk/'SDKSettings.plist']
    tools=[toolroot/'bin/ld',toolroot/'bin/nm',toolroot/'bin/otool',toolroot/'lib/libLTO.dylib',*sorted((toolroot/'lib/clang/21/lib/darwin').glob('libclang_rt.osx*'))]
    exact(f['sdkFiles'],list(map(str,sdkfiles)),'SDK stub membership'); exact(f['toolchainFiles'],list(map(str,tools)),'native runtime/tool membership')
    required.update(map(str,sdkfiles+tools))
    need(required<=set(f['bindings']),'omitted mandatory input binding')
    exact(len(clirows),12,'CLI count'); exact({k:v for k,v in rows[0]['result'].items() if k!='receipts'},{k:v for k,v in rows[1]['result'].items() if k!='receipts'},'native/candidate fields')
    return dict(status='FINITE_FRESH_LRU_PCM_12CLI_PASS',sourceRevision='5074db1a',sourceCount=1499,configuredCount=472,pcm=rows,cli=clirows,inputBindings=len(f['bindings']),limits=['conversion calls, not mixer; no Ogg/device/resampling/full audio port claim','CLI exits after SDL_Init(0), before SDL video/controller/audio/window initialization','local source/object/dependency binding, not reproducible-build or signed attestation','host dyld shared-cache runtime bytes not independently attested; SDK TBDs and compiler runtime/libLTO files bound','actual TCP/save/BTree/PNG and Universe interoperability are separate gates'])

if __name__=='__main__':
    result=verify(); exact(read(OUT/'report.json'),result,'report reconstruction'); print(json.dumps(result,sort_keys=True))
