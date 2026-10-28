#!/usr/bin/env python3
"""Strengthen finite membership without rewriting the acquired auditor epoch.

The acquisition pins audit_auxiliary.py bytes. Keep those bytes intact and wrap
its replay: summing 22 commands alone allowed duplicate reference recipes to
omit the candidate. Actual receipts/admission remain unchanged.
"""
import copy
import json
from pathlib import Path
import audit_auxiliary as original

sha = original.sha
need = original.need
ROOT = original.ROOT


def membership(recipes):
    need([r['role'] for r in recipes] == ['reference', 'candidate'],
         'exact one reference and one candidate recipe, in admitted order')
    prefixes = []
    for recipe in recipes:
        role = recipe['role']
        prefixes.extend(role+'-'+mode for mode in ['compile', 'link', 'decode', 'repeat', 'negative'])
        prefixes.extend('cli/'+role+'/'+name+'/run' for name in original.old.NAMES)
    need(len(prefixes) == len(set(prefixes)) == 22, '22 unique actual command prefixes')
    return prefixes


def membership_controls():
    good = [dict(role='reference'), dict(role='candidate')]
    membership(good)
    rejected = []
    for name, bad in [('duplicate-reference', [good[0], good[0]]),
                      ('duplicate-candidate', [good[1], good[1]]),
                      ('missing-candidate', [good[0]]),
                      ('extra-candidate', good+[good[1]])]:
        try:
            membership(copy.deepcopy(bad))
        except (ValueError, KeyError):
            rejected.append(name)
            continue
        raise ValueError('membership negative control accepted: '+name)
    return rejected


def audit():
    admission = original.load(original.OUT/'admission.json')
    prefixes = membership(admission['recipes'])
    result = original.audit()
    result['uniqueReceiptPrefixes'] = prefixes
    result['negativeControls'] += membership_controls()
    result['bindings'][str(Path(__file__).resolve().relative_to(ROOT))] = sha(__file__)
    result['membershipCorrection'] = 'v1 preserved; duplicate-reference omission now rejected before replay'
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))
