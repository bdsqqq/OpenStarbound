#!/usr/bin/env python3
"""Finite candidate compiler seal; no execution, signed attestation or SDK claim.

The accepted pre-mutation closure is immutable except four explicitly reconstructed
production files, one inventory test and pinned consumer/build fixtures.
Empty fill and empty copy are new defined no-op contracts; earlier native seals are historical.
SDK .tbd map entries are checked by path only, not SDK contents.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import host_seal as host

stage = host.stage
need, equal, sha, subset, rehash = host.need, host.equal, host.sha, host.subset, host.rehash
HERE, ROOT = host.HERE, host.ROOT
BASE = ROOT / 'build/byte-array-rust'
BEFORE = BASE / 'native-before-r1.json'
CORE = ROOT / 'source/core'
OWNED = [CORE / 'StarByteArray.cpp', CORE / 'StarByteArray.hpp',
         ROOT / 'source/CMakeLists.txt', ROOT / 'source/rust/ffi/src/lib.rs']
NEW = [CORE / 'StarByteArrayHost.hpp', CORE / 'StarRustByteArray.h',
       ROOT / 'source/rust/ffi/src/byte_array.rs']
SCOPE = dict(native_objects=113, source_routed_definitions=56,
             required_compiled_abi_symbols=33, native_executions=0,
             sdk_link_stubs='path-only', signed_attestation=False)


def original(path):
    return subprocess.check_output(['git', 'show', '84f27041:' + str(path.relative_to(ROOT))], cwd=ROOT).decode()


NATIVE_FILL_EDIT = ('  memset(m_data, c, m_size);',
                    '  if (m_size != 0) memset(m_data, c, m_size);')
HOST_FILL_EDIT = (
    '   case SB_BA_FILL_BYTES:{need(b<=255&&!d);auto& o=role(c,a);span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::capacity(o),0,ByteArrayNativeAccess::size(o));std::memset(ByteArrayNativeAccess::data(o),static_cast<unsigned char>(b),ByteArrayNativeAccess::size(o));break;}',
    '   case SB_BA_FILL_BYTES:{need(b<=255&&!d);auto& o=role(c,a);auto n=ByteArrayNativeAccess::size(o);if(n!=0){span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::capacity(o),0,n);std::memset(ByteArrayNativeAccess::data(o),static_cast<unsigned char>(b),n);}break;}')
NATIVE_COPY_EDIT = ('  std::memcpy(m_data + m_size - len, data, len);',
                    '  if (len != 0) std::memcpy(m_data + m_size - len, data, len);')
HOST_COPY_EDIT = (
    '   case SB_BA_COPY_IN:{auto& o=role(c,a);span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::size(o),b,d);need(ByteArrayNativeAccess::size(o)<=ByteArrayNativeAccess::capacity(o));span(c.input,c.inputCount,0,d);std::memcpy(ByteArrayNativeAccess::data(o)+b,c.input,d);break;}',
    '   case SB_BA_COPY_IN:{auto& o=role(c,a);if(d==0){need(b<=ByteArrayNativeAccess::size(o));need(ByteArrayNativeAccess::size(o)<=ByteArrayNativeAccess::capacity(o));break;}span(ByteArrayNativeAccess::data(o),ByteArrayNativeAccess::size(o),b,d);need(ByteArrayNativeAccess::size(o)<=ByteArrayNativeAccess::capacity(o));span(c.input,c.inputCount,0,d);std::memcpy(ByteArrayNativeAccess::data(o)+b,c.input,d);break;}')
BUILD_FIXTURE = ROOT / 'scripts/build-behavior-lab.sh'
BUILD_FIXTURE_EDIT = ('then base="$base-r3"; fi', 'then base="$base-r5"; fi')
FIXTURES = {
    BUILD_FIXTURE: (
        'dd0733d02d82b429eccf2127aa7ba27db0db9d32f61463452aea9db855f6f632',
        'df9e44984d65915db86c67f0e256cc25b6da7286923db4ef7474279bdbf2082d'),
    ROOT / 'source/base/StarBufferLab.hpp': (
        'bba48e74a2490b204ef3982869d10abbf9bee7134710cbfd0ecbc84389fc160f',
        'e9f3bacab586e425bc3ddd0bc65af3817029a9538c69a5fd8c5cc4348dc8aa8c'),
    ROOT / 'source/client/StarClientApplication.cpp': (
        'fc6c57806bbbc3c8976915d5b23783e7a1a327035e782aefda63b6193a409a8d',
        '8bcaf396ca0feef064148a34000112b4ff71092f3b4545c54c2e914f8276d113'),
}


def revision_source(path, revision):
    return subprocess.check_output(['git', 'show', revision + ':' + str(path.relative_to(ROOT))], cwd=ROOT)


def exact_edit(text, edit):
    before, after = edit
    need(text.count(before) == 1, 'unique exact repair site')
    return text.replace(before, after, 1)


def check_host():
    old = revision_source(NEW[0], '135d6e03')
    equal(hashlib.sha256(old).hexdigest(),
          '48366f6df8e9fc08b9d96f8a50771979d6ce8a01014adf50b2df6af1936042c9', 'original host identity')
    expected = exact_edit(exact_edit(old.decode(), HOST_FILL_EDIT), HOST_COPY_EDIT)
    equal(NEW[0].read_bytes(), expected.encode(), 'only host empty fill and copy repairs')


def check_fixtures(bindings, fresh=False, required=False):
    # Historical closure receipts may retain old hashes. Fresh compiler inputs
    # must bind the entire accepted instrumented fixture, never its predecessor.
    for p, (old_hash, current_hash) in FIXTURES.items():
        if str(p) not in bindings and not required:
            continue
        old = original(p).encode()
        current = revision_source(p, '968993b4')
        if p == BUILD_FIXTURE:
            equal(hashlib.sha256(current).hexdigest(),
                  '737c6d89a92bfcdfea27546796b1c4d0edb16ebeb0d8bc267698fc12c6d29874', 'accepted build fixture identity')
            current = exact_edit(current.decode(), BUILD_FIXTURE_EDIT).encode()
        equal(hashlib.sha256(old).hexdigest(), old_hash, 'original fixture identity')
        equal(hashlib.sha256(current).hexdigest(), current_hash, 'accepted fixture identity')
        equal(p.read_bytes(), current, 'only accepted fixture bytes')
        digest = bindings.get(str(p))
        need(type(digest) is str and digest in ((current_hash,) if fresh else (old_hash, current_hash)),
             'recorded fixture identity')


def branches(text, header=False):
    prefix = '#pragma once\n' if header else ''
    marker = prefix + '#ifdef STAR_USE_RUST_BYTE_ARRAY\n'
    need(text.startswith(marker) and text.endswith('#endif\n'), 'owned OFF source wrapper')
    inside = text[len(marker):-len('#endif\n')]
    # The outer selector alone is split; nested directives remain byte-exact.
    depth = 0
    offset = 0
    for line in inside.splitlines(keepends=True):
        if re.match(r'\s*#\s*(if|ifdef|ifndef)\b', line):
            depth += 1
        elif re.match(r'\s*#\s*endif\b', line):
            depth -= 1
        elif line == '#else\n' and depth == 0:
            return inside[:offset], prefix + inside[offset + len(line):]
        offset += len(line)
    raise ValueError('missing owned OFF source')


def check_owned(old):
    equal(set(old), {str(p) for p in OWNED}, 'exact four owned-before files')
    originals = {p: original(p) for p in OWNED}
    for p, text in originals.items():
        need(hashlib.sha256(text.encode()).hexdigest() == old[str(p)], 'owned original identity')
    selected = []
    for p in OWNED[:2]:
        on, off = branches(p.read_text(), p.suffix == '.hpp')
        expected = exact_edit(originals[p], NATIVE_FILL_EDIT) if p == OWNED[0] else exact_edit(originals[p], NATIVE_COPY_EDIT)
        equal(off, expected, 'exact repaired native OFF source')
        selected.append(on)
    equal(sorted(map(int, re.findall(r'execute\((\d+),', ''.join(selected)))), list(range(56)), '56 production source routes')
    equal(host.host_diagnostic.class_declaration(selected[1]),
          host.host_diagnostic.class_declaration(originals[OWNED[1]]), 'native class declaration')
    cmake = OWNED[2].read_text()
    option = 'option(STAR_USE_RUST_BYTE_ARRAY "Use experimental Rust ByteArray controllers" OFF)\n'
    block = 'if(STAR_USE_RUST_BYTE_ARRAY)\n  add_compile_definitions(STAR_USE_RUST_BYTE_ARRAY)\nendif()\n\n'
    for token in (option, block, ' OR STAR_USE_RUST_BYTE_ARRAY'):
        need(cmake.count(token) == 1, 'exact default OFF CMake addition')
        cmake = cmake.replace(token, '', 1)
    equal(cmake, originals[OWNED[2]], 'CMake changes limited to option OR compile definition')
    suffix = '\nmod byte_array;\npub use byte_array::{star_byte_array_call_count, star_byte_array_run, StarByteArrayHost};\n'
    equal(OWNED[3].read_text(), originals[OWNED[3]] + suffix, 'append-only Rust module exports')


INVENTORY_TEST = HERE / 'test_contract.py'
INVENTORY_EDITS = (
    ('import contract as c\n', 'import contract as c\nfrom rust_seal import branches\n'),
    ("cpp=(root/'source/core/StarByteArray.cpp').read_text().splitlines()",
     "cpp=branches((root/'source/core/StarByteArray.cpp').read_text())[1].splitlines()"),
    ("hpp=(root/'source/core/StarByteArray.hpp').read_text().splitlines()",
     "hpp=branches((root/'source/core/StarByteArray.hpp').read_text(), True)[1].splitlines()"),
)


def check_inventory_test(bindings):
    """Admit only the native-OFF projection of the original line-inventory test.

    Earlier compiler receipts also recorded this Python test, although it is not
    a compiler dependency. Preserve those historical records; validate their
    precise old/new identity and bind the current test separately at sealing.
    """
    old = original(INVENTORY_TEST)
    old_hash = hashlib.sha256(old.encode()).hexdigest()
    need(old_hash == '45769897063cbc7d63b8bbbf86f3a13f87d4d63dde8b3ccd1f58151086e8a67d', 'original inventory test identity')
    expected = old
    for before, after in INVENTORY_EDITS:
        need(expected.count(before) == 1, 'exact inventory projection site')
        expected = expected.replace(before, after, 1)
    equal(INVENTORY_TEST.read_text(), expected, 'only native OFF inventory projection')
    need(bindings.get(str(INVENTORY_TEST)) in (old_hash, sha(INVENTORY_TEST)), 'recorded inventory test identity')


def rehash_compiler_bindings(bindings, fresh=False):
    exceptions = {str(INVENTORY_TEST), *(str(p) for p in FIXTURES)}
    rehash({p: h for p, h in bindings.items() if p not in exceptions})
    check_inventory_test(bindings)
    check_fixtures(bindings, fresh=fresh)


def check_baseline(baseline, bindings):
    need(baseline['status'] == 'ACCEPTED_NATIVE_BEFORE_PRODUCTION_MUTATION', 'accepted before phase')
    equal(set(baseline['owned_before']), {str(p) for p in OWNED}, 'exact owned-before scope')
    unchanged = {p: h for p, h in baseline['bindings'].items() if p not in baseline['owned_before']}
    rehash_compiler_bindings(unchanged)
    check_inventory_test(bindings)
    check_fixtures(unchanged, required=True)
    check_fixtures(bindings, fresh=True, required=True)
    exceptions = {str(INVENTORY_TEST), *(str(p) for p in FIXTURES)}
    subset({p: h for p, h in unchanged.items() if p not in exceptions}, bindings, 'unchanged accepted host closure')
    for p in OWNED + NEW:
        need(str(p) in bindings and bindings[str(p)] == sha(p), 'current owned source binding: ' + str(p))
    check_owned(baseline['owned_before'])
    check_host()


def jobs_and_commands(root, recipes, backend, archive):
    need(backend in ('native', 'rust') and type(backend) is str, 'backend mode')
    compiler, flags, libs, _ = stage.recipe()
    jobs = [[r['compiler'], r['flags'], r['source'], str(i)] for i, r in enumerate(recipes)]
    names = ['lab', 'callback'] + (['protocol'] if backend == 'rust' else [])
    for name in names:
        src = root / (name + '-probe.cpp' if name != 'protocol' else 'protocol.cpp')
        jobs.append([str(compiler), flags, str(src), name])
    extra = (['-DSTAR_USE_RUST_BYTE_ARRAY'] if backend == 'rust' else []) + ['-I' + str(CORE)]
    commands = []
    for c, f, src, name in jobs:
        commands.append(('deps-' + name, [c, *f, *extra, '-M', '-MF', root / (name + '.d'), src]))
    for c, f, src, name in jobs:
        commands.append(('compile-' + name, [c, *f, *extra, '-c', src, '-o', root / (name + '.o')]))
    commands += [('archive', ['/usr/bin/ar', 'qcs', root / 'candidate-core.a', *[root / (str(i) + '.o') for i in range(113)]]),
                 ('archive-table', ['/usr/bin/ar', 't', root / 'candidate-core.a'])]
    for name in names:
        commands.append(('link-' + name, [compiler, *flags, *extra, root / (name + '.o'), root / 'candidate-core.a', archive, *libs,
            '-Wl,-dead_strip', '-Wl,-map,' + str(root / (name + '.map')), '-o', root / name]))
    bodies = [i for i, r in enumerate(recipes) if r['source'] == str(CORE / 'StarByteArray.cpp')]
    need(len(recipes) == 113 and len(bodies) == 1, '113 production recipes with one actual ByteArray body')
    commands.append(('body-symbols', ['/usr/bin/nm', '-C', '--defined-only', root / (str(bodies[0]) + '.o')]))
    return jobs, [(n, list(map(str, argv))) for n, argv in commands]


def check_dependencies(root, jobs, bindings):
    for _, _, src, name in jobs:
        need(src in bindings, 'bound actual compilation source')
        text = (root / (name + '.d')).read_text().replace('\\\n', ' ')
        for word in shlex.split(text.split(':', 1)[1]):
            p = Path(word)
            p = p.resolve() if p.is_absolute() else (stage.CM / p).resolve()
            need(str(p) in bindings, 'bound actual transitive dependency')


def check_archive(root):
    members = host.audit.archive_members((root / 'candidate-core.a').read_bytes())
    equal([n.decode() for n, _ in members], [str(i) + '.o' for i in range(113)], '113 fresh archive members')
    for n, data in members:
        need(hashlib.sha256(data).hexdigest() == sha(root / n.decode()), 'archive member bytes')
    stage.artifacts.check_archive_members((root / 'archive-table.stdout').read_bytes(), [n for n, _ in members])


def check_map(root, name, backend, archive, recipes):
    raw = (root / (name + '.map')).read_bytes()
    objects = stage.artifacts.link_map_objects(raw)
    body = next(i for i, r in enumerate(recipes) if r['source'] == str(CORE / 'StarByteArray.cpp'))
    own = str(root / (name + '.o')).encode()
    prefix = str(root / 'candidate-core.a').encode()
    members = {prefix + b'(' + str(i).encode() + b'.o)' for i in range(113)}
    need({own, prefix + b'(' + str(body).encode() + b'.o)'} <= set(objects), 'actual production archive route')
    _, flags, libs, _ = stage.recipe()
    sdk = Path(flags[flags.index('-isysroot') + 1]) if '-isysroot' in flags else None
    allowed = [str(Path(p)).encode() + b'(' for p in [str(archive), *libs] if str(p).endswith('.a') and Path(p).is_absolute()]
    need(all(p == own or p in members or p == b'linker synthesized'
        or any(p.startswith(a) and p.endswith(b')') for a in allowed)
        or (sdk is not None and p.endswith(b'.tbd') and Path(p.decode()).is_relative_to(sdk)) for p in objects), 'unexpected or Cpp controller map object')
    if backend == 'rust':
        rust = str(archive).encode() + b'('
        indexes = {m.group(1) for m in re.finditer(rb'^\[\s*(\d+)\]\s+' + re.escape(rust) + rb'[^\n]+\)$', raw, re.M)}
        need(indexes, 'actual Rust archive route')
        for symbol in (b'star_byte_array_run', b'star_byte_array_call_count'):
            routes = re.findall(rb'^0x[0-9A-Fa-f]+\s+0x[0-9A-Fa-f]+\s+\[\s*(\d+)\]\s+_?' + symbol + rb'\s*$', raw, re.M)
            need(any(i in indexes for i in routes), 'actual Rust symbol route: ' + symbol.decode())


def protocol_source():
    text = (HERE / 'host_protocol.cpp').read_text()
    remove = ['static uint32_t throws(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){throw 17;}\n',
              ' CHECK(sb_byte_array_run(SB_BA_CTOR,&c,throws)==3);\n']
    for line in remove:
        need(text.count(line) == 1, 'exact foreign callback throw removal')
        text = text.replace(line, '')
    return text.replace('ByteArrayHost', 'ByteArrayRust').replace('sb_byte_array_', 'star_byte_array_').replace('"host_api.h"', '"StarRustByteArray.h"')


def probe_source(name):
    count = 'star_byte_array_call_count'
    return ('#include "StarRustByteArray.h"\n#define main byte_array_frozen_main\n#include "' + str(HERE / (name + '.cpp')) + '"\n#undef main\n'
        'int main(int argc,char** argv) {\nuint64_t before[56][3];\n'
        f'for(unsigned m=0;m<56;++m)for(unsigned e=0;e<3;++e)before[m][e]={count}(m,e);\n'
        'int rc=byte_array_frozen_main(argc,argv);\nstd::cerr << "COUNTERS";\n'
        f'for(unsigned m=0;m<56;++m)for(unsigned e=0;e<3;++e)std::cerr << " " << ({count}(m,e)-before[m][e]);\n'
        'std::cerr << "\\n";return rc;\n}\n')


def check_generated(root, backend):
    for name, module in [('expected', host.contract), ('callback-expected', host.callback_contract)]:
        need((root / (name + '.jsonl')).read_bytes() == module.canonical(module.expected()), 'frozen golden corpus')
    for name in ('lab', 'callback'):
        equal((root / (name + '-probe.cpp')).read_text(), probe_source(name), 'unchanged native corpus wrapper')
    if backend == 'rust':
        equal((root / 'protocol.cpp').read_text(), protocol_source(), 'exact protocol without foreign Cpp throw')


def verifier_bindings():
    paths = [HERE / n for n in ('rust_seal.py', 'test_rust_seal.py', 'rust_execute.py', 'host_seal.py', 'host_diagnostic.py',
             'stage.py', 'audit.py', 'contract.py', 'callback_contract.py')]
    paths += [Path(stage.artifacts.__file__), Path(stage.provenance.__file__)]
    paths.append(INVENTORY_TEST)
    paths.extend(FIXTURES)
    return {str(p.resolve()): sha(p) for p in paths}


def validate_build(path):
    path = Path(path).resolve()
    need(path.name == 'build.json' and path.parent.parent == BASE, 'owned candidate build root')
    root = path.parent
    q = stage.load(path)
    need(q['status'] == 'COMPILED_BYTEARRAY_CANDIDATE_UNSEALED', 'unsealed candidate phase')
    archive = Path(q['archive'])
    need(archive.is_absolute() and sha(archive) == q['archive_sha256'], 'aggregate Rust archive hash')
    equal(q['before'], q['after'], 'source before/after freeze')
    rehash_compiler_bindings(q['before'], fresh=True)
    # Independent verifier/executor code is frozen by the seal before native
    # execution, not misclassified as an input to the earlier C++ compilation.
    subset({str(BEFORE): sha(BEFORE), str(archive): sha(archive)}, q['before'], 'archive and baseline compiler freeze')
    check_baseline(stage.load(BEFORE), q['before'])
    for name in ('rust_compile.py',):
        subset({str(HERE / name): sha(HERE / name)}, q['before'], 'producer source binding')
    recipes = host.configured_recipes()
    equal(q['recipes'], recipes, 'configured production recipes')
    jobs, commands = jobs_and_commands(root, recipes, q['backend'], archive)
    equal(q['jobs'], jobs, 'complete backend jobs')
    host.check_commands(root, q['commands'], commands)
    check_dependencies(root, jobs, q['before'])
    equal(stage.load(root / 'before.json'), q['before'], 'before manifest mirror')
    equal(stage.load(root / 'after.json'), q['after'], 'after manifest mirror')
    equal(stage.load(root / 'commands.json'), q['commands'], 'command inventory mirror')
    freeze = stage.load(root / 'precompile-freeze.json')
    subset(freeze, q['before'], 'precompile source freeze subset')
    subset({str(p): sha(p) for p in OWNED + NEW}, freeze, 'production frozen before dependency scan')
    rehash(q['artifacts'])
    equal(set(q['artifacts']), {str(p) for p in root.iterdir() if p.is_file() and p != path}, 'all compiler artifact hashes')
    names = {'lab-probe.cpp', 'callback-probe.cpp', 'expected.jsonl', 'callback-expected.jsonl',
             'precompile-freeze.json', 'before.json', 'after.json', 'commands.json', 'candidate-core.a'}
    if q['backend'] == 'rust':
        names.add('protocol.cpp')
    names.update(n + ext for _, _, _, n in jobs for ext in ('.o', '.d'))
    names.update(n + ext for n, _ in commands for ext in ('.command.json', '.stdout', '.stderr'))
    names.update(n + ext for n in ['lab', 'callback'] + (['protocol'] if q['backend'] == 'rust' else []) for ext in ('', '.map'))
    equal(set(q['artifacts']), {str(root / n) for n in names}, 'compiler-only artifact scope')
    check_archive(root)
    for name in ['lab', 'callback'] + (['protocol'] if q['backend'] == 'rust' else []):
        need((root / name).is_file(), 'linked program')
        check_map(root, name, q['backend'], archive, recipes)
    host.host_diagnostic.required_abi((host.PARENT.parent / 'symbols-current.stdout').read_bytes(), (root / 'body-symbols.stdout').read_bytes())
    check_generated(root, q['backend'])
    return q


def verify(seal_path):
    q = stage.load(Path(seal_path).resolve())
    equal(q['scope'], SCOPE, 'typed finite scope')
    need(q['status'] == 'SEALED_BYTEARRAY_CANDIDATE', 'candidate seal phase')
    equal(q['verifier_bindings'], verifier_bindings(), 'current sealer source and tests')
    need(Path(q['build']).is_absolute() and sha(q['build']) == q['build_sha256'], 'build manifest identity')
    build = validate_build(q['build'])
    equal(q['backend'], build['backend'], 'sealed backend')
    return q


def seal(build, output):
    build, output = Path(build).resolve(), Path(output).resolve()
    need(output.parent == BASE and re.fullmatch(r'(?:native|rust)-seal-[A-Za-z0-9_-]+', output.name), 'fresh owned seal path')
    before, code = sha(build), verifier_bindings()
    q = validate_build(build)
    equal(code, verifier_bindings(), 'sealer acquisition drift')
    need(before == sha(build), 'build acquisition drift')
    result = dict(status='SEALED_BYTEARRAY_CANDIDATE', backend=q['backend'], build=str(build), build_sha256=before,
                  scope=SCOPE, verifier_bindings=code)
    output.mkdir(exist_ok=False)
    stage.dump(output / 'seal.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='phase', required=True)
    create = sub.add_parser('seal')
    create.add_argument('--build', required=True)
    create.add_argument('--output', required=True)
    check = sub.add_parser('verify')
    check.add_argument('--seal', required=True)
    args = parser.parse_args()
    print(json.dumps(seal(args.build, args.output) if args.phase == 'seal' else verify(args.seal)))
