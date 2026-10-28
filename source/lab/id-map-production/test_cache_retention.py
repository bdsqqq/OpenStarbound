import copy,gzip,importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('cache_audit',Path(__file__).with_name('cache_retention.py'));v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class CacheRetentionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.repo=Path(self.temp.name).resolve()
  for name in v.SELECTED:
   p=self.repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'x'*v.THRESHOLD)
  self.small=self.repo/v.DEPS/'keep.d';self.small.write_bytes(b'current cache complement')
  self.canonical='build/id-map-rust-r1/target/aarch64-apple-darwin/release/libstar_engine_ffi.a';p=self.repo/self.canonical;p.write_bytes(b'current canonical archive')
  self.c=dict(version=1,roots=[v.SESSION,v.DEPS],minBytes=v.THRESHOLD,archiveRun=v.RUN,inventory=v.inventory(self.repo),protected={self.canonical:v.row(p)})
 def archive(self):
  entries=[]
  for name in v.SELECTED:
   r=self.c['inventory'][name];p=self.repo/name;blob=self.repo/'build/migration-evidence-archive/blobs'/r['sha256'][:2]/(r['sha256']+'.gz');blob.parent.mkdir(parents=True,exist_ok=True)
   if not blob.exists():blob.write_bytes(gzip.compress(p.read_bytes()))
   entries.append(dict(path=name,**r));p.unlink()
  return dict(status='ARCHIVED_VERIFIED_PRUNED',roots=self.c['roots'],min_bytes=v.THRESHOLD,entries=entries)
 def test_live_selection(self):self.assertEqual(v.verify(self.repo,self.c)['selected'],3)
 def test_archive_conservation(self):self.assertEqual(v.verify(self.repo,self.c,self.archive())['status'],'ARCHIVED_CACHE_BYTES_NO_LIVE_ORIGIN_RENEWAL')
 def test_extra_large_file_rejected(self):
  c=copy.deepcopy(self.c);c['inventory'][v.DEPS+'/extra.a']=dict(self.c['inventory'][v.SELECTED[0]])
  with self.assertRaisesRegex(ValueError,'exact three-file'):v.verify(self.repo,c)
 def test_external_hardlink_selected_rejected(self):
  c=copy.deepcopy(self.c);c['inventory'][v.SELECTED[0]]['fingerprint'][6]=2
  with self.assertRaisesRegex(ValueError,'external hardlink'):v.verify(self.repo,c)
 def test_live_complement_change_rejected(self):
  self.small.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'unchanged live cache complement'):v.verify(self.repo,self.c)
 def test_canonical_provider_change_rejected(self):
  (self.repo/self.canonical).write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'protected current provider'):v.verify(self.repo,self.c)
 def test_missing_archive_member_rejected(self):
  m=self.archive();m['entries'].pop()
  with self.assertRaisesRegex(ValueError,'exact manifest selection'):v.verify(self.repo,self.c,m)
 def test_corrupt_reconstructed_bytes_rejected(self):
  m=self.archive();r=m['entries'][0];p=self.repo/'build/migration-evidence-archive/blobs'/r['sha256'][:2]/(r['sha256']+'.gz');p.write_bytes(gzip.compress(b'wrong'))
  with self.assertRaisesRegex(ValueError,'exact reconstructed'):v.verify(self.repo,self.c,m)
 def test_oversized_reconstruction_rejected(self):
  m=self.archive();r=m['entries'][0];p=self.repo/'build/migration-evidence-archive/blobs'/r['sha256'][:2]/(r['sha256']+'.gz');p.write_bytes(gzip.compress(b'z'*(r['size']+1)))
  with self.assertRaisesRegex(ValueError,'bounded reconstruction'):v.verify(self.repo,self.c,m)
 def test_protected_path_escape_rejected(self):
  c=copy.deepcopy(self.c);c['protected']['/unrelated/user-storage']=c['protected'].pop(self.canonical)
  with self.assertRaisesRegex(ValueError,'protection scope'):v.verify(self.repo,c)
if __name__=='__main__':unittest.main()
