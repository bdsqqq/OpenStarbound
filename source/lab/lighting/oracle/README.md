# frozen lighting oracle

captured before any adapter edits, from HEAD `f5c4da285ba4bbb8eaf21211b8ff9d27654fed55`.

original SHA256:

- `source/base/StarCellularLightArray.hpp`: `f5eea98486ab72adc3ecb37f5e123cff37b49f9c6e9716da8053d87cde6c3ca9`
- `source/base/StarCellularLightArray.cpp`: `a0f3bab0bebb3839be8e30da4f56f73088ee27f976a03a72b090a2b2ff5dd7e4`

the only changes to these copies are opening `namespace Star { namespace LightingOracle {` instead of `namespace Star {`, and closing it with `}}` instead of `}`. includes and algorithms are unchanged. parent `Star` types remain visible without importing or duplicating support code. the `.cpp` resolves its quoted header to the frozen copy in this directory, not the adapter.

`../verify_oracle.py` checks both original hashes against the recorded commit and byte-for-byte equality after applying exactly those two namespace substitutions. do not update this oracle to make a differential failure pass.
