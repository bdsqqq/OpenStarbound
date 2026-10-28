# emitted-code witness — not game origin

`game_origin.py::attest(game_bytes, archive_bytes)` answers a narrower question
than build provenance. it requires unique physical canonical providers and exact
linked function identities for `sb_idmap_run`, `sb_idmap_count` and rust eh, plus
an encoded native `Star::RustIdMapDetail::Frame::run()` → `sb_idmap_run` branch.

current generic macho/archive parsers stay unchanged; weighted-pool owner/tool
selection is not reused. this source gate accepts only the previously understood
relocation types2/3/4/8. tlvp and unknown types block, without fitting new opcode
masks. normalized page targets remain a data-provenance limitation.

20 synthetic tests pass. both externally pinned old game executables were also
rejected against the actual current canonical idmap archive: native has four
missing-function/owner blockers, old combined candidate three. both checks
found three unique canonical archive providers. **mere archive presence did not accept a game.**
no program ran, no new game was built, no artifact was retired. independent
read-only review found no actionable defect at the tested source hashes.

completion: `build/id-map-game-origin-r1/completion.json`, sha256
`0f5d1cc4ed6c2c284ba068098331bdbfc6451bedab9db2914f39a85043f3b14a`.

this is not source/header/compiler/sdk/build admission, dynamic execution,
complete data-target provenance or whole-game qualification. the frontend's
required `id_map_origin.py` validator and launch producer remain unavailable;
**capture stays disabled** until a fresh actual29 epoch binds those contracts.
