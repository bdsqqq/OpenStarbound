#!/usr/bin/env python3
"""Evaluate the actual selector rules and build the actual sole Rust.cmake target."""
import argparse
from pathlib import Path
import re
import json
import subprocess
import hashlib
import stage

ROOT=Path(__file__).resolve().parents[3]
CMAKE=Path('/nix/store/fsdy1l7x2ybpry7lrhw2m7r6w8jvp01i-cmake-4.4.4/bin/cmake')
NINJA=Path('/nix/store/ndfr0d2nizw172ppn99n505ikpsq9727-ninja-1.13.2/bin/ninja')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(output):
    out=Path(output).resolve();stage.need(out.is_relative_to(ROOT/'build/byte-array-rust') and not out.exists(),'fresh selector output')
    out.mkdir(parents=True)
    source=(ROOT/'source/CMakeLists.txt').read_text()
    option=re.search(r'^option\(STAR_USE_RUST_BYTE_ARRAY .* OFF\)$',source,re.MULTILINE)
    stage.need(option is not None,'actual default-OFF option')
    start=source.index('if(STAR_USE_RUST_LIGHTING OR');end=source.index('if(STAR_USE_RUST_IO_DEVICE)',start)
    blocks=source[start:end]
    text='cmake_minimum_required(VERSION 3.21)\nproject(ByteArrayRustSelector LANGUAGES C CXX)\n'
    text+='set(PROJECT_SOURCE_DIR "'+str(ROOT/'source')+'")\nset(STAR_ARCHITECTURE arm64)\n'
    text+='list(APPEND CMAKE_MODULE_PATH "'+str(ROOT/'cmake')+'")\n'+option[0]+'\n'+blocks
    text+='get_directory_property(_defs COMPILE_DEFINITIONS)\n'
    text+='file(WRITE "${CMAKE_BINARY_DIR}/selector.txt" "${STAR_USE_RUST_BYTE_ARRAY}\\n${_defs}\\n${STAR_RUST_ARCHIVE}\\n")\n'
    (out/'CMakeLists.txt').write_text(text)
    before={str(p):sha(p) for p in (ROOT/'source/CMakeLists.txt',ROOT/'cmake/Rust.cmake',Path(__file__),CMAKE,NINJA)}
    commands=[]
    for mode in ('off','on'):
        args=[str(CMAKE),'-S',str(out),'-B',str(out/mode),'-G','Ninja','-DCMAKE_MAKE_PROGRAM='+str(NINJA)]
        if mode=='on':args+=['-DSTAR_USE_RUST_BYTE_ARRAY=ON']
        p=subprocess.run(args,capture_output=True,timeout=60);(out/(mode+'.stdout')).write_bytes(p.stdout);(out/(mode+'.stderr')).write_bytes(p.stderr)
        stage.need(p.returncode==0,'actual selector configure')
        commands.append(dict(command=args,returncode=p.returncode))
    off=(out/'off/selector.txt').read_text().splitlines();on=(out/'on/selector.txt').read_text().splitlines()
    stage.need(off[0]=='OFF' and (len(off)<2 or 'STAR_USE_RUST_BYTE_ARRAY' not in off[1]),'default native selector')
    stage.need(on[0]=='ON' and 'STAR_USE_RUST_BYTE_ARRAY' in on[1] and on[2].endswith('libstar_engine_ffi.a'),'selected Rust selector/runtime')
    args=[str(CMAKE),'--build',str(out/'on'),'--target','star_rust_engine_ffi_build']
    p=subprocess.run(args,capture_output=True,timeout=180);(out/'build.stdout').write_bytes(p.stdout);(out/'build.stderr').write_bytes(p.stderr)
    stage.need(p.returncode==0,'actual Rust.cmake aggregate build')
    archive=Path(on[2]);stage.need(archive.is_file(),'aggregate archive exists')
    stage.need(all(sha(p)==h for p,h in before.items()),'selector input drift')
    q=dict(status='ACTUAL_SELECTOR_AND_AGGREGATE_BUILD_PASS',archive=str(archive),archive_sha256=sha(archive),bindings=before,commands=commands+[dict(command=args,returncode=p.returncode)],
           limitations='extracted selector rules and actual Rust.cmake target; not a full native-project configuration or application run')
    (out/'report.json').write_text(json.dumps(q,indent=2)+'\n');print(json.dumps(q))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
