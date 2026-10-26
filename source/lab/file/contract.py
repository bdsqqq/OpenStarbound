"""Independent byte fixtures and source-derived observations, frozen before execution."""
LENGTHS=(0,1,1023,1024,1025,2049)
def fixtures():
 d={f'n{n}':bytes((i%251 for i in range(n))) for n in LENGTHS}
 d.update({'same':b'source','initial':b'I','backup.b1':b'A','backup.b3':b'old3','self-backup':b'S','self-backup.1':b'T','probe':b'abc','closed-resize':b'keep','trunc-clone':b'old'})
 return d
def final_files():
 d=fixtures()
 for n in LENGTHS:d[f'n{n}.copy']=d[f'n{n}'];d[f'n{n}']=b''
 d.update({'same':b'','raw':b'A\0B','bytes':b'C\0D','text':b'E\0F','rename-bytes':b'G\0H','rename-string':b'UTF8\xc3\xa9','backup.b1':b'I','backup.b2':b'A','self-backup.1':b'S','self-backup.2':b'T','trunc-clone':b''})
 return d
def expected():
 rows=[]
 def add(k,v):rows.append(f'{k}\t{v}\n')
 for k,v in [('default-mode',0),('default-name',1),('default-device',1),('closed-size',-1),('closed-pread',1),('closed-pwrite',1),('closed-output',1)]:add(k,v)
 for k in ['closed-pos','closed-seek','closed-eof','closed-read','closed-write','closed-sync','empty-open','empty-remove','missing-remove','missing-recursive','closed-clone','mkdir']:add(k,1)
 for n in LENGTHS:
  for k,v in [('read-size',n),('string-size',n),('file-size',n),('copy-size',n),('open-pos',0),('initial-eof',int(n==0)),('end-pos',n),('end-eof',1),('zero-read',0),('zero-write',0)]:add(k,v)
  if n:
   for k in ['pread-count','pread-pos','pwrite-count','pwrite-pos']:add(k,1)
  for k,v in [('clone-pos',int(n!=0)),('clone-size',n),('resize-size',0),('close-mode',0)]:add(k,v)
 for k,v in [('same-copy',0),('virtual-close-open',1),('set-open',1),('named-device',1),('virtual-pos-clone',1),('probe-clone-pos',1),('open-token',1),('remove-token',1),('failed-close-mode',3),('closed-resize',1),('resize-open-dispatch',1),('resize-mode',0),('resize-handle-pos',0),('truncate-clone-size',0),('truncate-clone-pos',2),('truncate-source-poscalls',1)]:add(k,v)
 return ''.join(rows).encode()
def check(data):
 if data!=expected():raise ValueError('independent ordered observations differ')
