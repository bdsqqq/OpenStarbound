import copy
import unittest
import callback_contract as c


class Callbacks(unittest.TestCase):
    def test_independent_terminal_literals(self):
        rows=c.expected();self.assertEqual(len(rows),14)
        self.assertEqual(rows[0],dict(id='pattern-0',value=['61','0','1','deleted','calls=1','dead']))
        self.assertEqual(rows[2]['value'][-5:],['deleted','terminal-marker','same-exception','calls=3','dead'])
        self.assertEqual(rows[5]['value'],['61','0','1','terminal-marker','same-exception','calls=1','alive'])
        self.assertEqual(rows[4]['value'][:9],['61','0','1','76','2','1','77','4','1'])
        c.check(c.canon(rows))

    def test_missing_identity_deletion_or_callback_rejected(self):
        for label in ('same-exception','deleted','calls=3'):
            rows=copy.deepcopy(c.expected())
            row=next(r for r in rows if label in r['value'])
            row['value'].remove(label)
            with self.assertRaises(ValueError):c.check(c.canon(rows))


if __name__=='__main__':unittest.main()
