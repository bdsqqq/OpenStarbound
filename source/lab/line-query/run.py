#!/usr/bin/env python3
"""Offline C++ calibration. No regeneration path for frozen source."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'build/line-query-lab'
SHA = 'ca4d5810770a085611304cc6c4871e620aad6f187bbad51390ea23befb522567'
ADAPTED_SHA = 'c34fddc148c9b9f4800638ae09cbe92eceb7c496dc03d0586c8d691395e4b628'
SHARED = {
    'StarVector.hpp': '35c50f7f3f4e9b412d01356209b27b5bfadd9d04a0ef1ec7620d23e05caefa70',
    'StarArray.hpp': '237edfaf71fc17b174cdc53e9ba4560ec71ddec44ff8ff54d2eb937aae1ffa76',
    'StarMathCommon.hpp': '1717b14b45a0725ce0186d69a20c5167642041bdd407a979c3eae48abd38708d',
    'StarMatrix3.hpp': '3d581fc1c2dbb4f4662e6efa53e1ec527262267e18be5e27ccdf10d7d7b265f5',
    'StarAlgorithm.hpp': '6fe386b71188d14509c8f10c5406058ec8ff6f535b35f1ee53e53b141f2316b6',
}
SUFFIX = b'template <typename T, size_t N>\nstd::ostream& operator<<'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def adapt(raw):
    # Exact suffix boundary is validated by the fixed full-source digest. No
    # query, constructor, alias, primitive or arithmetic edits are permitted.
    return raw[:raw.index(SUFFIX)].replace(b'namespace Star {', b'namespace FrozenReference {\nusing namespace Star;', 1) + b'}\n'


def gate(raw, adapted):
    if sha(raw) != SHA:
        raise ValueError('frozen source hash mismatch')
    if adapted != adapt(raw) or sha(adapted) != ADAPTED_SHA:
        raise ValueError('unauthorized adaptation')


def run(cmd, name):
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=90)
    (OUT / (name + '.log')).write_text(shlex.join(map(str, cmd)) + '\n' + result.stdout + result.stderr)
    return result


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--define', action='append', default=[], help='candidate backend macro; never changes the frozen header')
    parser.add_argument('--archive', type=Path, help='candidate archive, linked only into these standalone binaries')
    parser.add_argument('--direct-abi', action='store_true', help='diagnose the ABI directly; never bypasses the production adapter guard')
    parser.add_argument('--output', type=Path, default=OUT, help='isolated output beneath build/line-query-lab')
    parser.add_argument('--policy', action='append', choices=['uncontracted', 'default-contract', 'production-fast'],
                        help='select compiled policies; omitted means all three, never a cross-policy equivalence claim')
    args = parser.parse_args()
    if any(d not in ('STAR_USE_RUST_LINE_QUERY', 'STAR_USE_RUST_LINE_QUERY=1') for d in args.define):
        parser.error('only the candidate line-query backend define is permitted')
    if args.direct_abi and args.define:
        parser.error('select production adapter OR direct diagnostic ABI, not both')
    rust = bool(args.define) or args.direct_abi
    if rust != bool(args.archive):
        parser.error('Rust selection requires its adapter/direct-ABI selection and archive')
    OUT = args.output.resolve()
    if not OUT.is_relative_to((ROOT/'build/line-query-lab').resolve()):
        parser.error('output must stay beneath build/line-query-lab')
    tracked = [Path(__file__), HERE/'lab.cpp', HERE/'Production.hpp', ROOT/'source/core/StarLine.hpp',
               *(ROOT/'source/core'/p for p in SHARED)]
    if args.archive:
        tracked += [args.archive.resolve(), ROOT/'source/core/StarRustLine.h']
    before = {str(p): sha(p.read_bytes()) for p in tracked}
    OUT.mkdir(parents=True, exist_ok=True)
    for p, digest in SHARED.items():
        if sha((ROOT/'source/core'/p).read_bytes()) != digest:
            raise ValueError('shared primitive changed: '+p+'; research required, not regeneration')
    candidate_before = (ROOT/'source/core/StarLine.hpp').read_bytes()
    raw = (HERE / 'StarLine.original.hpp').read_bytes()
    adapted = adapt(raw)
    gate(raw, adapted)
    historical = subprocess.check_output(['git', 'show', 'a0296af5:source/core/StarLine.hpp'], cwd=ROOT)
    if raw != historical:
        raise ValueError('git snapshot mismatch')
    negatives = []
    for name, r, a in [('provenance-corruption', raw+b' ', adapted),
                       ('unauthorized-adaptation', raw, adapted.replace(b'isect.t = ta;', b'isect.t = tb;'))]:
        try:
            gate(r, a)
        except ValueError:
            negatives.append(name)
        else:
            raise ValueError('provenance negative escaped')
    (OUT / 'reference.hpp').write_bytes(adapted)
    mutants = []
    for namespace, old, new in [
        (b'DirectionMutant', b'VectorType ab = diff();', b'VectorType ab = -diff();'),
        (b'CoincidentMutant', b'isect.point = a < c ? c : a;', b'isect.point = a < c ? a : c;'),
        (b'GlancingMutant', b'!infinite && isect.intersects &&', b'!infinite && !isect.intersects &&'),
    ]:
        if adapted.count(old) != 1:
            raise ValueError('mutant edit not unique')
        mutants.append(adapted.replace(b'FrozenReference', namespace).replace(old,new))
    (OUT/'mutants.hpp').write_bytes(b'\n'.join(mutants))
    db = ROOT / 'build/behavior/reference/cmake/compile_commands.json'
    entry = next(e for e in json.loads(db.read_text()) if e['file'].endswith('StarWorld.cpp'))
    recorded = shlex.split(entry['command'])
    flags = []
    skip = False
    for flag in recorded[1:]:
        if skip:
            skip = False
            continue
        if flag == '-o':
            skip = True
        elif flag not in ('-c', '-ffast-math', entry['file']):
            flags.append(flag)
    results = {}
    selected = args.policy or ['uncontracted', 'default-contract', 'production-fast']
    unexpected = False
    for policy, fp in [('uncontracted', ['-fno-fast-math', '-ffp-contract=off']),
                       ('default-contract', ['-fno-fast-math']),
                       ('production-fast', ['-ffast-math'])]:
        if policy not in selected:
            continue
        binary = OUT / policy
        selection = ['-D'+d for d in args.define]
        if args.define and policy == 'uncontracted':
            selection.append('-DSTAR_RUST_LINE_FP_PRECISE')
        if args.direct_abi:
            selection += ['-DSTAR_LINE_LAB_DIRECT_ABI', '-DSTAR_LINE_LAB_POLICY='+str(
                {'uncontracted': 0, 'default-contract': 2, 'production-fast': 1}[policy])]
        cmd = [recorded[0], *flags, *fp, *selection, '-I'+str(OUT), '-fsanitize=undefined,float-cast-overflow',
               '-fno-sanitize-recover=all', str(HERE/'lab.cpp'), *([str(args.archive.resolve())] if args.archive else []), '-o', str(binary)]
        compiled = run(cmd, policy+'-compile')
        if compiled.returncode:
            raise RuntimeError('compile failed: '+policy+'; see '+str(OUT/(policy+'-compile.log')))
        observation_path = OUT/(policy+'-observations.txt')
        normal = run([str(binary), '', str(observation_path)], policy)
        repeat_path = OUT/(policy+'-repeat-observations.txt')
        repeat = run([str(binary), '', str(repeat_path)], policy+'-repeat')
        if repeat.returncode != normal.returncode or repeat.stdout != normal.stdout or repeat_path.read_bytes() != observation_path.read_bytes():
            raise RuntimeError('baseline not deterministic: '+policy)
        result = json.loads(normal.stdout)
        result['exit_code'] = normal.returncode
        result['compile_command'] = shlex.join(cmd)
        result['binary_sha256'] = sha(binary.read_bytes())
        result['observations_sha256'] = sha(observation_path.read_bytes())
        results[policy] = result
        unexpected |= normal.returncode != 0
        # A mutant rejecting an already-failing candidate proves nothing about
        # mutation detection. Preserve the failure report, skip those controls.
        if normal.returncode != 0:
            continue
        for mutant in ['direction', 'coincident-selection', 'glancing', 'point', 't', 'projection-clamp', 'numeric-field']:
            bad = run([str(binary), mutant], policy+'-'+mutant)
            if bad.returncode != 1 or 'FAIL ' not in bad.stderr or 'runtime error:' in bad.stderr:
                raise RuntimeError('mutant not rejected by comparator: '+policy+' '+mutant)
            negatives.append(policy+'-'+mutant)
    if (ROOT/'source/core/StarLine.hpp').read_bytes() != candidate_before:
        raise ValueError('candidate changed during calibration; rerun required')
    if {str(p): sha(p.read_bytes()) for p in tracked} != before:
        raise ValueError('calculation/checker inputs changed during calibration; rerun required')
    policy_differences = {}
    baseline = (OUT/'uncontracted-observations.txt').read_text().splitlines() if 'uncontracted' in results else []
    for policy in ('default-contract', 'production-fast'):
        if not baseline or policy not in results:
            continue
        other = (OUT/(policy+'-observations.txt')).read_text().splitlines()
        differing = [i for i, (a,b) in enumerate(zip(baseline,other)) if a != b]
        semantic = []
        finite_input = []
        for i in differing:
            def canonical(row):
                fields = row.split(' | ')[1].split()
                size = 32 if row.startswith('f32') else 64
                exp = 0x7f800000 if size == 32 else 0x7ff0000000000000
                mant = 0x7fffff if size == 32 else 0xfffffffffffff
                return [fields[0]] + ['nan' if (int(v,16)&exp)==exp and (int(v,16)&mant) else v for v in fields[1:]]
            if canonical(baseline[i]) != canonical(other[i]):
                semantic.append(i)
                inputs = baseline[i].split(' | ')[0].split()
                exp = 0x7f800000 if inputs[0]=='f32' else 0x7ff0000000000000
                if all((int(v,16)&exp)!=exp for v in inputs[2:]):
                    finite_input.append(i)
        policy_differences[policy] = {'raw_different_rows_from_uncontracted': len(differing),
            'nan_classified_different_rows': len(semantic), 'finite_input_different_rows': len(finite_input),
            'first_classified_differences': [{'case': i, 'uncontracted': baseline[i], 'other': other[i]} for i in semantic[:3]],
            'first_finite_input_differences': [{'case': i, 'uncontracted': baseline[i], 'other': other[i]} for i in finite_input[:3]]}
    report = {'reference_revision': 'a0296af5', 'raw_sha256': sha(raw), 'adapted_sha256': sha(adapted),
              'compiler': subprocess.check_output([recorded[0], '--version'], text=True),
              'compile_database_sha256': sha(db.read_bytes()),
              'shared_headers_sha256': {p: sha((ROOT/'source/core'/p).read_bytes()) for p in
                  ['StarVector.hpp','StarArray.hpp','StarMathCommon.hpp','StarMatrix3.hpp','StarAlgorithm.hpp']},
              'candidate_sha256': sha((ROOT/'source/core/StarLine.hpp').read_bytes()),
              'lab_sha256': sha((HERE/'lab.cpp').read_bytes()), 'runner_sha256': sha(Path(__file__).read_bytes()),
              'production_adapter_sha256': sha((HERE/'Production.hpp').read_bytes()),
              'tested_inputs_sha256': before, 'output': str(OUT),
              'candidate_defines': args.define, 'direct_abi': args.direct_abi,
              'candidate_archive': {'path': str(args.archive.resolve()), 'sha256': sha(args.archive.read_bytes())} if args.archive else None,
              'seed': '0x6c696e6551756572', 'requested_policies': selected, 'policies': results, 'cross_policy_observations': policy_differences, 'negative_controls': negatives,
              'scope': ('diagnostic direct Rust ABI' if args.direct_abi else 'Rust adapter' if args.define else 'C++ fallback') + ' f32/f64 sampled calibration; no game-equivalence claim',
              'numeric_policy': 'flags exact; finite/infinity/signed-zero exact bits; both NaN classified equal, payload/sign excluded',
              'exclusions': ['integer instantiations: signed multiplication/subtraction can overflow; not float-query scope',
                             'transforms, containers, rotation, length, angle: not ported/query contract scope']}
    (OUT/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 1 if unexpected else 0


if __name__ == '__main__':
    sys.exit(main())
