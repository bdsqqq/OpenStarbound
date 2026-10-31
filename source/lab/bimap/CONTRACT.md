# bimap policy and native adapter

`STAR_USE_RUST_BIMAP` enables experimental production dispatch, default **OFF**.
Rust owns the collection's branches and loops. native maps retain node storage,
layout, keys, iterators and typed returns. this is not retirement of C++ storage
or complete application qualification. the existing `star_engine_ffi` aggregate
remains the only Rust engine runtime.

## boundary

`StarRustBiMap.h` uses ABI1: request32/reply24 bytes, zero arguments/reserved
fields, VOID0/BOOL0..1/native-size replies. modes0..18 and leaves1..32 retain
their values; modes19..22/leaves33..36 add Maybe/take/pairs policy. throwing
leaves cannot acknowledge success. errors stop without writing results or
rolling back earlier native mutations.

`StarBiMapHost.hpp` is the single adapter used by lab and production callers.
its synchronous callbacks catch every C++ exception; native code rethrows only
AFTER Rust returns. context/envelope alignment checks do not establish pointer
provenance: callers must supply live objects and retain no callback addresses.

## why the native scopes remain explicit

- insertion keeps both original insertion-result locals through final pair
  construction. no optional slots or extra observable iterator moves.
- equality constructs its original named reference pair once. nested Rust
  EQUAL_PAIR runs lookup/comparison while the pair and pointer remain live.
  legacy flat mode16 remains available but is not used by this adapter.
- Maybe lookup keeps the native iterator alive through return construction.
  PRESENT chooses a return expression; no typed value crosses the scalar ABI.
- maybeTake removes the requested key, ends the pointer-Maybe full-expression,
  copies the still-live opposite key, THEN asks Rust to remove that key. the
  original `return right/left` expression constructs the native result. failures
  preserve partial mutations and normal local destruction.
- required take destroys an empty condition-local Maybe before its separate
  lazy missing-key throw. successful `.take()` retains native move/reset order.
- pairs destroys range iterators before its original NRVO-eligible return.
  value/default wrappers retain `.value(def)` as one native full-expression:
  the default parameter is copied even on a hit.

21 method bodies are guarded. `test_production.py` reverses those exact guards
and the include seam to recover the frozen header byte-for-byte, protecting
all remaining methods, declarations and fields. simple forwarding/accessor/
iterator operations remain typed native leaves, not a second policy engine.

## intentional native quirks

source locations below refer to `StarBiMap.original.hpp`, not the expanded
production header:

- right-duplicate insertion asserts and, with assertions off, continues linking
  (`:306–316`); do not add a right-side precheck or graceful false.
- equality skips absent keys (`:400–416`), so equal-sized disjoint maps can compare
  equal. conventional map equality would change native behavior.
- range construction ignores insertion results; list construction throws before
  advancing on false (`:170–183`).
- assignment clears left then right before iteration; add checks left first;
  overwrite removes left then right; ordinary removal removes the opposite
  mapping before the requested mapping. none is transactional.

## reproducible checks

```sh
python3 -B -m unittest discover -s source/lab/bimap -p 'test_*.py'
python3 -B source/lab/bimap/run_real.py --work-dir "$PWD/build/bimap-check" --production
```

use a fresh work directory. the runner uses one reusable target inside the
existing charged root, records compact commands/results and removes its own
native scratch after success. it never archives another copy of rebuildable
Cargo output. a narrowly guarded resume option preserves the original failed
post-Cargo budget receipt; it is not permission to replay successful stages.

actual evidence: 228 aggregate release Rust tests; real native Map/List/Maybe
and nontrivial-key20 cases matched generated and production OFF/ON traces;
extra-copy mutants differed;17 frame controls preserved exception type/message/
object identity, unwind ordering and partial state. exception linkage uses an
exact-body projection of the native Unix TU excluding unused logger/fatal
entrypoints, not a substitute exception implementation or full-TU claim.

remaining: debug-assert runtime behavior, custom iterator/return-proxy domains,
full platform configuration/linking and actual running-game behavior. finite
lab traces do not establish universal equivalence, game adoption or a future
aggregate allocation bound. archived providers are never restored as current.
