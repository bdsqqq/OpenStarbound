#!/usr/bin/env python3
"""Fresh production OFF/ON gate. Finite kernel evidence, never game qualification.

Reconstruct required jobs, dependency membership, link inputs and executions;
report dictionaries cannot choose which artifacts or sources are checked.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / 'build/path-embed-rust'
sys.path.insert(0, str(HERE.parent / 'path-embed-replay'))
import acquire as a
import link_witness
OLD = ROOT / 'build/path-embed-native-witness-r1/generation-2'
ARCHIVE = BASE / 'target/release/libstar_engine_ffi.a'
def rust_tool(name):
    return Path(subprocess.check_output([shutil.which('rustup'), 'which', name], text=True).strip())
RUSTC = rust_tool('rustc')
CARGO = rust_tool('cargo')
RUSTFMT = rust_tool('rustfmt')

def rust_inputs():
    import tomllib
    root = ROOT/'source/rust'
    manifest = tomllib.loads((root/'Cargo.toml').read_text())
    paths = {root/'Cargo.toml', root/'Cargo.lock'}
    for member in manifest['workspace']['members']:
        paths.add(root/member/'Cargo.toml')
        paths |= {p for p in (root/member/'src').rglob('*') if p.is_file()}
    toolchain = RUSTC.parent.parent
    paths |= {p for p in (toolchain/'lib').rglob('*') if p.is_file()}
    return paths
MUTATIONS = {
    'wrong-action': ('0 => Action::None,', '0 => Action::Zlib,'),
    'wrong-escape': ("b':' => Some(b'c'),", "b':' => Some(b'x'),"),
}

def safe(path, fresh=False):
    a.need(path.is_absolute() and path == Path(os.path.normpath(path)), 'normalized path')
    a.need(path.is_relative_to(BASE) and path != BASE, 'owned output')
    a.need(not any(p.is_symlink() for p in [path, *path.parents]), 'symlink output')
    if fresh:
        a.need(not path.exists(), 'fresh generation')
    elif path.exists():
        inodes = {}
        for directory, dirs, files in os.walk(path, followlinks=False):
            for name in dirs + files:
                p = Path(directory) / name
                st = p.lstat()
                a.need(not stat.S_ISLNK(st.st_mode), 'output symlink')
                a.need(stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode), 'output special file')
                if stat.S_ISREG(st.st_mode):
                    key = (st.st_dev, st.st_ino)
                    count, links = inodes.get(key, (0, st.st_nlink))
                    a.need(links == st.st_nlink, 'hardlink race')
                    inodes[key] = (count + 1, links)
        a.need(all(count == links for count, links in inodes.values()), 'external hardlink')

def env(out):
    return {'PATH': ':'.join(dict.fromkeys([str(CARGO.parent), str(RUSTC.parent), '/usr/bin', '/bin', '/usr/sbin', '/sbin'])),
            'RUSTC': str(RUSTC), 'HOME': str(out/'home'), 'TMPDIR': str(out/'tmp'), 'LANG': 'C', 'LC_ALL': 'C'}

def invoke(out, name, argv, stdin=b''):
    argv = list(map(str, argv))
    before = a.tool_binding(argv[0])
    p = subprocess.run(argv, cwd=a.native.CM, env=env(out), input=stdin, capture_output=True, timeout=120)
    for suffix, data in [('stdout',p.stdout),('stderr',p.stderr)]:
        with (out/(name+'.'+suffix)).open('xb') as f: f.write(data)
    q = {'name':name,'argv':argv,'cwd':str(a.native.CM),'environment':env(out),
         'tool_before':before,'tool_after':a.tool_binding(argv[0]),
         'stdin':{'size':len(stdin),'sha256':a.digest(stdin)},
         'stdout':a.digest(p.stdout),'stderr':a.digest(p.stderr),
         'exit':p.returncode,'exit_type':'normal' if p.returncode>=0 else 'signal'}
    a.write(out/(name+'.command.json'),q)
    a.equal(q['tool_before'],q['tool_after'],'tool drift')
    a.need(type(p.returncode) is int and p.returncode == 0,'command failed '+name)
    return q

def guard():
    a.need(a.sha(ROOT/'source/core/StarPathEmbed.hpp')=='18b21e801abe3a6211a8e1ef03d0344f04b07c2f2252aa5996db16beb207993b','public header unchanged')
    original=(HERE.parent/'path-embed/original/StarPathEmbed.cpp').read_text()
    a.need(a.digest(original.encode())=='4ac003690deacb5d18e4fed72d990326b02214bd7a84d84998925614cbfbc84d','frozen original')
    source=(ROOT/'source/core/StarPathEmbed.cpp').read_text()
    # Reconstruct the inactive branch by evaluating only our one new selector.
    def project(on):
        active=[True]; result=[]
        for line in source.splitlines(keepends=True):
            if line.strip()=='#ifdef STAR_USE_RUST_PATH_EMBED':active.append(active[-1] and on)
            elif line.strip()=='#else':active[-1]=active[-2] and not active[-1]
            elif line.strip()=='#endif':active.pop()
            elif active[-1]:result.append(line)
        a.need(len(active)==1,'selector nesting')
        return ''.join(result)
    off=project(False)
    # Added blank separators outside the original bodies have no semantics.
    a.need(off==original,'exact OFF body reconstruction')
    on=project(True)
    for expression in ['return base64Encode(data,true);','throw StarException("Compressing data in gzip is unsupported.");','return "zlib;"+base64Encode(compressData(data),true);','return "zstd;"+base64Encode(ZstdCompression::compress(data),true);']:
        a.need(on.count(expression)==1 and original.count(expression)==1,'original leaf '+expression)
    a.need('return nativeLeafTable[action](data);' in on and 'switch (compressionMethod)' not in on,'returned-action dispatch only')
    alloc="auto out = std::string(data.utf8Size()*2,'\\0');"
    a.need(on.index(alloc)<on.index('auto const& in = data.utf8();')<on.index('if (rustEscapeEligible'),'allocation/ref/borrow order')
    loop=original[original.index('  auto outIt = out.begin();'):original.index('  out.resize(len);')].replace('  size_t len = 0;\n','')
    a.need(''.join('  '+line for line in loop.splitlines(keepends=True)) in on,'original unsupported-span loop with indentation only')
    a.need('len > out.size()' in on and 'out.resize(len);\n  return String(std::move(out));' in on,'length and native return')
    a.need('n <= static_cast<size_t>(PTRDIFF_MAX) / 2 &&\n    capacity <= static_cast<size_t>(PTRDIFF_MAX) && capacity >= n * 2;' in on,'native eligibility math')
    cm=(ROOT/'source/CMakeLists.txt').read_text()
    a.need('option(STAR_USE_RUST_PATH_EMBED "Use experimental Rust PathEmbed selection and escaping" OFF)' in cm,'default off')
    a.need('OR STAR_USE_RUST_FILE OR STAR_USE_RUST_PATH_EMBED)' in cm,'single aggregate wiring')
    a.need('if(STAR_USE_RUST_PATH_EMBED)\n  add_compile_definitions(STAR_USE_RUST_PATH_EMBED)\nendif()' in cm,'coherent definition')
    a.need((ROOT/'source/rust/ffi/src/lib.rs').read_text().count('mod path_embed;')==1,'single aggregate module')
    return {'public_functions':['embedAndCompressData','embedEscapeText'],
            'native_leaf_adapters':re.findall(r'^String (\w+Leaf)\(',on,re.M),
            'enum_map':'data, not a compiled function',
            'off_projected_sha256':a.digest(off.encode()),'on_projected_sha256':a.digest(on.encode())}

def materialize(out):
    rust=(ROOT/'source/rust/ffi/src/path_embed.rs').read_text()
    for name,(old,new) in MUTATIONS.items():
        a.need(rust.count(old)==1,'mutant anchor '+name)
        (out/(name+'.rs')).write_text(rust.replace(old,new))
    cpp=(ROOT/'source/core/StarPathEmbed.cpp').read_text()
    (out/'bypass.cpp').write_text(cpp.replace('#ifdef STAR_USE_RUST_PATH_EMBED','#if 0'))
    (out/'inputs.tsv').write_bytes(a.contract.inputs())
    # Expectations are frozen independent byte/Python mapping + old native codec leaves.
    (out/'expected.tsv').write_bytes(a.contract.expected((OLD/'leaf.stdout').read_bytes()))

def recipe(out):
    rs,libs=a.native.recipe()
    a.need(len(rs)==113,'113 configured sources')
    base=next(r for r in rs if Path(r['source']).name=='StarPathEmbed.cpp')
    idx=rs.index(base)
    jobs=[]
    for backend in ['off','on']:
        for i,r in enumerate(rs):
            flags=[*r['flags']]+(['-DSTAR_USE_RUST_PATH_EMBED'] if backend=='on' else [])
            jobs.append((backend+'-'+str(i),r['compiler'],flags,Path(r['source'])))
        flags=[*base['flags']]+(['-DSTAR_USE_RUST_PATH_EMBED'] if backend=='on' else [])
        for driver in ['driver','layout']:
            jobs.append((backend+'-'+driver,base['compiler'],flags,HERE/(driver+'.cpp')))
    flags=[*base['flags'],'-DSTAR_USE_RUST_PATH_EMBED','-I'+str(HERE)]
    for name in ['protocol','sequence']:
        jobs.append((name,base['compiler'],flags,HERE/(name+'.cpp')))
    jobs.append(('bypass',base['compiler'],flags,out/'bypass.cpp'))
    sdk=flags[flags.index('-isysroot')+1]
    cflags=['-x','c','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-arch','arm64','-isysroot',sdk,'-I'+str(HERE),'-I'+str(ROOT/'source/core')]
    jobs.append(('c11',base['compiler'],cflags,HERE/'c11.c'))
    cargo=[str(CARGO),'--manifest-path',str(ROOT/'source/rust/Cargo.toml')]
    # Cargo subcommand precedes the remaining flags.
    common=['--manifest-path',str(ROOT/'source/rust/Cargo.toml'),'--package','star-engine-ffi','--locked','--offline','--target-dir',str(BASE/'target')]
    calls=[('rustc-version',[str(RUSTC),'-vV']),('cargo-version',[str(CARGO),'--version']),
           ('fmt',[str(RUSTFMT),'--edition','2021','--check',str(ROOT/'source/rust/ffi/src/path_embed.rs')]),
           ('unit-debug',[str(CARGO),'test',*common,'path_embed']),
           ('unit-release',[str(CARGO),'test',*common,'--release','path_embed']),
           ('cargo-build',[str(CARGO),'build',*common,'--release'])]
    deps=[('deps-'+n,[c,*f,'-M','-MF',str(out/(n+'.d')),str(s)]) for n,c,f,s in jobs]
    compiles=[('compile-'+n,[c,*f,'-c',str(s),'-o',str(out/(n+'.o'))]) for n,c,f,s in jobs]
    rustmut=[('compile-'+n,[str(RUSTC),'--edition=2021','--crate-type=staticlib','--crate-name','star_path_embed_mutant','-C','panic=unwind','-C','opt-level=3',str(out/(n+'.rs')),'-o',str(out/(n+'.a'))]) for n in MUTATIONS]
    links={}
    variants=['off','on',*MUTATIONS,'bypass','sequence','protocol','c11','off-layout','on-layout']
    for name in variants:
        backend='off' if name in ['off','off-layout'] else 'on'
        objects=[out/(backend+'-'+str(i)+'.o') for i in range(113)]
        if name=='bypass':objects[idx]=out/'bypass.o'
        driver=backend+'-driver' if name in ['off','on',*MUTATIONS,'bypass'] else name
        objects.insert(0,out/(driver+'.o'))
        extra=[] if backend=='off' else [str(out/(name+'.a')) if name in MUTATIONS else str(ARCHIVE)]
        target=out/'links'/name
        links[name]=[base['compiler'],*base['flags'],*map(str,objects),*libs,*extra,'-Wl,-dead_strip','-Wl,-map,'+str(target/'native.map'),'-o',str(target/'native'),'-Wl,-t,-trace_implicit_libraries']
    symbols=[('symbols-'+b,['/usr/bin/nm','-gUC',str(out/(b+'-'+str(idx)+'.o'))]) for b in ['off','on']]
    symbols += [('symbols-linked',['/usr/bin/nm','-gUC',str(out/'links/on/native')])]
    runs=[('run-'+n,[str(out/'links'/n/'native')]) for n in variants]
    runs += [('run-'+n+'-repeat',[str(out/'links'/n/'native')]) for n in ['off','on','protocol','sequence']]
    replays=[('replay-deps-'+n,[c,*f,'-M','-MF','-',str(s)]) for n,c,f,s in jobs]
    return rs,libs,jobs,sdk,calls,deps,compiles,rustmut,links,symbols,runs,replays

def source_paths(out,rs,libs,jobs):
    paths={Path(r['source']).resolve() for r in rs}
    paths|={Path(r['compiler']).resolve() for r in rs}
    paths|={Path(x).resolve() for x in libs if Path(x).is_file()}
    for folder in [HERE,HERE.parent/'path-embed',HERE.parent/'path-embed-boundary',HERE.parent/'path-embed-replay',ROOT/'cmake']:
        paths|={p.resolve() for p in folder.rglob('*') if p.is_file()}
    paths|=rust_inputs()
    paths|={ROOT/'source/CMakeLists.txt',ROOT/'CMakeLists.txt',ROOT/'source/core/StarPathEmbed.hpp',ROOT/'source/core/StarRustPathEmbed.h',HERE.parent/'native_artifacts.py'}
    paths|={a.native.CM/n for n in ['compile_commands.json','build.ninja','CMakeCache.txt']}
    paths|={Path(x).resolve() for x in [sys.executable,RUSTC,CARGO,RUSTFMT,'/usr/bin/nm']}
    paths|={out/(n+'.rs') for n in MUTATIONS}|{out/'bypass.cpp',out/'inputs.tsv',out/'expected.tsv',out/'plan.json'}
    paths|={OLD/'leaf.stdout',OLD/'report.json',BASE/'before-r1/manifest.json'}
    paths|={p for p in (BASE/'before-r1').rglob('*') if p.is_file()}
    for n,c,f,s in jobs:paths|=a.closure.dependencies((out/(n+'.d')).read_bytes(),s,f,a.native.CM)
    return paths

def stdin_for(name):
    return a.contract.inputs() if name in ['run-off','run-on','run-off-repeat','run-on-repeat','run-bypass',*['run-'+n for n in MUTATIONS]] else b''

def expected_routes():
    rows=a.contract.cases()
    return ('route counts '+str(sum(op=='C' for _,op,_,_ in rows))+' '+str(sum(op=='E' for _,op,_,_ in rows))+'\n').encode()

def validate_output(out):
    expected=a.contract.expected((OLD/'leaf.stdout').read_bytes())
    a.need((out/'inputs.tsv').read_bytes()==a.contract.inputs(),'independent inputs')
    a.need((out/'expected.tsv').read_bytes()==expected,'independent expected')
    for name in ['off','on','off-repeat','on-repeat']:
        a.contract.check((out/('run-'+name+'.stdout')).read_bytes(),expected)
        wanted=expected_routes() if name.startswith('on') else b''
        a.need((out/('run-'+name+'.stderr')).read_bytes()==wanted,'genuine selected routes '+name)
    for name in ['protocol','protocol-repeat']:
        a.need((out/('run-'+name+'.stdout')).read_bytes()==b'protocol 26 checks passed; counters selector=4 escape=2\n','protocol')
    for name in ['sequence','sequence-repeat']:
        a.need((out/('run-'+name+'.stdout')).read_bytes()==b'normal-error-normal: exact native exception, selector completed before throw, subsequent calls work\n','native gzip sequence')
    a.need((out/'run-off-layout.stdout').read_bytes()==(out/'run-on-layout.stdout').read_bytes(),'dynamic native layouts')
    rejected=[]
    for name in MUTATIONS:
        try:a.contract.check((out/('run-'+name+'.stdout')).read_bytes(),expected)
        except ValueError as exc:rejected.append({'name':name,'normal_exit':0,'rejected':str(exc)})
        else:raise ValueError('semantic mutant escaped '+name)
    a.contract.check((out/'run-bypass.stdout').read_bytes(),expected)
    a.need((out/'run-bypass.stderr').read_bytes()==b'route counts 0 0\n' and expected_routes()!=b'route counts 0 0\n','native bypass counter rejection')
    rejected.append({'name':'bypass','normal_exit':0,'rejected':'native semantic outputs match but both Rust completion routes are zero'})
    return rejected

def link_verify(out,name,argv,sdk):
    target=out/'links'/name
    r=a.read_json(target/'report.json')
    a.need(r['status']=='FINITE_DRIVER_FIRST_LINK_INPUT_WITNESS_PASS_NOT_NATIVE_CALIBRATION','link witness status')
    inv=a.read_json(target/'invocation-before.json')
    a.equal(inv['argv'],argv,'reconstructed link argv')
    a.equal(inv['cwd'],str(a.native.CM),'link cwd')
    expected_env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(target/'home'),'TMPDIR':str(target/'tmp'),'LANG':'C','LC_ALL':'C'}
    a.equal(inv['environment'],expected_env,'link env')
    a.equal(inv['compiler'],a.tool_binding(argv[0]),'link compiler')
    expansion=subprocess.run([argv[0],'-###',*argv[1:]],cwd=a.native.CM,env=expected_env,capture_output=True,timeout=30)
    a.need(expansion.returncode==0 and expansion.stdout==(target/'expansion.stdout').read_bytes() and expansion.stderr==(target/'expansion.stderr').read_bytes(),'fresh actual driver expansion')
    import shlex
    expanded=[shlex.split(line) for line in expansion.stderr.decode().splitlines() if line.lstrip().startswith('"')]
    a.need(len(expanded)==1,'one expansion')
    a.equal(inv['expanded'],expanded[0],'expanded command')
    a.expanded_invocation.verify(inv['inputs'],expanded[0])
    inventory=inv['inputs']['inventory']
    a.need(inventory['architecture']=='arm64' and inventory['sdk']==sdk,'SDK/architecture')
    objects=[p.encode() for p in inventory['file_inputs'] if p.endswith('.o')]
    a.need(objects==[p.encode() for p in argv if p.endswith('.o')],'ordered actual objects')
    blobs={p.encode():Path(p).read_bytes() for p in inventory['file_inputs'] if p.endswith('.a')}
    tables={p:b''.join(m['name']+b'\n' for m in a.arm64_archive_members(b)) for p,b in blobs.items()}
    a.equal(a.read_json(target/'archive-tables.json'),{p.hex():v.hex() for p,v in tables.items()},'actual archive members')
    trace=a.parse_trace((target/'link.stdout').read_bytes(),objects,tables)
    mapped=a.reconcile_map((target/'native.map').read_bytes(),objects,tables,blobs)
    paths=trace['sdk_paths']+mapped['unresolved_origins']+[row['source'] for row in trace['indirect_declarations']]
    sdk_before=a.read_json(target/'sdk-before.json')
    a.sdk_witness.verify(sdk_before,sdk,a.CANONICAL_SDK)
    a.equal(a.read_json(target/'sdk-after.json'),sdk_before,'SDK after')
    consumed=a.sdk_witness.reconcile_consumed(sdk_before,[os.fsdecode(p) for p in paths],requested_root=sdk,expected_canonical_root=a.CANONICAL_SDK)
    a.equal(a.read_json(target/'consumed.json'),consumed,'SDK consumed')
    required={target/n for n in ['sdk-before.json','sdk-after.json','expansion.stdout','expansion.stderr','invocation-before.json','archive-tables.json','link.stdout','link.stderr','native','native.map','consumed.json']}
    a.equal(r['artifacts'],a.hashes(required),'link artifact closure')
    # witness helpers are also in the independently reconstructed source closure.
    a.equal(inv['sources'],a.hashes({Path(p) for p in inv['sources']}),'link helper drift')
    return {'objects':len(objects),'archive_members':len(trace['archive_members']),'sdk_records':len(consumed),'expanded_files':len(inventory['file_inputs'])}

def all_commands(plan):
    rs,libs,jobs,sdk,calls,deps,compiles,rustmut,links,symbols,runs,replays=plan
    return calls+deps+compiles+rustmut+symbols+runs+replays

def artifact_paths(out,plan):
    rs,libs,jobs,sdk,calls,deps,compiles,rustmut,links,symbols,runs,replays=plan
    paths={out/n for n in ['plan.json','inventory.json','before.json','after.json','sdk-before.json','sdk-after.json','controls.json','archive.json']}
    paths|={out/(n+ext) for n,c,f,s in jobs for ext in ['.d','.o']}
    paths|={out/(n+'.a') for n in MUTATIONS}
    paths|={out/(n+'.'+ext) for n,argv in all_commands(plan) for ext in ['command.json','stdout','stderr']}
    paths|={out/'links'/name/file for name in links for file in ['report.json','sdk-before.json','sdk-after.json','expansion.stdout','expansion.stderr','invocation-before.json','archive-tables.json','link.stdout','link.stderr','native','native.map','consumed.json']}
    return paths

def verify(out,report=None, replay=False):
    safe(out)
    plan=recipe(out);rs,libs,jobs,sdk,calls,deps,compiles,rustmut,links,symbols,runs,replays=plan
    a.equal(a.read_json(out/'inventory.json'),guard(),'source-derived logical inventory')
    serialized={'jobs':jobs,'commands':all_commands(plan),'links':links}
    serialized=json.loads(json.dumps(serialized,default=str))
    a.equal(a.read_json(out/'plan.json'),serialized,'reconstructed complete recipes')
    paths=source_paths(out,rs,libs,jobs)
    # Actual aggregate is bound separately from the source-to-build command.
    paths.add(ARCHIVE)
    snapshots={out/'snapshots'/p.relative_to(ROOT):p for p in paths if p.is_relative_to(ROOT/'source') or p.is_relative_to(ROOT/'cmake')}
    for dest,source in snapshots.items():a.need(dest.read_bytes()==source.read_bytes(),'source snapshot')
    paths|=set(snapshots)
    bindings=a.hashes(paths)
    a.equal(a.read_json(out/'before.json'),bindings,'source before closure')
    a.equal(a.read_json(out/'after.json'),bindings,'source after closure')
    a.sdk_witness.verify(a.read_json(out/'sdk-before.json'),sdk,a.CANONICAL_SDK)
    a.equal(a.read_json(out/'sdk-after.json'),a.read_json(out/'sdk-before.json'),'whole SDK before/after')
    for name,argv in all_commands(plan):
        q=a.read_json(out/(name+'.command.json'))
        a.equal(q['name'],name,'command name');a.equal(q['argv'],argv,'required command argv')
        a.equal(q['cwd'],str(a.native.CM),'command cwd');a.equal(q['environment'],env(out),'command environment')
        a.need(type(q['exit']) is int and q['exit']==0 and q['exit_type']=='normal','normal exit')
        a.equal(q['tool_before'],a.tool_binding(argv[0]),'tool current binding')
        a.equal(q['tool_after'],q['tool_before'],'tool before/after')
        stdin=stdin_for(name)
        a.equal(q['stdin'],{'size':len(stdin),'sha256':a.digest(stdin)},'actual stdin')
        for ext in ['stdout','stderr']:a.need(q[ext]==a.sha(out/(name+'.'+ext)),'stdio bytes')
    for n,c,f,s in jobs:
        a.need((out/(n+'.d')).read_bytes()==(out/('replay-deps-'+n+'.stdout')).read_bytes(),'dependency replay bytes')
    native_source=(ROOT/'source/core/StarPathEmbed.cpp').read_text()
    a.need((out/'bypass.cpp').read_text()==native_source.replace('#ifdef STAR_USE_RUST_PATH_EMBED','#if 0'),'bypass reconstruction')
    rust=(ROOT/'source/rust/ffi/src/path_embed.rs').read_text()
    for name,(old,new) in MUTATIONS.items():a.need((out/(name+'.rs')).read_text()==rust.replace(old,new),'rust mutant reconstruction')
    for backend in ['off','on']:
        syms=(out/('symbols-'+backend+'.stdout')).read_text()
        a.need(len([l for l in syms.splitlines() if ' T Star::embed' in l])==2,'two compiled public functions')
        a.need('Star::EmbeddedCompressionMethodNames' in syms,'enum map is data')
    syms=(out/'symbols-linked.stdout').read_text()
    for name in ['select','escape','completed']:a.need('_star_path_embed_'+name in syms,'actual Rust export '+name)
    archive=a.read_json(out/'archive.json')
    members=a.arm64_archive_members(ARCHIVE.read_bytes())
    a.equal(archive,{'path':str(ARCHIVE),'sha256':a.sha(ARCHIVE),'members':[{'name':m['name'].hex(),'sha256':a.digest(m['body'])} for m in members]},'actual aggregate physical members')
    link_summaries={n:link_verify(out,n,argv,sdk) for n,argv in links.items()}
    controls=validate_output(out)
    a.equal(a.read_json(out/'controls.json'),controls,'normal semantic controls')
    if replay:
        for name,argv in runs:
            p=subprocess.run(argv,cwd=a.native.CM,env=env(out),input=stdin_for(name),capture_output=True,timeout=120)
            a.need(type(p.returncode) is int and p.returncode==0,'replay normal exit')
            a.need(p.stdout==(out/(name+'.stdout')).read_bytes() and p.stderr==(out/(name+'.stderr')).read_bytes(),'fresh execution bytes '+name)
    expected={'status':'FINITE_PRODUCTION_KERNEL_GATE_PASS_PENDING_PARENT_REPLAY','observations':357,'fresh_core_objects':226,'raw_protocol_checks':26,'semantic_controls':3,
              'bindings':bindings,'artifacts':a.hashes(artifact_paths(out,plan)),'links':link_summaries,
              'limits':['not game/application/full-engine qualification','not general pointer validation or arbitrary lifetime/OOM/performance proof','SDK interface bytes, not framework implementations; no transient edit/revert proof','C++17 return lifetime guarantee is source/language-traced; actual destructors not instrumented','huge allocation fallback source-traced only','mutant archives contain the actual mutated pure module only; production uses the single full aggregate']}
    if report is not None:a.equal(report,expected,'independently reconstructed report')
    return expected

def run(out):
    safe(out,True);out.mkdir();(out/'home').mkdir();(out/'tmp').mkdir()
    safe(BASE/'target');safe(BASE/'before-r1')
    materialize(out);inventory=guard();a.write(out/'inventory.json',inventory)
    plan=recipe(out);rs,libs,jobs,sdk,calls,deps,compiles,rustmut,links,symbols,runs,replays=plan
    a.write(out/'plan.json',json.loads(json.dumps({'jobs':jobs,'commands':all_commands(plan),'links':links},default=str)))
    # Source freeze precedes compiler/Cargo entry. Include whole new source files,
    # not a lexical exclusion or report-picked subset.
    initial={p for d in [HERE,ROOT/'source/core',ROOT/'cmake'] for p in d.rglob('*') if p.is_file()}
    initial|=rust_inputs()
    initial|={ROOT/'source/CMakeLists.txt',ROOT/'CMakeLists.txt'}
    initial_hashes=a.hashes(initial)
    for name,argv in calls:invoke(out,name,argv)
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda c:invoke(out,*c),deps))
    a.equal(a.hashes(initial),initial_hashes,'initial source/build drift')
    paths=source_paths(out,rs,libs,jobs)|{ARCHIVE}
    snapshots={out/'snapshots'/p.relative_to(ROOT):p for p in paths if p.is_relative_to(ROOT/'source') or p.is_relative_to(ROOT/'cmake')}
    for dest,source in snapshots.items():dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read_bytes())
    paths|=set(snapshots)
    before=a.hashes(paths);a.write(out/'before.json',before)
    a.write(out/'sdk-before.json',a.sdk_witness.capture(sdk,a.CANONICAL_SDK))
    print('frozen',len(before),'bindings; compiling',len(jobs),'fresh native translation units',flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda c:invoke(out,*c),compiles))
    for call in rustmut:invoke(out,*call)
    for name,argv in links.items():
        link_witness.observe(argv,a.native.CM,out/'links'/name,sdk,a.CANONICAL_SDK)
        print('linked',name,flush=True)
    for name,argv in symbols:invoke(out,name,argv)
    for name,argv in runs:invoke(out,name,argv,stdin_for(name))
    a.write(out/'controls.json',validate_output(out))
    members=a.arm64_archive_members(ARCHIVE.read_bytes())
    a.write(out/'archive.json',{'path':str(ARCHIVE),'sha256':a.sha(ARCHIVE),'members':[{'name':m['name'].hex(),'sha256':a.digest(m['body'])} for m in members]})
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda c:invoke(out,*c),replays))
    a.equal(a.hashes(paths),before,'final source/artifact drift')
    a.write(out/'after.json',a.hashes(paths))
    a.write(out/'sdk-after.json',a.sdk_witness.capture(sdk,a.CANONICAL_SDK))
    # Raw report remains explicitly pending until independent reconstruction succeeds.
    a.write(out/'raw.json',{'status':'RAW_ACQUISITION_COMPLETE_PENDING_VERIFICATION','source_bindings':len(before),'semantic_controls':3})
    report=verify(out,replay=True)
    a.write(out/'report.json',report)
    print(report['status'],a.sha(out/'report.json'),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['run','verify']);parser.add_argument('output');args=parser.parse_args()
    out=Path(args.output).absolute()
    if args.mode=='run':run(out)
    else:
        verify(out,a.read_json(out/'report.json'),replay=True)
        print('independent reconstruction and actual execution replay passed')
