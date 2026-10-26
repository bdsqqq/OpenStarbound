"""Persistent isolated CLI fixtures; deliberately no automatic cleanup."""
import hashlib,json,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
import inventory

def main(out):
 out.mkdir();results=[];expected=inventory.generate()
 assert [len(v) for v in expected.values()]==[34,30,30]
 assert any('List<pair<String, bool>>' in r['signature'] for r in expected['StarFile_unix.cpp'])
 assert expected==inventory.generate()
 # Token masking must keep coordinates and exclude comments/raw literals.
 masked=inventory.mask_cpp('/* File::fake() {} */\nR"tag(\nFile::rawFake() { }\n)tag";\n')
 assert 'File::' not in masked and len(masked.splitlines())==4
 for rows in expected.values():
  assert all(a['endLine']<b['line'] for a,b in zip(rows,rows[1:])), 'overlapping definition extents'
 assert next(r for r in expected['StarFile.cpp'] if r['signature']=='File::File(String filename)')['endLine']==127
 for mode in ['positive','catalog-drift','source-drift','near-match','block-near-match','raw-near-match','missing-output']:
  root=out/mode;lab=root/'source/lab/file';core=root/'source/core';lab.mkdir(parents=True);core.mkdir(parents=True)
  (lab/'inventory.py').write_bytes((inventory.HERE/'inventory.py').read_bytes())
  data=json.loads((inventory.HERE/'source-map.json').read_text())
  if mode=='catalog-drift':data['StarFile.cpp'][0]['sha256']='0'*64
  if mode!='missing-output':(lab/'source-map.json').write_text(json.dumps(data))
  for name in expected:
   text=(inventory.ROOT/'source/core'/name).read_text()
   if mode=='source-drift' and name=='StarFile.cpp':text=text.replace('auto parent = dirName(fileName);','auto parent = dirName(fileName); // drift',1)
   if mode=='near-match' and name=='StarFile.cpp':text+='\n// void File::nearMatch() {}\n'
   if mode=='block-near-match' and name=='StarFile.cpp':text+='\n/*\nvoid File::nearMatch() {}\n*/\n'
   if mode=='raw-near-match' and name=='StarFile.cpp':text+='\nchar const* fake = R"tag(\nvoid File::nearMatch() {}\n)tag";\n'
   (core/name).write_text(text)
  p=lab/'source-map.json';before=p.read_bytes() if p.exists() else None;r=subprocess.run([sys.executable,'-B',str(lab/'inventory.py'),'--check'],capture_output=True)
  (root/'stdout').write_bytes(r.stdout);(root/'stderr').write_bytes(r.stderr)
  assert (r.returncode==0)==(mode in ['positive','near-match','block-near-match','raw-near-match'])
  assert before==(p.read_bytes() if p.exists() else None)
  results.append(dict(mode=mode,returncode=r.returncode,nonwriting=True))
  if mode=='positive':
   subprocess.run([sys.executable,'-B',str(lab/'inventory.py'),'--write'],check=True)
   first=p.read_bytes();subprocess.run([sys.executable,'-B',str(lab/'inventory.py'),'--write'],check=True)
   assert p.read_bytes()==first
 (out/'report.json').write_text(json.dumps(results,indent=2)+'\n');print('7 inventory CLI fixtures passed; lexical extents and deterministic writes passed')
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
