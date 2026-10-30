# bimap scalar policy — implementation increment

this is Rust branch/loop policy, NOT a complete BiMap port. production
`source/core/StarBiMap.hpp` remains unchanged and has no Rust selector/caller.
reference/iterator/prvalue/exception adapters, native differential tests and game
qualification remain pending. the existing `star_engine_ffi` aggregate is the
only production Rust runtime; a standalone Rust test is not another engine.

## boundary and remaining ownership work

`StarRustBiMap.h` defines a 32-byte request and 24-byte reply, version1.
request arguments/reserved fields are zero; replies are VOID0, BOOL0/1 or a
native-size count. a host catches C++ exceptions and reports their status;
native code rethrows only after Rust returns. errors stop immediately, without
writing the result or undoing prior host mutations.

Rust owns add/overwrite/removal/clear/assignment/iteration/equality decisions.
map nodes, hashing, element operations and typed return values remain native.
`COPY_ENTRIES` and `EQUAL_ENTRIES` are continuation leaves: prepare native
begin/end expressions at their original point, then invoke the corresponding
Rust iteration mode inside that lifetime scope.

insertion needs two scopes. `INSERT_ROUTE` runs with the original left insertion
result alive. a false decision returns its native iterator/false; true permits
right insertion. `INSERT_LINK` runs with BOTH original native insertion results
alive, requesting assertion, left link, right link. a future native adapter must
construct the final pair before those results are destroyed. copying them into
optional slots or adding observable iterator moves is NOT an accepted design.
these typed lifetime/return adapters are not implemented by this increment.

value/default/Maybe/take wrappers and constructor/iterator adapters are also
pending. in particular, `maybeTakeRight`/`maybeTakeLeft` remove the requested key
before copying the opposite value (`StarBiMap.hpp:264–283`); removal policy is
not a substitute for their copy/return/unwind semantics.

## source quirks intentionally retained

- **right duplicate insertion is not a graceful false.** the comment at
  `StarBiMap.hpp:80–81` conflicts with `:306–316`: only a duplicate left returns
  false; right insertion is followed by native `starAssert`, then both links.
  the Rust linking stage always requests that assertion and retains the
  assertion-off continuation/partial mutations. do not add a right precheck.
- **missing keys can compare equal.** `StarBiMap.hpp:400–416` compares a value
  only when the other right pointer is present. an absent lookup advances.
  equal-sized disjoint maps therefore pass that policy; the Rust loop preserves
  it rather than implementing conventional map equality.
- **list and range duplicates differ.** `:170–183` ignores range insert results;
  list construction throws on false. a throw precedes cursor advance.
- **ordering is observable.** assignment clears left, then right, before source
  iteration (`:296–302,389–392`); add checks left before right (`:324–332`);
  overwrite removes left/right before insertion (`:340–344`); removal erases
  the opposite mapping before the requested one (`:352–371`). no rollback or
  transactional replacement is invented.

confidence: source-traced, not native runtime equivalence. a counterexample is
an in-domain native trace with different callback/exception/lifetime order;
scripted scalar tests alone cannot disprove that possibility.

## checks and qualification

Rust tests cover all17 modes, failure at each scripted effect, lazy throw paths,
missing-key equality, assertion-off linking order, invalid envelopes and panic
containment. they execute Rust against synthetic host responses, not the native
container. C11/C++17 header layout checks, when actually run, establish only that
ABI surface. no full module/adoption/game claim follows from these checks.

next: characterize the native custom-map/iterator and nontrivial-value domains,
implement typed lifetime-aware frames, compare actual C++/Rust traces and unwind
behavior, then default-OFF production dispatch. actual game acceptance remains a
separate gate; no allocation/provenance requirement is cleared by this source
increment, and no protected historical runtime is rebuilt or rebound.
