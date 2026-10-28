# status scene source preparation — NOT game evidence

Scene 25 (`id-map-room`) binds the actual main player's StatusController to the
normal status Lua callbacks. Literal status reads are `[8,12,16,18]`, `[2]`, `[34]`.
Returned values drive normal Assets/WorldPainter/Font output. The player is held
through owned-category restoration; cleanup precedes disconnect and follows the
third capture acknowledgement, producing `idmap-restoration.json`.

Source-preparation completion: `build/id-map-scene-r1/completion.json`, sha256
`5e04bc5654ca7c9b534babd084b492c1f274ec46b450baed2cada4ff9355ee55`.
Nine logical proof fixtures pass. ClientApplication typechecks OFF and ON.
Initial syntax acquisition failed AFTER a successful OFF command because its
broad snapshot included redirected `syntax.stdout`. The original failure stays
failed. Explicit composition verifies actual code/tool/SDK bytes unchanged and
continues ONLY the unexecuted ON command with generated outputs excluded.
This is parsing/typechecking, not Lua execution, captures or restoration evidence.

Before modifying ClientApplication/BehaviorLab, exact original code was retained.
Post-change WeightedPool/TTL/LRU byte-retention passes with scene epochs:

- WeightedPool: `27584708dbce88ab1f7b1e4df5b37c5e7af77108e99766e49838d41a298dac7d`
- TTL: `b6830e36134c6c21b0f9baa8e33dfeb95de132bfd24dd22fb74a4d52c09bd088`
- LRU: `ae2028db8374227b38538dfe8b8c006dc3da5f3658f4e21a1572ca81cc5d2c50`

## next gates

1. **runner integration pending.** The original `behavior_lab.py` and its contract
   tests remain byte-exact: they are acquired tools, not eligible for a source
   epoch waiver. A newly admitted successor frontend/explicit extension must
   consume scene-25 proofs, restoration receipt, image bounds and actual origins
   without relabeling scene 24 or substituting old tool bytes.
2. **fresh game admission blocked.** Keep the sole WeightedPool pair and 113
   reference objects. Existing build admission reserves 1536 MiB and rejects an
   older runnable pair. Do not lower that reservation from historical peak data.
3. Establish exact IdMap inactive-product retention/selection using the existing
   cleanup policy. Three candidate Rust cache/duplicate files account for
   52,568,064 allocated bytes, but must be independently frozen, archived and
   reconstructed before pruning. Do not select externally hardlinked increments.
4. WeightedPool's current protected-product guard cannot retire its old game
   binaries via source epochs. Add separate exact successor-manifest historical
   product conservation, preserving tools/SDK and the live complement; explicitly
   mark lost live inode/ctime/origin replay. Never waive the old guard.
5. Only after accounting/retirement/reservation gates: real game acquisition,
   all state/image/auxiliary checks, independent inspection and module cleanup.

No new game generation, captures or user-storage changes occurred. All 39
modules, application qualification and mandatory IdMap completion cleanup remain open.
