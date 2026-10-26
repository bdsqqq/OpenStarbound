# native-owned bytearray seam: source-traced design

status: DESIGN, not an accepted ABI or implementation. no production selector,
public header, allocation ownership, or rust code changes here. the accepted
987-case native gate remains separate. supplemental callback traces now pass
`build/byte-array-lab/callback-audit-r1/audit.json` (14 cases / four positive
streams / two normally exiting controls). that accepts only the finite native
observations, not this generic bridge or an ABI.

## the generic leaf is one full expression

`StarByteArray.hpp:194–213` selects smaller/larger objects once (ties choose rhs
as smaller), allocates the initial result, then rereads smaller size on each
condition. extension reads the current larger size and starts at the current
smaller size. changing logical sizes does not reselect roles.

a future rust loop should ask a templated native leaf to execute exactly:

```cpp
result[i] = combine((*smaller)[i], (*larger)[i]);
```

that leaf includes invocation, implicit character conversion, destination lookup,
assignment, and returned-temporary destruction. it is one expression, NOT the
legacy combine algorithm. rust owns role selection, loop conditions/increments,
resize decisions and the extension loop.

why not return a converted scalar and store it afterward? a proxy's destructor
runs at the original full-expression boundary, after assignment and before the
next condition. splitting the expression can destroy it early. retaining an
arbitrary result in optional/auto storage is not a general substitute: reference
results, nonmovable prvalues and conversion overloads differ. preserve the named
callable's lvalue invocation, without copying, moving or repeatedly forwarding it.

## do not validate dead inputs on return

source permits a distinct larger input to be destroyed on the last callback when
extend is false: the next condition only reads the still-live smaller input.
this may include deleting the receiver itself. no later wrapper/FINISH/exception
handler/context destructor may inspect that borrowed owner or its backing bytes.
no unconditional refresh-both-inputs guard is valid. coincident roles, another
iteration, or extension require different lifetime proofs; no arbitrary-pointer
validation is claimed.

capture callback arguments as native values at the source expression, not cached
data pointers spanning user code. callbacks, conversion and temporary destruction
can mutate inputs, reallocate them, or call the same API recursively. busy checks
belong to a context, not an owner: a fresh context on the same live owner must
remain usable while an outer callback is active.

## constructor-safe context and typed native slots

keep the common context free of unconditionally constructed ByteArrays. copying
IODeviceHost's embedded ByteArray result would recursively enter the migrated
ByteArray constructor. result-producing wrappers supply explicit native results;
constructor guards cannot read destination fields before source initialization.
private-field access thunks must be bound legally inside members; calling a newly
migrated public getter from its native leaf would recurse through the bridge.
header-visible typed callable state must also retain function/cv/reference cases,
not assume every callable is an ordinary object convertible to void*.

rust may exchange mode/op codes, indices, counts, byte values, flags and scalar
results. actual object/data/function pointers remain typed native state. returned
char references and iterators use native pointer slots; never encode pointers in
integer payloads or mirror the class's three-field layout in rust.

allocation leaves accept an exact rust-chosen capacity and retain native
malloc/realloc/free, including sized free. rust owns reserve's branches and
size-width arithmetic; native pointer/capacity updates happen only after successful
allocation. preserve copy/move/self-assignment distinctions. do not replace source
unsigned wrapping with eager rejection. noexcept move/destructor paths need an
explicit terminal protocol-failure policy before implementation.

## exceptions, aliases and inline coherence

native leaves capture the first std::exception_ptr, rust stops on pending status,
and wrappers rethrow the same native exception after rust returns. no foreign
unwind through rust, rollback, retry, or post-pending borrowed-object inspection.
rust panics are contained separately. no exception-wrapping policy is needed here.

preserve source-captured append pointers and memcpy/memmove distinctions; do not
reacquire a source pointer after resize to make an originally invalid alias work.
sub/right's admitted physical-backing quirks must not be rejected merely because
they exceed logical size. guards cannot infer initialized physical capacity from
logical size. these are finite capabilities, not universal pointer checks.

meaningful header allocation/copy/combine/hash control flow must become genuinely
rust-owned, not hidden in a whole legacy callback. native getters and typed leaves
are ownership mechanics, not additional substantive ports. all translation units
must select coherent inline definitions; compiling an altered control header next
to unchanged definitions risks an ODR violation. supplemental negative controls
use separate native free-function controllers, not mixed header definitions.
a prototype that redirects inline members must compile every participating native
translation unit against the same header selection; reusing this supplement's
original archive would NOT establish that coherence. use a fresh isolated native
core build with explicitly sealed header selection, or report header-routing as
unverified. testing free controllers alone must not be called actual routing of
all 23 header members.

ostream also has ordering: prefix insertion may execute user stream code before
hexEncode reads the ByteArray (`StarByteArray.cpp:253–255`). do not snapshot bytes
before that insertion. unsigned comparison and signed plain-char-to-size_t hashing
retain their different conversions.

## evidence and next action

mechanisms above are source-traced observations, supported by read-only oracle
advice, NOT ABI/runtime acceptance. sources: whole StarByteArray.cpp/.hpp,
StarMemory.cpp:21–105, StarHash.hpp:24–26, and the exception/reentry pattern in
StarIODeviceHost.hpp / ffi/src/io_device.rs. counterexamples sought: proxy cleanup,
role mutation, legal input deletion, recursive constructors and owner-global busy
checks. source disproves the simpler cached-view/scalar-return/global-owner designs.

next: accept supplemental native lifetime traces; settle a constructor-safe opaque
context, expression-step leaf, all-mode scalar contract and assertion-active native
protocol before rust implementation. old native/application evidence does not
qualify these future contracts. allocation faults, arbitrary lifetimes/aliases,
exhaustive templates, sanitizers, performance and other platforms remain open.
