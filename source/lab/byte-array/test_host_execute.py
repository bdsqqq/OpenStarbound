import unittest
import host_execute as execute
import contract
import callback_contract
import audit


class HostExecuteTests(unittest.TestCase):
    def counters(self):return b'COUNTERS'+b' 1 1 0'*56+b'\n'

    def test_frozen_streams_and_protocol(self):
        self.assertEqual(len(execute.check('lab',contract.canonical(contract.expected()),self.counters())),56)
        self.assertEqual(len(execute.check('callback',callback_contract.canonical(callback_contract.expected()),self.counters())),56)
        self.assertIsNone(execute.check('protocol',b'BYTE_ARRAY_NATIVE_PROTOCOL_PASS\n',b''))

    def test_source_derived_normal_controls(self):
        for name,model in [('growth','growth-control'),('signed','signed-control')]:
            self.assertEqual(len(execute.check(name,contract.canonical(audit.wrong_rows(model)),self.counters())),56)
            with self.assertRaises(ValueError):execute.check(name,contract.canonical(contract.expected()),self.counters())

    def test_missing_route_or_pending_balance(self):
        data=contract.canonical(contract.expected())
        for bad in (b'',self.counters().replace(b' 1 1 0',b' 1 0 0',1)):
            with self.assertRaises(ValueError):execute.check('lab',data,bad)

    def test_protocol_receipt_cannot_hide_stderr(self):
        for out,err in [(b'PASS\n',b''),(b'BYTE_ARRAY_NATIVE_PROTOCOL_PASS\n',b'CHECK failed\n')]:
            with self.assertRaises(ValueError):execute.check('protocol',out,err)


if __name__=='__main__':unittest.main()
