# actual dungeon cache consumer

status: **finite application qualification accepted**, production revision `5074db1a`, selectors default OFF. Parent independently replayed `build/lru-final-qualification-r3/qualification.json` (SHA256 `7b22bb0d323d85282aa958cb68054d119d5ad035a0bf5eb175901cc6eee40635`): 22 actual scene matrices, 66 PID-bound game captures, 198 selected PNG/receipt pairs, 44 exact edges and 66 historically inspected candidate frames. All nine R3 LRU images were inspected across Native/repeat/Rust. Production model/unwind/protocol, literal WAV conversion/12 CLI, finite TCP/SBVJ/BTree consumers are separately bound. This is not full-engine adoption, other-platform qualification, mixer/device audio, general save interchange or Universe handshake. Historical failure/status/identity limitations remain in the certificate and migration plan. Logical images in `test_lru_proof.py` are negative control inputs, never game evidence.

## boundary

`lru-room` adds a twenty-second issue-scoped scene; the previous twenty-one scenes
and their exact pixel/state gates are unchanged. ordinary runs do not arm the
observer or load these assets. the new overlay is selected only by the existing
sandbox capture runner. no cache clear, replacement, resize, installed-asset
write, user-storage access, or numeric pointer/liveness claim is introduced.

this scene uses 21 explicitly scoped `.dungeon` inputs instead of guessing which
installed definitions can be constructed. each goes through normal Assets JSON,
`DungeonDefinitions::readDefinition`, the actual `DungeonDefinition` constructor,
`root.dungeonMetadata`, and normal Lua conversion. metadata is independently
checked, including name, index, maxParts, protected, gravity and empty anchor
array. the definitions deliberately have empty parts: this proves metadata/cache
construction, NOT TMX parsing, dungeon placement or procedural world generation.
installed archive availability alone is not native-construction evidence.

`StarLruCacheLab.hpp` contains an opt-in, calling-thread-local observer. the
existing `m_cacheMutex` remains held while key-only storage leaves are inspected
before/after get and at producer entry. no Value/shared_ptr is copied for
observation; the production return expression still converts its original
prvalue within the original return full expression. the producer is unchanged
except for an observation at its entry; exceptions are recorded and rethrown,
never turned into success or rolled back. observer JSON/key allocation is
lab-only and is not an allocation-failure/OOM transparency proof.

raw cache key/name/error bytes are canonical lower-case hex, not UTF-8 map keys.
ROOT/GET counters are exact eight-byte big-endian hex; subtraction is modulo
2^64. measurements use `sb_lru_count(10, 0)` only under
`STAR_USE_RUST_LRU_CACHE`; native receipts declare `backend=native`, evaluated
selector OFF, and both counter values zero. individual Rust get deltas must be
one, INCLUDING the throwing producer. counters must be contiguous inside each
Lua phase; unrelated main-thread caches may advance them between phases. later
frame receipts must retain earlier event/counter history exactly.

## state matrix (write before acquisition)

all frames: ordinary sandbox lighting room, camera `[64,48]`, pixel ratio 2,
existing viewport/capture contract, real WorldPainter overlay and Font label.
the central 64x64 color is derived from actual selected dungeon metadata and
phase; receipts, not color alone, establish invisible cache behavior.

| frame/world action | normal Lua calls | expected actual cache (LRU to MRU) | rendered result |
| --- | --- | --- | --- |
| `lit-room` / room populated | definitions 1..21; MRU 21 hit | after 21: 2..21 (20); hit pre-evicts 2: 3..21 (19), no producer | metadata 21; RGBA 168,84,80,255; `LRU 1/3 metadata=21 continue=ok` |
| `occluder-added` | revisit 1; pcall unknown; valid 1 continues IN SAME invocation | revisit: 3..21,1 (20); error pre-evicts 3: 4..21,1 (19); continuing hit leaves 19, no producer | metadata 1; RGBA 8,4,160,255; `LRU 2/3 metadata=01 continue=ok` |
| `occluder-restored` | revisit 2; MRU 2 hit | revisit: 4..21,1,2 (20); hit pre-evicts 4: 5..21,1,2 (19) | metadata 2; RGBA 16,8,240,255; `LRU 3/3 metadata=02 continue=ok` |

the FIRST observed actual cache is retained, with arbitrary pre-existing keys,
not assumed empty. 21 distinct valid accesses converge the cache without a
reset. the verifier independently replays every operation from that snapshot and
also asserts the explicit terminal memberships above. any intervening unscoped
cache mutation that changes the expected boundary state rejects; it is not
silently discarded. 22/25/27 cumulative operation counts and exactly three
paired frame/receipt stages are required.

cross-run comparison is relational, not an assumption of identical bootstrap
inputs. EVERY raw transition is validated first. after twenty distinct successful
accesses, all untouched initial keys must have been evicted: accessed keys are
MRU, and before access twenty a full cache necessarily has an untouched entry.
therefore the exact state is1..20, then2..21 after access21. comparison retains
this proved convergence, event20 itself, all later transitions, metadata and error
messages. raw initial/warmup histories and exact within-run history prefixes stay
in their original receipts and remain mandatory validation inputs. tests cover
all initial occupancies0..20, existing fixture keys, opaque/mixed/reversed keys,
and warmup defects that later converge anyway; such defects still reject.

Lua appends an exception backtrace with ASLR addresses and backend-specific
frames. `StarException::what()` explicitly prints WITHOUT that trace
(`StarException_unix.cpp:69–75`). validation requires the Lua first line to equal
the complete native exception message bytes in the scoped receipt, and accepts
only the recognized diagnostic backtrace form. raw Lua diagnostics remain
untouched; only the exact message participates in cross-run semantic equality.
a changed message, malformed diagnostic, counter, transition or pixel still
rejects. this is not a tolerance or native-algorithm change.

