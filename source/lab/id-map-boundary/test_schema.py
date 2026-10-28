"""Catch duplicated C/Rust discriminator drift without invoking a compiler."""
import re
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
HEADER=ROOT/'source/core/StarRustIdMap.h'
RUST=ROOT/'source/rust/ffi/src/id_map.rs'

def check(header,rust):
    header=re.sub(r'/\*.*?\*/','',header,flags=re.S)
    c={k:int(v)for k,v in re.findall(r'SB_IDMAP_(\w+)\s*=\s*(\d+)',header)}
    r={k:int(v)for k,v in re.findall(r'const (\w+): (?:u32|usize) = (\d+);',rust)}
    aliases={'ABI_VERSION':'VERSION','MODE_COUNT':'MODES','STAGE_COUNT':'STAGES','OP_COUNT':'WRITE_CURSOR'}
    if len(c)!=44 or len(r)!=43:raise ValueError('exact C/Rust schema membership')
    for name,value in c.items():
        if r.get(aliases.get(name,name))!=value:raise ValueError('C/Rust discriminator mismatch '+name)

class SchemaTests(unittest.TestCase):
    def test_current_schema(self):check(HEADER.read_text(),RUST.read_text())
    def test_changed_rust_root_detected(self):
        with self.assertRaises(ValueError):check(HEADER.read_text(),RUST.read_text().replace('const NEXT: u32 = 2;','const NEXT: u32 = 99;'))
    def test_missing_c_leaf_detected(self):
        with self.assertRaises(ValueError):check(HEADER.read_text().replace('SB_IDMAP_READ_MIN=16,',''),RUST.read_text())
    def test_wrong_stage_count_detected(self):
        with self.assertRaises(ValueError):check(HEADER.read_text().replace('SB_IDMAP_STAGE_COUNT=2','SB_IDMAP_STAGE_COUNT=4'),RUST.read_text())

if __name__=='__main__':unittest.main()
