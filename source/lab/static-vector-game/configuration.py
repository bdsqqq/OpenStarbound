"""Supported scene26 profiles; no configure/compiler or historical-plan loading."""
import importlib.util
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
STATIC_VECTOR = 'STAR_USE_RUST_STATIC_VECTOR'
_spec = importlib.util.spec_from_file_location(
    '_static_vector_current_production_profiles',
    ROOT / 'source/lab/id-map-production/game_build_admission.py')
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
# scene26 keeps its historical 30-selector projection; newer kernels are not admitted.
SELECTORS = (*_legacy.SELECTORS, STATIC_VECTOR)
BIMAP = 'STAR_USE_RUST_BIMAP'
UUID = 'STAR_USE_RUST_UUID'
ORDERED_SET = 'STAR_USE_RUST_ORDERED_SET'
SET = 'STAR_USE_RUST_SET'
FLAT_HASH_TABLE = 'STAR_USE_RUST_FLAT_HASH_TABLE'
MAP = 'STAR_USE_RUST_MAP'
PERIODIC = 'STAR_USE_RUST_PERIODIC'
WORKER_POOL = 'STAR_USE_RUST_WORKER_POOL'
TIME = 'STAR_USE_RUST_TIME'
CURRENT_SELECTORS = (*SELECTORS, BIMAP, UUID, ORDERED_SET, SET, FLAT_HASH_TABLE, MAP, PERIODIC, WORKER_POOL, TIME)


def need(ok, why):
    if not ok:
        raise ValueError(why)


def profiles():
    # Inherit the EXISTING exclusion rather than inventing "all selectors on".
    # StarLine.hpp rejects LINE_QUERY + fast-math; neither flag is repaired here.
    return {role: dict(values, **{STATIC_VECTOR: 'ON' if role == 'candidate' else 'OFF'})
            for role, values in _legacy.profiles().items()}


def validate_source(text=None):
    if text is None:
        text = (ROOT / 'source/CMakeLists.txt').read_text()
    declared = re.findall(r'\b(?i:option)\s*\(\s*(STAR_USE_RUST_\w+)\b', text)
    rows = re.findall(r'\b(?i:option)\s*\(\s*(STAR_USE_RUST_\w+)\s+"[^"\n]*"\s+(ON|OFF)\s*\)', text)
    need(len(declared) == len(set(declared)) == len(CURRENT_SELECTORS) and
         set(declared) == set(CURRENT_SELECTORS), 'exact current selector declarations')
    need(len(rows) == len(CURRENT_SELECTORS) and dict(rows) == {key: 'OFF' for key in CURRENT_SELECTORS},
         'all source selector defaults must remain OFF')


def validate_profile(role, values):
    validate_source()
    need(role in profiles(), 'exact reference/candidate role required')
    need(values == profiles()[role], 'unsupported production selector profile')


def configure_options(role):
    validate_source()
    need(role in profiles(), 'exact reference/candidate role required')
    values = dict(profiles()[role], **{BIMAP: 'OFF', UUID: 'OFF', ORDERED_SET: 'OFF', SET: 'OFF', FLAT_HASH_TABLE: 'OFF', MAP: 'OFF', PERIODIC: 'OFF', WORKER_POOL: 'OFF', TIME: 'OFF'})
    return ['-D' + key + '=' + value for key, value in sorted(values.items())]


def validate_cache(role, text):
    entries = re.findall(r'^(STAR_USE_RUST_[A-Z0-9_]+):([^=\n]+)=(.*)$', text, re.M)
    need(len(entries) == len(CURRENT_SELECTORS) and all(kind == 'BOOL' and value in ('ON', 'OFF') for _, kind, value in entries),
         'exact current BOOL cached selectors required')
    rows = {key: value for key, _, value in entries}
    need(len(rows) == len(CURRENT_SELECTORS), 'unique cached selectors required')
    need(set(rows) == set(CURRENT_SELECTORS), 'exact current cached selectors required')
    need(rows.pop(BIMAP) == 'OFF', 'BiMap must remain OFF')
    need(rows.pop(UUID) == 'OFF', 'UUID must remain OFF')
    need(rows.pop(ORDERED_SET) == 'OFF', 'OrderedSet must remain OFF')
    need(rows.pop(SET) == 'OFF', 'Set must remain OFF')
    need(rows.pop(FLAT_HASH_TABLE) == 'OFF', 'FlatHashTable must remain OFF')
    need(rows.pop(MAP) == 'OFF', 'Map must remain OFF')
    need(rows.pop(PERIODIC) == 'OFF', 'Periodic must remain OFF')
    need(rows.pop(WORKER_POOL) == 'OFF', 'WorkerPool must remain OFF')
    need(rows.pop(TIME) == 'OFF', 'Time must remain OFF')
    validate_profile(role, rows)


def validate_flags(role, flags):
    """Check explicit Rust switches, not arbitrary source/response-file preprocessing.

    Both -DNAME and -D NAME count; NAME=0 still enables #ifdef, so value-bearing
    Rust definitions are rejected rather than misread as OFF. Fresh source and
    actual compiler dependencies still need their separate admission guards.
    """
    validate_source()
    need(role in profiles(), 'exact reference/candidate role required')
    enabled = []
    words = iter(flags)
    for word in words:
        need(not word.startswith('@'), 'expand response files before profile validation')
        if word in ('-D', '-U'):
            operation = word
            definition = next(words, None)
            need(definition is not None, 'dangling preprocessor switch')
        elif word.startswith(('-D', '-U')):
            operation, definition = word[:2], word[2:]
        else:
            continue
        key, separator, _ = definition.partition('=')
        if not key.startswith('STAR_USE_RUST_'):
            continue
        need(operation == '-D' and not separator, 'Rust selectors require bare positive definitions')
        need(key in SELECTORS, 'unknown Rust selector')
        need(key not in enabled, 'duplicate Rust selector definition')
        enabled.append(key)
    expected = {key for key, value in profiles()[role].items() if value == 'ON'}
    need(set(enabled) == expected, 'compiler Rust definitions differ from supported production profile')
