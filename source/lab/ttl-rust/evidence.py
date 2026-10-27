"""Pure Mach-O archive/link-map/provider reconstruction; no subprocesses."""
import re,shlex
from common import *
import canonical,expanded_invocation,archive_identity,object_inventory,link_trace,native_symbols
ARCHIVE=canonical.ARCHIVE
SDK=canonical.SDK
def archive_providers():
 members=archive_identity.members(ARCHIVE.read_bytes());result=[]
 for symbol in (b'_sb_ttl_run',b'_sb_ttl_count',b'_rust_eh_personality'):
  owners=[]
  for member in members:
   if member['body'][:4]==b'\xcf\xfa\xed\xfe' and symbol in archive_identity.external_definitions(member['body']):owners.append(member)
  need(len(owners)==1,'unique physical aggregate provider '+repr(symbol))
  m=owners[0];result.append({'symbol':symbol,'archive':str(ARCHIVE).encode(),'name':m['name'],'offset':m['offset'],'sha256':m['sha256']})
 need(result[0]['sha256']==result[1]['sha256'],'TTL exports owned by same canonical Rust member')
 return result

def origins(name,r,sdk_before,read_bytes=None):
 data=read_bytes or (lambda path:Path(path).read_bytes())
 def typed(path):return codec.loads(data(path).decode('ascii'))
 objects=[*r['objects'],str(OUT/(name+'.o'))]
 early_symbols=native_symbols.live_symbols(data(OUT/(name+'.map')))
 for owner in archive_providers():
  if owner['symbol'] not in (b'_sb_ttl_run',b'_sb_ttl_count'):continue
  s=native_symbols.unique_symbol(early_symbols,owner['symbol'])
  need(s.object_path==str(ARCHIVE).encode()+b'('+owner['name']+b')' and s.size>0,'physical canonical Rust provider barrier')
 commands=[shlex.split(x) for x in data(OUT/(name+'-expand.stderr')).decode().splitlines() if x.lstrip().startswith('"')]
 need(len(commands)==1,'single expanded linker')
 bound=typed(OUT/(name+'-expanded.typed'));expanded_invocation.verify(bound,commands[0]);inv=bound['inventory']
 same([x for x in inv['file_inputs'] if x.endswith('.o')],objects,'actual object list without mock controller')
 rust_archives=[x for x in inv['file_inputs'] if x.endswith('.a') and ('star_engine_ffi' in x or '/rust' in x)]
 same(rust_archives,[str(ARCHIVE)],'exactly one aggregate archive')
 blobs={x.encode():Path(x).read_bytes() for x in inv['file_inputs'] if x.endswith('.a')}
 tables={p:b''.join(m['name']+b'\n' for m in archive_identity.arm64_archive_members(blob)) for p,blob in blobs.items()}
 trace=link_trace.parse(data(OUT/(name+'-link.stdout')),[p.encode() for p in objects],tables)
 mapped=object_inventory.reconcile(data(OUT/(name+'.map')),[p.encode() for p in objects],tables,blobs)
 sdk=r['flags'][r['flags'].index('-isysroot')+1]
 paths=trace['sdk_paths']+mapped['unresolved_origins']+[x['source'] for x in trace['indirect_declarations']]
 consumed=sdk_witness.reconcile_consumed(sdk_before,[os.fsdecode(x) for x in paths],requested_root=sdk,expected_canonical_root=SDK)
 symbols=native_symbols.live_symbols(data(OUT/(name+'.map')));providers=[]
 physical=archive_providers()
 prelink={os.fsdecode(path):[{k:m[k] for k in ('name','offset','sha256')} for m in archive_identity.arm64_archive_members(blob)] for path,blob in blobs.items()}
 same({'archives':prelink,'rust_providers':physical},typed(OUT/(name+'-physical-prelink.typed')),'prelink physical archive providers')
 for symbol_name in [b'_main',b'_sb_ttl_run',b'_sb_ttl_count']:
  symbol=native_symbols.unique_symbol(symbols,symbol_name)
  if symbol_name in (b'_sb_ttl_run',b'_sb_ttl_count'):
   member=next(m for m in physical if m['symbol']==symbol_name)
   expected=str(ARCHIVE).encode()+b'('+member['name']+b')'
  else:expected=str(OUT/(name+'.o')).encode()
  need(symbol.object_path==expected and symbol.size>0,'fresh symbol provider '+repr(symbol_name));providers.append(symbol.manifest())
 runtime=[s for s in symbols if s.name==b'_rust_eh_personality']
 need(len(runtime)==1 and runtime[0].object_path.startswith(str(ARCHIVE).encode()+b'('),'single aggregate runtime provider')
 providers.append(runtime[0].manifest())
 for symbol_name,suffix in [(b'__ZN4Star4Time21monotonicMillisecondsEv',b'StarTime.cpp.o'),(b'__ZN4Star6Random7randIntExx',b'StarRandom.cpp.o'),(b'__ZN4Star12RandomSource7randIntExx',b'StarRandom.cpp.o')]:
  symbol=native_symbols.unique_symbol(symbols,symbol_name)
  need(symbol.object_path.endswith(suffix) and symbol.size>0,'actual native Time/Random provider')
  providers.append(symbol.manifest())
 need(not any(b'mock' in s.name.lower() for s in symbols),'no linked mock-controller symbol')
 dis=data(OUT/(name+'-disassemble.stdout'))
 need(any(b'_sb_ttl_run' in line and (b'\tbl\t'in line or b'\tb\t'in line) for line in dis.splitlines()),'surviving native to Rust call edge')
 return {'providers':providers,'physical_rust_providers':physical,'consumed_sdk':consumed,'trace':trace,'map':mapped,'physical_archive_tables':tables}
