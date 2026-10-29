# static vector — native characterization first

scope: the complete owned `StarStaticVector.hpp` class, not `SmallVector`,
list mixins, allocation policy or math/lighting. no Rust/production changes yet.
use one existing aggregate later; generic inline element storage stays native.

## why a vector oracle is insufficient

- moves preserve the source size; self-move assignment still runs element moves.
- copy/range insertion resizes/default-constructs before assigning inputs. even
  an empty insertion can self-move the tail; a clean no-op changes callbacks.
- default `Element()` arguments and assigned `Element(args...)` temporaries have
  native full-expression lifetimes, including on no-op resize and exceptions.
- size increments before placement construction and decrements before destruction.
  observer callbacks must see the native value, not an eventual committed size.
- overflow text deliberately uses `m_size + requested`; do not repair it.
- equality calls element `!=`; ordering calls `a < b` then `b < a` and short-circuits.
- initializer-list assignment uses dependent `list[i]`: characterize its lazy
  compile failure separately. do not make unused members eagerly instantiate.

constructing failure after the size increment can poison the object's live-slot
count. invalid iterators, invalid index operations and subsequent destruction of
an unconstructed slot are NOT defined-domain parity cases. keep diagnostics
separate; no normalization into Rust's cleaner container semantics.

## first corpus

fixed source-derived literals BEFORE compilation: capacities0/1/2/4; ordered
values and return offsets for constructors, copy/move/self-assignment, all valid
insertion/erase positions, empty ranges, resize, reverse/const access and each
comparison branch. exact typed exception and full `what()` checks come from
native exception code, never output-calibrated goldens. ABI size/alignment are
recorded native observations, not claims about every platform.

producer stdout: one JSON object `{"schema":1,"cases":[{"name":...,"value":...}],
"abiObservations":...}`. unique case names; no extra stdout. model returns the
literal expected case mapping. only explicit ABI observations are outside that
mapping. keep the serializer standard-library-only so a frozen reference header
cannot collide with production `StaticVector` through `StarList` includes.

known semantic mutants must distinguish moved-from clearing, insertion shift
order, overflow arithmetic or pre-construction/pre-destruction size publication.
the fixture compiles its frozen class under a dedicated identifier via the
`StaticVector=StaticVectorCharacterization` test macro. this prevents already
compiled Core weak instantiations from satisfying a mutated-header test. the
same isolation applies to baseline and mutants; production selectors/optimization
flags stay untouched, exception literals stay unchanged, and no RTTI/type-name
parity is claimed by this value corpus.

trace/exception/constraint follow-up is mandatory before any ABI promotion:
value tables alone do not qualify generic lifetimes or reentry.

## epoch and ownership

new explicit lab paths end the prior game's closed-tree membership epoch; its
finite IdMap certificate remains historical, not rebound. production source and
selectors stay untouched. parent alone admits/runs compiler, linker, Cargo,
game, archive and commits. no native process before current tool/SDK/source/argv
admission, no flags/model fitting or deadline resets. fixed4/16gib caps and only
one necessary game pair remain; no new game generation in characterization.
