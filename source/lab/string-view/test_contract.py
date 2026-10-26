import unittest
import contract as c
class Contract(unittest.TestCase):
 def test_literals(self):
  self.assertEqual(c.fields('é,,x,',','),['c3a9','0','2','','3','0','78','4','1','','6','0'])
  self.assertEqual(len('é,,x,'),5)
  self.assertEqual('é,,x,'.find('x'),3)
  self.assertEqual(c.low('AÉ'),'aÉ')
  self.assertNotIn('\v',c.SPACE);self.assertNotIn('\f',c.SPACE);self.assertIn('\ufeff',c.SPACE)
 def test_replay(self):
  self.assertEqual(c.corpus(),c.corpus());c.check(c.canon(c.corpus()[1]))
 def test_controls(self):
  for mode in ('trailing','codepoint','emptyfind'):
   cases,rows=c.corpus();changed=0
   for case,row in zip(cases,rows):
    v=row['value'];a=bytes.fromhex(case[2]);p=bytes.fromhex(case[3])
    if mode=='trailing' and case[1] in ('split','any') and len(v)>=3 and v[-1]=='0':del v[-3:];changed+=1
    if mode=='codepoint' and case[1] in ('split','any') and b'\xc3\xa9' in a:
     for i in range(1,len(v),3):
      n=int(v[i]);v[i]=str(len(a[:n].decode('utf-8',errors='replace')))
     changed+=1
    if mode=='emptyfind' and case[1]=='search' and not p and int(case[4])>0:v[0]=case[4];changed+=1
   self.assertGreater(changed,0)
   with self.assertRaises(ValueError):c.check(c.canon(rows))
 def test_endpoint_expansion_and_overload_mapping(self):
  cases,rows=c.corpus()
  self.assertTrue(any(x[1]=='substr-default' for x in cases))
  self.assertTrue(any(x[1]=='char' and int(x[4])>len(bytes.fromhex(x[2]).decode()) for x in cases))
  mapped=c.source_map();self.assertEqual(len(mapped),58)
  char_find=next(r for r in mapped if 'find(Char ' in r['definition'])
  self.assertTrue(all(i.startswith('char-') for i in char_find['evidence_ids']))
 def test_mapping(self):self.assertEqual(len(c.source_map()),58)
if __name__=='__main__':unittest.main()
