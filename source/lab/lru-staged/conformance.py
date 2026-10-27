"""Isolated live controls, retained under the assigned build root.

Every subprocess below goes through acquirer.execute. Expected rejections are
controls, not class acquisition attempts. No temporary-directory default is used.
"""
import copy
import os
import sys

sys.dont_write_bytecode = True
import acquirer as a
import native_plan as np

REPO = os.fsencode(os.path.dirname(os.path.dirname(a.LAB)))
SOURCE = os.fsencode(os.path.dirname(os.path.abspath(__file__)))
BASE = REPO+b'/build/lru-staged-native-r1/controls-r2'
PYTHON = os.fsencode(os.path.realpath(sys.executable))
FILES = tuple(SOURCE+b'/'+n for n in (b'acquirer.py',b'recipe.py',b'worker.py',b'conformance.py'))
SHARED = tuple(os.fsencode(a.LAB)+b'/'+n for n in
               (b'native_plan.py',b'native_evidence_json.py',b'path-embed-replay/sdk_witness.py'))


def mkdir(path):
    os.mkdir(path)


def setup(label, script=b'import sys\nsys.stdout.buffer.write(b"ok\\n")\n',
          expected=b'ok\n', products=None, timeout=5000, extra_inputs=()):
    root = BASE+b'/'+label.encode('ascii')
    mkdir(root)
    for name in (b'work',b'home',b'tmp'):
        mkdir(root+b'/'+name)
    program = root+b'/program.py'
    a.write(program, script)
    products = {} if products is None else {root+b'/'+k:v for k,v in products.items()}
    stage = np.Stage('fixture', (PYTHON,b'-B',program),
                     (PYTHON,program)+FILES+SHARED+extra_inputs,
                     tuple(products)+(root+b'/receipt.typed',root+b'/certificate.typed'),
                     tuple(root+b'/'+name for name in (b'stdout',b'stderr',b'stdin')))
    plan = np.Plan(root, stage.inputs, (stage,))
    command = {'stage_id':'fixture', 'cwd':root+b'/work',
               'env':{b'HOME':root+b'/home',b'TMPDIR':root+b'/tmp',
                      b'LC_ALL':b'C',b'LANG':b'C',b'PYTHONDONTWRITEBYTECODE':b'1'},
               'stdin':b'', 'timeout_ms':timeout, 'failure_action':'stop-preserve',
               'validator':'literal-v1', 'rules':{'stdout':expected,'stderr':b'',
                                                'products':products}}
    return plan, (command,)


def freeze(label, plan, commands, aliases=(PYTHON,)):
    frozen = a.contract(plan, commands, aliases)
    # Outside the plan's process-owned tree, explicitly bootstrap metadata.
    a.emit(BASE+b'/'+label.encode('ascii')+b'.contract.typed', frozen)
    return frozen


RESULTS = {}


def reject(label, fn):
    try:
        fn()
    except (a.Rejected, ValueError, TypeError, OSError) as exc:
        RESULTS[label] = {'rejected':True, 'exception':type(exc).__name__, 'reason':str(exc)}
        return
    raise AssertionError('known bad accepted: '+label)


