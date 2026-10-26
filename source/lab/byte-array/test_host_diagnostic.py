import unittest
import host_diagnostic as diagnostic
import host_stage


class HostDiagnosticTests(unittest.TestCase):
    def baseline(self):
        return b''.join(b'000000 T Star::ByteArray::method'+str(i).encode()+b'()\n' for i in range(33))

    def test_helper_symbols_are_not_class_definition_credit(self):
        original=self.baseline();candidate=original+b'000000 T Star::ByteArrayHost::helper()\n'
        self.assertEqual(diagnostic.required_abi(original,candidate),{'required_compiled_abi_symbols':33,'extra_emitted_symbols':1})

    def test_known_missing_member_not_hidden_by_helpers(self):
        original=self.baseline();candidate=b'\n'.join(original.splitlines()[1:])+b'\n000000 T Star::ByteArrayHost::helper()\n'
        with self.assertRaises(ValueError):diagnostic.required_abi(original,candidate)

    def test_class_friend_not_layout_change(self):
        before='class ByteArray {\nprivate:\n  char* data;\n};'
        after=before.replace('private:\n','private:\n  friend struct ByteArrayNativeAccess;\n')
        self.assertEqual(diagnostic.class_declaration(before),diagnostic.class_declaration(after))
        self.assertNotEqual(diagnostic.class_declaration(before),diagnostic.class_declaration(after.replace('char* data','char* changed')))

    def test_route_counter_rejects_malformed_and_unbalanced(self):
        good=b'COUNTERS'+b' 1 1 0'*56+b'\n'
        self.assertEqual(len(host_stage.counters(good)),56)
        for bad in (b'COUNTERS\n',good.replace(b' 1 1 0',b' 2 1 0',1)):
            with self.assertRaises(ValueError):host_stage.counters(bad)


if __name__=='__main__':unittest.main()
