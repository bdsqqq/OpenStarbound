"""Text/schema checks only. Actual C11/C++/Rust parsing requires fresh admission."""
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HEADER = ROOT / 'source/core/StarRustStaticVector.h'
MODES = """DEFAULT_CTOR CTOR_INSERT CTOR_RESIZE RANGE_COPY RANGE_MOVE COPY_ASSIGN
MOVE_ASSIGN LIST_ASSIGN SIZE EMPTY RESIZE AT INDEX PUSH_BACK POP_BACK INSERT_ONE
INSERT_RANGE INSERT_LIST EMPLACE EMPLACE_BACK CLEAR ERASE_ONE ERASE_RANGE EQUAL
NOT_EQUAL LESS""".split()
OPS = """READ_SIZE READ_CAPACITY READ_TARGET READ_INDEX READ_TO_ADD READ_START READ_END
READ_SHIFT READ_REMOVE OTHER_SIZE SELF THROW_RESIZE THROW_AT ASSERT_INDEX THROW_POP
THROW_EMPLACE_BACK INCREMENT_SIZE CONSTRUCT_LAST DECREMENT_SIZE DESTROY_LAST CALL_POP
CALL_EMPLACE_VALUE CALL_RESIZE_OTHER CALL_ASSIGN ITERATOR_PRESENT CALL_EMPLACE_CURRENT
ADVANCE_ITERATOR CALL_FORWARD CALL_RESIZE_ADD CALL_RESIZE_PLUS_ONE CALL_RESIZE_MINUS_ONE
CALL_RESIZE_MINUS_REMOVE MOVE_ASSIGN_SLOTS ASSIGN_FROM_ITERATOR ASSIGN_FROM_ARGS
ELEMENT_NOT_EQUAL CALL_EQUAL COMPARE_PAIR PAIR_LESS PAIR_GREATER""".split()

def constants(text):
    pairs = re.findall(r'SB_STATIC_VECTOR_([A-Z_]+)\s*=\s*([0-9]+)', text)
    if len(pairs) != len(dict(pairs)):
        raise ValueError('duplicate ABI name')
    return {k: int(v) for k, v in pairs}

def validate(text):
    c = constants(text)
    expected = dict(ABI_VERSION=1, OK=0, EXCEPTION=1, INVALID=2, PANIC=3,
                    MODE_COUNT=26, ROOT=0, CONTINUE=1, STAGE_COUNT=2,
                    VOID=0, BOOL=1, SIZE_VALUE=2, OP_COUNT=40)
    expected.update({n: i for i, n in enumerate(MODES)})
    expected.update({n: i for i, n in enumerate(OPS, 1)})
    if c != expected:
        raise ValueError('ABI constant drift')
    return c

class Schema(unittest.TestCase):
    def test_complete_schema(self):
        validate(HEADER.read_text())
        self.assertEqual(len(MODES), 26)
        self.assertEqual(len(OPS), 40)

    def test_known_drift_is_rejected(self):
        text = HEADER.read_text()
        with self.assertRaises(ValueError):
            validate(text.replace('SB_STATIC_VECTOR_MODE_COUNT = 26', 'SB_STATIC_VECTOR_MODE_COUNT = 27'))

    def test_duplicate_is_rejected(self):
        with self.assertRaises(ValueError):
            validate(HEADER.read_text() + '\nSB_STATIC_VECTOR_ROOT = 0')

    def test_scalar_c_shapes_and_signatures(self):
        text = HEADER.read_text()
        self.assertIn('uint32_t size, version, op, reserved;', text)
        self.assertIn('uint64_t arg0, arg1;', text)
        self.assertIn('uint32_t size, version, tag, reserved;', text)
        self.assertIn('uint64_t value;', text)
        self.assertIn('uint64_t sb_static_vector_count(uint32_t mode, uint32_t stage);', text)

if __name__ == '__main__':
    unittest.main()
