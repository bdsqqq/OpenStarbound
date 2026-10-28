# id-map native contract gate

## scope and status

source-derived finite contract, not a rust port or game qualification. the normal
fixture includes the actual `source/core/StarIdMap.hpp`; it does not replace or
modify that production header. `StarIdMap.original.hpp` preserves its exact raw
bytes, sha256
`ff8b48f3931efedf8e5b19bc074b84a04f04329aedabbfd3eeb7b7b6ffeaad62`.

these five files are the complete child-owned write scope: `native.cpp`,
`model.py`, `test_model.py`, `StarIdMap.original.hpp`, `CONTRACT.md`. the parent
alone owns compilation, linking, acquisition, mutant generation and verification
against current optimized flags, current 113 reference objects and freshly
admitted tools/sdk. no compiler/linker/cargo/game/archive/cleanup/commit command
was run by this child. the current game pair, reference objects, user storage and
steam remain untouched. no production selector or rust abi exists for this slice.

## exact owned surface

VERIFIED by source trace, `source/core/StarIdMap.hpp`:

| definition | original line | observable contract |
|---|---:|---|
| default constructor | 80 | lowest/highest key bounds, cursor starts at minimum |
| range constructor | 84 | stores bounds and minimum cursor; debug-only `max > min` assertion |
| `nextId` | 90 | fullness uses `(IdType)size > max - min`; skip occupied ids; advance cursor before returning; no reservation |
| explicit `add(id, value)` | 102 | moves into insertion; duplicate throws; no range validation or cursor advance |
| automatic `add(value)` | 108 | calls `nextId` before insertion; named mapped parameter is copied into the base-map insert argument |
| `clear` | 115 | destroys map contents and resets cursor to minimum |
| `operator==` | 121 | compares range and base contents, not cursor |
| `operator!=` | 126 | negates equality |
| stream extraction | 131 | mutates base map, then minimum, maximum, cursor, sequentially |
| stream insertion | 140 | writes base map, then minimum, maximum, cursor |

exact three owned fields: `m_min`, `m_max`, `m_nextId` at lines 68–70.
`IdMap` and `IdHashMap` are aliases over ordered `Map` and flat `HashMap`, not
additional owned method definitions. compiler-generated special members are not
counted among the ten definitions.

all sixteen inherited native names at lines 45–60 are exercised for each alias:
`keys`, `values`, `pairs`, `contains`, `size`, `empty`, `get`, `ptr`, `maybe`,
`take`, `maybeTake`, `remove`, `value`, `begin`, `end`, `erase`.
`get`/`ptr` and iteration exercise const and mutable access; `erase` exercises
iterator and key forms. missing `ptr`/`maybe`/`maybeTake`/`remove` and explicit
`value` fallback are checked. this is coverage of the exposed names and selected
forms, not every overload or every exceptional base-map path. inherited
`MapException` behavior is not relabeled as an owned IdMap definition.

## oracle and finite cases

`model.expected()` returns a self-contained ASCII string, with a terminal newline:
44 tab-delimited `CASE` lines (22 per alias) and
12 `PASS` property lines (6 per alias): each backend's cases precede its properties. `case_names` and `property_names` expose
the exact qualified inventory. running `model.py` writes only that string to
stdout. `verify(actual)` requires exact string equality, including row order,
missing/extra rows and newline. its hermetic tests reject known semantic,
rollback, property-omission, duplicate, reorder and framing corruptions.

literal expectations were derived from the source before any native execution;
no native output, rust implementation or output files feed this oracle.
`ReferenceMap` is an independently expressed bounded Python model, while the
transcript is separately literal so a broken simulator cannot rewrite goldens.
stream byte literals are also cross-checked using Python's standard integer
big-endian encoding, not native serialization output.

both aliases use defined `uint32_t` ranges. the default constructor is checked
only for its first two ids. custom ranges include `[10,12]`, `[20,25]`,
`[40,44]`, `[10,14]`, and `[4294967293,4294967295]`. cases cover unreserved
`nextId`, inclusive wrap, upper-uint32 wrap, collision skip, explicit insertion
without advancement or range checking, last available slot, exhaustion,
duplicate preservation, holes, clear/reset, and range/content/cursor equality.

native checks use throwing `check`, never the standard `assert` macro, so
`NDEBUG` cannot remove them. a mismatch returns 1 and reports `FAIL` on stderr;
stdout is a successful contract transcript only if execution completes.

### known semantic falsifier

with `IDMAP_MUTANT_HEADER` defined, the fixture includes
`StarIdMap.mutant.hpp` instead. the parent generates this file in its build root
by changing ONLY the fullness comparison from `>` to `>=`. with two occupied
slots of the three-id range, `fill-last-slot` must succeed in the original and
throw in that mutant. the fixture catches the unexpected exception at main,
returns 1 and cannot print a complete expected transcript. this is a real
native negative control to be acquired by the parent; child tests demonstrate
rejection of the corresponding corrupted transcript, not mutant execution.

## exceptions, lifetime and template laziness

