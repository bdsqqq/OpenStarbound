#!/usr/bin/env python3
"""Configure-only probes of the actual backend-selection block; no native builds."""
import json
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/traversal-cmake'
source = (ROOT / 'source/CMakeLists.txt').read_text()
options = '\n'.join(line for line in source.splitlines() if line.startswith('option(STAR_USE_RUST_') or line.startswith('option(STAR_BUILD_LIGHTING_LAB '))
start = source.index('if(STAR_USE_RUST_LIGHTING OR STAR_USE_RUST_BLOCKS_ALONG_LINE)')
end = source.index('# External code included', start)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'CMakeLists.txt').write_text(f'''cmake_minimum_required(VERSION 3.23)
project(traversal_probe NONE)
set(PROJECT_SOURCE_DIR "{ROOT / 'source'}")
set(CMAKE_MODULE_PATH "{ROOT / 'cmake'}")
{options}
{source[start:end]}
get_directory_property(defs COMPILE_DEFINITIONS)
get_property(targets DIRECTORY PROPERTY BUILDSYSTEM_TARGETS)
file(WRITE "${{CMAKE_BINARY_DIR}}/selection.txt" "defs=${{defs}}\nlibs=${{STAR_EXT_LIBS}}\ntargets=${{targets}}\n")
''')
passed = []
for lighting, traversal in [(False, False), (False, True), (True, False), (True, True)]:
    name = f'{int(lighting)}{int(traversal)}'
    build = OUT / name
    args = ['cmake', '-S', str(OUT), '-B', str(build),
            '-DSTAR_ARCHITECTURE=' + platform.machine(),
            '-DSTAR_USE_RUST_LIGHTING=' + ('ON' if lighting else 'OFF'),
            '-DSTAR_USE_RUST_BLOCKS_ALONG_LINE=' + ('ON' if traversal else 'OFF')]
    result = subprocess.run(args, text=True, capture_output=True)
    (OUT / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, name
    selection = (build / 'selection.txt').read_text()
    assert ('defs=STAR_USE_RUST_LIGHTING' in selection or ';STAR_USE_RUST_LIGHTING' in selection) == lighting, selection
    assert ('STAR_USE_RUST_BLOCKS_ALONG_LINE' in selection) == traversal, selection
    assert selection.count('libs=star_rust_engine_ffi') == int(lighting or traversal), selection
    assert selection.count('star_rust_engine_ffi_build') == int(lighting or traversal), selection
    if not lighting and not traversal:
        assert 'STAR_CARGO_EXECUTABLE' not in (build / 'CMakeCache.txt').read_text()
    passed.append(name)
for name, extra, diagnostic in [
    ('cross', ['-DCMAKE_SYSTEM_NAME=Generic'], 'native builds only'),
    ('multi', ['-DSTAR_ARCHITECTURE=arm64;x86_64'], 'multi-architecture'),
    ('unsupported', ['-DSTAR_ARCHITECTURE=wasm32'], 'native arm64 and x86_64'),
]:
    result = subprocess.run(['cmake', '-S', str(OUT), '-B', str(OUT / name),
        '-DSTAR_ARCHITECTURE=' + platform.machine(), '-DSTAR_USE_RUST_BLOCKS_ALONG_LINE=ON', *extra], text=True, capture_output=True)
    (OUT / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode != 0 and diagnostic in result.stdout + result.stderr, name
    passed.append(name + '-rejected')
print(json.dumps({'passed': passed}))
