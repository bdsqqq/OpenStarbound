# finite native byte-array contract

status: SOURCE ONLY. native compilation, execution, independent acceptance, and
mutation controls belong to the parent. no Rust, ABI, game, screenshot, sanitizer,
OOM, allocator-release, or performance claim is made here.

## frozen corpus

987 JSONL rows, 33 compiled definitions (32 class members plus ostream), and 23
header definitions, including `combineWith` and `hash<ByteArray>::operator()`.
`source_map()` enumerates each definition start, operation families, and concrete
case IDs. this is a source-exercise map, not instrumented coverage or proof that
every branch executes. constructors/destructors also run through ordinary local
object lifetimes; no freed object is inspected. destructor mapping does not prove
that allocator releases were observed.

canonical expected rows use ASCII JSON, sorted keys, compact separators, and a
newline after each row. SHA-256:

`05258a405c475acc6d46ec78c74ac67270d70d730ab2cf757ab2ef45f9918d8c`

`contract.py` is a pure Python stdlib model derived from the source, written before
any native output was acquired. `lab.cpp` includes the real public
`StarByteArray.hpp`, operates on real `Star::ByteArray` instances, and emits manual
JSON through std::ostream. there is no native class model, subclass, namespace
clone, private layout mirror, or StarJson serialization dependency. the ordinary
ostream probe deliberately invokes the real ByteArray ostream implementation.

## execution interface

native executable: no arguments, no stdin. `main(int argc, char**)` returns 2 when
`argc != 1`, otherwise emits the ordered corpus and explicitly returns 0. build
and run original/reference/current in separate programs with their original
namespace and byte-exact whole native cpp/header. do not fit expectations to their
output. parent owns compiler staging, dependency provenance, archive binding,
commands, logs, independent review, and commits.

python commands from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s source/lab/byte-array -p test_contract.py -v
python3 source/lab/byte-array/contract.py freeze
python3 source/lab/byte-array/contract.py expected
python3 source/lab/byte-array/contract.py map
python3 source/lab/byte-array/contract.py check PATH_TO_NATIVE_JSONL
```

`expected()`, `check(data)`, `canonical(rows)`, `source_map()`, and
`validate_source_map(mapping)` expose the io-device-style integration API. checker
rejects duplicate keys, nonfinite numbers, unknown/missing fields, reordered or
missing cases, altered options, and bool/int substitutions. JSON object key order
and harmless JSON whitespace are not semantically significant; canonicalization
is used for digesting. empty JSONL lines are rejected.

## defined finite domain

profile is 64-bit size_t and signed plain char, enforced by static assertions.
regular objects begin with 64 initialized bytes (`80 ff 01 00 7f 41 a5 10` repeated)
then shrink to logical sizes 0..8. only public APIs initialize or access storage.
metadata-only reserve probes start at capacities 1, 3, 7, 64, or 127; their
uninitialized allocations are never read. largest requests/results/capacities are
bounded by 256. growth beyond seeded backing is observed only after filled resize
or complete writes. all copied spans are live, in bounds of initialized physical
storage, and disjoint. self-append stays within reserved storage; source and
destination spans are adjacent and no realloc can invalidate the source pointer.

null memcpy/memset arguments are excluded even for zero lengths. no empty default
copy, empty `fromCString`, empty default append/copyTo/fill, zero-sized constructor,
or `left(0)`/zero-result sub is invoked. zero-byte memory operations use nonnull
seeded objects and nonnull external buffers. default construction, accessors,
clear, resize(0), reset, self-copy/self-move, moving a default-empty object, and
`fromCStringWithNull("")` are represented. null end()+0 follows this task's admitted
domain. seeded iterators avoid null subtraction; invalid []/assert-abort cases
are excluded. out-of-range `at` catches its documented exception class, without
claiming an exact message/stack or allocation-failure behavior.

## preserved source behavior

- first reserve allocation uses the exact request; subsequent growth uses
  `max(old_capacity*2, request, 8)`. observations inspect capacity and initialized
  logical bytes only. small-capacity probes exercise the minimum-eight floor.
- `sub(b,s)` copies `min(size,b+s)`, except its whole-copy shortcut. `right(0)`
  starts at the logical end and still copies the logical size. physical backing
  is explicitly initialized far enough for these quirks; logical size is never
  treated as proof of physical initialization. `right(s>size)` copies the whole.
- iterator insertion returns `begin()+position+1`; index insertion has no return.
  positions include start and logical end with nonnull iterators.
- comparisons order unsigned bytes, while PLHasher receives signed char converted
  to size_t. anchors include 80, ff, 01 and modulo-2^64 results. ostream is `0x`
  followed by lowercase hex and returns the same stream object.
- combine selects the smaller array first, regardless of lhs; equal sizes select
  rhs first. and/or/xor and a noncommutative callback exercise both extend modes,
  empty inputs, unequal sizes, and ties. custom callbacks record argument bytes,
  mutate live lhs/rhs first elements, then return or throw a pointer to a local
  token on call 1 or 2. caught pointer equality records exception identity. logical
  sizes stay stable, every successful result byte is initialized, and no partial
  result is read after throw. only still-live inputs/call trace are serialized.
- copy constructor capacity differs from seeded copy-assignment capacity; moving
  transfers capacity and empties its source. assignments observe returned object
  identity; self-assignment is a no-op, including default-empty self-assignment.

## verification and deferred acceptance

synthetic tests exercise expected-row roundtrip, strict rejection, source inventory,
defined-domain bounds, quirks, signed hashes, callback ordering/effects/throws,
and manually corrupted growth/compare/iterator outputs. those corrupted fixtures
are checker tests, NOT compiled native mutation controls.

the parent must separately compile normally exiting cpp-only controls on this same
corpus: growth `m_capacity*2` to `m_capacity`, comparison unsigned char to signed
char, and iterator `+d+1` to `+d`. each must independently fail this unchanged
contract without relying on crash/UB. no original/ref/domain/output fitting.

remaining gaps include allocator OOM/fault injection, free tracking, exhaustive
sizes/aliasing, callbacks changing logical sizes or reentering the API, exact
exception diagnostics, other platform profiles, sanitizers, timing, Rust/ABI,
full native-project and game execution, rendering, and screenshots. passing this
contract would prove only these finite native observations at parent-bound source
and build artifacts.
