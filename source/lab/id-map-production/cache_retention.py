#!/usr/bin/env python3
"""Exact inactive-cache conservation around the existing archive/prune tool.

Not a semantic replay or tool/SDK/product source resolver. Inode/ctime assertions
on archived originals become historical; current complement remains live-bound.
"""
import argparse,gzip,hashlib,json,os,stat
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
THRESHOLD=3*1024**2
SESSION='build/id-map-rust-r1/target/aarch64-apple-darwin/debug/incremental/star_engine_ffi-39bvlel73630p/s-hnmx9d5wm1-0gv3wu9-dqegfmlr9lde362ncax1ufol1'
DEPS='build/id-map-rust-r1/target/aarch64-apple-darwin/release/deps'
SELECTED=[SESSION+'/query-cache.bin',SESSION+'/dep-graph.bin',DEPS+'/libstar_engine_ffi-1cf53265b459a09a.a']
RUN='20261028-id-map-inactive-cache-r1'
def need(b,s):
 if not b:raise ValueError(s)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
def row(p):
 s=p.lstat();need(stat.S_ISREG(s.st_mode),'regular input only');before=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_nlink];h=sha(p);t=p.lstat();need(before==[t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns,t.st_mode,t.st_nlink],'input changed while hashing');return dict(sha256=h,size=s.st_size,fingerprint=before,allocated=s.st_blocks*512)
def inventory(repo):
 result={}
 for rel in [SESSION,DEPS]:
  root=repo/rel;need(root.resolve()==root and root.is_dir(),'physical cache root')
  for parent,dirs,files in os.walk(root,followlinks=False):
   need(not any((Path(parent)/d).is_symlink()for d in dirs),'no cache directory aliases')
   for name in files:
    p=Path(parent)/name;result[str(p.relative_to(repo))]=row(p)
 return result
def validate_selection(rows):
 selected=sorted(p for p,r in rows.items()if r['size']>=THRESHOLD)
 need(selected==sorted(SELECTED),'exact three-file selection')
 need(all(rows[p]['fingerprint'][6]==1 for p in selected),'selected external hardlink exclusion')
 return selected
def verify(repo,closure,manifest=None):
 need(closure['version']==1 and closure['roots']==[SESSION,DEPS]and closure['minBytes']==THRESHOLD and closure['archiveRun']==RUN,'fixed cache scope')
 selected=validate_selection(closure['inventory']);now=inventory(repo)
 need(set(now)==set(closure['inventory'])-(set(selected)if manifest else set()),'live complement membership')
 for p,r in now.items():need(r==closure['inventory'][p],'unchanged live cache complement '+p)
 protected_inodes=set()
 for p,r in closure['protected'].items():
  path=Path(p)
  need(not path.is_absolute() and '..' not in path.parts and
       (p.startswith('build/behavior/weighted-pool-combined-r1/') or
        p=='build/id-map-rust-r1/target/aarch64-apple-darwin/release/libstar_engine_ffi.a'),
       'fixed current game/provider protection scope')
  current=row(repo/p);need(current==r,'protected current provider/game bytes '+p);protected_inodes.add(tuple(current['fingerprint'][:2]))
 need(all(tuple(closure['inventory'][p]['fingerprint'][:2])not in protected_inodes for p in selected),'selected protected inode overlap')
 if manifest:
  need(manifest['status']=='ARCHIVED_VERIFIED_PRUNED'and manifest['roots']==closure['roots']and manifest['min_bytes']==THRESHOLD,'exact verified archive state/scope')
  entries=manifest['entries'];need(len(entries)==3 and sorted(e['path']for e in entries)==sorted(selected),'exact manifest selection')
  for e in entries:
   expected=closure['inventory'][e['path']];need(e['sha256']==expected['sha256']and e['size']==expected['size']and e['fingerprint']==expected['fingerprint'],'original source pin')
   h=hashlib.sha256();size=0;blob=repo/'build/migration-evidence-archive/blobs'/e['sha256'][:2]/(e['sha256']+'.gz')
   with gzip.open(blob,'rb')as f:
    while b:=f.read(min(1024**2,e['size']-size+1)):
     size+=len(b);need(size<=e['size'],'bounded reconstruction size');h.update(b)
   need((h.hexdigest(),size)==(e['sha256'],e['size']),'exact reconstructed cache bytes')
 return dict(status='ARCHIVED_CACHE_BYTES_NO_LIVE_ORIGIN_RENEWAL'if manifest else'LIVE_CACHE_PREFLIGHT',selected=3,complement=len(now)-(0 if manifest else 3),protected=len(closure['protected']),archivedLogicalBytes=sum(closure['inventory'][p]['size']for p in selected),limits=['archived original inode/ctime/live-path replay unavailable','byte conservation only; no kernel/game/provider qualification renewal'])
def main():
 p=argparse.ArgumentParser();p.add_argument('--closure',required=True);p.add_argument('--closure-sha',required=True);p.add_argument('--manifest');p.add_argument('--manifest-sha');a=p.parse_args();need(sha(a.closure)==a.closure_sha,'external closure pin');c=json.loads(Path(a.closure).read_bytes());m=None
 if a.manifest:need(a.manifest_sha and sha(a.manifest)==a.manifest_sha,'external archive manifest pin');m=json.loads(Path(a.manifest).read_bytes())
 print(json.dumps(verify(ROOT,c,m),indent=2,sort_keys=True))
if __name__=='__main__':main()
