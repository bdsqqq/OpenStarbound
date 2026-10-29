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
SELECTORS = (*_legacy.SELECTORS, STATIC_VECTOR)


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
    need(len(declared) == len(set(declared)) == len(SELECTORS) == 30 and
         set(declared) == set(SELECTORS), 'exact current30 selector declarations')
    need(len(rows) == 30 and dict(rows) == {key: 'OFF' for key in SELECTORS},
         'all source selector defaults must remain OFF')


def validate_profile(role, values):
    validate_source()
    need(role in profiles(), 'exact reference/candidate role required')
    need(values == profiles()[role], 'unsupported production selector profile')


def configure_options(role):
    validate_source()
    need(role in profiles(), 'exact reference/candidate role required')
    return ['-D' + key + '=' + value for key, value in sorted(profiles()[role].items())]


def validate_cache(role, text):
    entries = re.findall(r'^(STAR_USE_RUST_[A-Z0-9_]+):([^=\n]+)=(.*)$', text, re.M)
    need(len(entries) == 30 and all(kind == 'BOOL' and value in ('ON', 'OFF') for _, kind, value in entries),
         'exact30 BOOL cached selectors required')
    rows = [(key, value) for key, _, value in entries]
    need(len(dict(rows)) == 30, 'unique cached selectors required')
    validate_profile(role, dict(rows))


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
