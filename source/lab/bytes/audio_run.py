#!/usr/bin/env python3
"""Decode a literal WAV through compiled production Audio; no game/audio device."""
import argparse, hashlib, io, json, shlex, struct, subprocess, wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
WAV=bytes.fromhex('524946463400000057415645666d74201000000001000100401f0000803e00000200100064617461100000000080c7cfffff000001003930ff7f0000')
PCM=[-32768,-12345,-1,0,1,12345,32767,0]
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cmake',type=Path,required=True);ap.add_argument('--backend',choices=['cpp','rust'],required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--reference-report',type=Path);a=ap.parse_args()
    out=a.output.resolve();cm=a.cmake.resolve()
    if not out.is_relative_to(ROOT/'build/bytes-audio') or out==ROOT/'build/bytes-audio':ap.error('output must be nested in build/bytes-audio')
    out.mkdir(parents=True,exist_ok=True)
    # The independent decoder runs BEFORE any native build or candidate execution.
    with wave.open(io.BytesIO(WAV)) as w:
        assert (w.getnchannels(),w.getframerate(),w.getsampwidth(),w.getnframes())==(1,8000,2,8)
        assert list(struct.unpack('<8h',w.readframes(8)))==PCM
    (out/'literal.wav').write_bytes(WAV)
    db=cm/'compile_commands.json';entry=next(e for e in json.loads(db.read_text()) if e['file'].endswith('/StarAudio.cpp'))
    recipe=shlex.split(entry['command']);flags=[];skip=False
    for f in recipe[1:]:
        if skip:skip=False;continue
        if f=='-o':skip=True
        elif f not in ['-c',entry['file']]:flags.append(f)
    active=any(f.startswith('-DSTAR_USE_RUST_BYTES') for f in flags)
    if active != (a.backend=='rust'):raise RuntimeError('compiled recipe backend mismatch')
    ninja=cm/'build.ninja';lines=ninja.read_text().splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('build ') and '/bin/starbound:' in x)
    # CMake uses OBJECT libraries here, not a pre-existing core .a. Package the
    # exact existing native objects into an ISOLATED archive; never rebuild them.
    objects=[cm/t for t in shlex.split(lines[i].split(': ',1)[1])[1:] if t.endswith('.o') and (t.startswith('core/') or t.startswith('extern/'))]
    if not objects or any(not x.is_file() for x in objects):raise RuntimeError('native core/extern objects not ready; no shared build started')
    libs=shlex.split(next(x.split(' = ',1)[1] for x in lines[i+1:i+15] if x.startswith('  LINK_LIBRARIES = ')))
    # Resolve CMake-relative archive names without changing them.
    libs=[str(cm/x) if x.endswith('.a') and not Path(x).is_absolute() else x for x in libs]
    if a.backend=='rust' and not any('star_engine_ffi' in x for x in libs):raise RuntimeError('native Rust aggregate missing from exact link recipe')
    tracked=[Path(__file__).resolve(),HERE/'audio.cpp',db,ninja,Path(recipe[0]).resolve(),*objects,*(Path(x) for x in libs if x.endswith('.a')),ROOT/'source/core/StarAudio.cpp',ROOT/'source/core/StarAudio.hpp',ROOT/'source/core/StarBytes.hpp',ROOT/'source/core/StarRustBytes.h',ROOT/'source/rust/ffi/src/bytes.rs',ROOT/'source/rust/ffi/src/lib.rs']
    tracked += [p for p in (ROOT/'source/core').rglob('*') if p.is_file() and p.suffix in ['.cpp','.hpp','.h']]
    tracked += list((ROOT/'source/rust/ffi/src').glob('*.rs'))
    if a.reference_report:tracked.append(a.reference_report.resolve())
    tracked=list(dict.fromkeys(x.resolve() for x in tracked));before={str(x):digest(x) for x in tracked};(out/'before.json').write_text(json.dumps(before,indent=2))
    commands=[]
    def run(cmd,name):
        commands.append(shlex.join(map(str,cmd)));r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90);(out/(name+'.log')).write_text(commands[-1]+'\n'+r.stdout+r.stderr);return r
    archive=out/'native-core-extern.a'
    r=run(['/usr/bin/ar','rcs',str(archive),*map(str,objects)],'archive')
    if r.returncode:raise RuntimeError('isolated archive creation failed')
    binary=out/'audio';r=run([recipe[0],*flags,str(HERE/'audio.cpp'),str(archive),*libs,'-Wl,-dead_strip','-o',str(binary)],'compile')
    if r.returncode:raise RuntimeError('native helper compile/link failed')
    binary_hash=digest(binary);archive_hash=digest(archive)
    good=run([str(binary)],'decode');repeat=run([str(binary)],'repeat')
    if good.returncode or repeat.returncode or good.stdout!=repeat.stdout:raise RuntimeError('baseline comparison failed')
    result=json.loads(good.stdout);assert result['pcm']==PCM
    if a.reference_report:
        ref=json.loads(a.reference_report.read_text())
        if ref['status']!='PASS' or ref['backend']!='cpp':raise RuntimeError('invalid C++ reference report')
        if {k:v for k,v in ref['result'].items() if k!='receipts'}!={k:v for k,v in result.items() if k!='receipts'}:raise RuntimeError('C++/Rust observable decode mismatch')
    bad=run([str(binary),'corrupt-expected-pcm'],'negative-pcm')
    if bad.returncode!=1 or 'COMPARISON pcm/metadata/end/seek/receipt mismatch' not in bad.stderr:raise RuntimeError('known failure not rejected by comparison')
    after={str(x):digest(x) for x in tracked};(out/'after.json').write_text(json.dumps(after,indent=2))
    if before!=after or digest(binary)!=binary_hash or digest(archive)!=archive_hash:raise RuntimeError('artifact/source drift')
    report={'status':'PASS','backend':a.backend,'result':result,'negative_control':'corrupt expected PCM exits 1 comparison','commands':commands,'binary_sha256':binary_hash,'isolated_archive_sha256':archive_hash,'bindings':before,'core_built_current':'NOT PROVEN: parent build seal required; object bytes/source bound before/after only','limits':['PCM WAV only','no audible playback, mixer, performance, screenshot, big-endian host or full audio port claim']}
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['bindings','commands']}))
if __name__=='__main__':main()
