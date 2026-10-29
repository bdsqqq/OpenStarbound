"""Source-derived literals frozen before native output; no producer imports."""
import copy

EXPECTED = {
    'reentry.copy.assign': {
        'events': ['default:0:size=2', 'dtor:0:size=2', 'ctor:9:size=3',
                   'ctor:8:size=3', 'copy.assign:9<-1:size=2',
                   'copy.assign:8<-2:size=3', 'copy.assign:9<-8:size=3'],
        'state': [1, 2, 8], 'source': [1, 2, 8], 'result': True, 'error': []},
    'reentry.resize.grow': {
        'events': ['default:0:size=0', 'ctor:9:size=2', 'copy.ctor:0:size=1',
                   'copy.ctor:0:size=3', 'dtor:0:size=3'],
        'state': [0, 9, 0], 'source': [], 'result': False, 'error': []},
    'reentry.resize.shrink': {
        'events': ['default:0:size=3', 'dtor:2:size=1', 'dtor:3:size=2',
                   'dtor:1:size=0', 'copy.ctor:0:size=1', 'dtor:0:size=1'],
        'state': [0], 'source': [], 'result': False, 'error': []},
    'reentry.clear': {
        'events': ['dtor:2:size=1', 'dtor:3:size=2', 'dtor:1:size=0'],
        'state': [], 'source': [], 'result': False, 'error': []},
    'ctor.copy.same': {
        'events': ['default:0:size=2', 'copy.ctor:0:size=2', 'copy.ctor:0:size=2',
                   'dtor:0:size=2', 'copy.assign:0<-1:size=2', 'copy.assign:0<-2:size=2'],
        'state': [1, 2], 'source': [1, 2], 'result': False, 'error': []},
    'ctor.copy.capacity': {
        'events': ['copy.ctor:1:size=2', 'copy.ctor:2:size=2'],
        'state': [1, 2], 'source': [1, 2], 'result': False, 'error': []},
    'ctor.range': {
        'events': ['default:0:size=2', 'copy.ctor:0:size=2', 'copy.ctor:0:size=2',
                   'dtor:0:size=2', 'copy.assign:0<-1:size=2', 'copy.assign:0<-2:size=2'],
        'state': [1, 2], 'source': [1, 2], 'result': False, 'error': []},
    'ctor.fill.explicit': {
        'events': ['copy.ctor:7:size=0', 'copy.ctor:7:size=0'],
        'state': [7, 7], 'source': [7], 'result': False, 'error': []},
    'ctor.list.full.expression': {
        'events': ['ctor:1:size=0', 'ctor:2:size=0', 'copy.ctor:1:size=0',
                   'copy.ctor:2:size=0', 'dtor:2:size=0', 'dtor:1:size=0'],
        'state': [1, 2], 'source': [], 'result': False, 'error': []},
    'ctor.copy.unwind': {
        'events': ['default:0:size=2', 'copy.ctor:0:size=2', 'copy.ctor:0:size=2',
                   'dtor:0:size=2', 'copy.assign:0<-1:size=2', 'copy.assign:0<-2:size=2',
                   'throw:copy assignment #2:size=2', 'dtor:0:size=2', 'dtor:1:size=2'],
        'state': [], 'source': [1, 2], 'result': False,
        'error': ['SupplementFailure', 'copy assignment #2']},
    'erase.single.middle': {
        'events': ['move.assign:2<-3:size=3', 'default:0:size=3',
                   'dtor:-1:size=2', 'dtor:0:size=2'],
        'state': [1, 3], 'source': [], 'result': True, 'error': []},
    'erase.range.middle': {
        'events': ['move.assign:2<-4:size=4', 'default:0:size=4',
                   'dtor:-1:size=3', 'dtor:3:size=2', 'dtor:0:size=2'],
        'state': [1, 4], 'source': [], 'result': True, 'error': []},
    'erase.range.empty': {
        'events': ['move.assign:2<-2:size=3', 'move.assign:3<-3:size=3',
                   'default:0:size=3', 'dtor:0:size=3'],
        'state': [1, -777, -777], 'source': [], 'result': True, 'error': []},
    'alias.emplace.reference': {
        'events': ['default:0:size=3', 'copy.ctor:0:size=4', 'dtor:0:size=4',
                   'move.assign:0<-3:size=4', 'move.assign:-1<-2:size=4',
                   'copy.ctor:2:size=4', 'move.assign:-1<-2:size=4', 'dtor:-1:size=4'],
        'state': [1, 2, 2, 3], 'source': [], 'result': False, 'error': []},
    'alias.insert.value': {
        'events': ['copy.ctor:3:size=3', 'default:0:size=3', 'copy.ctor:0:size=4',
                   'dtor:0:size=4', 'move.assign:0<-3:size=4', 'move.assign:-1<-2:size=4',
                   'move.ctor:3:size=4', 'move.assign:-1<-3:size=4',
                   'dtor:-1:size=4', 'dtor:-1:size=4'],
        'state': [1, 3, 2, 3], 'source': [], 'result': True, 'error': []},
    'alignment.runtime64': {
        'events': ['ctor:7:size=1', 'dtor:7:size=0'],
        'state': [], 'source': [64, 0], 'result': True, 'error': []},
    'pop.destructor.throw.once': {
        'events': ['dtor:3:size=2', 'throw:destructor once:size=2'],
        'state': [1, 2], 'source': [], 'result': False,
        'error': ['SupplementFailure', 'destructor once']},
}


def expected_cases():
    return copy.deepcopy(EXPECTED)


def _exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _exact(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def validate(document):
    """Case order is immaterial; event order, fields and exact types are not."""
    if type(document) is not dict or set(document) != {'schema', 'cases'}:
        raise ValueError('invalid document fields')
    if type(document['schema']) is not int or document['schema'] != 1:
        raise ValueError('invalid schema')
    if type(document['cases']) is not list:
        raise ValueError('invalid cases')
    seen = {}
    for case in document['cases']:
        if (type(case) is not dict or set(case) != {'name', 'value'}
                or type(case['name']) is not str):
            raise ValueError('invalid case')
        name = case['name']
        if name in seen or name not in EXPECTED or not _exact(case['value'], EXPECTED[name]):
            raise ValueError('duplicate, unknown, or wrong case: ' + name)
        seen[name] = case['value']
    if set(seen) != set(EXPECTED):
        raise ValueError('missing cases')
    return seen


def semantic_mutant(document, name):
    """Synthetic model rejection controls, NEVER actual native evidence."""
    changed = copy.deepcopy(document)
    witnesses = {
        'copy-cache-bound': ('reentry.copy.assign', 'state', [1, 2, 9]),
        'resize-current-size': ('reentry.resize.grow', 'state', [0, 9]),
        'clear-cache-count': ('reentry.clear', 'error',
                              ['OutOfRangeException', '(OutOfRangeException) StaticVector::pop_back called on empty StaticVector']),
    }
    case_name, field, value = witnesses[name]
    for case in changed['cases']:
        if case['name'] == case_name:
            case['value'][field] = value
            return changed
    raise ValueError('missing mutant witness')
