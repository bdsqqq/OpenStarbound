"""Source-first value oracle; never imports or executes the native producer.

Coverage: constructors and assignments (including preserved int move sources),
size/empty/MaximumSize, access/iteration/ptr, growth/shrink/clear, all valid
single/range insert and erase offsets, comparison value branches, typed errors.
Int self-moves leave values unchanged. This is NOT a lifetime/event oracle.
Deferred before ABI promotion: lifetime/full-expression/read-only reentry,
recoverable element throws, move-only/overaligned/non-default element constraints,
lazy initializer-list assignment compile-negative, invalid-domain diagnostics.
"""

# Literal vectors and returns, specified from StarStaticVector.hpp before native
# execution. Exception prefixes come from StarException_unix.cpp what(): the
# printer receives false (no stack), then emits '(' + type + ') ' + message.
EXPECTED = {
    'default.0': [], 'default.1': [], 'default.2': [], 'default.4': [],
    'meta.0': [0, 1, 0, 1, 1], 'meta.1': [0, 1, 1, 1, 1],
    'meta.2': [0, 1, 2, 1, 1], 'meta.4': [0, 1, 4, 1, 1],
    'fill.default': [0, 0], 'fill.value': [7, 7, 7, 7],
    'fill.zero': [], 'list.empty': [], 'list.one': [9],
    'list.full': [1, 2, 3, 4], 'range': [2, 3], 'range.empty': [],
    'copy': [1, 2], 'copy.source': [1, 2], 'copy.empty': [],
    'move': [1, 2], 'move.source': [1, 2], 'move.empty': [],
    'convert': [3, 4], 'convert.empty': [],
    'assign.copy.grow': [1, 2, 3], 'assign.copy.return': True,
    'assign.copy.shrink': [8], 'assign.copy.empty': [],
    'assign.move.grow': [1, 2, 3], 'assign.move.return': True,
    'assign.move.source': [1, 2, 3], 'assign.move.shrink': [8],
    'assign.move.shrink.source': [8], 'assign.move.empty': [],
    'assign.self.copy': [1, 2], 'assign.self.copy.return': True,
    'assign.self.move': [1, 2], 'assign.self.move.return': True,
    'access.const': [1, 2, 3, 4], 'access.mutable': [11, 22, 33, 44],
    'access.reverse': [44, 33, 22, 11], 'access.const.reverse': [44, 33, 22, 11],
    'access.links': [1, 1, 4, 4],
    'push.one': [5], 'push.full': [5, 6], 'pop': [5], 'pop.empty': [],
    'emplace.back': [8], 'resize.grow': [8, 6, 6, 6],
    'resize.same': [8, 6, 6, 6], 'resize.shrink': [8, 6],
    'resize.default': [8, 6, 0, 0], 'resize.zero': [],
    'clear': [], 'clear.again': [],
    'insert.single.0': [9, 1, 2, 3], 'insert.single.0.return': 0,
    'insert.single.1': [1, 9, 2, 3], 'insert.single.1.return': 1,
    'insert.single.2': [1, 2, 9, 3], 'insert.single.2.return': 2,
    'insert.single.3': [1, 2, 3, 9], 'insert.single.3.return': 3,
    'insert.empty.vector': [9], 'insert.empty.vector.return': 0,
    'emplace.0': [9, 1, 2, 3], 'emplace.1': [1, 9, 2, 3],
    'emplace.2': [1, 2, 9, 3], 'emplace.3': [1, 2, 3, 9],
    'insert.range.0': [8, 9, 1, 2], 'insert.range.0.return': 0,
    'insert.range.1': [1, 8, 9, 2], 'insert.range.1.return': 1,
    'insert.range.2': [1, 2, 8, 9], 'insert.range.2.return': 2,
    'insert.list': [1, 8, 9, 2], 'insert.list.return': 1,
    'insert.range.overlap': [8, 1, 2, 3], 'insert.range.overlap.return': 0,
    'insert.empty.0': [1, 2], 'insert.empty.0.return': 0,
    'insert.empty.1': [1, 2], 'insert.empty.1.return': 1,
    'insert.empty.2': [1, 2], 'insert.empty.2.return': 2,
    'insert.empty.zero': [], 'insert.empty.zero.return': 0,
    'erase.single.0': [2, 3, 4], 'erase.single.0.return': 0,
    'erase.single.1': [1, 3, 4], 'erase.single.1.return': 1,
    'erase.single.2': [1, 2, 4], 'erase.single.2.return': 2,
    'erase.single.3': [1, 2, 3], 'erase.single.3.return': 3,
    'erase.only': [], 'erase.only.return': 0,
    'erase.range.0.0': [1, 2, 3, 4], 'erase.range.0.0.return': 0,
    'erase.range.0.1': [2, 3, 4], 'erase.range.0.1.return': 0,
    'erase.range.0.2': [3, 4], 'erase.range.0.2.return': 0,
    'erase.range.0.3': [4], 'erase.range.0.3.return': 0,
    'erase.range.0.4': [], 'erase.range.0.4.return': 0,
    'erase.range.1.1': [1, 2, 3, 4], 'erase.range.1.1.return': 1,
    'erase.range.1.2': [1, 3, 4], 'erase.range.1.2.return': 1,
    'erase.range.1.3': [1, 4], 'erase.range.1.3.return': 1,
    'erase.range.1.4': [1], 'erase.range.1.4.return': 1,
    'erase.range.2.2': [1, 2, 3, 4], 'erase.range.2.2.return': 2,
    'erase.range.2.3': [1, 2, 4], 'erase.range.2.3.return': 2,
    'erase.range.2.4': [1, 2], 'erase.range.2.4.return': 2,
    'erase.range.3.3': [1, 2, 3, 4], 'erase.range.3.3.return': 3,
    'erase.range.3.4': [1, 2, 3], 'erase.range.3.4.return': 3,
    'erase.range.4.4': [1, 2, 3, 4], 'erase.range.4.4.return': 4,
    'erase.empty': [], 'erase.empty.return': 0,
    # Each triple is [==, !=, <]. Distinct objects unless named self.
    'compare.self': [True, False, False],
    'compare.empty': [True, False, False],
    'compare.equal': [True, False, False],
    'compare.short': [False, True, True],
    'compare.long': [False, True, False],
    'compare.first.less': [False, True, True],
    'compare.first.greater': [False, True, False],
    'compare.later.less': [False, True, True],
    'compare.later.greater': [False, True, False],
    'compare.empty.left': [False, True, True],
    'compare.empty.right': [False, True, False],
    'error.at.mutable': ['OutOfRangeException', '(OutOfRangeException) out of range in StaticVector::at(2)', [1, 2]],
    'error.at.const': ['OutOfRangeException', '(OutOfRangeException) out of range in StaticVector::at(3)', [1, 2]],
    'error.pop': ['OutOfRangeException', '(OutOfRangeException) StaticVector::pop_back called on empty StaticVector', []],
    'error.resize.0': ['StaticVectorSizeException', '(StaticVectorSizeException) StaticVector::resize(1) out of range 0', []],
    'error.resize.quirk': ['StaticVectorSizeException', '(StaticVectorSizeException) StaticVector::resize(7) out of range 4', [1, 2]],
    'error.push.0': ['StaticVectorSizeException', '(StaticVectorSizeException) StaticVector::emplace_back would extend StaticVector beyond size 0', []],
    'error.push.1': ['StaticVectorSizeException', '(StaticVectorSizeException) StaticVector::emplace_back would extend StaticVector beyond size 1', [1]],
    'error.emplace.back': ['StaticVectorSizeException', '(StaticVectorSizeException) StaticVector::emplace_back would extend StaticVector beyond size 2', [1, 2]],
    'error.insert.single': ['StaticVectorSizeException', '(StaticVectorSizeException) StaticVector::resize(5) out of range 2', [1, 2]],
    'error.insert.range': ['StaticVectorSizeException', '(StaticVectorSizeException) StaticVector::resize(6) out of range 2', [1, 2]],
    'error.emplace': ['StaticVectorSizeException', '(StaticVectorSizeException) StaticVector::resize(5) out of range 2', [1, 2]],
}


