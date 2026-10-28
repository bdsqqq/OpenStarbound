#!/usr/bin/env python3
"""Read-only acceptance of existing game TCP/save/BTree scopes; isolated negatives only."""
import copy
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'source/lab/behavior'))
import buffer_proof as proof
OWN = ROOT/'build/weighted-pool-buffer-gates-r1'
OWN.mkdir()
def sha(path):
    path = Path(path)
    assert path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1
    return hashlib.sha256(path.read_bytes()).hexdigest()
bindings = {str(ROOT/'source/lab/behavior/buffer_proof.py'): sha(ROOT/'source/lab/behavior/buffer_proof.py'), str(ROOT/'source/client/StarClientApplication.cpp'): sha(ROOT/'source/client/StarClientApplication.cpp')}
for role,expected in [('reference','57305ea18f2f11edff14826d8732bd5559115231673a19ebec0088302f44a09f'),('candidate','8ea903429572485ddc3afb253c19d08f52a7bc3209e217342234d77ada97790b')]:
 game=ROOT/'build/behavior/weighted-pool-combined-r1'/role/'bin/starbound'
 assert sha(game)==expected
 bindings[str(game)]=expected
bindings[str(Path(__file__).resolve())]=sha(Path(__file__).resolve())
rows = []
normalized = []
for role in ('reference', 'reference-repeat', 'candidate'):
    base = ROOT/'build/behavior/weighted-pool-old23-r1/buffer-room'/role
    configpath = base/'sbinit.config'; config = json.loads(configpath.read_text())
    bindings[str(configpath)] = sha(configpath)
    for stage in ('lit-room', 'occluder-added', 'occluder-restored'):
        receiptpath = base/'frames'/(stage+'.json')
        receipt = json.loads(receiptpath.read_text())['metadata']
        observed = proof.validate(receipt)
        proof.bind(receipt, config)
        proof.visible(Image.open(receiptpath.with_suffix('.png')), receipt)
        normalized.append(observed)
        bindings[str(receiptpath)] = sha(receiptpath)
        bindings[str(receiptpath.with_suffix('.png'))] = sha(receiptpath.with_suffix('.png'))
        p = receipt['bufferProof']
        for section in ('save', 'database'):
            path = Path(p[section]['filename']); bindings[str(path)] = sha(path)
        rows.append(dict(role=role,stage=stage,transport=p['network']['transport'],wireHex=p['network']['actualWireHex'],stages=p['network']['stages'],typedTexts=p['network']['receivedTexts'],saveBytes=len(bytes.fromhex(p['save']['wireHex'])),databaseBytes=len(bytes.fromhex(p['database']['pagesHex'])),memoryAndFileReopened=True))
assert len(rows) == 9 and all(value == normalized[0] for value in normalized)
# Wrong wire and coherently changed save expectations must hit literal contracts.
controls = []
for name, section, fields in [('wrong-wire','network',('actualWireHex',)), ('coherent-wrong-save','save',('wireHex','expectedWireHex'))]:
    mutated = copy.deepcopy(receipt)
    for field in fields:
        value = mutated['bufferProof'][section][field]
        mutated['bufferProof'][section][field] = ('00' if value[:2] != '00' else '01') + value[2:]
    try: proof.validate(mutated)
    except ValueError as error: controls.append(dict(name=name,rejected=True,diagnostic=str(error)))
    else: raise AssertionError(name+' escaped')
# Actual on-disk corruption is exercised in a separate owned fixture, never storage.
fixture = OWN/'file-control'; fixture.mkdir()
mutated = copy.deepcopy(receipt)
for section in ('save','database'):
    source = Path(receipt['bufferProof'][section]['filename'])
    target = fixture/source.name; target.write_bytes(source.read_bytes())
    mutated['bufferProof'][section]['filename'] = str(target)
config = {'storageDirectory':str(fixture.resolve())}
proof.bind(mutated, config)
save = Path(mutated['bufferProof']['save']['filename']); raw = save.read_bytes()
save.write_bytes(bytes([raw[0]^1])+raw[1:])
try: proof.bind(mutated, config)
except ValueError as error: controls.append(dict(name='actual-owned-save-byte',rejected=True,diagnostic=str(error)))
else: raise AssertionError('actual corrupted save escaped')
result = dict(status='FINITE_ACTUAL_GAME_TCP_SBVJ_BTREE_PNG_PASS',productionRevision='2aa0c6e0',rows=rows,bindings=bindings,controls=controls,sourceTrace='StarClientApplication.cpp:2910-3286; actual numeric listener/raw fragmentation and typed decoder, native memory/file BTree commit-close-reopen and VersionedJson decode before Assets/Font',limits=['finite literal fixture only, not general player/world/ship interoperability','universeHandshake=false; actual TCP typed framing is not Universe handshake','existing actual game captures; no new game or native process launched','producer/source/process binding composed separately with current24 matrix aggregate'])
out = OWN/'report.json'
with out.open('x') as stream: json.dump(result,stream,indent=2,sort_keys=True)
print(result['status'],sha(out))
