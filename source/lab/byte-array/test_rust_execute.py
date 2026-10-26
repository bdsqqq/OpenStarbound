import unittest
import rust_execute as execute
import contract
import callback_contract


class RustExecuteTests(unittest.TestCase):
    def zero(self):return b'COUNTERS'+b' 0 0 0'*56+b'\n'
    def active(self):return b'COUNTERS'+b' 1 1 0'*56+b'\n'

    def test_native_off_has_no_rust_calls(self):
        data=contract.canonical(contract.expected())
        self.assertEqual(len(execute.check(data,self.zero(),'native','lab')),56)
        with self.assertRaises(ValueError):execute.check(data,self.active(),'native','lab')

    def test_rust_frozen_callback_stream(self):
        self.assertEqual(len(execute.check(callback_contract.canonical(callback_contract.expected()),self.active(),'rust','callback')),56)
        rows=callback_contract.expected();rows[0]['result']['size']=True
        with self.assertRaises(ValueError):execute.check(callback_contract.canonical(rows),self.active(),'rust','callback')

    def test_unbalanced_route_rejected(self):
        with self.assertRaises(ValueError):execute.check(contract.canonical(contract.expected()),self.active().replace(b' 1 1 0',b' 2 1 0',1),'rust','lab')

    def test_exact_native_context_protocol_receipt(self):
        self.assertIsNone(execute.check(b'BYTE_ARRAY_NATIVE_PROTOCOL_PASS\n',b'','rust','protocol'))
        with self.assertRaises(ValueError):execute.check(b'PASS\n',b'','rust','protocol')


if __name__=='__main__':unittest.main()
