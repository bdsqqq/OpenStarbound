#!/usr/bin/env python3
"""Exact compiled StringView boundary inventory; declarations/calls are not definitions.

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


def sha(data):
    return hashlib.sha256(data).hexdigest()


def mask(text):
    token = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
    return token.sub(lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), text)


def definitions(text):
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
                           line=text.count('\n', 0, match.start()) + 1,
                           endLine=text.count('\n', 0, end - 1) + 1,
                           definitionSha256=sha(text[match.start():end].encode())))
        end_previous = end
    return result


def generate(cpp=None, hpp=None):
    cpp = CPP.read_bytes() if cpp is None else cpp
    hpp = HPP.read_bytes() if hpp is None else hpp
    records = definitions(cpp.decode())
    counts = {kind: sum(r['kind'] == kind for r in records) for kind in ('member', 'string-bridge', 'free', 'formatter')}
    if counts != dict(member=46, **{'string-bridge': 4}, free=7, formatter=1):
        raise ValueError('compiled boundary changed: ' + str(counts))
    return dict(schema=1, generator='python3 -B source/lab/string-view/inventory.py --write',
                scope='58 out-of-line definitions including private compare; native Unicode iterator dependency excluded',
                sources={'source/core/StarStringView.cpp': sha(cpp), 'source/core/StarStringView.hpp': sha(hpp)},
                counts=counts, definitions=records)


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
