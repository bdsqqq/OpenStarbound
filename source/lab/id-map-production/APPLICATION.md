# idmap production integration — finite gate

`STAR_USE_RUST_ID_MAP` is default OFF. ON uses the existing aggregate's qualified
policy through typed inline native frames. Original OFF definitions, declarations
and three fields remain intact; the promoted helper differs only in namespace.

Certificate `build/id-map-production-r2/certificate.json`:
`8ea50a71097008157b811c7c97156315e4279dd5dd55451833bf6d50a909c488`.
Report: `37686413c162ac5561ceeafbe6269a8da78387246ffd8020f3ffb5d8b0fa3484`.
Replay: `python3 -B source/lab/id-map-production/verify.py --report-sha <report>`.

- 42 acquired commands: six OFF/ON images compiled, linked and run twice;
  baseline/edge streams (44+12 cases, 12+6 properties) and five typed key/NRVO/
  fullness/const traces match. OFF links without any Rust archive/providers.
- ON uses the same actual canonical Rust archive; full trace fixture observes
  all ten production Rust roots and live canonical run/count/runtime providers.
- six deleted-copy negative compilations preserve lazy constraints; StatSet and
  StatusController typecheck in both configurations.
- actual source-derived 29-option CMake selector blocks and real Rust.cmake
  configure graph pass default-OFF/ON checks, including selected RUSTC propagation.
  Cargo was not run, and this is not a whole platform/game build.
- six Python role/default/gate falsifiers pass. Read-only independent review found
  no actionable defects. WeightedPool/TTL/LRU source-byte retention passes AFTER
  production mutation with externally pinned pre-mutation epochs.

No ABI/Rust source, storage, game generation or source/model/golden/flag fitting
changed. Earlier IdMap strict current-source replays now describe historical
source epochs; do not rebind their receipts or claim them fresh. Exact originals
and acquired verifiers were retained before mutation.

**Not application adoption or module completion.** Next: establish the real
status-modifier behavior scene and account for every existing generation before
fresh game admission. Keep one runnable game pair; respect fixed 4/16GiB caps.
Module-completion cleanup and all actual-game/auxiliary qualification remain open.
