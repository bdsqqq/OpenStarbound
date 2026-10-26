# native StringView calibration

this is a native-only contract for the complete58-definition compiled boundary,
not a Rust port or completion of `foundation.text`. production files stay intact.
`inventory.py --check` runs before compilation and receipt verification; the
bounded extractor distinguishes definitions from declarations/comments/literals
and records exact source coordinates/body hashes. it is not a general C++ parser.

```sh
python3 -B source/lab/string-view/inventory.py --check
python3 -B -m unittest discover -s source/lab/string-view -p 'test_*.py'
python3 -B source/lab/string-view/run.py run \
  --output build/string-view-lab/native-worker-r1/parent-final-r1
python3 -B source/lab/string-view/run.py verify \
  --output build/string-view-lab/native-worker-r1/parent-final-r1
```

output must be fresh. no regeneration occurs in check/verify. the runner freezes
the source-derived expected JSONL before native execution, materializes all113
native core/extern translation units with selectors off, and substitutes the
byte-identical frozen StringView unit. no stale header/object mixture or second
StringView definition is linked. source/dependency/tool snapshots, compiler/link
commands, compiled58-symbol inventory, ordered outputs/repeat and controls are
bound. these are unsigned local receipts, not reproducible-build or full SDK
content attestation.

## domains that change the implementation

- most searches and substrings count decoded scalars; split methods instead use
  byte offsets/lengths, emit trailing empties, and issue zero callbacks for an
  empty separator. empty-pattern find/findLast return0 even with a nonzero start
  (`StarStringView.cpp:136–165,179–271`).
- case folding changes only ASCII A–Z; whitespace is space/tab/LF/CR/BOM, not
  vertical tab/form feed (`StarString.cpp:11–47`). malformed iterator fixtures
  use explicit byte/scalar anchors, not Python's grouped replacement decoding.
- borrowed storage stays alive. `Char*` constructors expose initialized native
  object bytes, not UTF32 encoding; `utf8Ptr()` does not promise termination.
  returned references, alias offsets, native iterators, String bridges, stream
  references and formatter dispatch remain part of the contract.
- general indexed access requires a readable scalar. nonempty `at(size)` and
  larger requests throw at loop index size−1. empty/default `at(0)` is excluded;
  a view endpoint is not necessarily a readable backing object.
- substring endpoint cases use `std::string`'s live NUL at data()+size, avoiding
  an `&*` indirection through null or a true array-one-past pointer. default-null
  substring endpoints are excluded. this conservative domain is not a repair or
  universal classification of every pointer expression (`StringView.cpp:356–375`).
- first-of/not-of and boundary indices stay≤scalar size. Char/pattern find may
  start beyond size because their advancement stops at end. default-NPos
  substring traversal and explicit zero/clamped lengths are tested separately.
- split callbacks can throw, reenter, mutate live backing bytes or reassign the
  receiver. the next byte begin must remain≤replacement length. the pattern is
  passed by value; no Rust slice may span a future native callback. the original
  exception identity and already-issued callback effects matter.
- private compare's unusual otherLen decrement is preserved, but public calls
  all pass otherOffset0. no private-access hack claims coverage of nonzero
  offsets (`StringView.cpp:103,126,345,388`).

three normally exiting compiled **driver** mutants drop trailing fields,
substitute scalar offsets, or normalize empty-find behavior. they deliberately
leave the frozen module unchanged: discriminating oracle controls, not Rust
native-bypass proof. finite macOS arm64 only; no sanitizer, arbitrary-pointer,
borrowed-lifetime/OOM/platform/performance/application equivalence claim.

## next gates

before production mutation: reviewed opaque native ownership/controller protocol,
then substantive Rust branches/loops under a separate default-off selector and
the existing sole aggregate. preserve std::string_view/reference/iterator/layout,
exception identity and typed native full expressions. never unwind C++ through
Rust or cache a borrowed slice across callbacks.

actual-game validation remains required. the retained proposal uses normal
Assets loading with `?setcolor=123456` (literal RGB18,52,86, alpha/dimensions
unchanged) and normal Font text `^shadow=#123456,noshadow;VIEW`, plus baseline
repeat, scoped executing-thread receipts and inspected framebuffer restoration.
that proposal is UNEXECUTED; kernels do not close its application gate.
