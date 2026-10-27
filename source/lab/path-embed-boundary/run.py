#!/usr/bin/env python3
"""Private native boundary acquisition; no Rust or application qualification."""
import copy,json,subprocess,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.dont_write_bytecode=True
from reuse import a,ROOT,OLD,verify_reuse
import link_witness
HERE=Path(__file__).resolve().parent
BASE=ROOT/'build/path-embed-boundary-r1'
MUTATIONS={
 'wrong-action':('reference.cpp','case 0: selected = PE_NONE;','case 0: selected = PE_ZLIB;'),
 'wrong-escape':('reference.cpp',"case ':': replacement = 'c';","case ':': replacement = 'x';"),
 'stop-nul':('reference.cpp','i < n; ++i','i < n && input[i]; ++i'),
 'bypass':('reference.cpp','size_t len = 0;','*written = 0; ++completed[1]; return PE_OK; size_t len = 0;'),
 'wrong-order':('lifetime.cpp',"auto action=select(method); events+='R';","events+='R'; auto action=select(method);")}

def guard():
    a.need(a.sha(ROOT/'source/core/StarPathEmbed.cpp')=='4ac003690deacb5d18e4fed72d990326b02214bd7a84d84998925614cbfbc84d','original cpp')
    a.need(a.sha(ROOT/'source/core/StarPathEmbed.hpp')=='18b21e801abe3a6211a8e1ef03d0344f04b07c2f2252aa5996db16beb207993b','original hpp')
    source=(HERE/'facade.cpp').read_text();original=(ROOT/'source/core/StarPathEmbed.cpp').read_text()
    expressions=['return base64Encode(data,true);','throw StarException("Compressing data in gzip is unsupported.");','return "zlib;"+base64Encode(compressData(data),true);','return "zstd;"+base64Encode(ZstdCompression::compress(data),true);']
    for e in expressions:a.need(source.count(e)==1 and original.count(e)==1,'exact original leaf '+e)
    a.need('constexpr NativeLeaf nativeLeafTable[] = {noneLeaf, gzipLeaf, zlibLeaf, zstdLeaf};' in source,'frozen typed leaf order')
    a.need('return nativeLeafTable[action](data);' in source,'dispatch returned action')
    allocation="auto out = std::string(data.utf8Size()*2,'\\0');"
    a.need(source.index(allocation)<source.index('auto const& in = data.utf8();')<source.index('if (pe_span_eligible'),'allocation/ref/entry order')
    a.need('out.resize(len);\n  return String(std::move(out));' in source,'native return construction')
    driver=(ROOT/'source/lab/path-embed/lab.cpp').read_text().replace('#include "StarPathEmbed.hpp"','#include "facade.hpp"').replace('output=embedEscapeText(', 'output=PathEmbedBoundary::escape(').replace('output=embedAndCompressData(', 'output=PathEmbedBoundary::compress(')
    a.need((HERE/'driver.cpp').read_text()==driver,'driver only renames target calls')

def plan(out,rs,libs):
    base=next(r for r in rs if Path(r['source']).name=='StarPathEmbed.cpp')
    flags=[*base['flags'],'-I'+str(HERE)]
    jobs=[(n,HERE/(n+'.cpp'),flags) for n in ('reference','facade','driver','protocol','wrap','lifetime','sequence')]
    jobs += [(n,out/(n+'.cpp'),flags) for n in MUTATIONS]
    cflags=['-x','c','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-arch','arm64','-isysroot',flags[flags.index('-isysroot')+1],'-I'+str(HERE)]
    jobs += [('c11',HERE/'c11.c',cflags)]
    calls=[]
    for n,s,f in jobs:calls.append(('deps-'+n,[base['compiler'],*f,'-M','-MF',str(out/(n+'.d')),str(s)]))
    for n,s,f in jobs:calls.append(('compile-'+n,[base['compiler'],*f,'-c',str(s),'-o',str(out/(n+'.o'))]))
    variants={'boundary':['driver','facade','reference'],'sequence':['sequence','facade','reference'],
              'protocol':['protocol','reference'],'wrap':['wrap'],'lifetime':['lifetime'],'c11':['c11','reference'],
              'wrong-order':['wrong-order']}
    for n in MUTATIONS:
        if n!='wrong-order':variants[n]=['driver','facade',n]
    links={}
    for name,own in variants.items():
        # Always retain genuine original definitions in the accepted Core set.
        objects=[str(out/(n+'.o')) for n in own]+[str(OLD/(str(i)+'.o')) for i in range(113)]
        target=out/'links'/name
        links[name]=[base['compiler'],*base['flags'],*objects,*libs,'-Wl,-dead_strip','-Wl,-map,'+str(target/'native.map'),'-o',str(target/'native'),'-Wl,-t,-trace_implicit_libraries']
    return jobs,calls,links

