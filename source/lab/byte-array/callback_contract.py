#!/usr/bin/env python3
"""Source-derived callback traces, frozen independently of any native output."""
import argparse
import hashlib
import json
from pathlib import Path

CASES = ('tie_rhs', 'lhs_small', 'shrink_noextend', 'shrink_extend',
         'grow_large', 'shrink_large', 'flip_roles', 'proxy_convert_shrink',
         'proxy_dtor_grow', 'throw_callback', 'throw_convert', 'reenter',
         'delete_rhs_large', 'delete_this_large')


def receipt(size, capacity, prefix):
    return dict(size=size, capacity=capacity, prefix=list(prefix))


def expected():
    # Literal source traces: inputs are 10,11,... / 40,41,...; callback is 2*a+b.
    # These anchors do not simulate the C++ loop or derive values from native output.
    lhs = [10, 11, 12]
    rhs = [40, 41, 42, 43, 44]
    calls = ['call:1:10:40', 'call:2:11:41', 'call:3:12:42']
    rows = []
    def add(case, size, cap, prefix, events, a=lhs, b=rhs, status='ok', nested=None):
        rows.append(dict(case=case, status=status, events=events,
                         result=None if size is None else receipt(size, cap, prefix),
                         lhs=None if a is None else receipt(len(a), 64, a),
                         rhs=None if b is None else receipt(len(b), 64, b), nested=nested))
    add('tie_rhs', 3, 3, [90, 93, 96],
        ['call:1:40:10', 'call:2:41:11', 'call:3:42:12'], b=rhs[:3])
    add('lhs_small', 5, 8, [60, 63, 66, 43, 44], calls)
    add('shrink_noextend', 3, 3, [60], calls[:1], a=[10])
    add('shrink_extend', 5, 8, [60, 41, 42, 43, 44], calls[:1], a=[10])
    add('grow_large', 7, 8, [60, 63, 42, 43, 44, 77, 77], calls[:2],
        a=lhs[:2], b=rhs + [77, 77])
    add('shrink_large', 3, 8, [60, 63, 42], calls[:2], a=lhs[:2], b=rhs[:3])
    add('flip_roles', 0, 3, [], calls[:1], a=[10], b=[])
    add('proxy_convert_shrink', 5, 8, [60, 41, 42, 43, 44],
        [calls[0], 'convert:1', 'dtor:1'], a=[10])
    add('proxy_dtor_grow', 7, 8, [60, 63, 66, 43, 44, 77, 77],
        [calls[0], 'convert:1', 'dtor:1', calls[1], 'convert:2', 'dtor:2',
         calls[2], 'convert:3', 'dtor:3'], b=rhs + [77, 77])
    add('throw_callback', None, None, None, calls[:1], a=[78, 11, 12], status='throw_same')
    add('throw_convert', None, None, None, [calls[0], 'convert:1', 'dtor:1'],
        b=[79, 41, 42, 43, 44], status='throw_same')
    add('reenter', 5, 8, [60, 63, 66, 43, 44],
        [calls[0], 'nested_begin:1', 'nested:10:40', 'nested:11:41', 'nested:12:42',
         'nested_end:1'] + calls[1:], nested=receipt(3, 3, [50, 52, 54]))
    add('delete_rhs_large', 2, 2, [60, 63], calls[:2] + ['delete_large:2'], a=lhs[:2], b=None)
    add('delete_this_large', 2, 2, [90, 93],
        ['call:1:40:10', 'call:2:41:11', 'delete_large:2'], a=None, b=rhs[:2])
    return rows


def canonical(rows):
    return b''.join((json.dumps(row, sort_keys=True, separators=(',', ':'),
                               ensure_ascii=True, allow_nan=False) + '\n').encode('ascii') for row in rows)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key: ' + key)
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError('nonfinite number: ' + value)


def _typed_equal(actual, wanted, path):
    if type(actual) is not type(wanted):
        raise ValueError('wrong type: ' + path)
    if isinstance(wanted, dict):
        if actual.keys() != wanted.keys():
            raise ValueError('wrong fields: ' + path)
        for key in wanted:
            _typed_equal(actual[key], wanted[key], path + '.' + key)
    elif isinstance(wanted, list):
        if len(actual) != len(wanted):
            raise ValueError('wrong length: ' + path)
        for i, (a, b) in enumerate(zip(actual, wanted)):
            _typed_equal(a, b, path + '[' + str(i) + ']')
    elif actual != wanted:
        raise ValueError('wrong value: ' + path)


def check(data):
    if type(data) is not bytes:
        raise ValueError('expected bytes')
    try:
        lines = data.decode('ascii').splitlines()
        rows = [json.loads(line, object_pairs_hook=_pairs, parse_constant=_nonfinite) for line in lines]
    except (UnicodeError, json.JSONDecodeError) as e:
        raise ValueError('invalid JSONL') from e
    _typed_equal(rows, expected(), 'rows')
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('expected', 'freeze', 'check'))
    parser.add_argument('path', nargs='?')
    args = parser.parse_args()
    if args.command == 'check':
        if args.path is None:
            parser.error('check requires a path')
        print(check(Path(args.path).read_bytes()))
    elif args.command == 'freeze':
        print(json.dumps(dict(count=len(expected()), sha256=hashlib.sha256(canonical(expected())).hexdigest()), sort_keys=True))
    else:
        print(canonical(expected()).decode('ascii'), end='')


if __name__ == '__main__':
    main()