def run():
    mkdir(BASE)
    # Whole-tree and nested opaque byte transport, physical output, actual
    # command/receipt/semantic certificate, then read-only reconstruction.
    label = 'positive-opaque'
    script = b'import os,sys\np=os.fsencode(os.getcwd())+b"/../opaque-\\xff-\\x93.o"\nwith open(p,"xb") as f:f.write(b"object\\x00bytes")\nsys.stdout.buffer.write(b"ok\\n")\n'
    plan, commands = setup(label, script, products={b'opaque-\xff-\x93.o':b'object\x00bytes'})
    frozen = freeze(label, plan, commands)
    a.execute(frozen)
    replay = a.reconstruct(a.load(BASE+b'/'+label.encode()+b'.contract.typed'))
    a.emit(BASE+b'/positive-reconstruction.typed', replay)
    RESULTS[label] = {'accepted':True,'stages':replay['stages']}
    stage = plan.stages[0]
    command = commands[0]
    good_record = a.load(a.meta(stage)[0])
    for label, key, bad in (
        ('false-as-zero','exit_code',False), ('partial-status','completed',False),
        ('wrong-argv','argv',(PYTHON,b'wrong')), ('wrong-env','env',{}),
        ('wrong-stdin','stdin',b'changed'), ('wrong-membership','outputs',()),
        ('unreaped','reaped',False), ('wrong-pgid','pgid',1),
        ('no-process-interval','elapsed_ns',-1)):
        record = dict(good_record)
        record[key] = bad
        reject(label, lambda r=record:a.admit(frozen,stage,command,r,plan.initial_inputs))
    # A complete downstream plan exists before the first process; semantic
    # rejection must prevent the dependent command from being launched.
    from dataclasses import replace
    plan2, commands2 = setup('semantic-before-dependent', expected=b'wrong\n')
    first = plan2.stages[0]
    root = plan2.owned_root
    second = np.Stage('forbidden-dependent', (PYTHON,b'-B',root+b'/program.py'),
                      first.inputs+first.outputs,
                      (root+b'/second.receipt',root+b'/second.certificate'),
                      tuple(root+b'/second.'+s for s in (b'out',b'err',b'in')),
                      ('fixture',))
    second_command = dict(commands2[0],stage_id='forbidden-dependent')
    frozen2 = freeze('semantic-before-dependent',replace(plan2,stages=(first,second)),commands2+(second_command,))
    reject('semantic-before-dependent',lambda:a.execute(frozen2))
    assert not any(os.path.lexists(p) for p in second.writes)
    RESULTS['dependent-not-started'] = {'verified':True}
    # Pre-process physical mutation controls use isolated prebound objects.
    for kind in ('missing','stale','replaced','symlink','hardlink'):
        root = BASE+b'/input-'+kind.encode()
        mkdir(root)
        obj = root+b'/input.o'
        a.write(obj,b'initial')
        p,c = setup('physical-'+kind,extra_inputs=(obj,))
        f = freeze('physical-'+kind,p,c)
        # Never overwrite/delete retained nodes. rename preserves the original
        # and models a missing/replaced input in this isolated owned fixture.
        if kind == 'stale':
            st = os.stat(obj)
            os.utime(obj,ns=(st.st_atime_ns,st.st_mtime_ns+1000000))
        else:
            os.rename(obj,obj+b'.retained-original')
            if kind == 'replaced':a.write(obj,b'initial')
            elif kind == 'symlink':os.symlink(obj+b'.retained-original',obj)
            elif kind == 'hardlink':os.link(obj+b'.retained-original',obj)
        reject('physical-'+kind,lambda f=f:a.execute(f))
        assert not os.path.lexists(a.meta(p.stages[0])[0])
    p,c = setup('escape-log')
    escaped = replace(p.stages[0], logs=(BASE+b'/outside-log',)+p.stages[0].logs[1:])
    reject('escape-log',lambda:a.contract(replace(p,stages=(escaped,)),c,(PYTHON,)))
    # Process exits zero but creates undeclared output: no credit.
    p,c = setup('unexpected-output',b'import sys\nwith open("extra","xb") as f:f.write(b"unexpected")\nsys.stdout.buffer.write(b"ok\\n")\n')
    f = freeze('unexpected-output',p,c)
    reject('unexpected-output',lambda:a.execute(f))
    # Process mutates a declared input: recheck occurs before semantic credit.
    p,c = setup('input-mutation',b'import os,sys\np=os.fsencode(__file__)\nos.rename(p,p+b".retained")\nwith open(p,"xb") as f:f.write(b"replacement")\nsys.stdout.buffer.write(b"ok\\n")\n')
    f = freeze('input-mutation',p,c)
    reject('input-mutation',lambda:a.execute(f))
    # Live runtime/plugin is an immutable bound input; alias chain is separately
    # frozen, so an unchanged target payload cannot hide a changed hop.
    runtime_dir = BASE+b'/runtime-inputs'
    mkdir(runtime_dir)
    runtime = runtime_dir+b'/libLTO.dylib'
    a.write(runtime,b'fixture-plugin-not-an-actual-dylib')
    tool = runtime_dir+b'/python-alias'
    os.symlink(PYTHON,tool)
    p,c = setup('runtime-drift',extra_inputs=(runtime,))
    f = freeze('runtime-drift',p,c,(PYTHON,tool))
    os.rename(runtime,runtime+b'.retained')
    a.write(runtime,b'changed-fixture-plugin')
    reject('runtime-input-changed',lambda:a.execute(f))
    p,c = setup('alias-drift')
    f = freeze('alias-drift',p,c,(PYTHON,tool))
    os.rename(tool,tool+b'.retained')
    intermediate = runtime_dir+b'/intermediate'
    os.symlink(PYTHON,intermediate)
    os.symlink(intermediate,tool)
    reject('alias-chain-changed',lambda:a.execute(f))
    # Timeout: only the newly owned session is signaled. Parent explicitly
    # waits its child after group TERM; both IDs must be gone afterward.
    script = b'''import os,signal,sys,time
child=os.fork()
if child == 0:
    time.sleep(30)
    os._exit(0)
def stop(sig,frame):
    os.waitpid(child,0)
    sys.exit(0)
signal.signal(signal.SIGTERM,stop)
print(os.getpid(),child,os.getpgrp(),flush=True)
time.sleep(30)
'''
    p,c = setup('timeout-descendants',script,timeout=500)
    f = freeze('timeout-descendants',p,c)
    reject('timeout-descendants',lambda:a.execute(f))
    record = a.load(a.meta(p.stages[0])[0])
    parent,child,pgid = map(int,record['stdout'].split())
    assert parent == pgid == record['pid'] and record['reaped'] is True and record['group_gone'] is True
    for pid in (parent,child):
        try:os.kill(pid,0)
        except ProcessLookupError:pass
        else:raise AssertionError('owned PID survives timeout')
    RESULTS['timeout-owned-ids-reaped'] = {'verified':True,'parent':parent,'child':child,'pgid':pgid}
    # Corrupt certificate in a fresh retained fixture. Renaming preserves the
    # valid original, and the same read-only reconstructor rejects corruption.
    p,c = setup('corrupt-reconstruction')
    f = freeze('corrupt-reconstruction',p,c)
    a.execute(f)
    assert a.reconstruct(f)['stages'] == ('fixture',)
    cert = a.meta(p.stages[0])[1]
    os.rename(cert,cert+b'.retained-valid')
    a.emit(cert,{'caller_asserted':'PASS'})
    reject('corrupt-reconstruction',lambda:a.reconstruct(f))
    # The strict record checks above are also exercised by reconstruction,
    # rather than only by direct admission calls.
    p,c = setup('bool-exit-reconstruction')
    f = freeze('bool-exit-reconstruction',p,c)
    a.execute(f)
    receipt = a.meta(p.stages[0])[0]
    record = a.load(receipt)
    os.rename(receipt,receipt+b'.retained-valid')
    record['exit_code'] = False
    a.emit(receipt,record)
    reject('bool-exit-reconstruction',lambda:a.reconstruct(f))
    a.emit(BASE+b'/conformance.typed',{'format':'lru-machinery-controls-v1','results':RESULTS,
           'class_acquisitions_started':0,'unsuccessful_mechanical_attempts_total':1,
           'class_execution_admitted':False,
           'not_covered':('whole expanded runtime/libLTO membership omission',
                          'SDK unknown consumed origin','physical archive ambiguity',
                          'actual dispatch provider/surviving call edge',
                          'production dependency/source/SDK closure')})
    print('machinery controls:',len(RESULTS),'class executions: 0; remaining class barriers OPEN')


if __name__ == '__main__':
    run()
