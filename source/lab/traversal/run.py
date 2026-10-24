#!/usr/bin/env python3
"""Standalone, offline traversal calibration; never configures/builds the project."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'build/traversal-lab'
FROZEN_SHA256 = 'c917ceeeba883c8c267b03861e0b171d0c7c3f2098b9cc419e6e463ea006d077'
REVISION = 'f5c4da28'
HEADER = 'source/base/StarBlocksAlongLine.hpp'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def freeze_gate(raw, adapted):
    if sha(raw) != FROZEN_SHA256:
        raise ValueError('frozen algorithm hash differs; no regeneration permitted')
    expected = raw.replace(b'namespace Star {', b'namespace TraversalReference {\nusing namespace Star;', 1)
    if adapted != expected:
        raise ValueError('adaptation differs from the sole permitted namespace/import edit')


def run(cmd, name, expected_success=True):
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=90)
    (OUT / (name + '.log')).write_text(shlex.join(map(str, cmd)) + '\n' + result.stdout + result.stderr)
    if (result.returncode == 0) != expected_success:
        raise RuntimeError(f'{name}: unexpected exit {result.returncode}; see output log')
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raw = (HERE / 'StarBlocksAlongLine.frozen.hpp').read_bytes()
    adapted = raw.replace(b'namespace Star {', b'namespace TraversalReference {\nusing namespace Star;', 1)
    freeze_gate(raw, adapted)
    historical = subprocess.check_output(['git', 'show', f'{REVISION}:{HEADER}'], cwd=ROOT)
    if historical != raw:
        raise ValueError('historical source does not match frozen bytes')
    # Exercise both independent provenance rejection paths without touching source.
    corrupt = raw.replace(b'      --n;', b'      n -= 2;', 1)
    negatives = []
    for name, original, adaptation in [
        ('algorithm-corruption', corrupt, adapted),
        ('unauthorized-adaptation', raw, adapted.replace(b'      --n;', b'      n -= 2;', 1)),
    ]:
        try:
            freeze_gate(original, adaptation)
        except ValueError:
            negatives.append(name)
        else:
            raise RuntimeError(f'provenance negative escaped: {name}')
    (OUT / 'reference.hpp').write_bytes(adapted)
    mutant = raw.replace(b'namespace Star {', b'namespace TraversalMutant {\nusing namespace Star;', 1)
    mutant = mutant.replace(b'      } else {\n        --n;', b'      } else {\n        /* deliberately omit tie count decrement */', 1)
    if mutant == raw or b'deliberately omit' not in mutant:
        raise RuntimeError('mutation fixture not applied')
    (OUT / 'mutant.hpp').write_bytes(mutant)

    database = ROOT / 'build/behavior/reference/cmake/compile_commands.json'
    entry = next(e for e in json.loads(database.read_text()) if e['file'].endswith('StarWorld.cpp'))
    recorded = shlex.split(entry['command'])
    # Preserve recorded native includes/defines/SDK/architecture/optimization. Remove only
    # source/output and FP policy; do not invoke CMake, Ninja, or dependency installation.
    flags = []
    skip = False
    for item in recorded[1:]:
        if skip:
            skip = False
            continue
        if item == '-o':
            skip = True
        elif item not in ('-c', '-ffast-math', entry['file']):
            flags.append(item)
    base = [recorded[0], *flags, '-I' + str(OUT),
            '-fsanitize=undefined,float-cast-overflow', '-fno-sanitize-recover=all', str(HERE / 'lab.cpp')]
    results = {}
    for policy, fp in [('precise', ['-fno-fast-math', '-ffp-contract=off']),
                       ('production-fast', ['-ffast-math'])]:
        for mutation in ('normal', 'tie', 'abort', 'exception'):
            name = policy + '-' + mutation
            binary = OUT / name
            define = [] if mutation == 'normal' else ['-D' + {'tie':'TIE_MUTANT','abort':'ABORT_MUTANT','exception':'EXCEPTION_MUTANT'}[mutation]]
            run([*base, *fp, *define, '-o', str(binary)], name + '-compile')
            result = run([str(binary)], name, mutation == 'normal')
            if mutation == 'normal':
                results[policy] = json.loads(result.stdout)
            else:
                # Reject crashes/sanitizer diagnostics as mutation evidence: the comparator
                # must reach an assertion that names observable incompatibility.
                if result.returncode != 1 or 'FAIL after' not in result.stderr or 'runtime error:' in result.stderr:
                    raise RuntimeError('negative control did not fail through comparator')
                negatives.append(name)
    report = {
        'reference_revision': REVISION, 'reference_sha256': sha(raw),
        'production_sha256': sha((ROOT / HEADER).read_bytes()),
        'shared_semantics_sha256': {p: sha((ROOT / p).read_bytes()) for p in (
            'source/core/StarVector.hpp', 'source/core/StarArray.hpp',
            'source/core/StarMathCommon.hpp')},
        'compiler_version': subprocess.check_output([recorded[0], '--version'], text=True),
        'lab_sha256': sha((HERE / 'lab.cpp').read_bytes()),
        'runner_sha256': sha(Path(__file__).read_bytes()),
        'recorded_compile_database_sha256': sha(database.read_bytes()),
        'policies': results, 'detected_negatives': negatives,
        'excluded_not_compatibility_passed': [
            {'example': 'origin=(NaN,0) or delta=(inf,0)', 'reason': 'nonfinite floor-to-int'},
            {'example': 'f64 origin=(1e100,0), delta=(0,0)', 'reason': 'finite floor outside int range'},
            {'example': 'f64 origin=(1e308,0), delta=(1e308,0)', 'reason': 'Scalar endpoint overflow'},
            {'example': 'origin=(-2e9,-2e9), delta=(4e9,4e9), abort=0',
             'reason': 'nonaxis int subtraction/count overflow BEFORE callback'},
            {'example': 'f64 origin=(2147483646,0), delta=(1,0), callback always true',
             'reason': 'post-last-cell axis increment overflow'},
            {'example': 'origin=(-2147483648,-2147483648), delta=(0,0), callback true',
             'reason': 'post-last-cell zero-length axis decrement overflow'},
            {'example': 'f64 origin=(2147483646,2147483646), delta=(1,1), callback always true',
             'reason': 'post-last-cell nonaxis tie step overflow'},
        ],
        'scope': 'finite sampled C++ calibration, not a Rust port or universal equivalence proof',
    }
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
