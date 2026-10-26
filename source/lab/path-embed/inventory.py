"""Exact-source bounded lexical inventory, not a general C++ parser."""
import hashlib,json,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def extract(s):
    # Anchored definitions exclude declarations/calls/comment lines and suffixed names.
    return [{'name':m.group(1),'line':s.count('\n',0,m.start())+1} for m in re.finditer(r'^String (embedAndCompressData|embedEscapeText)\([^;\n]*\) \{',s,re.M)]
def generate():
    cpp=(ROOT/'source/core/StarPathEmbed.cpp').read_text()
    return {'definitions':extract(cpp),'enum_values':dict(zip(('None','Gzip','Zlib','Zstd'),range(4))), 'sources':{n:sha(ROOT/'source/core'/n) for n in ('StarPathEmbed.cpp','StarPathEmbed.hpp')}}
def check():
    q=generate()
    if q!=json.loads((HERE/'inventory.json').read_text()):raise ValueError('inventory/source drift')
    if [x['name'] for x in q['definitions']]!=['embedAndCompressData','embedEscapeText']:raise ValueError('definitions')
    for n,h in q['sources'].items():
        if sha(HERE/'original'/n)!=h:raise ValueError('frozen original drift')
    fixture='String embedEscapeText(String const& data);\n// String embedEscapeText(String const& data) {\nString embedEscapeTextExtra(String const& data) {\nString embedEscapeText(String const& data) {\n'
    if extract(fixture)!=[{'name':'embedEscapeText','line':4}]:raise ValueError('lexical controls')
    return q
if __name__=='__main__':
    if '--check' in sys.argv:check();print('inventory PASS')
    else:(HERE/'inventory.json').write_text(json.dumps(generate(),indent=2)+'\n')
