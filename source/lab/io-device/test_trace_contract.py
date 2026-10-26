"""Synthetic model/validator regressions. No native execution or native credit."""
import copy
import hashlib
import json
import pathlib
import unittest
import trace_contract as t

class TraceContractTests(unittest.TestCase):
    def test_second_iteration_after_throw_commits_caller_offset(self):
        r=t.Controller(t.options('readfullabs',faultOp='read',faultIndex=2,phase='after')).run()
        self.assertEqual(r['output'],'4141424251515151')
        self.assertEqual(r['cursor'],0)
        self.assertEqual(r['outcome'],'IO/same')
        self.assertEqual([(x['phase'],x['ptr']) for x in r['events'] if x['op']=='read'],
                         [('before',0),('mutated',0),('return',0),('before',2),('mutated',2),('throw',2)])
        self.assertEqual(r['events'][-1]['phase'],'throw')
    def test_second_iteration_before_throw_retains_only_first(self):
        r=t.Controller(t.options('readfullabs',faultOp='read',faultIndex=2,phase='before')).run()
        self.assertEqual((r['output'],r['cursor']),('4141515151515151',-2))
    def test_write_after_throw_retains_sink(self):
        r=t.Controller(t.options('writefullabs',faultOp='write',faultIndex=2,phase='after')).run()
        self.assertEqual((r['sink'],r['cursor']),('61626364',0))
    def test_restore_failure_does_not_advance_controller(self):
        r=t.Controller(t.options('readfullabs',faultOp='seek',faultIndex=2,phase='after')).run()
        self.assertEqual(r['output'],'4141515151515151')
        self.assertEqual(r['cursor'],6)
        self.assertEqual(len([e for e in r['events'] if e['op']=='read' and e['phase']=='before']),1)
    def test_temp_partial_throw_only_records_known_writes(self):
        r=t.Controller(t.options('readbytesabs',faultOp='read',faultIndex=2,phase='after')).run()
        self.assertEqual(r['output'],'51'*8)
        self.assertEqual(r['writes'],['temp/0/4141','temp/2/4242'])
        self.assertIsNone(r['value'])
    def test_primitive_kind_phase_type_are_independent(self):
        p=t.Primitive(t.options('readfull',faultOp='read',faultIndex=1,phase='after',tag='OTHER'))
        with self.assertRaises(t.Fault) as c:p.call('read','caller',2,2)
        self.assertEqual(c.exception.tag,'OTHER')
        self.assertEqual(p.output,b'QQAAQQQQ')
        self.assertEqual([e['phase'] for e in p.events],['before','mutated','throw'])
        self.assertFalse(t.strict_equal(True,1))
    def test_size_io_wrap_vs_other_identity(self):
        for phase in ('before','after'):
            for tag,want in (('IO','IO/wrapped'),('EOF','IO/wrapped'),('OTHER','OTHER/same')):
                r=t.Controller(t.options('size',faultOp='seek',faultIndex=1,phase=phase,tag=tag)).run()
                self.assertEqual(r['outcome'],want)
                self.assertEqual(r['cursor'],6 if phase=='before' else 8)
    def test_empty_wrappers_and_null_distinction(self):
        self.assertFalse(t.Controller(t.options('readbytes',length=0)).run()['events'])
        self.assertFalse(t.Controller(t.options('writebytesabs',length=0)).run()['events'])
        r=t.Controller(t.options('writebytes',length=0)).run()
        self.assertEqual((r['events'][0]['op'],r['events'][0]['kind']),('write','null'))
        self.assertEqual(t.Controller(t.options('readfull',length=0)).run()['events'][0]['kind'],'caller')
    def test_short_single_and_absolute_zero_progress(self):
        r=t.Controller(t.options('readfull',length=4,chunk=2,eof=True)).run()
        self.assertEqual(r['outcome'],'EOF/new')
        self.assertEqual([e['op'] for e in r['events'] if e['phase']=='before'],['read','end'])
        r=t.Controller(t.options('readfullabs',length=t.MAX,chunk=0)).run()
        self.assertEqual(r['outcome'],'IO/new')
        self.assertNotIn('end',[e['op'] for e in r['events']])
    def test_mode_domain_and_lazy_open(self):
        cs=t.corpus()
        for a in ('construct','copy','assign','self','set','close','open'):
            self.assertEqual({c['options']['mode'] for c in cs if c['options']['action']==a},set(range(256)))
        self.assertFalse(t.Controller(t.options('open')).run()['events'])
        r=t.Controller(t.options('open',dispatch='unequal',reentry=True)).run()
        self.assertEqual((r['mode'],r['outcome']),(4,'IO/new'))
    def test_source_map_and_actual_definitions(self):
        source=pathlib.Path(__file__).parents[2]/'core'/'StarIODevice.cpp'
        lines=source.read_text().splitlines()
        m=t.source_map(); self.assertEqual(len(m),22)
        for line,entry in m.items():
            self.assertIn('IODevice::',lines[int(line)-1])
            self.assertTrue(entry['cases'])
        self.assertEqual(t.validate_source_map(m),22)
        bad=copy.deepcopy(m);bad['7']['cases']=['invented']
        with self.assertRaises(ValueError):t.validate_source_map(bad)
        with self.assertRaises(ValueError):t.validate_source_map({**m,'999':{}})
    def test_full_synthetic_roundtrip_and_known_corruptions(self):
        rows=t.expected(); data=t.canonical(rows)
        self.assertEqual(t.check(data),len(rows))
        changes=[lambda r:r.pop(),lambda r:r[0].update(mode=True),
                 lambda r:r[0].update(output='51'),lambda r:r[0].update(case='unknown'),
                 lambda r:r[0].update(extra=0)]
        for mutation in changes:
            bad=copy.deepcopy(rows);mutation(bad)
            with self.assertRaises(ValueError):t.check(t.canonical(bad))
        target=next(i for i,r in enumerate(rows) if r['options']['action']=='readfullabs' and r['options']['faultOp']=='read' and r['options']['faultIndex']==2 and r['options']['phase']=='after')
        for key,value in [('ptr',0),('phase','return'),('kind','temp'),('n',False)]:
            bad=copy.deepcopy(rows);bad[target]['events'][-1][key]=value
            with self.assertRaises(ValueError):t.check(t.canonical(bad))
        with self.assertRaises(ValueError):t.check(b'{"case":"a","case":"b"}\n')
        with self.assertRaises(ValueError):t.check(b'{"x":NaN}\n')

if __name__=='__main__':unittest.main()
