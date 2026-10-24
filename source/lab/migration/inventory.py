#!/usr/bin/env python3
"""Static migration scope, not a CMake evaluator or proof of a completed port."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = Path('source/lab/migration/catalog.json')
NATIVE = {'.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx', '.inl', '.inc', '.ipp', '.tcc', '.m', '.mm', '.rs'}
EXCLUDED = {'target', 'build', 'builds', 'dist', '.git', '__pycache__', 'CMakeFiles'}


def included(path):
    p = Path(path)
    if not p.parts:
        return False
    return (not any(x in EXCLUDED or x.startswith('build-') for x in p.parts)
            and not p.as_posix().startswith('source/lab/migration/')
            and (p.suffix in NATIVE or p.name.endswith(('.cpp.in', '.h.in', '.hpp.in'))
                 or (p.parts[0] in {'scripts', 'attic'} or p.as_posix().startswith('source/lab/'))
                 and p.suffix in {'.py', '.sh'}))


def discover(root):
    found = []
    # Prune before recursion: a Rust target or build tree must never become input.
    import os
    for area in ('source', 'attic', 'scripts', 'lib'):
        for directory, dirs, files in os.walk(root / area):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not d.startswith('build-')
                             and Path(directory, d) != root / 'source/lab/migration')
            for name in sorted(files):
                p = Path(directory, name).relative_to(root)
                if included(p):
                    found.append(p.as_posix())
    return sorted(found)


def classify(path, rules):
    matches = [r for r in rules if re.fullmatch(r['pattern'], path)]
    if len(matches) != 1:
        raise ValueError(f'{path}: expected one classification, got {[r["id"] for r in matches]}')
    return matches[0]


# CMake lexer: comments, bracket arguments, quoted arguments and nested parentheses.
# Keeping token offsets gives declaration coordinates rather than invented line 1s.
TOKEN = re.compile(r'#[=]*\[[\s\S]*?\][=]*\]|\[(=*)\[[\s\S]*?\]\1\]|#[^\n]*|"(?:\\.|[^"\\])*"|[()]|[^\s()"#]+')
VAR = re.compile(r'\$\{([^}]+)\}')


def commands(text):
    tokens = [(m.group(), text.count('\n', 0, m.start()) + 1) for m in TOKEN.finditer(text)
              if not m.group().startswith('#')]
    i = 0
    while i + 1 < len(tokens):
        if tokens[i + 1][0] != '(':
            i += 1
            continue
        name, line = tokens[i]
        i += 2
        depth, args = 1, []
        while i < len(tokens) and depth:
            value, at = tokens[i]
            i += 1
            if value == '(':
                depth += 1
            elif value == ')':
                depth -= 1
            if depth:
                if value.startswith('"'):
                    value = value[1:-1]
                elif re.match(r'^\[=*\[', value):
                    value = re.sub(r'^\[=*\[|\]=*\]$', '', value)
                args.append((value, at))
        if depth:
            raise ValueError(f'unclosed CMake command at line {line}')
        yield name.lower(), args, line


def cmake_inventory(root, paths):
    """Union literal alternatives; never infer configured membership or includes."""
    members = defaultdict(list)
    declarations = defaultdict(list)
    limits = []
    import os
    inputs = []
    for directory, dirs, files in os.walk(root / 'source'):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not d.startswith('build-')
                         and Path(directory, d) != root / 'source/lab/migration')
        if 'CMakeLists.txt' in files:
            inputs.append(Path(directory, 'CMakeLists.txt'))
    inputs = sorted(inputs + list(root.glob('cmake/*.cmake')))
    for cmake in inputs:
        rel = cmake.relative_to(root).as_posix()
        parsed = list(commands(cmake.read_text()))
        definitions = defaultdict(list)
        targets = []
        stack = []
        # Values are scoped per file. Cross-directory inherited variables are not guessed.
        for name, args, line in parsed:
            vals = [x[0] for x in args]
            if name in {'if', 'foreach', 'while'}:
                stack.append(name + '(' + ' '.join(vals) + ')')
                if name == 'foreach' and len(args) > 1 and vals[1] not in {'IN', 'RANGE'}:
                    definitions[vals[0]].extend((v, at, tuple(stack)) for v, at in args[1:])
                continue
            if name in {'elseif', 'else'}:
                if stack:
                    # ELSE is an alternative, not an assertion that earlier IF is true.
                    stack[-1] += ' -> ' + name + '(' + ' '.join(vals) + ')'
                continue
            if name in {'endif', 'endforeach', 'endwhile'}:
                if stack:
                    stack.pop()
                continue
            if name == 'set' and args:
                definitions[vals[0]].extend((v, at, tuple(stack)) for v, at in args[1:])
            elif name == 'list' and len(args) > 2 and vals[0].upper() == 'APPEND':
                definitions[vals[1]].extend((v, at, tuple(stack)) for v, at in args[2:])
            elif name in {'add_library', 'add_executable', 'target_sources'} and args:
                targets.append((args, line, tuple(stack)))
            elif name == 'file' and vals and vals[0].upper() in {'GLOB', 'GLOB_RECURSE'}:
                limits.append({'path': rel, 'line': line, 'reason': 'glob not expanded; filesystem registry still covers files'})
            elif name == 'configure_file' and args:
                declarations['generated_templates'].append({'path': rel, 'line': line, 'input': vals[0]})

        constants = {'PROJECT_SOURCE_DIR': 'source', 'CMAKE_SOURCE_DIR': 'source',
                     'CMAKE_CURRENT_SOURCE_DIR': cmake.parent.relative_to(root).as_posix()}

        def expand(value, at, guards, seen=()):
            match = VAR.search(value)
            if not match:
                yield value, at, guards
                return
            key = match[1]
            if key in constants:
                yield from expand(value[:match.start()] + constants[key] + value[match.end():], at, guards, seen)
            elif key not in seen and key in definitions:
                for val, loc, conditions in definitions[key]:
                    yield from expand(value[:match.start()] + val + value[match.end():], loc,
                                      tuple(dict.fromkeys(guards + conditions)), seen + (key,))
            elif key not in seen:
                limits.append({'path': rel, 'line': at, 'reason': 'unresolved target/source expression: ' + value})

        for args, line, guards in targets:
            for target, _, target_guards in expand(args[0][0], args[0][1], guards):
                # Imported targets declare no local source membership.
                if any(v == 'IMPORTED' for v, _ in args):
                    continue
                for value, at in args[1:]:
                    if value.startswith('$<TARGET_OBJECTS:'):
                        continue  # link/object aggregation is not direct source ownership
                    for resolved, loc, conditions in expand(value, at, target_guards):
                        for item in resolved.split(';'):
                            if not included(item) or not Path(item).suffix:
                                continue
                            candidate = Path(item) if item.startswith('source/') else cmake.parent.relative_to(root) / item
                            import posixpath
                            candidate = posixpath.normpath(candidate.as_posix())
                            if candidate in paths:
                                evidence = {'target': target, 'cmake': rel, 'target_line': line,
                                            'source_line': loc, 'static_context': list(conditions)}
                                if evidence not in members[candidate]:
                                    members[candidate].append(evidence)
                            elif not item.startswith('$'):
                                limits.append({'path': rel, 'line': loc, 'reason': 'source reference absent from scanned files: ' + item})
    for value in members.values():
        value.sort(key=lambda x: (x['target'], x['cmake'], x['source_line'], x['static_context']))
    unique_limits = {json.dumps(x, sort_keys=True): x for x in limits}
    return members, sorted(unique_limits.values(), key=lambda x: (x['path'], x['line'], x['reason'])), inputs, declarations


def generate(root):
    rules_path = root / 'source/lab/migration/modules.json'
    config = json.loads(rules_path.read_text())
    ids = [r['id'] for r in config['rules']]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate classification rule IDs')
    for rule in config['rules']:
        if rule['module'] not in config['modules']:
            raise ValueError(f'unknown module in rule {rule["id"]}')
    paths = discover(root)
    memberships, limits, cmake_inputs, declarations = cmake_inventory(root, set(paths))
    records = []
    for path in paths:
        rule = classify(path, config['rules'])
        native = Path(path).suffix not in {'.py', '.sh'}
        records.append({'path': path, 'line': 1, 'module': rule['module'], 'rule': rule['id'],
                        'disposition': rule['disposition'],
                        'language': 'rust' if path.endswith('.rs') else 'c/c++' if native else 'harness/tool script',
                        'cmake_membership': memberships.get(path, []),
                        'membership_status': 'static-alternative' if path in memberships else 'no-direct-target-found'})
    # Input hashes make body edits and extraction changes stale too; no revision ID that
    # becomes instantly stale on the checkpoint containing this catalog.
    input_paths = sorted(set(paths) | {p.relative_to(root).as_posix() for p in cmake_inputs}
                         | {'source/lab/migration/modules.json', 'source/lab/migration/inventory.py'})
    return {'schema': 1, 'generated_by': 'python3 source/lab/migration/inventory.py --write',
            'membership_semantics': 'static alternatives only; not an evaluated CMake configuration; direct sources only',
            'scope': {'roots': ['source', 'attic', 'scripts', 'lib'], 'native_suffixes': sorted(NATIVE),
                      'templates': ['*.cpp.in', '*.h.in', '*.hpp.in'],
                      'script_scope': 'scripts/, attic/, source/lab/: *.py and *.sh',
                      'excluded_directory_names': sorted(EXCLUDED),
                      'excluded_prefixes': ['build-*', 'source/lab/migration/']},
            'summary': {'files': len(records), 'modules': len({r['module'] for r in records}),
                        'by_module': dict(sorted(Counter(r['module'] for r in records).items())),
                        'by_disposition': dict(sorted(Counter(r['disposition'] for r in records).items())),
                        'no_direct_target': sum(not r['cmake_membership'] for r in records)},
            'modules': config['modules'], 'files': records,
            'cmake_extraction_limits': limits,
            'generated_template_declarations': declarations.get('generated_templates', []),
            'inputs': [{'path': p, 'sha256': hashlib.sha256((root / p).read_bytes()).hexdigest()} for p in input_paths]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--check', action='store_true')
    parser.add_argument('--root', type=Path, default=ROOT, help='repository/isolated fixture root')
    args = parser.parse_args(argv)
    try:
        catalog = generate(args.root)
        expected = json.dumps(catalog, indent=2, sort_keys=True) + '\n'
        output = args.root / OUTPUT
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(expected)
        elif not output.is_file() or output.read_text() != expected:
            print('migration inventory missing/stale; run --write explicitly', file=sys.stderr)
            return 1
        print(f'migration inventory: {catalog["summary"]["files"]} files, {catalog["summary"]["modules"]} modules; ' + ('written' if args.write else 'current'))
        return 0
    except (ValueError, OSError) as error:
        print(f'migration inventory: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
