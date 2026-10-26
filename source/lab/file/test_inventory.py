"""Persistent isolated CLI fixtures; deliberately no automatic cleanup."""
import hashlib,json,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
import inventory


def snapshot(root):
 return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def main(out):
 out.mkdir(parents=True);results=[];expected=inventory.generate()
 assert [len(expected[n]) for n in inventory.COUNTS]==[34,30,30]
 assert expected==inventory.generate()
 assert any('List<pair<String, bool>>' in r['signature'] for r in expected['StarFile_unix.cpp'])
 for name in inventory.COUNTS:
  rows=expected[name]
  assert all(a['endLine']<b['line'] for a,b in zip(rows,rows[1:]))
 assert next(r for r in expected['StarFile.cpp'] if r['signature']=='File::File(String filename)')['endLine']==127
 masked=inventory.mask_cpp('/* File::fake() {} */\nR"tag(\nFile::rawFake() { }\n)tag";\n')
 assert 'File::' not in masked and len(masked.splitlines())==4
 assert len(inventory.definitions('void File::real() {\ncase 2: { File::resize(x,y); }\n}\n'))==1
 metadata=expected['_conditional']
 assert (metadata['physicalDefinitions'],metadata['logicalDefinitions'],metadata['selectedAlternatives'])==(68,34,34)
 current=(inventory.ROOT/'source/core/StarFile.cpp').read_text().splitlines(True)
 original=(inventory.HERE/'StarFile.original.cpp').read_text().splitlines(True)
 for mode,pair in enumerate(metadata['alternatives']):
  assert pair['mode']==mode
  for branch in ['selected','native']:
   row=pair[branch]
   assert inventory.digest(''.join(current[row['line']-1:row['endLine']]).encode())==row['sha256']
   assert row['signature']==expected['StarFile.cpp'][mode]['signature']
  row=expected['StarFile.cpp'][mode]
  assert inventory.digest(''.join(original[row['line']-1:row['endLine']]).encode())==row['sha256']==pair['native']['sha256']
 plain_modes=['positive','catalog-drift','source-drift','near-match','block-near-match','raw-near-match','missing-output']
 conditional_modes=['positive','catalog-drift','missing-output','wrong-branch','missing-alternative','changed-fallback','changed-header','changed-wrapper','mode-order','comment-drift','raw-drift','fake-selector','frozen-drift','prototype-drift']
 for family,modes in [('plain',plain_modes),('conditional',conditional_modes)]:
  for mode in modes:
   root=out/(family+'-'+mode);lab=root/'source/lab/file';core=root/'source/core';lab.mkdir(parents=True);core.mkdir(parents=True);(lab/'host').mkdir()
   for name in ['inventory.py','StarFile.original.cpp','host/wrappers.cpp']:(lab/name).write_bytes((inventory.HERE/name).read_bytes())
   for name in [*inventory.COUNTS,'StarFile.hpp']:(core/name).write_bytes((inventory.ROOT/'source/core'/name).read_bytes())
   if family=='plain':(core/'StarFile.cpp').write_bytes((lab/'StarFile.original.cpp').read_bytes())
   data=inventory.generate(root)
   if mode=='catalog-drift':data['StarFile.cpp'][0]['sha256']='0'*64
   p=lab/'source-map.json'
   if mode!='missing-output':p.write_text(json.dumps(data))
   cpp=core/'StarFile.cpp';text=cpp.read_text()
   if mode=='source-drift':text=text.replace('auto parent = dirName(fileName);','auto parent = dirName(fileName); // drift',1)
   if mode in ['near-match','comment-drift']:text+='\n// void File::nearMatch() {}\n'
   if mode=='block-near-match':text+='\n/*\nvoid File::nearMatch() {}\n*/\n'
   if mode in ['raw-near-match','raw-drift']:text+='\nchar const* fake = R"tag(\nvoid File::nearMatch() {}\n)tag";\n'
   if mode=='wrong-branch':text=text.replace('#ifdef STAR_USE_RUST_FILE','#ifndef STAR_USE_RUST_FILE',1)
   if mode=='missing-alternative':text=text.replace('void File::makeDirectoryRecursive','void Gone::makeDirectoryRecursive',1)
   if mode=='changed-fallback':text=text.replace('auto parent = dirName(fileName);','auto parent = dirName(fileName); // changed',1)
   if mode=='changed-header':(core/'StarFile.hpp').write_bytes((core/'StarFile.hpp').read_bytes()+b'\n')
   if mode=='changed-wrapper':text=text.replace('FileRust::invoke(0, 4','FileRust::invoke(0, 5',1)
   if mode=='mode-order':text=text.replace('FileRust::invoke(0, 4','FileRust::invoke(1, 4',1)
   if mode=='fake-selector':text=text.replace('#ifdef STAR_USE_RUST_FILE','// #ifdef STAR_USE_RUST_FILE',1)
   if mode=='frozen-drift':(lab/'StarFile.original.cpp').write_bytes((lab/'StarFile.original.cpp').read_bytes()+b'\n')
   if mode=='prototype-drift':(lab/'host/wrappers.cpp').write_bytes((lab/'host/wrappers.cpp').read_bytes()+b'\n')
   cpp.write_text(text)
   before=snapshot(root)
   r=subprocess.run([sys.executable,'-B',str(lab/'inventory.py'),'--check'],capture_output=True)
   assert before==snapshot(root), (family,mode,'check wrote files')
   passed=mode=='positive' or family=='plain' and mode in ['near-match','block-near-match','raw-near-match']
   assert (r.returncode==0)==passed,(family,mode,r.stderr.decode())
   (root/'stdout').write_bytes(r.stdout);(root/'stderr').write_bytes(r.stderr)
   results.append(dict(family=family,mode=mode,returncode=r.returncode,nonwriting=True))
   if passed or mode in ['catalog-drift','missing-output']:
    for attempt in range(2):
     subprocess.run([sys.executable,'-B',str(lab/'inventory.py'),'--write'],check=True)
     if attempt:assert p.read_bytes()==first
     first=p.read_bytes()
     subprocess.run([sys.executable,'-B',str(lab/'inventory.py'),'--check'],check=True)
   elif family=='conditional':
    before=snapshot(root)
    rejected=subprocess.run([sys.executable,'-B',str(lab/'inventory.py'),'--write'],capture_output=True)
    assert rejected.returncode!=0 and snapshot(root)==before, (mode,'write accepted invalid input')
 (out/'report.json').write_text(json.dumps(results,indent=2)+'\n')
 print(f'{len(results)} inventory CLI fixtures passed; coordinates, nested calls, deterministic write/check passed')
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
