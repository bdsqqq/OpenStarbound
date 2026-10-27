"""Configured Core/extern discovery, with no compiler/build invocation.

Membership comes from the two actual Ninja object-library edges; compile DB
rows must agree exactly. This does NOT establish dependency freshness: Ninja's
dependency database and the existing source/configured witness remain a later
barrier. No direct object count is acceptance authority.
"""
import json
import os
import re
import shlex

from acquirer import require, read, identity, encoded, load, equal


def validate_recipe_rules(stage, rules):
    require(type(rules) is dict and set(rules) == {'build_root', 'targets', 'config_inputs'},
            'recipe rule fields')
    require(rules['targets'] == (b'extern/star_extern', b'core/star_core'),
            'fixed configured object-library targets')
    root = rules['build_root']
    require(type(root) is bytes and os.path.realpath(root) == root, 'canonical build root')
    require(rules['config_inputs'] == tuple(root+b'/'+name for name in
            (b'build.ninja', b'compile_commands.json', b'CMakeCache.txt')),
            'exact configured discovery inputs')
    require(set(rules['config_inputs']) <= set(stage.inputs), 'undeclared discovery source')
    require(len(stage.outputs[:-2]) == 1, 'one typed recipe product')


def discover(rules):
    root = rules['build_root']
    ninja, database, cache = (read(p) for p in rules['config_inputs'])
    require(b'$\n' not in ninja, 'continued Ninja lines unsupported')
    lines = ninja.splitlines()
    ordered = []
    for target in rules['targets']:
        rows = [line for line in lines if line.startswith(b'build '+target+b':')]
        require(len(rows) == 1 and rows[0].startswith(b'build '+target+b': phony '),
                'one configured phony object-library edge')
        tokens = rows[0].split(b': phony ',1)[1].split()
        require(tokens and all(b'$' not in t and t.endswith(b'.o') and
                not t.startswith(b'/') and b'..' not in t.split(b'/') for t in tokens),
                'unsupported target object syntax')
        ordered.extend(root+b'/'+token for token in tokens)
    require(len(set(ordered)) == len(ordered), 'duplicate configured object')
    # compile_commands is a standard textual configuration format, not raw
    # native evidence. Its explicit path fields become byte paths here.
    rows = json.loads(database)
    selected = {}
    for row in rows:
        output = os.fsencode(row['output'])
        if output.startswith((root+b'/core/', root+b'/extern/')):
            require(output not in selected, 'duplicate compile DB object')
            selected[output] = row
    require(set(selected) == set(ordered), 'Ninja/compile DB membership differs')
    configs = tuple(line for line in cache.splitlines()
                    if re.fullmatch(rb'STAR_USE_RUST_[A-Z_]+:BOOL=.*', line))
    require(configs and all(line.endswith(b'=OFF') for line in configs),
            'configured Rust selectors are not all OFF')
    result = []
    for output in ordered:
        row = selected[output]
        require(os.fsencode(row['directory']) == root, 'foreign compile cwd')
        argv = tuple(os.fsencode(t) for t in shlex.split(row['command']))
        relative = output[len(root)+1:]
        edges = [i for i, line in enumerate(lines) if line.startswith(b'build '+relative+b': ')]
        require(len(edges) == 1, 'one compiler edge per configured object')
        start = edges[0]
        block = []
        for line in lines[start+1:]:
            if not line.startswith(b'  '):
                break
            block.append(line)
        source = os.fsencode(row['file'])
        require(lines[start].split(b' ||',1)[0].endswith(b' '+source),
                'Ninja/compile DB source differs')
        fields = dict(line.strip().split(b' = ',1) for line in block if b' = ' in line)
        for field in (b'DEFINES', b'FLAGS', b'INCLUDES'):
            require(field in fields, 'missing configured compile field')
        expected_args = tuple(os.fsencode(t) for field in (b'DEFINES', b'FLAGS', b'INCLUDES')
                              for t in shlex.split(os.fsdecode(fields[field])))
        # CMake orders defines/includes before flags in compile_commands.
        db_args = argv[1:argv.index(b'-o')]
        expected_db = tuple(os.fsencode(t) for field in (b'DEFINES', b'INCLUDES', b'FLAGS')
                            for t in shlex.split(os.fsdecode(fields[field])))
        require(db_args == expected_db, 'Ninja/compile DB flags differ')
        require(argv[-2:] == (b'-c',source) and argv[argv.index(b'-o')+1] == relative,
                'compiler input/output recipe differs')
        require(b'-O3' in expected_args and b'-ffast-math' in expected_args and
                b'-DNDEBUG' in expected_args, 'production optimization profile missing')
        result.append({'object':output, 'source':source, 'argv':argv,
                       'ninja_edge':lines[start], 'ninja_fields':fields,
                       'source_identity':identity(source), 'object_identity':identity(output)})
    manifest = {'format':'lru-configured-discovery-v1', 'targets':rules['targets'],
                'build_root':root, 'configs':configs, 'objects':tuple(result),
                'configuration':tuple(identity(p) for p in rules['config_inputs']),
                'dependency_freshness_admitted':False, 'native_execution_admitted':False}
    encoded(manifest)
    return manifest


def validate_recipe(stage, rules, record):
    require(record['stdout'] == b'' and record['stderr'] == b'', 'discovery unexpected I/O')
    expected = discover(rules)
    require(equal(load(stage.outputs[0]), expected), 'discovery manifest differs from configured rules')
    return {'validator':'recipe-v1', 'ordered_objects':tuple(r['object'] for r in expected['objects']),
            'dependency_freshness_admitted':False, 'native_execution_admitted':False}
