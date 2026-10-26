"""Synthetic controller-control sensitivity only; no native execution credit."""
import copy
import unittest
import host_controls
import trace_contract as contract


class HostControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.base=contract.expected()

    def encoded(self,rows):return contract.canonical(rows)

    def test_missing_or_malformed_control_is_not_semantic_credit(self):
        for data in (b'',b'{',b'{}\n',b'{"x":1,"x":1}\n'):
            with self.subTest(data=data),self.assertRaises(ValueError):host_controls.check('eof-choice',data)

    def test_wrong_exception_choice_is_scoped(self):
        rows=copy.deepcopy(self.base)
        target=next(row for row in rows if row['outcome']=='EOF/new');target['outcome']='IO/new'
        self.assertEqual(host_controls.check('eof-choice',self.encoded(rows)),1)
        target['output']='00'*8
        with self.assertRaises(ValueError):host_controls.check('eof-choice',self.encoded(rows))

    def test_pending_wrap_control_preserves_other_fields(self):
        rows=copy.deepcopy(self.base)
        target=next(row for row in rows if row['outcome']=='IO/wrapped')
        target['outcome']=target['options']['tag']+'/same'
        self.assertEqual(host_controls.check('size-no-wrap',self.encoded(rows)),1)

    def test_zero_io_elision_is_not_allowed_for_nonzero_case(self):
        rows=copy.deepcopy(self.base)
        target=next(row for row in rows if row['options']['action']=='readfull' and row['options']['length']==0)
        target['events']=[];target['outcome']='OK'
        self.assertEqual(host_controls.check('skip-zero-full',self.encoded(rows)),1)
        rows[0]['cursor']=True
        with self.assertRaises(ValueError):host_controls.check('skip-zero-full',self.encoded(rows))


if __name__=='__main__':unittest.main()
