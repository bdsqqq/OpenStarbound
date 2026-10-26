"""Sealed non-destructive supplement; coherent parent objects, no historical rebinding."""
import argparse,json,shlex,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run,contract,audit


def model():
    fixtures={k:v for k,v in contract.fixtures().items() if k.startswith('n')}
    fixtures.update({'initial':b'I','backup.b2':b'B','backup.b3':b'C'})
    expected=b''.join((v.hex()+'\n').encode()*2 for k,v in fixtures.items() if k.startswith('n'))+b'close:other:0\nopen:1\ndestroy:1\nbackup:1\nwrite:1\nabsolute:1\nread:1\n'
    final=dict(fixtures);final.update({'reentry':b'','backup.b3':b'B'})
    return fixtures,expected,final


def plan(out,parent):
    rs,libs=run.recipe();r=next(r for r in rs if Path(r['source']).name=='StarFile.cpp')
    source=run.HERE/'supplement.cpp'
    return [(n,list(map(str,args))) for n,args in [('deps',[r['compiler'],*r['flags'],'-M','-MF',out/'driver.d',source]),('compile',[r['compiler'],*r['flags'],'-c',source,'-o',out/'driver.o']),('link',[r['compiler'],*r['flags'],out/'driver.o',*[parent/(str(i)+'.o') for i in range(113)],*libs,'-Wl,-dead_strip','-o',out/'native']),*[(n,[out/'native',out/(n+'-cases')]) for n in ('native','repeat')]]]


def bindings(out,parent):
    rs,libs=run.recipe()
    paths={p.resolve() for p in run.HERE.iterdir() if p.is_file()}
    paths.update([out/'expected.stdout',out/'driver.d',parent/'report.json',*[parent/(str(i)+'.o') for i in range(113)]])
    paths.update(Path(p).resolve() for p in libs if Path(p).is_file())
    paths.update(Path(r['compiler']).resolve() for r in rs)
    paths.update(run.CM/n for n in ('build.ninja','compile_commands.json','CMakeCache.txt'))
    for word in shlex.split((out/'driver.d').read_text().replace('\\\n',' ').split(':',1)[1]):
        p=Path(word);paths.add((p if p.is_absolute() else run.CM/p).resolve())
    return {str(p):run.sha(p) for p in sorted(paths)}


def verify(out,parent):
    audit.validate(json.loads((parent/'report.json').read_text()),parent)
    q=json.loads((out/'report.json').read_text());fixtures,expected,final=model()
    run.need(q['status']=='SUPPLEMENT_NATIVE_REPEAT_PASS' and q['parent']==str(parent),'supplement scope')
    run.need(q['bindings']==json.loads((out/'before.json').read_text())==json.loads((out/'after.json').read_text())==bindings(out,parent),'complete supplement dependency closure')
    run.need((out/'expected.stdout').read_bytes()==expected,'supplement expected oracle')
    run.need([(c['name'],c['command']) for c in q['commands']]==plan(out,parent),'supplement command plan')
    for group in ('bindings','artifacts'):
        for p,h in q[group].items():run.need(run.sha(p)==h,'supplement drift '+p)
    required={out/'driver.d',out/'driver.o',out/'native',out/'before.json',out/'after.json',out/'expected.stdout'}
    required.update(out/(n+ext) for n,_ in plan(out,parent) for ext in ('.stdout','.stderr','.command.json'))
    for name in ('native','repeat'):
        required.update(out/(name+'-cases')/p for p in final)
        run.audit(out/(name+'-cases'),final)
        run.need((out/(name+'.stdout')).read_bytes()==expected,'supplement ordered output')
    run.need(set(q['artifacts'])==set(map(str,required)),'complete supplement artifacts')
    for c in q['commands']:
        run.need(c==json.loads((out/(c['name']+'.command.json')).read_text()) and type(c['returncode']) is int and c['returncode']==0,'supplement command receipt')
        run.need(str(Path(c['command'][0]).resolve())==c['executable'] and run.sha(c['executable'])==c['before']==c['after'],'supplement executable identity')
        wanted={'kind':'pipe','sha256':run.hashlib.sha256(b'').hexdigest(),'size':0} if c['name'] in ('native','repeat') else {'kind':'inherit'}
        run.need(c['stdin']==wanted,'supplement owned stdin')
        for s in ('stdout','stderr'):run.need(run.sha(out/(c['name']+'.'+s))==c[s],'supplement command stream')
    return q


def acquire(out,parent):
    run.need(out.is_relative_to(run.BASE) and not out.exists(),'fresh supplement')
    audit.validate(json.loads((parent/'report.json').read_text()),parent);out.mkdir()
    fixtures,expected,final=model();(out/'expected.stdout').write_bytes(expected)
    commands=[run.cmd(plan(out,parent)[0][1],'deps',out)]
    before=bindings(out,parent);run.dump(out/'before.json',before)
    for name,args in plan(out,parent)[1:]:
        if name in ('native','repeat'):
            leaf=out/(name+'-cases');leaf.mkdir();(leaf/'backup.b1').mkdir()
            for k,v in fixtures.items():
                with (leaf/k).open('xb') as f:f.write(v)
            run.audit(leaf,fixtures)
        commands.append(run.cmd(args,name,out,b'' if name in ('native','repeat') else None))
        if name in ('native','repeat'):
            run.need((out/(name+'.stdout')).read_bytes()==expected,'supplement oracle');run.audit(leaf,final)
    after={p:run.sha(p) for p in before};run.need(before==after,'supplement source drift');run.dump(out/'after.json',after)
    run.dump(out/'report.json',dict(status='SUPPLEMENT_NATIVE_REPEAT_PASS',parent=str(parent),bindings=before,commands=commands,artifacts={str(p):run.sha(p) for p in out.rglob('*') if p.is_file()}))
    verify(out,parent)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);parser.add_argument('parent',type=Path);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    out,parent=args.output.resolve(),args.parent.resolve()
    if args.verify:verify(out,parent)
    else:acquire(out,parent)
    print('SUPPLEMENT_NATIVE_REPEAT_PASS')
