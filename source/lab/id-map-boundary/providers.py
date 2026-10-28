"""Physical and live provider declarations; not surviving machine-code attestation."""
import sys
from pathlib import Path
LAB=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(LAB),str(LAB/'path-embed-replay')]
import archive_identity,native_symbols
EXPORTS=(b'_sb_idmap_run',b'_sb_idmap_count',b'_rust_eh_personality')
def need(b,s):
    if not b:raise ValueError(s)
def physical(archive):
    owners={symbol:[]for symbol in EXPORTS}
    for member in archive_identity.members(Path(archive).read_bytes()):
        if member['body'][:4]!=b'\xcf\xfa\xed\xfe':continue
        definitions=archive_identity.external_definitions(member['body'])
        for symbol in EXPORTS:
            if symbol in definitions:owners[symbol].append(dict(symbol=symbol,name=member['name'],offset=member['offset'],sha256=member['sha256']))
    for symbol,rows in owners.items():need(len(rows)==1,'one physical aggregate provider '+repr(symbol))
    return [owners[symbol][0]for symbol in EXPORTS]
def live(symbols,owners,archive,require_count):
    need(not any(s.name.startswith(b'_sb_idmap_mock_')or s.object_path.endswith(b'/mock.o')for s in symbols),'no live C++ mock controller')
    result=[]
    for owner in owners:
        if owner['symbol']==b'_sb_idmap_count'and not require_count:continue
        symbol=native_symbols.unique_symbol(symbols,owner['symbol']);need(symbol.size>0 and symbol.object_path==str(archive).encode()+b'('+owner['name']+b')','exact live canonical owner '+repr(owner['symbol']));result.append(symbol.manifest())
    return result
