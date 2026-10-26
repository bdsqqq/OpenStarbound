# finite native callback supplement

status: SOURCE ONLY, frozen before native compilation/execution. 14 source-derived
JSONL rows; expected canonical SHA-256:

`c44665b0ef232eda3e689de2cc9d736bec83d330aeb079511652a9a11f3c7464`

The accepted 987-row contract remains unchanged. This supplement uses the real
public `Star::ByteArray::combineWith`, unchanged native header, no class mirror,
namespace clone, or StarJson. Parent owns staging, native compilation/execution,
provenance, compiled controls, independent audit, integration, and commits. No
Rust, ABI, application, full-engine, sanitizer, performance, or allocator claim.

## source contract and host boundary

VERIFIED by source trace: `source/core/StarByteArray.hpp:194-213` selects roles
once, ties choose rhs as smaller, initializes result to initial smaller size,
re-reads smaller size on every condition, and re-reads larger size for extension
and tail conditions. `StarByteArray.cpp:83-109` supplies exact first allocation,
minimum-eight growth, and filled-resize semantics. Countercheck: there is no
cached loop bound, role reselection, owner-wide guard, or larger read in the
non-extend epilogue. These are source findings, not observed execution results.

A future generic host leaf must execute the complete original full-expression:

```cpp
res[i] = combine(smaller[i], larger[i]);
```

Here `res`, `smaller`, `larger`, and `combine` refer to native objects/callable in
the per-invocation context. The leaf must include the callable return temporary,
char conversion, destination lookup/store, and temporary destruction BEFORE Rust
asks the next loop condition. A leaf returning char after only callback/conversion
is insufficient: the proxy destructor may mutate live inputs. Preserve the named
callable's lvalue invocation even when its argument was an rvalue. Preserve native
argument evaluation rules, without inventing an ordering for independent reads.

The native wrapper supplies result storage; a shared host context must not embed
an unconditionally constructed ByteArray (its construction could reenter the
controller). Store borrowed pointers/references and scalar state instead. Native
exceptions must remain native, retaining identity and already-performed effects;
no C++ exception may unwind through Rust. This document does not implement that
bridge or validate an exception relay. Same-owner reentry with a fresh context
must remain valid. Do not add owner/global guards.

## defined corpus

All inputs first initialize 64 physical bytes through public APIs, then shrink to
logical sizes at most 5; mutations reach at most 7. Lhs bytes start 10,11,12,...;
rhs 40,41,42,..., with an eight-byte repeating pattern in backing. All values are
representable signed chars; profile requires 64-bit size_t and signed char.
The callback computes `2*a+b` on copied arguments. No source spans outlive their
objects; no uninitialized result suffix is observed. Empty-result serialization
performs no byte access and its backing remains allocated.

- `tie_rhs`, `lhs_small`: noncommutative anchors establish role order; all direct
  cases use a noncopyable/nonmovable lvalue-qualified combiner passed as an rvalue.
- `shrink_noextend`: smaller 3 to 1; result size/capacity remain 3/3, only the known
  written prefix `[60]` is inspected. `shrink_extend` instead fills from fresh
  smaller size 1, producing `[60,41,42,43,44]` with capacity 8.
- `grow_large`: stable smaller 2, larger 5 to 7 using filled resize with 77.
  `shrink_large`: stable smaller 2, larger 5 to 3. Fresh extension bounds differ.
- `flip_roles`: original smaller 3 to 1, original larger 5 to 0 in first callback.
  First store is valid in the initially size-3 result; next condition fails.
  Fixed larger role yields result size 0/capacity 3 and no tail reads. Roles really
  invert (1 > 0), without another read from the now-empty original larger input.
- `proxy_convert_shrink`: char conversion shrinks smaller; `proxy_dtor_grow` grows
  larger in the first proxy destructor. Ordered call/convert/dtor events and tail
  bytes are checked. C++17 nonmovable prvalues rely on guaranteed elision.
- `throw_callback`, `throw_convert`: throw a pointer to the local token after a
  live-input mutation; retain pointer identity. Conversion failure still destroys
  its proxy. No failed result is inspected.
- `reenter`: first outer callback calls combineWith on the same owner using fresh
  local callback state. Nested `[50,52,54]` is fully written and serialized.
- `delete_rhs_large`, `delete_this_large`: reset the unique_ptr owning the larger
  operand on the second/last callback, extend false. Smaller remains alive and
  has size 2. Arguments are already copied; result `[60,63]` or `[90,93]` is fully
  written. No deleted-owner read, fixture guard, or receipt occurs afterward;
  its receipt is null. The direct combiner has no destructor touching that owner.

The finite observations distinguish recorded lifetime order and mutations across
iterations/tail. They do not expose the private result address to a callback and
therefore do not independently observe destination-store versus destructor order;
the full-expression requirement is traced directly to native source.

## execution and controls

Native executable: no arguments/stdin; argc != 1 returns 2, otherwise emits the
14 ordered rows and returns 0. C++17 or newer is required. No native command was
run by the source author. Python stdlib-only interfaces:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s source/lab/byte-array -p test_callback_contract.py -v
PYTHONDONTWRITEBYTECODE=1 python3 source/lab/byte-array/callback_contract.py freeze
PYTHONDONTWRITEBYTECODE=1 python3 source/lab/byte-array/callback_contract.py expected
PYTHONDONTWRITEBYTECODE=1 python3 source/lab/byte-array/callback_contract.py check PATH_TO_JSONL
```

`expected()` contains literal source-derived traces, not a native-output adapter
or C++ loop echo. `canonical(rows)` returns sorted-key compact ASCII JSONL bytes;
`check(bytes)` returns 14 or raises ValueError. Exact recursive type/schema/value
checking rejects reordered/missing cases, unknown fields/statuses, bool/int and
float/int substitutions, duplicate JSON keys, nonfinite numbers, blank lines,
and fabricated receipts. Whitespace/key ordering alone are insignificant.

Eight synthetic tests exercise strict checking and defined spans, plus fabricated
fixed-loop, stale-tail, proxy-cleanup, reentry, dead-object, and exception-identity
failures. These are NOT normally exiting compiled mutation controls. In particular,
the invented fixed-loop record is never executed against a shrunken native input.

Parent control anchor: exactly one source occurrence of this complete line:

```cpp
      return lhs->combineWith(Direct{c}, *rhs, extend);
```

It immediately follows `CALLBACK_GROW_LARGE_NATIVE_ANCHOR`. A safe parent variant
may replace it with a conditional selecting a new free function ONLY for
`name == "grow_large"`, leaving native public API calls for every other case.
That free function may use public ByteArray operations and the same named-lvalue
combiner, select roles once, save initial larger size 5, run the genuine fresh
smaller loop, then resize/copy tail using the stale saved 5. This is safe because
smaller stays 2 and larger grows to 7 filled bytes: result is the wrong but fully
initialized `[60,63,42,43,44]`, size 5/capacity 8. Do not change the inline header,
introduce conflicting class definitions, or invoke this mutant on other cases.
The source author has not implemented or compiled that wrong free function.

Freeze discipline: the four owned files and expected digest must be captured
before any native acquisition; stop source writes after handoff. Parent source
review corrected pre-freeze role inversion from 3→1/5→2 to 3→1/5→0; no native
output existed or informed that change. Zero failed source/test attempts. Later
native disagreement requires retained evidence and explicit source-contract
review; no data fitting or silent expected-output changes.
