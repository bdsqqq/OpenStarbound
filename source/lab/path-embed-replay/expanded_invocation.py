"""Fail-closed inventory of the measured Apple clang-expanded ld argv profile."""
import os
import re
from sdk_witness import _digest, _resolve


BARE = {'-demangle', '-dynamic', '-O0', '-O1', '-O2', '-O3', '-dead_strip',
        '-t', '-trace_implicit_libraries'}


def parse(argv):
    if type(argv) is not list or not argv or any(type(x) is not str or not x or '\0' in x for x in argv):
        raise ValueError('nonempty string argv required')
    def absolute(path):
        if not os.path.isabs(path) or os.path.normpath(path) != path:
            raise ValueError('normalized absolute file path required')
        return path
    files, outputs, frameworks, libraries = [absolute(argv[0])], [], [], []
    arch, platform, sdk, output_kinds = [], [], [], []
    i = 1
    while i < len(argv):
        token = argv[i]
        if token in BARE:
            i += 1
            continue
        arity = {'-lto_library': 1, '-arch': 1, '-platform_version': 3,
                 '-syslibroot': 1, '-o': 1, '-map': 1, '-mllvm': 1,
                 '-framework': 1, '-weak_framework': 1}.get(token)
        if arity is not None:
            values = argv[i + 1:i + 1 + arity]
            if len(values) != arity:
                raise ValueError('missing linker option value')
            if token == '-lto_library':
                files.append(absolute(values[0]))
            elif token in ('-o', '-map'):
                outputs.append(absolute(values[0]))
                output_kinds.append(token)
            elif token == '-syslibroot':
                sdk.append(absolute(values[0]))
            elif token == '-arch':
                arch.append(values[0])
            elif token == '-platform_version':
                platform.append(values)
            elif token == '-mllvm':
                if values != ['-enable-linkonceodr-outlining']:
                    raise ValueError('unsupported LLVM linker option')
            else:
                if not re.fullmatch(r'[A-Za-z0-9_.+-]+', values[0]):
                    raise ValueError('unsupported framework name')
                frameworks.append([token, values[0]])
            i += arity + 1
        elif re.fullmatch(r'-l[A-Za-z0-9_.+-]+', token):
            libraries.append(token)
            i += 1
        elif token.startswith('/') and token.endswith(('.o', '.a', '.tbd')):
            files.append(absolute(token))
            i += 1
        else:
            raise ValueError('unsupported expanded linker argument: ' + token)
    if len(arch) != 1 or len(platform) != 1 or len(sdk) != 1:
        raise ValueError('one architecture/platform/SDK required')
    if (sorted(output_kinds) != ['-map', '-o'] or len(set(outputs)) != 2
            or any(p in files for p in outputs)):
        raise ValueError('distinct binary/map outputs disjoint from inputs required')
    return {'tool': argv[0], 'file_inputs': files, 'outputs': outputs,
            'architecture': arch[0], 'platform': platform[0], 'sdk': sdk[0],
            'frameworks': frameworks, 'libraries': libraries}


def bind(argv):
    """Prebind driver-added runtime archives/plugins, not just original argv.

    The source-bound filesystem resolver is shared with the SDK witness to
    retain every intermediate symlink. The caller separately binds compiler,
    expansion stdout/stderr, environment and SDK interface manifest.
    """
    inventory = parse(argv)
    files = []
    for requested in sorted(set(inventory['file_inputs'])):
        canonical, hops = _resolve(requested)
        # Static snapshots are not a filesystem race/capability guarantee.
        files.append({'requested': requested, 'canonical': canonical, 'hops': hops,
                      **_digest(canonical)})
    return {'inventory': inventory, 'files': files}


def verify(baseline, argv):
    # Exact recursive types matter: Python otherwise treats True as integer 1.
    import json
    current = bind(argv)
    if json.dumps(baseline, sort_keys=True) != json.dumps(current, sort_keys=True):
        raise ValueError('expanded invocation inputs differ from frozen baseline')