def expected_cases():
    """Return isolated literals so callers cannot silently mutate the oracle."""
    import copy
    return copy.deepcopy(EXPECTED)


def _exact(a, b):
    # Python otherwise treats True == 1; native schema must retain JSON types.
    return type(a) is type(b) and (len(a) == len(b) and all(
        _exact(x, y) for x, y in zip(a, b)) if isinstance(a, list) else a == b)


def validate(document):
    """Validate full membership/value identity; ABI numbers are observations only."""
    if type(document) is not dict or set(document) != {'schema', 'cases', 'abiObservations'}:
        raise ValueError('invalid document fields')
    if type(document['schema']) is not int or document['schema'] != 1:
        raise ValueError('invalid schema')
    if type(document['cases']) is not list:
        raise ValueError('invalid cases')
    seen = {}
    for case in document['cases']:
        if type(case) is not dict or set(case) != {'name', 'value'} or type(case['name']) is not str:
            raise ValueError('invalid case')
        name = case['name']
        if name in seen or name not in EXPECTED or not _exact(case['value'], EXPECTED[name]):
            raise ValueError('duplicate, unknown, or wrong case: ' + name)
        seen[name] = case['value']
    if set(seen) != set(EXPECTED):
        raise ValueError('missing cases')
    abi = document['abiObservations']
    if type(abi) is not dict or set(abi) != {'int.0', 'int.1', 'int.2', 'int.4'}:
        raise ValueError('invalid ABI observation names')
    for value in abi.values():
        if type(value) is not dict or set(value) != {'sizeof', 'alignof'} or any(
                type(n) is not int or n <= 0 for n in value.values()):
            raise ValueError('invalid ABI observation shape')
    return seen


def semantic_mutant(document, name):
    """Isolated value controls, NOT substitutes for compiling mutated headers.

    Parent should additionally mutate the copied move constructor to clear other;
    reverse range insertion's descending shift loop; or replace m_size + size in
    resize's error with size. These cases are intended rejection witnesses.
    """
    import copy
    changed = copy.deepcopy(document)
    replacements = {
        'move-clears-source': ('move.source', []),
        'forward-shift': ('insert.range.overlap', [8, 1, 1, 1]),
        'resize-request-only': ('error.resize.quirk', [
            'StaticVectorSizeException',
            '(StaticVectorSizeException) StaticVector::resize(5) out of range 4', [1, 2]]),
    }
    case_name, value = replacements[name]
    for case in changed['cases']:
        if case['name'] == case_name:
            case['value'] = value
            return changed
    raise ValueError('missing mutant witness')
