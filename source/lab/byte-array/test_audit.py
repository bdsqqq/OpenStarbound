import copy
import unittest
import audit
import contract


def member(name,body):
    name=name.encode();n=len(name);size=n+len(body)
    header=(f'#1/{n}'.ljust(16)+'0'.ljust(12)+'0'.ljust(6)+'0'.ljust(6)+'100644'.ljust(8)+str(size).ljust(10)+'`\n').encode()
    return header+name+body+(b'\n' if size%2 else b'')


class AuditTests(unittest.TestCase):
    def test_bsd_archive_bytes(self):
        self.assertEqual(audit.archive_members(b'!<arch>\n'+member('__.SYMDEF',b'index')+member('long-object.cpp.o',b'\0\xffabc')),
                         [(b'long-object.cpp.o',b'\0\xffabc')])

    def test_archive_known_failures(self):
        good=b'!<arch>\n'+member('a.o',b'payload')
        for bad in (good[:-1],good.replace(b'`\n',b'xx',1),b'!<arch>\n'+member('a.o',b'1')+member('a.o',b'2'),b'not archive'):
            with self.subTest(bad=bad[:20]),self.assertRaises(ValueError):audit.archive_members(bad)

    def test_exact_wrong_controllers(self):
        streams={'original':contract.canonical(contract.expected())}
        for k in ('growth-control','signed-control','iterator-control'):streams[k]=contract.canonical(audit.wrong_rows(k))
        result=audit.validate_streams(streams)
        self.assertEqual(set(result),{'growth-control','signed-control','iterator-control'})
        self.assertTrue(all(v>0 for v in result.values()))

    def test_growth_control_includes_filled_resize(self):
        rows=audit.wrong_rows('growth-control')
        selected=[r for r in rows if r['options']['action']=='resize_fill' and r['options']['p']==65]
        self.assertEqual(len(selected),9)
        self.assertTrue(all(r['capacity']==65 for r in selected))
        # The immutable correct native oracle still requires doubled capacity.
        self.assertTrue(all(r['capacity']==128 for r in contract.expected()
                            if r['options']['action']=='resize_fill' and r['options']['p']==65))

    def test_known_forged_control(self):
        rows=audit.wrong_rows('iterator-control');rows[0]['size']=True
        with self.assertRaisesRegex(ValueError,'wrong-controller exact replay'):
            audit.validate_streams({'iterator-control':contract.canonical(rows)})

    def test_missing_or_extra_control_case(self):
        rows=audit.wrong_rows('signed-control')
        for bad in (rows[:-1],rows+[copy.deepcopy(rows[-1])]):
            with self.assertRaises(ValueError):audit.validate_streams({'signed-control':contract.canonical(bad)})

    def test_duplicate_and_nonfinite(self):
        for data in ('{"x":1,"x":1}','{"x":NaN}'):
            with self.assertRaises(ValueError):audit.parse(data)


if __name__=='__main__':unittest.main()
