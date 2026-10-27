# finite numeric-expression witness: pre-observation contract

This is a DISTINCT compositional source/protocol prototype, not the closed
JsonBuilderStream 20-body calibration, an ABI, Rust port, or application gate.
Reference calls the retained native JsonBuilderStream::putDouble/putInteger.
Candidate controls four separate operations: String construction (11), lexical
conversion (23), Json construction (37), stack append (41). Numeric leaf results
and native errors are UNKNOWN parameters, never IEEE/zero expected constants.
All old I/D token occurrences, including all five inf/nan strings, are inputs.
Supplementary malformed/Unicode/NUL/invalid-UTF32 inputs have owned storage and
one readable sentinel. No input domain is narrowed after observation.

## source contracts and falsifiers

- StarJsonBuilder.cpp:49–54 and 83–84: String(s,len) survives the entire outer
  full-expression, including Json construction, push's parameter and append.
  push's Json prvalue directly constructs its by-value parameter in C++17; that
  parameter is moved into List<Maybe<Json>>. No extra Json moves are permitted.
- StarLexicalCast.hpp:62–63 selects lexicalCast<T>(StringView by value), not
  tryLexicalCast(String const&). StarStringView.hpp:25 supplies the sole
  String -> StringView constructor, taking String const&. The original prvalue
  and candidate xvalue bind that exact const&; neither adds a String object or
  selects a different overload. Lexical leaf return is retained in a native
  scalar slot; no FP computation/normalization is performed by the viewer.
- StarStringView.cpp:88 binds view to s.utf8(). Native String ownership MUST stay
  live until all inner Json/append work and pending rethrow complete.
- StarString.cpp:89–95 constructs from all len UTF32 units via append. Native
  replacement/error behavior is a leaf parameter, not a Python reimplementation.
- StarList.hpp:435–437 and StarMaybe.hpp:118–122 retain native value ownership.
  Frame owns actual List<Maybe<Json>>, not a layout mirror of the private class.

with_string(String&&) binds the original temporary at the dispatcher call's
outer full-expression; it does not own an extra String. with_json(Json by value)
is the push parameter pattern and directly constructs Json(parsed) as its
argument. There is no borrowed unmanaged foreign pointer API. Fixed opaque
scalar tokens 101/203 are checked before every use and invalidated at boundary.
The early-release negative only invalidates the token while actual String
storage remains alive: never dereference a dead owner.

Every native dispatcher catches to exception_ptr before returning to controller.
Controller returns before a pending exception is rethrown inside the native
owner scope. No C++ unwind passes through controller. Tokens/trace are checked
owner/language-pattern observations, NOT production destructor instrumentation,
allocation/OOM timing or universal exception guarantees. StringView's const&
conversion and trivial view destruction do not introduce an owning object.

## frozen acceptance predictions

The comparator requires actual reference/correct typed Json bits, native exact
dynamic exception type + unsigned-hex what bytes, partial stack and subsequent
integer-17 continuation to be equal. Reference numeric constants are NEVER
minted into goldens. Native protocol is independently checked:

success: string-open,lexical,lexical-ok,json-open,append,json-close,string-close
lexical failure: string-open,lexical,pending,rethrow-live,string-unwind,pending
String construction failure: pending (no owner established)
mock-before-append: string-open,lexical,lexical-ok,json-open,pending,rethrow-live,
json-unwind,pending,rethrow-live,string-unwind,pending; native stack stays null.

The correct mode must pass. All controls must exit normally AND fail the SAME
actual semantic/protocol comparator: skip-append; substitute fixed integer 2
for successful input 1 (not fitted to observations); append-after-error;
early-release checked token; suppress pending exception; pretend owner released
before rethrow. Exit 0 alone is never acceptance. Native mock-before-append is
synthetic protocol coverage, not actual production allocator failure evidence.

Before execution, bind dependencies/113 OFF objects/source/header/profile,
compiler/tool aliases/expanded runtime/SDK interface closure/static archive
physical members/exact argv/stdin and required acquisition artifacts. Link 113
old native objects FIRST, then new fixture. Actual map plus surviving code must
prove reference parse helpers are provided by retained Core, not fixture weak
instantiations coalesced over both sides; same source/flags is NOT proof. Stop
at FIRST semantic/state/scope/origin mismatch; no repair, flags/domain/model
changes or whole-body callback/fullclass fallback. At most two initial mechanical
acquisition errors, preserving all artifacts. Known verifier source drift and
missing artifact must be rejected in isolated fixtures before PASS publication.

Final allowed label only: finite NUMERICEXPRESSION_WITNESS. Until every required
claim checks, status is UNPROVED. All former class budgets remain CLOSED.
