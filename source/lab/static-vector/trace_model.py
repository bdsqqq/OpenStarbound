"""Independent source-first lifetime oracle. No producer execution or output goldens.

Event strings record operation, pre-mutation operand values, and the observed
owner size. Only read-only size reentry is exercised. See EDGES.md for domain.
"""
import copy

# Fixed from the complete frozen class algorithm BEFORE any native execution.
# State/source are snapshots, not an implementation of StaticVector.
EXPECTED = {
    'emplace.back.publish': {
        'events': ['ctor:7:size=1'], 'state': [7], 'source': [], 'result': False, 'error': []},
    'pop.publish': {
        'events': ['dtor:2:size=1'], 'state': [1], 'source': [], 'result': False, 'error': []},
    'push.named': {
        'events': ['copy.ctor:5:size=0', 'move.ctor:5:size=1', 'dtor:-1:size=1'],
        'state': [5], 'source': [5], 'result': False, 'error': []},
    'resize.same': {
        'events': ['default:0:size=2', 'dtor:0:size=2'],
        'state': [1, 2], 'source': [], 'result': False, 'error': []},
    'resize.grow': {
        'events': ['default:0:size=1', 'copy.ctor:0:size=2', 'copy.ctor:0:size=3', 'dtor:0:size=3'],
        'state': [8, 0, 0], 'source': [], 'result': False, 'error': []},
    'clear.reverse': {
        'events': ['dtor:3:size=2', 'dtor:2:size=1', 'dtor:1:size=0'],
        'state': [], 'source': [], 'result': False, 'error': []},
    'emplace.middle': {
        'events': ['default:0:size=2', 'copy.ctor:0:size=3', 'dtor:0:size=3',
                   'move.assign:0<-2:size=3', 'ctor:9:size=3',
                   'move.assign:-1<-9:size=3', 'dtor:-1:size=3'],
        'state': [1, 9, 2], 'source': [], 'result': False, 'error': []},
    'insert.empty': {
        'events': ['default:0:size=3', 'dtor:0:size=3',
                   'move.assign:3<-3:size=3', 'move.assign:2<-2:size=3'],
        'state': [1, -777, -777], 'source': [], 'result': True, 'error': []},
    'move.construct': {
        'events': ['move.ctor:1:size=2', 'move.ctor:2:size=2'],
        'state': [1, 2], 'source': [-1, -1], 'result': False, 'error': []},
    'move.assign': {
        'events': ['default:0:size=1', 'copy.ctor:0:size=2', 'dtor:0:size=2',
                   'move.assign:8<-1:size=2', 'move.assign:0<-2:size=2'],
        'state': [1, 2], 'source': [-1, -1], 'result': True, 'error': []},
    'move.self': {
        'events': ['default:0:size=2', 'dtor:0:size=2',
                   'move.assign:1<-1:size=2', 'move.assign:2<-2:size=2'],
        'state': [-777, -777], 'source': [], 'result': True, 'error': []},
    'copy.assign.throw': {
        'events': ['default:0:size=3', 'dtor:0:size=3',
                   'copy.assign:9<-1:size=3', 'copy.assign:8<-2:size=3', 'throw:copy assignment #2:size=3'],
        'state': [1, 8, 7], 'source': [1, 2, 3], 'result': False,
        'error': ['TraceFailure', 'copy assignment #2']},
    'compare.equal': {
        'events': ['ne:1,1:size=2', 'ne:2,2:size=2'],
        'state': [1, 2], 'source': [1, 2], 'result': True, 'error': []},
    'compare.self': {
        'events': [], 'state': [1, 2], 'source': [], 'result': True, 'error': []},
    'order.less': {
        'events': ['lt:1,1:size=2', 'lt:1,1:size=2', 'lt:2,3:size=2'],
        'state': [1, 2], 'source': [1, 3], 'result': True, 'error': []},
    'order.greater': {
        'events': ['lt:1,1:size=2', 'lt:1,1:size=2', 'lt:3,2:size=2', 'lt:2,3:size=2'],
        'state': [1, 3], 'source': [1, 2], 'result': False, 'error': []},
    'compare.throw': {
        'events': ['ne:1,1:size=2', 'ne:2,3:size=2', 'throw:comparison #2:size=2'],
        'state': [1, 2], 'source': [1, 3], 'result': False,
        'error': ['TraceFailure', 'comparison #2']},
    'order.throw': {
        'events': ['lt:2,1:size=2', 'lt:1,2:size=2', 'throw:comparison #2:size=2'],
        'state': [2, 9], 'source': [1, 8], 'result': False,
        'error': ['TraceFailure', 'comparison #2']},
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
    """Reject unknown/missing/duplicate cases, fields, values, order and types."""
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
    """Synthetic rejection controls; NOT evidence of native mutant execution."""
    changed = copy.deepcopy(document)
    witnesses = {
        'emplace-publish-after': ('emplace.back.publish', 'events', ['ctor:7:size=0']),
        'pop-publish-after': ('pop.publish', 'events', ['dtor:2:size=2']),
        'empty-insert-return-after-resize': ('insert.empty', 'events',
                                             ['default:0:size=3', 'dtor:0:size=3']),
    }
    case_name, field, value = witnesses[name]
    for case in changed['cases']:
        if case['name'] == case_name:
            case['value'][field] = value
            if name == 'empty-insert-return-after-resize':
                case['value']['state'] = [1, 2, 3]
            return changed
    raise ValueError('missing mutant witness')