VERIFIED source contract: exhaustion has dynamic type `IdMapException`, message
`No id space left in IdMapWrapper`; duplicate explicit insertion has the same
exact dynamic type and message
`IdMapWrapper::add(id, value) called with pre-existing id '11'` in the fixture.
`StarException_unix.cpp:78–86` formats `what()` as `(Type) message`, without
stack text; both full native `what()` strings are checked literally.

`Counted` tracks construction/destruction and live objects; successful auto-add
must perform a copy because `StarIdMap.hpp:110` passes a named lvalue to
`MapMixin::insert(key, mapped)` (`StarMap.hpp:261`). explicit insertion must
move without copying in the exercised operation. there are no machine/container
move-count goldens: only positive copy/move constraints and live conservation.
`StarFlatHashTable.hpp` bucket relocation can select copying: its bucket move
constructor is not noexcept. mapped noexcept-move alone does not remove this
native base-container requirement. exact acquired traces can be diagnostics later.

an injected copy exception carries a unique identity token. automatic add must
propagate that identity, leave the attempted key absent, and retain the cursor
advance performed before argument-copy failure. this is not a general strong
exception guarantee for arbitrary allocators/hashers/base containers. clear and
scope exit must conserve all successful constructions/destructions.

`NoDefault` is valid for explicit add, get and nextId: unused default-requiring
operations must remain lazily instantiated. ordered `IdMap` explicit add of a
move-only payload is valid; native `IdHashMap` construction itself instantiates
bucket copies and rejects it. the first actual compile falsified the broader
fixture assumption; original failed source/receipt remain retained. the property
label now explicitly scopes native base constraints; 44 literal case values are
unchanged. `IDMAP_LAZY_NEGATIVE` checks ordered automatic-add copying;
`IDMAP_HASH_MOVE_ONLY_NEGATIVE` separately checks the hash-base limitation.
these are parent-owned negative compiles, not new supported APIs.

## serialization and partial failure

VERIFIED trace: `StarDataStream.hpp:347–387` encodes unsigned VLQ count, then
key/value pairs; `StarIdMap.hpp:131–145` appends range and cursor in that order.
`DataStream` defaults to big-endian primitive encoding. real
`DataStreamBuffer` APIs (`StarDataStreamDevices.hpp`) are used for writing,
seeking, reading and truncating; no synthetic stream substitutes are used.

one entry with key 11/value 77 in range 10..12, cursor 10, must encode as:

```text
01 0000000b 0000004d 0000000a 0000000c 0000000a
```

using one entry intentionally preserves unordered-map serialization freedom.
collections from inherited APIs are sorted or checked by membership; hash
iteration order is never a golden. roundtrip must replace prior contents/range
and restore the cursor, demonstrated by next ids 10 then 12.

`readMapContainer` clears before count and inserts each fully read pair before
reading range fields. `DataStreamBuffer::readData` delegates to
`IODevice::readFull` (`StarDataStreamDevices.cpp:125`, `StarIODevice.cpp:54`),
which throws `IOException`-family failure on truncation. truncations at byte
0 and 5 leave empty contents and old fields; byte 9 retains the completed entry
and old fields; byte 13 retains the entry and new minimum, but old maximum and
cursor. these exact post-failure states are serialized and checked. cuts end at
primitive boundaries to avoid asserting a portable golden for a partially
written scalar. there is NO invented rollback guarantee and no claim about
all malformed streams, duplicate stream keys, or arbitrary partial scalar data.

## numeric and diagnostic boundaries

`cycleIncrement` (`StarMathCommon.hpp:318`) wraps when `val >= max` rather than
incrementing past the upper bound. tested uint32 literals are defined and finite.
this gate DOES NOT execute full small-integer-domain, signed-overflow, invalid
range or hanging cases. the fullness cast can truncate container size for small
id types, permitting nonprogress when every id is occupied; default signed
bounds can make `max - min` overflow. these remain source-derived diagnostic
risks, not accepted new semantics, executed failures, or bugs repaired here.
finite cases do not prove equivalence for those domains or all integral types.

## future consumer, source only

VERIFIED source path, NOT game evidence:
`status.addPersistentEffects` registration
(`source/game/scripting/StarStatusControllerLuaBindings.cpp:58,197–199`) →
`StatusController::addPersistentEffects`
(`source/game/StarStatusController.cpp:248–262`) →
`StatCollection::addStatModifierGroup`
(`source/game/StarStatCollection.cpp:140–141`) →
`StatSet::addStatModifierGroup` (`source/game/StarStatSet.cpp:43–48`) →
`m_statModifierGroups.add`. `StatModifierGroupMap` is an `IdMap` alias
(`source/game/StarStatusTypes.hpp:56`). this is a possible later integration
route, not proof that this fixture or current game pair exercised it.

## verification boundary

child ran only hermetic Python tests with bytecode writes disabled: 18 tests
passed, including intentional corruption rejection. no native parse, build,
link, runtime, mutant or negative compile result is claimed. falsification still
required from parent: actual header runtime transcript, final-slot mutant
failure and move-only auto-add syntax failure with source/model frozen first.
concrete API errors may be repaired against source; literal expectations must
not be fitted to observed output. source-derived claims above would be falsified
by different actual source/encoding, not by changing a golden to match a failed
candidate.
