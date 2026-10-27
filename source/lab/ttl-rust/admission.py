#!/usr/bin/env python3
"""Read-only admission audit. Static consistency is NOT acquisition admission.
Missing pre-execution pins cannot be repaired by hashing tools after execution.
"""
import copy,re
from common import *
import canonical
TOOL_KEYS=('CMAKE_C_COMPILER','CMAKE_CXX_COMPILER','CMAKE_AR','CMAKE_RANLIB','CMAKE_LINKER','CMAKE_C_COMPILER_AR','CMAKE_CXX_COMPILER_AR','CMAKE_C_COMPILER_RANLIB','CMAKE_CXX_COMPILER_RANLIB','CMAKE_C_COMPILER_LAUNCHER','CMAKE_CXX_COMPILER_LAUNCHER','STAR_CARGO_EXECUTABLE','STAR_RUSTC_EXECUTABLE')

def selected_tools():
 cache=(canonical.CM/'CMakeCache.txt').read_text();values=dict(re.findall(r'^([^/#\n][^:\n]*):[^=\n]*=(.*)$',cache,re.M))
 selected={'CMAKE_EXECUTABLE':canonical.CMAKE,'CMAKE_MAKE_PROGRAM':values['CMAKE_MAKE_PROGRAM'],'APPLE_TOOLCHAIN_SELECTOR':'/usr/bin/xcrun'}
 for key in TOOL_KEYS:
  value=values.get(key)
  if value and not value.endswith('-NOTFOUND'):selected[key]=value
 return selected

def evaluate(pins,tools,digest=sha):
 missing=[];changed=[];unresolved=[]
 for key,path in tools.items():
  # A launcher list needs an explicit executable/argument resolution receipt.
  if ';' in path or not Path(path).is_absolute():unresolved.append({'key':key,'selected':path});continue
  before=pins.get(path)
  if before is None:missing.append({'key':key,'selected':path});continue
  if type(before)is not str or before!=digest(path):changed.append({'key':key,'selected':path})
 return {'missing_before_execution':missing,'changed_tools':changed,'unresolved_wrappers':unresolved,'admitted':not (missing or changed or unresolved)}

def inspect():
 canonical.verify()
 pins=load(OUT/'sealed-configure-source-before.typed');tools=selected_tools();result=evaluate(pins,tools)
 return {'status':'ADMITTED' if result['admitted'] else 'BLOCKED_PREEXECUTION_TOOL_ADMISSION','stage':'sealed-cmake','canonical_record_sha256':sha(OUT/'sealed-canonical.typed'),'preconfigure_manifest_sha256':sha(OUT/'sealed-configure-source-before.typed'),'selected_tools':tools,**result,'limits':'read-only static audit; configured tools are not all claimed executed. Compiler/linker/archiver process tracing and complete transitive executable/runtime attestation are not established. No fourth configure/build authorized. No TTL boundary acquisition has run.'}

def require_complete():
 record=inspect();need(record['admitted'],'canonical admission BLOCKED: missing pre-execution selected-tool pins; no retrospective repair')
 return record

def controls():
 # Isolated synthetic manifests only. Never upgrade the actual stage's admission.
 tools={'cc':'/fixture/cc','ar':'/fixture/ar'};digest=lambda p:'a'*64
 positive={p:'a'*64 for p in tools.values()};need(evaluate(positive,tools,digest)['admitted'],'synthetic positive admission')
 missing=copy.deepcopy(positive);del missing['/fixture/ar'];need(not evaluate(missing,tools,digest)['admitted'],'missing archiver detected')
 wrong=copy.deepcopy(positive);wrong['/fixture/cc']='b'*64;need(not evaluate(wrong,tools,digest)['admitted'],'changed compiler detected')
 boolean=copy.deepcopy(positive);boolean['/fixture/cc']=True;need(not evaluate(boolean,tools,digest)['admitted'],'boolean digest detected')
 need(not evaluate(positive,{'cc':'/fixture/cc;--wrapper'},digest)['admitted'],'unresolved wrapper detected')
 return ['synthetic-positive','missing-archiver-rejected','changed-compiler-rejected','boolean-digest-rejected','unresolved-wrapper-rejected']

if __name__=='__main__':
 print(json.dumps({'audit':inspect(),'controls':controls()},sort_keys=True,indent=2))