def run(out):
    a.need(out.is_relative_to(BASE) and out!=BASE and not out.exists(),'fresh owned generation')
    out.mkdir();(out/'home').mkdir();(out/'tmp').mkdir()
    guard()
    for name,(file,before,after) in MUTATIONS.items():
        s=(HERE/file).read_text();a.need(s.count(before)==1,'mutant source anchor '+name)
        (out/(name+'.cpp')).write_text(s.replace(before,after))
    expected=a.contract.expected((OLD/'leaf.stdout').read_bytes());inputs=a.contract.inputs()
    (out/'expected.tsv').write_bytes(expected);(out/'inputs.tsv').write_bytes(inputs)
    state,reused_before,sdk_before=verify_reuse(out)
    rs,libs,oldjobs,sdk,oldplan,oldlinks,olddeps,oldpaths,oldbindings=state
    jobs,calls,links=plan(out,rs,libs)
    a.write(out/'plan.json',{'commands':calls,'links':links})
    source_paths={p for p in HERE.iterdir() if p.is_file()}|{out/(n+'.cpp') for n in MUTATIONS}|{out/'expected.tsv',out/'inputs.tsv',out/'plan.json'}
    source_before=a.hashes(source_paths);a.write(out/'source-before.json',source_before)
    # Compiler dependency output is captured before source freeze and replayed
    # after execution; no prior public header is mixed with a changed layout.
    for call in calls[:len(jobs)]:a.invoke(out,*call)
    newdeps=set()
    for n,s,f in jobs:newdeps|=a.closure.dependencies((out/(n+'.d')).read_bytes(),s,f,a.native.CM)
    all_before=a.hashes(source_paths|newdeps);a.write(out/'before.json',all_before)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda c:a.invoke(out,*c),calls[len(jobs):]))
    a.equal(a.hashes(source_paths|newdeps),all_before,'compile source drift')
    for name,argv in links.items():
        link_witness.observe(argv,a.native.CM,out/'links'/name,sdk,a.CANONICAL_SDK)
        print('linked private',name,flush=True)
    runs=[]
    for name in links:
        stdin=inputs if name in ('boundary','wrong-action','wrong-escape','stop-nul','bypass') else b''
        a.invoke(out,'run-'+name,[out/'links'/name/'native'],stdin);runs.append(name)
    a.invoke(out,'run-boundary-repeat',[out/'links/boundary/native'],inputs)
    a.contract.check((out/'run-boundary.stdout').read_bytes(),expected)
    a.contract.check((out/'run-boundary-repeat.stdout').read_bytes(),expected)
    a.need((out/'run-lifetime.stdout').read_bytes()==b'SRTEVtHv|SRTXtC\n','synthetic deleted-copy/move temporary sequence')
    rejections=[]
    for name in MUTATIONS:
        wanted=b'SRTEVtHv|SRTXtC\n' if name=='wrong-order' else expected
        try:a.contract.check((out/('run-'+name+'.stdout')).read_bytes(),wanted)
        except ValueError as exc:rejections.append({'name':name,'normal_exit':0,'rejected':str(exc)})
        else:raise ValueError('semantic control escaped '+name)
    a.invoke(out,'symbols',['/usr/bin/nm','-gUC',out/'links/boundary/native'])
    symbols=(out/'symbols.stdout').read_text()
    for symbol in ('_pe_select','_pe_escape','PathEmbedBoundary::compress(','PathEmbedBoundary::escape('):
        a.need(symbol in symbols,'linked native symbol '+symbol)
    original_index=next(i for i,r in enumerate(rs) if Path(r['source']).name=='StarPathEmbed.cpp')
    a.invoke(out,'original-symbols',['/usr/bin/nm','-gUC',OLD/(str(original_index)+'.o')])
    original_symbols=(out/'original-symbols.stdout').read_text()
    for symbol in ('Star::embedEscapeText(','Star::embedAndCompressData(','Star::EmbeddedCompressionMethodNames'):
        a.need(symbol in original_symbols,'genuine original Core object symbol '+symbol)
    # Same actual command validator detects a changed compiler argument; source
    # closure control removes a dependency from a cloned manifest.
    def validate_manifest(b,commands):
        a.equal(b,a.hashes(source_paths|newdeps),'required private source/dependency membership')
        a.equal(commands,[(n,argv) for n,argv in calls],'required private compiler argv')
    validate_manifest(all_before,calls)
    for label,b,c in [('closure',dict(list(all_before.items())[1:]),calls),('argument',all_before,copy.deepcopy(calls))]:
        if label=='argument':c[0][1].append('-DUNAUTHORIZED_ARGUMENT')
        control=out/(label+'-control.json');a.write(control,{'bindings':b,'commands':c})
        clone=a.read_json(control)
        try:validate_manifest(clone['bindings'],clone['commands'])
        except ValueError as exc:rejections.append({'name':label,'rejected':str(exc)})
        else:raise ValueError('manifest control escaped')
    for n,s,f in jobs:
        replay=a.invoke(out,'replay-deps-'+n,[calls[0][1][0],*f,'-M','-MF','-',s])
        a.need((out/('replay-deps-'+n+'.stdout')).read_bytes()==(out/(n+'.d')).read_bytes(),'private dependency replay')
    a.equal(a.hashes(source_paths|newdeps),all_before,'final private drift')
    a.equal(a.hashes(oldpaths),reused_before,'final accepted native drift')
    a.equal(a.sdk_witness.capture(sdk,a.CANONICAL_SDK),sdk_before,'final SDK drift')
    for argv,b in oldbindings.items():a.equal(a.expanded_invocation.bind(list(argv)),b,'final accepted driver drift')
    for name,argv in links.items():
        invocation=a.read_json(out/'links'/name/'invocation-before.json')
        a.expanded_invocation.verify(invocation['inputs'],invocation['expanded'])
    a.write(out/'after.json',a.hashes(source_paths|newdeps))
    a.write(out/'reuse-final.json',a.hashes(oldpaths))
    a.write(out/'controls.json',rejections)
    artifacts={p for p in out.rglob('*') if p.is_file()}
    report={'status':'FINITE_PRIVATE_NATIVE_BOUNDARY_CHECKS_PASS_PENDING_PARENT_REPLAY','revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
      'observations':357,'reused_configured_objects':113,'fresh_private_translation_units':len(jobs),
      'normal_semantic_controls':5,'manifest_controls':2,'reuse_controls':2,
      'bindings':all_before,'artifacts':a.hashes(artifacts),
      'limits':['not Rust or application acceptance','synthetic lifetime probe is a C++17 language-pattern witness, not actual String/ByteArray destruction or OOM proof',
      'codec leaf bytes reused, not codec reproof','SDK interfaces only; no framework implementation/transient-edit/other-platform/universal proof','unsupported huge native allocation/fallback not executed','native stack-trace bytes may differ; exact exception dynamic type and what literal checked']}
    a.write(out/'report.json',report)
    print(report['status'],a.sha(out/'report.json'),flush=True)

if __name__=='__main__':run(Path(sys.argv[1]).absolute())
