# inactive cache retirement — completed, not module completion

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
