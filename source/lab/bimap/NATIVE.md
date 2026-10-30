# native core characterization

`StarBiMap.original.hpp` is a byte-exact frozen copy of the current production
header, not an edited oracle. `native.cpp` instantiates that template with explicit
`TraceMap<int, int const*, 'L'/'R'>` custom ordered maps. the quoted
`StarString.hpp` provides fixture parsing/formatting/exception support only.

this domain exposes native BiMap branching and underlying map-call order without
linking historical engine objects. it is NOT production `Map`/`StableHashMap`,
`StarException`, hashing or game qualification. `Maybe` is deliberately incomplete:
Maybe/take/default-value wrappers must not be tested against a substitute and
called native coverage. `STAR_DEBUG` is forbidden; the empty assertion macro
matches production's non-STAR_DEBUG branch and does not evaluate its argument.

20 named cases self-check ordinary/duplicate insertion, assertion-off right
conflict, lazy add errors, overwrite/removal/clear ordering, self/distinct
assignment, copy/range/list construction, missing-key equality, unequal values,
iterator references/increments and a right-insert exception after left mutation.
partial/corrupt relationships are observed only through safe counts/contains/
pointer-presence queries; null or dangling mapped pointers are never dereferenced.
no intentional abort, assertion-on run or crash is part of this fixture.

trace expectations are checked in the source before execution; results are not
fitted after a run. the parent must inspect the emitted JSONL, repeatability and
an isolated semantic mutant. no checked-in golden trace replaces the source.

remaining coverage: production storage/exception classes, nontrivial key/value
copy/move/destruction, observable custom iterator lifetimes and reentry, Maybe/
take prvalue construction/unwind, debug assertions, typed Rust-host adapters,
native-vs-Rust differential execution and actual game behavior. passing this
fixture does not close those gates or justify an allocation/provenance waiver.
