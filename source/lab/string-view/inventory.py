#!/usr/bin/env python3
"""Logical StringView boundary and static conditional alternatives inventory; declarations/calls are not definitions.

This deliberately bounded extractor accepts the two current source files, not
arbitrary C++. It masks literals/comments, then balances each out-of-line body.
A future syntax change must be reviewed rather than silently widening coverage.
"""
import argparse
import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
CPP = ROOT / 'source/core/StarStringView.cpp'
HPP = ROOT / 'source/core/StarStringView.hpp'
OUTPUT = HERE / 'source-map.json'
ORIGINAL = HERE / 'StarStringView.original.cpp'
# Reviewed freezes: the fallback and public class must not drift during promotion.
ORIGINAL_SHA = 'a73916009fca7d23df1df83fd20be455a4137504b35eb897e5bdc6cd33aac60d'
HEADER_SHA = '2a08586162b46431483dc282d6a6a7306bd49e4dd93de8c4650ba74ae659ac3c'
# Qualified host_wrapper.cpp with only the production include/namespace renames.
# This is intentionally a closed grammar, not permission to regenerate new bodies.
WRAPPER_SHA = 'f0bb88508debe56f627437ff92468b4d77c6d5c33ff251902b8cdb3e9f74388d'
COUNTS = dict(member=46, **{'string-bridge': 4}, free=7, formatter=1)



def sha(data):
    return hashlib.sha256(data).hexdigest()


def mask(text):
    token = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
    return token.sub(lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), text)


def definitions(text, line_offset=0, selected=False):
    clean = mask(text)
    pattern = re.compile(r'(?m)^(?!\s)([^;{}]*?(?:StringView::|String::|(?<!\w)operator(?:==|!=|<<|<)|fmt::formatter<Star::StringView>::)[^;{}]*?)\{')
    result = []
    end_previous = 0
    for match in pattern.finditer(clean):
        if match.start() < end_previous:
            continue
        opening = match.end() - 1
        depth = 1
        end = opening + 1
        while depth and end < len(clean):
            depth += (clean[end] == '{') - (clean[end] == '}')
            end += 1
        if depth:
            raise ValueError('unclosed definition')
        signature = ' '.join(text[match.start():opening].split())
        # Calls/declarations must not consume a later function body.
        if not re.search(r'(?:StringView::(?:\w+|operator(?:\[\]|=))|String::(?:String|operator\+=)|operator(?:==|!=|<<|<)|::format)\s*\(', signature):
            raise ValueError('unsupported signature: ' + signature)
        if signature.startswith('fmt::appender '):
            kind = 'formatter'
        elif re.search(r'\bString::', signature):
            kind = 'string-bridge'
        elif re.search(r'\bStringView::', signature):
            kind = 'member'
        else:
            kind = 'free'
        result.append(dict(id=len(result) + 1, kind=kind, signature=signature,
                           line=text.count('\n', 0, match.start()) + 1 + line_offset,
                           endLine=text.count('\n', 0, end - 1) + 1 + line_offset,
                           mode=len(result),
                           bodySha256=sha(text[opening:end].encode()),
                           definitionSha256=sha(text[match.start():end].encode())))
        if selected:
            # Bridge modes 0/1 occur in constructor initializers, so include the
            # signature as well as the balanced body when checking dispatch.
            calls = re.findall(r'\b(bridge|execute)\s*\(\s*(\d+)\s*,', clean[match.start():end])
            mode = len(result) - 1
            if calls != [('bridge' if mode < 4 else 'execute', str(mode))]:
                raise ValueError('selected wrapper positional mode changed: ' + str(mode))
        end_previous = end
    return result


def boundary(text, line_offset=0, selected=False):
    records = definitions(text, line_offset, selected)
    counts = {kind: sum(r['kind'] == kind for r in records) for kind in COUNTS}
    if counts != COUNTS:
        raise ValueError('compiled boundary changed: ' + str(counts))
    return records, counts


def generate(cpp=None, hpp=None):
    cpp = CPP.read_bytes() if cpp is None else cpp
    hpp = HPP.read_bytes() if hpp is None else hpp
    if sha(hpp) != HEADER_SHA:
        raise ValueError('public header freeze changed')
    prefix, separator, suffix = (b'#ifdef STAR_USE_RUST_STRING_VIEW\n',
                                 b'\n#else\n', b'\n#endif\n')
    alternatives = None
    if cpp.startswith(prefix):
        # Byte slices preserve all whitespace, comments and the original EOF.
        # Only this exact outer selector is supported; never strip directives.
        if cpp.count(separator) != 1 or not cpp.endswith(suffix):
            raise ValueError('unsupported outer conditional structure')
        selected, native = cpp[len(prefix):-len(suffix)].split(separator)
        original = ORIGINAL.read_bytes()
        if sha(original) != ORIGINAL_SHA or native != original:
            raise ValueError('native fallback must equal exact frozen original bytes')
        directives = re.findall(r'(?m)^\s*#[^\n]*', mask(cpp.decode()))
        if [x.strip() for x in directives] != [
                '#ifdef STAR_USE_RUST_STRING_VIEW', '#include', '#else', '#include', '#endif']:
            raise ValueError('unsupported branch directives')
        wrappers, wrapper_counts = boundary(selected.decode(), 1, selected=True)
        if sha(selected) != WRAPPER_SHA:
            raise ValueError('selected wrapper freeze changed')
        native_start = len(prefix) + len(selected) + len(separator)
        records, counts = boundary(native.decode(), cpp[:native_start].count(b'\n'))
        if [r['kind'] for r in wrappers] != [r['kind'] for r in records]:
            raise ValueError('branch positional kinds differ')
        alternatives = dict(selector='STAR_USE_RUST_STRING_VIEW',
                            selection='static alternatives; no runtime execution claim',
                            counts=wrapper_counts, definitions=wrappers,
                            sourceSha256=sha(selected), nativeFallbackSha256=sha(native))
    else:
        # Original plain-C++ fixtures retain source-derived extraction; unexpected
        # preprocessor branches cannot silently become a second logical boundary.
        if re.search(r'(?m)^\s*#\s*(?:if|else|elif|endif)', mask(cpp.decode())):
            raise ValueError('unsupported outer conditional structure')
        records, counts = boundary(cpp.decode())
    result = dict(schema=2, generator='python3 -B source/lab/string-view/inventory.py --write',
                  scope='58 logical native definitions including private compare; native Unicode iterator dependency excluded',
                  sources={'source/core/StarStringView.cpp': sha(cpp), 'source/core/StarStringView.hpp': sha(hpp)},
                  counts=counts, definitions=records)
    if alternatives is not None:
        result['selectedWrapperAlternatives'] = alternatives
    return result


def check(path=OUTPUT):
    expected = json.dumps(generate(), indent=2) + '\n'
    if not path.exists() or path.read_text() != expected:
        raise ValueError('StringView inventory missing/stale; explicitly --write after review')
    return 58


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.write:
        OUTPUT.write_text(json.dumps(generate(), indent=2) + '\n')
    else:
        check()
    print('STRING_VIEW_COMPILED_BOUNDARY_58_' + ('WRITTEN' if args.write else 'CURRENT'))


if __name__ == '__main__':
    main()
