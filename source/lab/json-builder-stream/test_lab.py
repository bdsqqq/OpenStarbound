"""Source-derived model literals and inventory rejection fixtures (no native run)."""
import copy
import json
import unittest
from pathlib import Path
import model
import inventory

HERE=Path(__file__).resolve().parent
class Contract(unittest.TestCase):
    def test_literals(self):model.literal_checks()
    def test_nested_byte_comparison(self):
        import run
        run.equal([b'/native/object.o'],[b'/native/object.o'],'positive byte list')
        with self.assertRaises(ValueError):run.equal([b'/native/object.o'],[b'/foreign/object.o'],'negative byte list')
        with self.assertRaises(ValueError):run.equal({'exit':0},{'exit':False},'bool distinct from int')
        with self.assertRaises(ValueError):run.equal({'exit':0},{'exit':0.0},'float distinct from int')
    def test_unsigned_bytes(self):
        self.assertEqual(model.dump(('s',b'\x00\x80\xff')),'s0080ff')
        self.assertEqual(model.string([0x7f,0x80,0xd800,0xffffffff]).hex(),'7fc280efbfbdefbfbd')
    def test_typed_scalars(self):
        self.assertNotEqual(model.dump(('i',1)),model.dump(('b',True)))
        self.assertNotEqual(model.dump(('f','0000000000000000')),model.dump(('f','8000000000000000')))
    def test_double_literal_boundaries(self):
        for token,bits in [('4.9406564584124654e-324','0000000000000001'),('1.7976931348623157e308','7fefffffffffffff'),('-1e-400','8000000000000000')]:
            self.assertEqual(model.number('D',tuple(map(ord,token))),('f',bits))
    def test_empty_pop_and_sentry_differ(self):
        b=model.Builder()
        with self.assertRaises(model.Fault) as c:b.apply(model.event('EO'))
        self.assertEqual(c.exception.name,'OutOfRangeException')
        b.apply(model.event('BA'))
        with self.assertRaises(model.Fault) as c:b.apply(model.event('T'))
        self.assertEqual(c.exception.name,'InvalidMaybeAccessException');self.assertEqual(b.stack,[])
    def test_nonstring_consumes_both(self):
        b=model.Builder()
        for e in [('BO',''),('I','1'),('I','2')]:b.apply(model.event(*e))
        with self.assertRaises(model.Fault) as c:b.apply(model.event('EO'))
        self.assertEqual(c.exception.what,b'(JsonException) Cannot convert from int to string');self.assertEqual(b.stack,[None])
    def test_reverse_duplicate_key(self):
        b=model.Builder()
        for op,s in [('BO',''),('K','a'),('I','1'),('K','a'),('I','2'),('K','z'),('I','3'),('K','z'),('I','4')]:b.apply(model.event(op,s))
        with self.assertRaises(model.Fault) as c:b.apply(model.event('EO'))
        self.assertIn(b"key 'z'",c.exception.what)
        self.assertEqual(b.stack,[None,('s',b'a'),('i',1),('s',b'a'),('i',2)])
    def test_manual_inventory(self):
        rows=inventory.manual(HERE/'original/StarJsonBuilder.cpp')
        self.assertEqual(len(rows),20);self.assertEqual(rows[-1]['end'],101)
        self.assertEqual(len({r['name'] for r in rows}),20)
        self.assertNotIn('toJsonStream',{r['name'] for r in rows})
    def test_constructor_name_and_missing_body_detection(self):
        rows=inventory.manual(HERE/'original/StarJsonBuilder.cpp')
        implicit=[{'kind':'CXXConstructorDecl','name':'JsonBuilderStream','isImplicit':True,'isUsed':True,'type':{'qualType':'void ()'}}]
        implicit += [{'kind':'CXXMethodDecl','name':'operator=','isImplicit':True,'isUsed':True}]*4
        implicit += [{'kind':'CXXDestructorDecl','name':'~JsonBuilderStream','isImplicit':True,'isUsed':True}]
        record={'kind':'CXXRecordDecl','name':'JsonBuilderStream','completeDefinition':True,'inner':implicit}
        bodies=[{'kind':'CXXMethodDecl','name':r['name'],'range':{'begin':{'offset':r['begin']},'end':{'offset':r['finish']-1,'tokLen':1}},'inner':[{'kind':'CompoundStmt'}]} for r in rows]
        ast='\n'.join(map(json.dumps,[record,*bodies])).encode()
        self.assertEqual(len(inventory.reconcile(HERE/'original/StarJsonBuilder.cpp',ast)['definitions']),20)
        self.assertEqual(inventory.specials(json.dumps(record).encode())[0]['name'],'JsonBuilderStream')
        with self.assertRaises(ValueError):inventory.reconcile(HERE/'original/StarJsonBuilder.cpp','\n'.join(map(json.dumps,[record,*bodies[:-1]])).encode())
        bad=copy.deepcopy(bodies);bad[-1]['name']='toJsonStream'
        with self.assertRaises(ValueError):inventory.reconcile(HERE/'original/StarJsonBuilder.cpp','\n'.join(map(json.dumps,[record,*bad])).encode())
    def test_replay_deterministic(self):
        self.assertEqual(model.inputs(),model.inputs());self.assertEqual(model.expected(),model.expected())
        self.assertEqual(len(model.inputs().splitlines()),len(model.expected().splitlines()))
        self.assertGreater(len(model.cases()),800)

if __name__=='__main__':unittest.main()
