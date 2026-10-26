"""Reconstruct the finite native receipt; recorded dictionaries cannot define scope."""
import copy,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run,contract,inventory


def artifact_paths(out,rs,libs):
    paths={out/n for n in ('recipes.json','libraries.json','expected.tsv','initial.json','before.json','after.json','commands.json','compiled-symbols.json','preexecute.json','native','native.map')}
    for n,_,_,_ in run.compile_jobs(rs):paths.update((out/(n+'.d'),out/(n+'.o')))
    for name,_ in run.command_plan(out,rs,libs):
        paths.update(out/(name+ext) for ext in ('.stdout','.stderr','.command.json'))
    for folder,files in (('inputs',contract.fixtures()),('native-cases',contract.final_files()),('repeat-cases',contract.final_files())):
        paths.update(out/folder/name for name in files)
    return paths


def validate(q,out):
    run.need(out.is_relative_to(run.BASE) and out!=run.BASE,'owned receipt root')
    run.originals()
    run.need(q['status']=='FINITE_NATIVE_FILE_CALIBRATION_WITH_GAPS','status')
    run.need(all(type(q[k]) is int and q[k]==n for k,n in (('source_definitions',34),('objects',113),('observations',len(contract.expected().splitlines())))),'scope')
    rs,libs=run.recipe()
    run.need(rs==json.loads((out/'recipes.json').read_text()) and libs==json.loads((out/'libraries.json').read_text()),'configured recipes/libraries')
    run.need((out/'expected.tsv').read_bytes()==contract.expected(),'expected corpus')
    run.audit(out/'inputs',contract.fixtures())
    initial=run.initial_bindings(out,rs,libs)
    run.need(initial==json.loads((out/'initial.json').read_text()),'complete initial closure')
    required={**initial,**run.dependency_bindings(out,rs)}
    # Snapshots are independently associated with each actual source dependency.
    for path,digest in list(required.items()):
        source=Path(path)
        if source.is_relative_to(run.ROOT/'source'):
            snapshot=out/'snapshots'/source.relative_to(run.ROOT)
            run.need(run.sha(snapshot)==digest,'snapshot drift')
            required[str(snapshot)]=digest
    before=json.loads((out/'before.json').read_text());after=json.loads((out/'after.json').read_text())
    run.need(required==before==after==q['bindings'],'complete source/dependency closure')
    expected_artifacts=artifact_paths(out,rs,libs)
    run.need(set(q['artifacts'])==set(map(str,expected_artifacts)),'complete artifact inventory')
    for group in ('bindings','artifacts'):
        for path,digest in q[group].items():run.need(run.sha(path)==digest,'drift '+path)
    commands=q['commands'];plan=run.command_plan(out,rs,libs)
    run.need(commands==json.loads((out/'commands.json').read_text()),'command mirror list')
    run.need([(c['name'],c['command']) for c in commands]==plan,'complete command argv plan')
    for c in commands:
        name=c['name']
        run.need(c==json.loads((out/(name+'.command.json')).read_text()),'command mirror')
        run.need(type(c['returncode']) is int and c['returncode']==0,'normal exit')
        exe=Path(c['command'][0]).resolve()
        run.need(str(exe)==c['executable'] and run.sha(exe)==c['before']==c['after'],'executable identity')
        wanted={'kind':'pipe','size':0,'sha256':hashlib.sha256(b'').hexdigest()} if name in ('native','repeat') else {'kind':'inherit'}
        run.need(c['stdin']==wanted,'owned stdin protocol')
        for stream in ('stdout','stderr'):run.need(run.sha(out/(name+'.'+stream))==c[stream],'command stream')
    pre=json.loads((out/'preexecute.json').read_text())
    removed={out/n for n in ('after.json','commands.json','preexecute.json')}
    removed.update(out/(name+ext) for name in ('native','repeat') for ext in ('.stdout','.stderr','.command.json'))
    expected_pre={p for p in expected_artifacts if p.parent==out}-removed
    run.need(set(pre)==set(map(str,expected_pre)),'complete preexecution artifacts')
    for path,digest in pre.items():run.need(run.sha(path)==digest,'preexecution drift')
    names=sorted({line.split(' T ',1)[1] for line in (out/'symbols.stdout').read_text().splitlines() if ' T Star::File::' in line})
    run.need(names==q['compiled_symbols']==json.loads((out/'compiled-symbols.json').read_text()) and len(names)==34,'compiled symbols')
    for name in ('native','repeat'):
        contract.check((out/(name+'.stdout')).read_bytes())
        run.audit(out/(name+'-cases'),contract.final_files())
    return q


def controls(out,dest):
    dest.mkdir();q=json.loads((out/'report.json').read_text());validate(q,out);results=[]
    dependency=next(p for p in q['bindings'] if p.endswith('/StarFile.hpp') and '/snapshots/' not in p)
    mutations=[('scope',lambda x:x.update(source_definitions=33)),('commands',lambda x:x['commands'].pop()),('exit',lambda x:x['commands'][0].update(returncode=1)),('symbols',lambda x:x['compiled_symbols'].pop()),('binding',lambda x:x['bindings'].update({next(iter(x['bindings'])):'0'*64})),('omitted-dependency',lambda x:x['bindings'].pop(dependency)),('omitted-object',lambda x:x['artifacts'].pop(str(out/'0.o'))),('link-argv',lambda x:next(c for c in x['commands'] if c['name']=='link')['command'].append('-Wl,-undefined,dynamic_lookup')),('scan-argv',lambda x:x['commands'][0]['command'].append('-DWRONG')),('stdin',lambda x:x['commands'][-1].update(stdin={'kind':'inherit'}))]
    for name,mutate in mutations:
        bad=copy.deepcopy(q);mutate(bad);run.dump(dest/(name+'.json'),bad)
        try:validate(bad,out)
        except ValueError as e:results.append({'name':name,'rejected':str(e)})
        else:raise ValueError('control escaped '+name)
    for name,data in [('missing-row',contract.expected().split(b'\n',1)[1]),('wrong-byte',contract.expected().replace(b'default-mode\t0',b'default-mode\t1'))]:
        (dest/(name+'.tsv')).write_bytes(data)
        try:contract.check(data)
        except ValueError as e:results.append({'name':name,'rejected':str(e)})
        else:raise ValueError('oracle control escaped')
    run.dump(dest/'results.json',results)
    return results


if __name__=='__main__':
    out=Path(sys.argv[1]).resolve();q=validate(json.loads((out/'report.json').read_text()),out)
    if len(sys.argv)>2:print(json.dumps(controls(out,Path(sys.argv[2]).resolve()),indent=2))
    else:print(q['status'])
