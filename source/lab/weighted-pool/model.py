"""pre-observation literal/dyadic contract, separate from the native oracle.

finite positive dyadic arithmetic only; nonfinite/subnormal/overflow probes are
optimized-build diagnostics, never IEEE expectations under -ffast-math.
"""
from fractions import Fraction

CASES = [([], [0, 0.5, 1, 1.25]), ([1], [-0.25, 0, 0.5, 1, 1.25]),
         ([1, 1], [-0.25, 0, 0.25, 0.5, 0.75, 1, 1.25]),
         ([1, 1, 2, 4], [0, 0.125, 0.25, 0.5, 0.75, 1, 1.25]),
         ([-2, -0.0, 0, 1, 1], [0, 0.5, 1, 1.25])]

def corpus():
    rows = []
    expected = []
    for weights, targets in CASES:
        retained = [w for w in weights if w > 0]
        for target in targets:
            rows.append(' '.join(map(str, [len(weights), *weights, target])))
            total = sum(map(Fraction, retained))
            accumulated = Fraction(0)
            index = len(retained) - 1 if retained else -1
            for i, weight in enumerate(retained):
                accumulated += Fraction(weight) / total
                if Fraction(target) <= accumulated:
                    index = i
                    break
            expected.append(str(index))
    return '\n'.join(rows)+'\n', '\n'.join(expected)+'\n'

# Structural/lifecycle properties are asserted in the fixture. These identifiers
# are fixed before compiling; raw native event traces are a distinct oracle.
PROPERTIES = ['accessors-alias', 'copy-move-clear-reuse', 'empty-select-no-random',
 'empty-index-consumes', 'unique-zero-consumes-global-seed', 'unique-index-not-value',
 'unique-seed-wrap-order', 'by-value-container', 'add-full-expression-before-total',
 'throw-move-native-identity', 'throw-copy-select-unwind', 'clear-observer-reentry',
 'nondefault-moveonly-lazy', 'native-range-exception', 'real-random-consumption',
 'real-global-consumption', 'real-static-reference', 'reference-clone-parity']
