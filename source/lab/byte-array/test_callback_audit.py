import copy
import unittest
import callback_audit as audit
import callback_contract as contract


class CallbackAuditTests(unittest.TestCase):
    def test_complete_positive_and_wrong_controller_streams(self):
        self.assertEqual(audit.check_stream(contract.canonical(contract.expected()),'current'),14)
        for name in audit.CONTROLS:
            self.assertEqual(audit.check_stream(contract.canonical(audit.expected_control(name)),name),14)

    def test_known_corrupt_lifetime_and_partial_prefix(self):
        for case in ('delete_this_large','shrink_noextend','proxy_dtor_grow'):
            rows=copy.deepcopy(contract.expected())
            row=next(r for r in rows if r['case']==case)
            if case=='delete_this_large':row['lhs']={'size':5,'capacity':64,'prefix':[10,11,12,13,14]}
            elif case=='shrink_noextend':row['result']['prefix']+=[0,0]
            else:row['events']=list(reversed(row['events']))
            with self.assertRaises(ValueError):audit.check_stream(contract.canonical(rows),'original')

    def test_known_control_forgery_rejected(self):
        for name in audit.CONTROLS:
            rows=audit.expected_control(name);rows[0]['result']['capacity']=True
            with self.assertRaises(ValueError):audit.check_stream(contract.canonical(rows),name)
            with self.assertRaises(ValueError):audit.check_stream(contract.canonical(rows[:-1]),name)

    def test_unknown_route(self):
        with self.assertRaises(ValueError):audit.check_stream(contract.canonical(contract.expected()),'invented')


if __name__=='__main__':unittest.main()
