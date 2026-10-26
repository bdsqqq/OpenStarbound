"""Strict dependency and Apple link object-table membership, independently parsed.

Object-table boundaries follow source/lab/native_artifacts.py. Ordered link
membership and per-job primary-source guards follow file/production/runner.py.
Only object paths are decoded: symbol-table bytes need not be UTF-8.
"""
import re,shlex
from pathlib import Path

def need(ok,msg):
 if not ok:raise ValueError(msg)

def dependencies(data,source,flags,cwd):
 need(type(data) is bytes,'dependency bytes')
 s=data.decode('utf8').replace('\\\n',' ')
 need(s.count(':')==1,'malformed dependency rule')
 target,body=s.split(':')
 need(shlex.split(target)==[source.stem+'.o'],'dependency target')
 words=shlex.split(body);need(bool(words),'empty dependencies')
 found=set();resolved={}
 sdk_args=[flags[i+1] for i,x in enumerate(flags) if x=='-isysroot' and i+1<len(flags)]
 need(len(sdk_args)==1,'one configured SDK')
 sdk=Path(sdk_args[0]).resolve(strict=True)
 sdk_found=set()
 for word in words:
  need(not any(x in word for x in ('\n','\r',':')),'malformed dependency token')
  p=Path(word);p=p if p.is_absolute() else cwd/p
  actual=p.resolve(strict=True);need(actual.is_file(),'dependency file')
  resolved[word]=str(actual);found.add(actual)
  for ancestor in [p,*p.parents]:
   if ancestor.name.endswith('.sdk'):
    sdk_found.add(ancestor.resolve(strict=True));break
 need(source.resolve(strict=True) in found,'dependency primary source')
 need(sdk_found=={sdk},'unique dependency SDK resolution')
 return found

def objects(data):
 lines=data.splitlines();need(lines.count(b'# Object files:')==1,'one object table')
 start=lines.index(b'# Object files:')+1;entries=[];indices=[];ended=False
 for line in lines[start:]:
  if line.startswith(b'#'):ended=True;break
  if not line.strip():continue
  m=re.fullmatch(rb'\[\s*([0-9]+)\]\s+(.+)',line)
  need(m is not None,'malformed object table')
  indices.append(int(m[1]));entries.append(m[2].decode('utf8'))
 need(ended and entries and len(indices)==len(set(indices)),'object table indices/end')
 return entries

def link(data,args,tables):
 entries=objects(data)
 need(entries[0]=='linker synthesized' and entries.count('linker synthesized')==1,'linker synthesized')
 expected=[a for a in args if a.endswith('.o')]
 actual=[a for a in entries if a.endswith('.o')]
 need(actual==expected,'actual ordered link objects')
 used=[]
 for entry in entries:
  if entry=='linker synthesized' or entry in actual:continue
  m=re.fullmatch(r'(.+\.a)\(([^()]+)\)',entry)
  need(m is not None,'unknown linked object origin')
  archive,member=m.groups();need(archive in tables and archive in args,'undeclared linked archive')
  need(member.encode() in tables[archive].splitlines(),'used archive member absent from ar table')
  used.append([archive,member])
 return {'objects':actual,'used_archive_members':used}
