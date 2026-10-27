#!/usr/bin/env python3
"""bounded CPU-only acquisition; process launches are durable before product inspection."""
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
sys.dont_write_bytecode=True
from common import *

def execute(argv,d,name,deadline=90,env=None,products=(),cli=False):
    d.mkdir(parents=True,exist_ok=True); argv=list(map(str,argv)); exe=Path(argv[0]).resolve(); executable=sha(exe)
    environment=dict(os.environ) if env is None else env
    environment.update(TMPDIR=str(OUT/'tmp'),PYTHONDONTWRITEBYTECODE='1')
    (OUT/'tmp').mkdir(exist_ok=True)
    before_wall=time.time_ns(); before_mono=time.monotonic_ns()
    with (d/(name+'.stdout')).open('xb') as stdout,(d/(name+'.stderr')).open('xb') as stderr:
        p=subprocess.Popen(argv,cwd=d,env=environment,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,start_new_session=True)
        p.stdin.close()
        start=dict(argv=argv,cwd=str(d),environment=environment,pid=p.pid,pgid=os.getpgid(p.pid),startedWallNs=before_wall,startedMonotonicNs=before_mono,deadlineSeconds=deadline,stdin=dict(kind='PIPE',bytes=0,closed=True),executablePath=str(exe),executableSha256=executable,stdout=str(d/(name+'.stdout')),stderr=str(d/(name+'.stderr')))
        write(d/(name+'.start.json'),start)
        timed=False; startup=False
        while p.poll() is None:
            if cli:
                raw=(d/(name+'.stdout')).read_bytes()+(d/(name+'.stderr')).read_bytes()
                startup=any(x in raw for x in (b'Initializing SDL Video',b'Creating SDL window',b'Initializing SDL Audio',b'Compiled with Clang',b'Loading assets'))
            if startup or time.monotonic_ns()-before_mono>deadline*1_000_000_000:
                timed=not startup
                try: os.killpg(p.pid,signal.SIGTERM)
                except ProcessLookupError: pass
                try: p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid,signal.SIGKILL); p.wait(timeout=2)
                break
            time.sleep(0.01)
        code=p.wait(); ended=time.monotonic_ns()
    try: os.killpg(p.pid,0); gone=False
    except ProcessLookupError: gone=True
    # Never leave owned descendants running after a failed auxiliary command.
    if not gone:
        os.killpg(p.pid,signal.SIGKILL)
    row=dict(start=start,exitCode=code,reaped=True,groupGone=gone,timedOut=timed,unexpectedStartup=startup,endedMonotonicNs=ended,endedWallNs=time.time_ns(),executableAfter=sha(exe),stdoutSha256=sha(d/(name+'.stdout')),stderrSha256=sha(d/(name+'.stderr')))
    # Status is persisted even when outputs are missing or an unexpected exit occurs.
    write(d/(name+'.status.json'),row)
    row['products']=snapshot(products) if code==0 and not timed and not startup else {}
    write(d/(name+'.json'),row)
    need(not timed and not startup and gone,'timeout/startup/descendant failure: '+name)
    return row

