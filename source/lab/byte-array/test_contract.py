"""Synthetic checks only: no compilation, native execution, or observed-output fitting."""
import copy
import hashlib
import json
import pathlib
import unittest
import contract as c
from rust_seal import branches

class ContractTests(unittest.TestCase):
    def rows(self,op): return [r for r in c.expected() if r['options']['action']==op]
    def one(self,op,n=0,p=0,q=0): return c.model(dict(action=op,n=n,p=p,q=q))
    def test_roundtrip(self):
        rows=c.expected()
        self.assertEqual(len(rows),987)
        self.assertEqual(c.check(c.canonical(rows)),987)
        self.assertEqual(len({r['case'] for r in rows}),987)
        self.assertEqual(hashlib.sha256(c.canonical(rows)).hexdigest(), EXPECTED_SHA256)
    def test_full_definition_inventory(self):
        root=pathlib.Path(__file__).resolve().parents[3]
        cpp=branches((root/'source/core/StarByteArray.cpp').read_text())[1].splitlines()
        hpp=branches((root/'source/core/StarByteArray.hpp').read_text(), True)[1].splitlines()
        compiled=[i for i,s in enumerate(cpp,1) if not s[:1].isspace() and ('ByteArray::' in s or s.startswith('std::ostream& operator<<'))]
        header=[i for i,s in enumerate(hpp,1) if (s.startswith('inline ') or s.startswith('ByteArray ByteArray::combineWith')) and s.endswith('{')]
        self.assertEqual(compiled,[x[0] for x in c.CPP])
        self.assertEqual(header,[x[0] for x in c.HPP])
        mapping=c.source_map()
        self.assertEqual(c.validate_source_map(mapping),56)
        self.assertTrue(all(x['cases'] for x in mapping.values()))
        bad=copy.deepcopy(mapping); bad.pop(next(iter(bad)))
        with self.assertRaises(ValueError): c.validate_source_map(bad)
    def test_defined_domains(self):
        for row in c.corpus():
            o=row['options']; op,n,p,q=(o[k] for k in ('action','n','p','q'))
            r=c.model(o)
            self.assertLessEqual(r['size'],256)
            self.assertLessEqual(r['size'],r['capacity'])
            self.assertEqual(len(r['bytes']),r['size']*2)
            if op in ('copy_ctor','copy_assign','ptr_ctor','fill_ctor'): self.assertGreater(n,0)
            if op=='left': self.assertGreater(p,0)
            if op=='sub': self.assertGreater(min(n,p+q),0); self.assertLessEqual(p+min(n,p+q),64)
            if op=='append_self': self.assertLessEqual(n*2,64)
            if op in ('write','insert','insert_iter'): self.assertLessEqual(max(n+1,p+q),64)
    def test_growth_anchors(self):
        self.assertEqual(c.grown(0,1),1)
        self.assertEqual(c.grown(1,2),8)
        self.assertEqual(c.grown(64,65),128)
        self.assertEqual(self.one('reserve_growth',127,128)['capacity'],254)
        self.assertEqual(self.one('reserve',3,256)['bytes'],'80ff01')
    def test_sub_right_quirks(self):
        self.assertEqual(self.one('sub',3,2,1)['bytes'],'01007f')
        self.assertEqual(self.one('right',3,1)['bytes'],'01007f')
        self.assertEqual(self.one('right',3,0)['bytes'],'007f41')
        self.assertEqual(self.one('right',3,4)['bytes'],'80ff01')
    def test_signed_hash_unsigned_compare(self):
        self.assertEqual(self.one('hash',1)['value'],str((1<<64)-128))
        self.assertEqual(self.one('hash',2)['value'],str((-128*101-1)&c.MASK))
        self.assertEqual(self.one('hash',3)['value'],str(((-128*101-1)*101+1)&c.MASK))
        self.assertEqual(self.one('compare',1,1,1)['value'],'0,1,0,0,1')
    def test_custom_calls_and_identity(self):
        small_left=self.one('custom',1,2,0)
        small_right=self.one('custom',2,1,0)
        self.assertEqual(small_left['value'],'80/d5;')
        self.assertEqual(small_right['value'],'d5/80;')
        for q,count in ((2,1),(3,1),(4,2),(5,2)):
            r=self.one('custom',2,5,q)
            self.assertEqual(r['outcome'],'same_token')
            self.assertEqual(r['calls'],count)
            self.assertEqual(r['bytes'],('81ff' if count==1 else '80ff'))
        self.assertEqual(self.one('custom',0,5,5)['outcome'],'ok')
        self.assertEqual(self.one('custom',0,5,5)['calls'],0)
    def test_insert_and_exception(self):
        self.assertEqual(self.one('insert_iter',3,3)['value'],'4')
        self.assertEqual(self.one('at',0,0)['outcome'],'out_of_range')
        self.assertEqual(self.one('at',3,2)['value'],'01')
    def test_synthetic_native_control_rejections(self):
        for op,field,replacement in (('reserve','capacity',65),('compare','value','0,-1,1,0,1'),('insert_iter','value','0')):
            rows=c.expected()
            target=next(r for r in rows if r['options']==dict(action=op,n=1 if op=='compare' else 0,p=1 if op=='compare' else 65 if op=='reserve' else 0,q=1 if op=='compare' else 0))
            self.assertNotEqual(target[field],replacement)
            target[field]=replacement
            with self.assertRaises(ValueError): c.check(c.canonical(rows))
    def test_strict_rejection(self):
        rows=c.expected()
        for change in ('boolint','extra','missing','case','options','order','drop','upperhex'):
            bad=copy.deepcopy(rows)
            if change=='boolint': bad[0]['size']=False
            elif change=='extra': bad[0]['unexpected']=1
            elif change=='missing': del bad[0]['null']
            elif change=='case': bad[0]['case']='B0'
            elif change=='options': bad[0]['options']['n']=True
            elif change=='order': bad[0],bad[1]=bad[1],bad[0]
            elif change=='drop': bad.pop()
            else: next(r for r in bad if 'ff' in r['bytes'])['bytes']='FF'
            with self.assertRaises(ValueError): c.check(c.canonical(bad))
        data=c.canonical(rows)
        for bad in (data.replace(b'"size":0',b'"size":NaN',1),data.replace(b'"size":0',b'"size":0,"size":0',1),data+b'\n',b'\xff'):
            with self.assertRaises((ValueError,UnicodeDecodeError)): c.check(bad)

EXPECTED_SHA256='05258a405c475acc6d46ec78c74ac67270d70d730ab2cf757ab2ef45f9918d8c'
if __name__=='__main__': unittest.main()
