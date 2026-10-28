# prebuild cleanup — not module completion

## old game pair, 2026-10-28 21:51 utc

exactly the two old WeightedPool `bin/starbound` files were separately archived,
reconstructed before pruning, and checked with the strict retired-product reader.
1,037 remaining game/provider files and all113 original reference objects stayed
unchanged. prior50 native-product blobs were independently reconstructed again.

- closure `build/id-map-game-retirement-r1/closure.json`:
  `6199bd682ddbd0cfeac67ce9c59c42293a112e5c2a828a5e275414777f5986bf`
- archive `20261028-id-map-prebuild-retire-weighted-bins-r1/manifest.json`:
  `0410f3f45507c7cd5b1ac7c4ab87b7ab44cddcf8b5ca0e99610f079d4dcaa1aa`
- completion `build/id-map-game-retirement-r1/completion.json`:
  `ad7c7b02d8ad5f548b0bb477057c12c9f6d01e3406ae31a825b39326df42c115`

119,305,712 logical /119,312,384 allocated bytes retired. archive grew38,608,896,
below39,682,048 bound. Weighted/TTL/LRU byte-retention passed before and after;
Weighted's default correctly rejects the missing originals, while its exact-two
pinned opt-in passes and reports archived origins unavailable. historical closure
limits are now explicitly historical metadata, not current live-pair assertions;
guards unchanged and77 tests pass. old report/tool bytes remain retained.

fixed4/16gib caps and UNCHANGED1536mib reservation now pass. no current runnable
migration pair remains; only ONE fresh admitted IdMap pair may be built next.
no actual build/runtime qualification or original live-origin renewal occurred.

## native proof products, 2026-10-28 21:34 utc

50 inactive generated products under exactly seven IdMap lab roots were archived
with the unchanged existing tool, under the exclusive cleanup lock. all blobs
reconstructed BEFORE pruning; independent bounded reconstruction, manifest and
complete complement/protection checks passed afterward. 34 conservation tests pass.

- closure `build/id-map-product-retention-r1/closure.json`:
  `fe37e34d3930ff38ac4f423aba3984eeb8964909981bd63120570275e84f309b`
- archive run `20261028-id-map-native-products-r1`, manifest:
  `c21ae6bbca9415abd4b479a1a5fb5e8dc39e99309cf7513585003dee594a5da6`
- completion `build/id-map-product-retention-r1/completion.json`:
  `05f71f34bbb384505cced76769c04990ce832a464cfef8447a62dc34b1e7885d`

330,069,243 logical /330,178,560 allocated bytes retired. archive grew74,551,296
bytes, below76,386,304 bound. 836 small files and1,039 protected files unchanged:
whole1,038-file old game tree plus canonical archive. all113 reference objects
also match original external admission pins, not newly rebound hashes.

large admission jsons, maps, executables and two exact disassembly products retain
FULL original bytes in blobs. compact source, models, golden data, commands,
stdout, failure receipts and digest index remain live. archived metadata is DATA,
never a tool/source resolver or renewed pre-execution evidence. archived originals'
live-path/inode/ctime/native-origin replay is **unavailable**. the before/after
conservation gate describes this action, not future mutations of protected files.

old pair remains live; no build or pair retirement occurred. archive16,804,302,848
and live2,753,572,864 bytes fit fixed4/16gib caps, but1536mib future reservation
still fails until the separately conserved old pair is retired. no user storage,
Steam, assets, sources or unrelated process was removed. all39 remain OPEN.

## earlier inactive cache retirement

Exactly three inspected, inactive, singleton cache files were archived with the
existing cleanup tool. Every blob reconstructed before pruning; independent
post-prune reconstruction and live-complement/protection checks passed.

- closure: `build/id-map-retention-r1/closure.json`,
  `b1e7563faa41ed099bffd8387012ab7027c9f2ebe521b117238828ad0b770ac2`
- archive run: `20261028-id-map-inactive-cache-r1`, manifest
  `9e9da7b6c266afb421a9b3ce8e95e5371be52b9d2e9673ce8ad2c4ca76663036`
- completion: `build/id-map-retention-r1/completion.json`,
  `d4eb5babf528318295e900bcb13d21330ea8bf23112a2d29ae00b176b1666d69`

52,560,429 logical bytes / 52,568,064 allocated bytes selected. Actual archive
allocation grew 21,483,520 bytes, below the 23,572,480-byte bound. Ten hermetic
selection, hardlink, complement, provider, membership and corruption controls
pass. Read-only independent pre-prune review found no actionable safety defect.

262 cache complement files and 240 protected canonical/current-game paths stayed
unchanged. Protection includes 226 game objects and 113 required reference
objects, not every unrelated file in the old pair tree. The canonical Rust
archive, current proof binaries, sole runnable game pair, storage and Steam were
not removed. Other externally hardlinked incremental files were not selected.

Old cache live-path/inode/ctime replay is **unavailable**. No receipts or original
source/tool/product provenance were rebound; this is byte conservation only.
Fixed 4/16GiB caps passed after retirement. Further native-lab accounting and a
separate protected-game-product conservation mechanism are needed before fresh
game admission. Do not use source epochs for retired products or lower the
1536MiB build reservation. IdMap application qualification and final module
cleanup remain pending.