def main():
    need(not (OUT/'inputs.json').exists(),'fresh acquisition only; preserve earlier failures')
    OUT.mkdir(parents=True,exist_ok=True)
    independent=independent_wave(); write(OUT/'independent-wave.json',independent)
    recipes={side:recipe(side) for side in ('reference','candidate')}
    paths=[*HERE.glob('*.py'),AUDIO,CLI,ROOT/'source/lab/behavior/build_provenance.py',Path(sys.executable).resolve()]
    physical={}
    compiler=Path(recipes['reference']['compiler']); toolroot=compiler.parents[1]
    tools=[toolroot/'bin/ld',toolroot/'bin/nm',toolroot/'bin/otool',toolroot/'lib/libLTO.dylib',*sorted((toolroot/'lib/clang/21/lib/darwin').glob('libclang_rt.osx*'))]
    need(all(p.is_file() for p in tools),'native toolchain/runtime missing')
    sdk=Path(recipes['reference']['flags'][recipes['reference']['flags'].index('-isysroot')+1])
    sdkfiles=[*sorted(sdk.rglob('*.tbd')),sdk/'SDKSettings.json',sdk/'SDKSettings.plist']
    need(len(sdkfiles)>100,'SDK/runtime closure missing'); paths+=tools+sdkfiles
    # Every production/source/tool/archive is frozen before compiler invocation.
    for side,r in recipes.items():
        cm=Path(r['cm']); paths += [ROOT/p for p in r['sourceFiles']]+list(map(Path,r['configuredSources']))+list(map(Path,r['objects']))
        paths += [BASE/side/n for n in ('build-inputs.json','bin/starbound','bin/starbound.behavior-build.json')]+[cm/n for n in ('CMakeCache.txt','build.ninja','compile_commands.json','.ninja_deps')]
        paths += [Path(x['path']) for x in r['tools'].values()]+[Path(x) for x in r['libs'] if x.endswith('.a')]
        physical[side]={p:archive_members(p) for p in dict.fromkeys(x for x in r['libs'] if x.endswith('.a'))}
    before=snapshot(paths); write(OUT/'before-preflight.json',before)
    for side,r in recipes.items():
        d=OUT/'preflight'/side; cm=Path(r['cm'])
        cmd=[r['cache']['CMAKE_MAKE_PROGRAM'],'-C',str(cm),'-t','deps',*[str(Path(p).relative_to(cm)) for p in r['objects']]]
        exact(execute(cmd,d,'ninja-deps',30)['exitCode'],0,'Ninja dependency inspection')
        paths+=dep_paths((d/'ninja-deps.stdout').read_bytes(),cm,r['objects'])
        dep=[r['compiler'],*r['flags'],'-M','-MT','audio-helper',str(AUDIO)]
        exact(execute(dep,d,'helper-deps',30)['exitCode'],0,'precompile helper dependencies')
        paths+=make_deps((d/'helper-deps.stdout').read_bytes(),d)
        expand=[r['compiler'],*r['flags'],'-###','-c',str(AUDIO),'-o',str(OUT/'acquisition'/side/'audio.o')]
        exact(execute(expand,d,'compile-driver',30)['exitCode'],0,'compile driver expansion')
    exact(snapshot(before),before,'source/tool/object drift during preflight')
    frozen=dict(schema=1,sourceRevision='5074db1a',independentWave=independent,recipes=recipes,bindings=snapshot(paths),physicalArchives=physical,sdkFiles=list(map(str,sdkfiles)),toolchainFiles=list(map(str,tools)))
    write(OUT/'inputs.json',frozen)
    for side,r in recipes.items():
        d=OUT/'acquisition'/side; d.mkdir(parents=True); (d/'literal.wav').write_bytes(WAV)
        commands=command_plan(side,r)
        for name in ('archive','compile'):
            products=[d/'native-core-extern.a'] if name=='archive' else [d/'audio.o',d/'audio.d']
            exact(execute(commands[name],d,name,products=products)['exitCode'],0,name+' failed')
        # Actual driver, providers, runtime and SDK are all witnessed before linking.
        exact(execute([r['compiler'],'-###',*commands['link'][1:]],d,'link-driver',30)['exitCode'],0,'link expansion')
        nm=[str(toolroot/'bin/nm'),'-g',str(d/'native-core-extern.a')]
        exact(execute(nm,d,'physical-providers',30)['exitCode'],0,'prelink native physical provider symbols')
        indexes={str(d/'native-core-extern.a'):archive_index(d/'native-core-extern.a')}
        if side=='candidate':
            aggregate=next(x for x in r['libs'] if x.endswith('libstar_engine_ffi.a')); indexes[aggregate]=archive_index(aggregate)
        write(d/'before-link.json',dict(bindings=snapshot([*frozen['bindings'],d/'audio.o',d/'native-core-extern.a']),physicalArchive=archive_members(d/'native-core-extern.a'),physicalSymbolIndexes=indexes,expandedDriverSha256=sha(d/'link-driver.stderr')))
        exact(execute(commands['link'],d,'link',products=[d/'audio',d/'audio.map'])['exitCode'],0,'link failed')
        exact(execute([str(toolroot/'bin/otool'),'-L',str(d/'audio')],d,'runtime-libraries',30)['exitCode'],0,'runtime inspection')
        for name in ('decode','repeat','negative'):
            row=execute(commands[name],d,name,10)
            exact(row['exitCode'],1 if name=='negative' else 0,'PCM exit '+name)
            exact(read(d/(name+'.stdout')),pcm_expected(side,name=='negative'),'PCM fields '+name)
            exact((d/(name+'.stderr')).read_bytes(),BADERR if name=='negative' else b'','PCM stderr')
    for side in ('reference','candidate'):
        for name in NAMES:
            d=OUT/'cli'/side/name; d.mkdir(parents=True); (d/'home').mkdir(); (d/'storage').mkdir(); write(d/'sbinit.config',cli_config(d))
            env=dict(os.environ)
            for k in ('SteamAppId','SteamGameId','STAR_BEHAVIOR_LAB','SDL_AUDIODRIVER','SDL_VIDEODRIVER'): env.pop(k,None)
            # Early-exit source paths precede video/audio. Dummy backends also deny hardware if that contract regresses.
            env.update(HOME=str(d/'home'),XDG_DATA_HOME=str(d/'home/data'),XDG_CONFIG_HOME=str(d/'home/config'),XDG_CACHE_HOME=str(d/'home/cache'),SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
            cmd=[str(BASE/side/'bin/starbound'),'-bootconfig',str(d/'sbinit.config'),*cli_args(name,d)]
            row=execute(cmd,d,'run',10,env=env,cli=True)
            code,out,err=cli_expected(name); exact(row['exitCode'],code,'CLI exit '+name); exact((d/'run.stdout').read_bytes(),out,'CLI literal '+name); exact((d/'run.stderr').read_bytes(),err,'CLI stderr '+name)
    exact(snapshot(frozen['bindings']),frozen['bindings'],'final input drift')
    report=verify(); write(OUT/'report.json',report); print(json.dumps(report,sort_keys=True))

if __name__=='__main__':
    try: main()
    except BaseException as e:
        if not (OUT/'failure.json').exists(): write(OUT/'failure.json',dict(error=repr(e),wallNs=time.time_ns()))
        raise
