# emitted-code witness — not game origin

`game_origin.py::attest(game_bytes, archive_bytes)` answers a narrower question
than build provenance. it requires unique physical canonical providers and exact
linked function identities for `sb_idmap_run`, `sb_idmap_count` and rust eh, plus
an encoded native `Star::RustIdMapDetail::Frame::run()` → `sb_idmap_run` branch.

current generic macho/archive parsers stay unchanged; weighted-pool owner/tool
selection is not reused. relocation types2/3/4/8 remain zero-addend only. type9
now uses ONLY the unchanged, independently sourced apple ld64-951.9 local-tlvp
rule: complete defined descriptors in both artifacts and exact linked offset,
registers and encoding. no blanket mask or future game observation was used.
normalized page targets remain a data-provenance limitation.

this pre-build extension passes24 IdMap,19 generic and23 whole-origin tests.
a literal two-segment synthetic macho positive failed the preserved old policy
before extension, then passed; wrong offset/register/opcode/addend, missing/wrong/
short descriptors and invalid relocations still fail. authoritative source is
`apple-ld64-951.9-OutputFile.cpp:2185–2200`, sha256
`885ecee52272d46076af3402af032ee578590165c09355b3675ee76a497cbc2a`.
completion `build/id-map-tlvp-r1/completion.json` sha256
`3401800a2ac0633fc973b0d0a40826748b1775601454e590617f1941c9d7dbde`.
no actual new game, linker or compiler ran.

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
required `id_map_origin.py` validator and launch producer are now source-tested
(see `LAUNCH.md`), but no fresh actual29 epoch has bound their runtime contracts.
**the existing old pair still cannot launch as an IdMap game.**