actual acquisitionr1 remains FAILED: candidate was correctly blocked when the
old comparator demanded equality of arbitrary initial cache histories and Lua
ASLR traces. no old artifact/report was rewritten. fresh acquisitionr2 used the
revised, pre-frozen verifier and passed semantically; parent inspected all nine real images. Successful R2 manifests lacked PID/start receipts and were NOT upgraded. Fresh R3 used unchanged binaries and a pre-frozen non-mutating process observer, with three actual PID/PGID/start/normal-exit receipt pairs. The final composition combines R3 with the old21 scenes and PCM/save/TCP/CLI gates. Original final-r1 remains rejected and interrupted final-r2 unaccepted. Archived historical bytes are verified through exact pinned manifest membership; old inode/ctime/live-path seals are not renewed.

restoring the world is still checked against the existing scene fields, but the
three LRU images intentionally differ because cache phases differ. this special
rule applies ONLY to `lru-room`; it does not loosen old restoration goldens or
baseline-vs-baseline/candidate exact framebuffer comparisons.

## integration contract

the game-dependent implementation lives in `StarClientApplication.cpp`, not the lower application library. `BehaviorLab::prepareLruFrame(WorldRenderData&, unsigned stage)` executes one
normal Lua phase when the stage advances, and submits a normal Drawable on each
eligible render. `renderLruLabel(GuiContext&)` uses the normal Font/TextPainter
path. `lruProof()` supplies the nested frame receipt. client wiring accepts `lru-room` in the native gate, calls prepare only when ready/no pending capture/not fullbright before WorldPainter, renders the label before capture, and binds scenario plus `lruProof` in metadata.
no additional client-owned synthetic cache or image is needed.

`behavior_lab.py` selects only `lru-assets` for this scene, validates real
receipt/frame membership and visual samples, preserves original evidence while
normalizing backend/counter differences for semantic equality, binds the receipt
to evaluated CMake `STAR_USE_RUST_LRU_CACHE`, and enforces native repeat followed
by Rust candidate comparison. the generic build-provenance reader already
records all `STAR_` cache entries. existing local provenance limitations remain:
this is not a signed attestation or complete transitive SDK reproducibility
proof.

## source-only verification

```sh
cd "/Users/bdsqqq/www/OpenStarbound/source/lab/behavior"
python3 -B -m unittest -v test_lru_proof
```

19 deterministic tests exercise native/Rust normalization, occupied and opaque
non-UTF8 initial states, exact u64 wrap, membership/type failures, per-call
producer/error/partial effects, continuation, sequence history, pixels/Font,
fixture input literals, evaluated selector mismatch and common comparator
repeat/candidate backend enforcement. four coherent alternate executions
(hit-keeps-capacity, hit-produces, error-rolls-back, error-not-counted) fail the
SAME verifier, without merely changing a top-level hash. these tests are NOT
application acceptance.

## retained replay and historical acquisition recipe

The accepted final verifier is read-only and forbids subprocess creation:

```sh
python3 -B source/lab/lru-qualification/verify.py \
  --certificate build/lru-final-qualification-r3/qualification.json --controls
python3 -B scripts/cleanup-migration-artifacts.py budget
```

Do not rerun acquisition merely to reproduce the certificate. Cleanup is mandatory before another component: preserve only the current necessary Native/Rust pair and compact exact-byte evidence; pinned successor archive evidence is required before pruning dependencies of the final certificate. The commands below document the original fresh-generation recipe, NOT authorization to accumulate another generation. Any future acquisition requires settled ownership, an explicit prior-candidate disposition and passing disk budget; never rebuild into a historical accepted artifact tree.

```sh
# inside the established offline build-tool environment; choose unused N.
STAR_BEHAVIOR_LRU_GENERATION=N bash "scripts/build-behavior-lab.sh" lru-cache-combined

python3 -B "source/lab/behavior/behavior_lab.py" run \
  --reference "build/behavior/lru-cache-combined-rN/reference/bin/starbound" \
  --candidate "build/behavior/lru-cache-combined-rN/candidate/bin/starbound" \
  --assets "/absolute/read-only/path/to/packed.pak" \
  --scenario lru-room --output "build/behavior/lru-actual-rN"

# independent replay of those SAME stored outputs, no game process:
python3 -B "source/lab/behavior/behavior_lab.py" compare \
  --reference "build/behavior/lru-actual-rN/reference/frames" \
  --repeat "build/behavior/lru-actual-rN/reference-repeat/frames" \
  --candidate "build/behavior/lru-actual-rN/candidate/frames" \
  --output "build/behavior/lru-replay-rN"
```

`N` is a placeholder, not a valid generation value; choose an unused positive
integer. the parent recipe evaluates all 26 native selectors OFF and the
combined candidate's 25 selectors ON except LINE_QUERY OFF, configures before
freezing generated sources/recipes, and uses offline vcpkg without install.

required AFTER build: actual LRU scene baseline twice BEFORE candidate; inspect
all nine real PNGs and all receipts (27 operations in each final receipt), bind
artifact/revision identities, then rerun ALL old 21 scenes/63 stage matrices with
unchanged historical checks, existing actual PCM/audio, TCP/save and CLI gates.
no game execution, passing visual claim, or LRU application qualification may be
inferred from the source-only tests here. do not overwrite old goldens or relax
caps/tolerances to make a candidate pass. a local cache fixture does not close
the full Rust migration or supported-platform qualification.

retain issue-scoped code/inputs until the parent accepts this regression slice;
then decide whether it remains a permanent opt-in regression. no cleanup or
publication is authorized by this fixture.
