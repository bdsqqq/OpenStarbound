#!/usr/bin/env python3
"""Verify retained artifacts, not semantic equivalence or migration completion."""
import argparse,copy,gzip,hashlib,json,sys,tempfile
from pathlib import Path

def hash_stream(stream):
 h=hashlib.sha256();size=0
 while True:
  data=stream.read(1024*1024)
  if not data:return h.hexdigest(),size
  h.update(data);size+=len(data)
def file_hash(path):
 with path.open('rb') as stream:return hash_stream(stream)[0]
def check_receipt(row,root):
 if type(row['returncode']) is not int or row['returncode']!=0:raise ValueError('RECEIPT status')
 if type(row['stdout_bytes']) is not int or row['stdout_bytes']<0:raise ValueError('RECEIPT byte count')
 executable=Path(row['command'][0]).resolve()
 if file_hash(executable)!=row['executable_sha256']:raise ValueError('RECEIPT executable')
 artifact=Path(row['stdout_artifact'])
 if artifact.is_symlink() or not artifact.resolve().is_relative_to(root.resolve()):raise ValueError('RECEIPT scope')
 if file_hash(artifact)!=row['stdout_artifact_sha256']:raise ValueError('RECEIPT stored hash')
 opener=gzip.open if artifact.suffix=='.gz' else open
 with opener(artifact,'rb') as stream:actual,size=hash_stream(stream)
 if actual!=row['stdout_sha256'] or size!=row['stdout_bytes']:raise ValueError('RECEIPT decoded hash/size')
def self_test():
 # Isolated artifact corruption never touches a native observation or golden.
 with tempfile.TemporaryDirectory(prefix='zstd-receipt-',dir=Path(__file__).resolve().parents[3]/'build/zstd-lab') as tmp:
  root=Path(tmp);artifact=root/'stdout.gz';payload=b'receipt\0bytes'
  with gzip.open(artifact,'wb') as stream:stream.write(payload)
  row=dict(returncode=0,command=[sys.executable],executable_sha256=file_hash(Path(sys.executable)),stdout_artifact=str(artifact),stdout_artifact_sha256=file_hash(artifact),stdout_sha256=hashlib.sha256(payload).hexdigest(),stdout_bytes=len(payload))
  check_receipt(row,root);controls=[]
  for key,value in [('stdout_sha256','0'*64),('stdout_artifact_sha256','0'*64),('stdout_bytes',True),('returncode',False),('executable_sha256','0'*64)]:
   bad=copy.deepcopy(row);bad[key]=value
   try:check_receipt(bad,root)
   except ValueError:controls.append(key)
   else:raise RuntimeError('known corruption escaped '+key)
  bad=copy.deepcopy(row);bad['stdout_artifact']=str(root.parent/'outside.gz')
  try:check_receipt(bad,root)
  except ValueError:controls.append('scope')
  else:raise RuntimeError('outside artifact escaped')
 return controls

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
 if args.self_test:print(json.dumps({'self_test':'PASS','controls':self_test()}))
 if args.report:
  path=args.report.resolve();report=json.loads(path.read_text())
  if report['status'] not in ('PASS_NATIVE_VALUES_AND_TRACE','PASS_ACTUAL_RUST_VALUES_AND_NATIVE_TRACE'):raise ValueError('not a complete native trace report')
  for field in ['bindings','generated_sources']:
   for filename,expected in report[field].items():
    if file_hash(Path(filename))!=expected:raise ValueError('BINDING '+filename)
  for row in report['runtime_receipts']:check_receipt(row,path.parent)
  print(json.dumps({'artifact_integrity':'PASS','bindings':len(report['bindings']),'generated_sources':len(report['generated_sources']),'execution_receipts':len(report['runtime_receipts']),'report_sha256':file_hash(path)}))
 if not args.report and not args.self_test:parser.error('choose --report or --self-test')
if __name__=='__main__':main()
