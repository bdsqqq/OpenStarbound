"""Driver-first link-input witness. Does not compile objects or run its binary."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import expanded_invocation
import sdk_witness
from archive_identity import arm64_archive_members
from link_trace import parse as parse_trace
from object_inventory import reconcile as reconcile_map


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write('\n')


def observe(argv, cwd, out, requested_sdk, canonical_sdk):
    """Bind the expanded driver footprint BEFORE linking, including compiler-rt.

    Caller owns recipe reconstruction and a fresh isolated output directory.
    The two original producer generations and retained-object link probes are
    not retroactively qualified. A full native gate still needs fresh coherent
    compilation, source/dependency closure, execution and independent replay.
    """
    out = Path(out).absolute()
    if out.exists() or any(p.is_symlink() for p in [out, *out.parents]):
        raise ValueError('fresh non-symlink owned output required')
    # Outputs must be explicit: never accidentally overwrite an old artifact.
    argv = list(argv)
    if argv.count('-o') != 1:
        raise ValueError('one explicit compiler output required')
    maps = [a for a in argv if a.startswith('-Wl,-map,')]
    if len(maps) != 1 or Path(argv[argv.index('-o') + 1]) != out / 'native' or maps[0] != '-Wl,-map,' + str(out / 'native.map'):
        raise ValueError('binary and map must belong to fresh output')
    if argv[-1] != '-Wl,-t,-trace_implicit_libraries':
        raise ValueError('explicit supported trace flags required')
    out.mkdir(parents=True)
    (out / 'home').mkdir(); (out / 'tmp').mkdir()
    env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(out / 'home'),
           'TMPDIR': str(out / 'tmp'), 'LANG': 'C', 'LC_ALL': 'C'}
    compiler, hops = sdk_witness._resolve(argv[0])
    compiler_before = {'requested': argv[0], 'canonical': compiler,
                       'hops': hops, **sdk_witness._digest(compiler)}
    sources = [Path(m.__file__).resolve() for m in
               (expanded_invocation, sdk_witness, sys.modules[arm64_archive_members.__module__],
                sys.modules[parse_trace.__module__], sys.modules[reconcile_map.__module__])]
    sources += [Path(__file__).resolve(), Path(__file__).resolve().parents[1] / 'native_artifacts.py',
                Path(sys.executable).resolve()]
    source_before = {str(p): sha(p) for p in sources}
    sdk_before = sdk_witness.capture(requested_sdk, canonical_sdk)
    write(out / 'sdk-before.json', sdk_before)
    expansion = subprocess.run([argv[0], '-###', *argv[1:]], cwd=cwd, env=env,
                               capture_output=True, timeout=30)
    (out / 'expansion.stdout').write_bytes(expansion.stdout)
    (out / 'expansion.stderr').write_bytes(expansion.stderr)
    if expansion.returncode != 0:
        raise ValueError('driver expansion failed')
    lines = expansion.stderr.decode('utf8').splitlines()
    commands = [shlex.split(line) for line in lines if line.lstrip().startswith('"')]
    if len(commands) != 1:
        raise ValueError('one expanded linker command required')
    expanded = commands[0]
    inputs_before = expanded_invocation.bind(expanded)
    inventory = inputs_before['inventory']
    if inventory['architecture'] != 'arm64' or inventory['platform'][0] != 'macos' or inventory['sdk'] != requested_sdk:
        raise ValueError('unsupported target or independently configured SDK mismatch')
    if inventory['outputs'] != [str(out / 'native'), str(out / 'native.map')]:
        raise ValueError('expanded outputs changed')
    write(out / 'invocation-before.json', {'argv': argv, 'cwd': str(cwd), 'environment': env,
          'compiler': compiler_before, 'expanded': expanded, 'inputs': inputs_before,
          'sources': source_before})
    # Membership comes from the measured driver expansion, NEVER the later
    # observed trace. Compiler runtime and LTO plugin are included automatically.
    blobs = {p.encode(): Path(p).read_bytes() for p in inventory['file_inputs'] if p.endswith('.a')}
    tables = {p: b''.join(m['name'] + b'\n' for m in arm64_archive_members(blob))
              for p, blob in blobs.items()}
    write(out / 'archive-tables.json', {p.hex(): table.hex() for p, table in tables.items()})
    expanded_invocation.verify(inputs_before, expanded)
    sdk_witness.verify(sdk_before, requested_sdk, canonical_sdk)
    link = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=120)
    (out / 'link.stdout').write_bytes(link.stdout)
    (out / 'link.stderr').write_bytes(link.stderr)
    if type(link.returncode) is not int or link.returncode != 0:
        raise ValueError('link did not exit normally with zero status')
    expanded_invocation.verify(inputs_before, expanded)
    current_compiler, current_hops = sdk_witness._resolve(argv[0])
    if compiler_before != {'requested': argv[0], 'canonical': current_compiler,
                           'hops': current_hops, **sdk_witness._digest(current_compiler)}:
        raise ValueError('compiler drift')
    objects = [p.encode() for p in inventory['file_inputs'] if p.endswith('.o')]
    trace = parse_trace(link.stdout, objects, tables)
    mapped = reconcile_map((out / 'native.map').read_bytes(), objects, tables, blobs)
    sdk_paths = [os.fsdecode(p) for p in trace['sdk_paths'] + mapped['unresolved_origins']]
    sdk_paths += [os.fsdecode(r['source']) for r in trace['indirect_declarations']]
    consumed = sdk_witness.reconcile_consumed(sdk_before, sdk_paths,
               requested_root=requested_sdk, expected_canonical_root=canonical_sdk)
    sdk_witness.verify(sdk_before, requested_sdk, canonical_sdk)
    if source_before != {str(p): sha(p) for p in sources}:
        raise ValueError('witness source/tool drift')
    write(out / 'sdk-after.json', sdk_witness.capture(requested_sdk, canonical_sdk))
    write(out / 'consumed.json', consumed)
    report = {'status': 'FINITE_DRIVER_FIRST_LINK_INPUT_WITNESS_PASS_NOT_NATIVE_CALIBRATION',
              'standalone_objects': len(objects), 'loaded_archive_members': len(trace['archive_members']),
              'map_archive_members': len(mapped['used_archive_members']),
              'physical_duplicate_witnesses': [{k: v.hex() if type(v) is bytes else v for k, v in row.items()}
                                             for row in mapped['physical_member_identities']],
              'sdk_loaded_paths': len(trace['sdk_paths']), 'sdk_indirect_sources': len(trace['indirect_declarations']),
              'sdk_reconciled_records': len(consumed), 'sdk_unique_interfaces': len({r['canonical'] for r in consumed}),
              'artifacts': {str(p): sha(p) for p in out.iterdir() if p.is_file()},
              'limits': ['binary NOT executed; retained objects not freshly compiled',
                         'not native calibration, Rust or application qualification',
                         'no retrospective SDK byte recovery, framework implementations or transient-edit proof']}
    write(out / 'report.json', report)
    return report
