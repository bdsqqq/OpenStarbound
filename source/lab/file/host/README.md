# native file controller prototype

native-only, provisional. `abi.h` has the scalar C11 boundary; `controller.cpp`
contains mode sequencing and loops in the zero-based portable source-map order.
`generate.py --check` checks the generated member wrappers without writing.
no public header, production source, selector, Rust, or build-system change.

`FilePrototype::host` catches native exceptions into `exception_ptr`. `invoke`
rethrows before wrapper locals unwind. controller catch-all status 3 is a
NATIVE PROTOTYPE containment test; it must never be exercised through Rust.
0 is success, 1 pending native exception, 2 invalid protocol. counters wrap as
unsigned 64-bit TLS scalars, with attempt/success/error for each of 34 modes.

native member lambdas retain lexical private/protected access and native fields,
virtual calls, platform helpers, String/List/std::string/ByteArray/shared_ptr
ownership. no header overlay, fake class, or private-access macro is used.
callback payload is an opaque pointer to a live native lambda; the controller
retains only scalar values. the host validates registered live Context addresses,
operation bounds, null/alignment/nonwrapping output, and overlap with Context or
lambda object. this is NOT validation of arbitrary output pointers, nor complete
reachable-object/backing-span protection; that remains a gate before promotion.

`readFile` and `readFileString` deliberately retain native prefixes:
`FilePtr file = File::open(...); ByteArray bytes;` and
`FilePtr file = File::open(...); std::string str;`, respectively. their original
direct `return bytes;` (NRVO eligible) and `return str;` (implicit std::string to
String move conversion) remain native. all these counters begin AFTER the prefix:
open/construction failures are not controller attempts. modes 0, 2, 3, 7 and 33
also preserve their original native directory-parent/shared_ptr initialization
prefixes before controller entry; copy opens source BEFORE target. Rust can later own the
EOF/read/append loop and byte-by-byte push_back loop, without owning these types.
getter String return expressions and constructor initialization lists remain
native. the named constructor's controller is a no-op receipt, not an algorithm.

recursive removal uses actual native List and iterators, assigns the tuple and
relative path on every iteration, then resets its inner typed scope BEFORE the
final static remove. backups descend as unsigned, retain native concatenation
full expressions and source/target selection. copy retains EOF-before-read,
1024-byte reads and writeFull, target-before-source destruction. close leaves
field/mode untouched on failed close. resize does not add a finally-close;
clone retains original mode (including Truncate) before virtual source pos.

remaining source review: recursive removal and backup iteration use native
optional aggregate scopes to retain typed locals across scalar callbacks. their
construction/destruction sites and full-expression fidelity need parent review. no OOM, arbitrary lifetime/alias, allocation-count, destructor-event,
thread-safety, performance, other-platform, application or universal-equivalence
claim follows from finite replay. final source/full-expression audit is OPEN.

acquisition uses authenticated parent-final-r2's unchanged 113-object closure,
replacing ONLY portable object 57, never linking original and prototype File
objects together. native bypass intentionally links the original portable object
and verifies zero controller counters, while retaining exact corpus outputs.
`verify.py` reconstructs commands, dependency and artifact membership, link-map
objects, native oracles, counters, repeats, executable/stdin/stream receipts and
preexecution artifacts. malformed supplied dictionaries cannot define coverage.

`removal_replay.py` consumes the separately qualified instrumented removal report
SHA e0484806e075469a90751be55c7044564198567a3405ada3db60a365fe1d893d.
it substitutes that platform object plus this portable prototype; six cases run
twice on retained ordinary trees. it proves conditional instrumented event and
exception identity/order only, NOT actual OS deletion or invisible destruction.

all evidence paths and final hashes belong in the worker handoff under
build/file-lab/host-worker-r1; parent owns integration and acceptance.
