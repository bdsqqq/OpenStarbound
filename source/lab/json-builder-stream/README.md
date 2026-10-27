# json builder stream native calibration

scope: all 20 explicit `JsonBuilderStream` bodies in `StarJsonBuilder.cpp:6–101`
and class declarations at `StarJsonBuilder.hpp:8–37`. the adjacent
`JsonStreamer<Json>::toJsonStream`, parser, full header, serialization module,
rust, private abi and game behavior are NOT selected or qualified here.

## contract and planned gate

`model.py` is a separate python stack machine and source-backed scalar oracle.
it is frozen, with corpus, literal checks, original cpp/header copies, compiler
profile, dependency/source closure and whole sdk interface witness BEFORE any
native observations. no observed outputs become expected values. the selected
cpp/hash and header/hash are pinned in `run.py`.

- `List.last` throws on empty (`StarList.hpp:472–482`); `takeLast` removes before
  `Maybe.take` (`StarList.hpp:507–510`, `StarMaybe.hpp:306–314`). an empty sentry
  is distinct from json null. errors can destructively consume values and keys.
- objects pop value then key, insert in reverse stack order, and discard their
  local partially assembled object on error (`StarJsonBuilder.cpp:14–27`). the
  sentry is not removed by duplicate errors. the first repeated key encountered
  in reverse processing determines the error, not a first/last-key-wins rule.
- arrays reverse only after reaching their sentry (`:33–44`). both container
  kinds share a sentry; cross-kind endings are included, not assumed undefined.
- string construction uses explicit utf32 length and native unicode replacement
  (`StarString.cpp:89–95,667–671`, `StarUnicode.cpp:296–342`). surrogate units and
  values above unicode's maximum become U+fffd; embedded nul remains a byte.
- numeric leaves use native `fast_float::from_chars`, not locale streams
  (`StarLexicalCast.hpp:50–57`). full-consumption integer overflow is accepted
  with initialized zero (`fast_float.h:1468–1555`); doubles retain raw bits,
  including signed zero, infinity and native quiet nan. finite decimal oracles
  use python ieee conversion with independently asserted literal boundaries.
- exception observation includes actual dynamic c++ type and `what()` c-string
  bytes, not stack traces. embedded nul terminates the public c-string even if
  the internally formatted message has later bytes (`StarException_unix.cpp:70`).

`lab.cpp` dumps json type, integer, scalar double bits, unsigned raw utf8 bytes,
array sequence and object key/value members. semantic oracle comparison sorts
object members ONLY; this does NOT prove unordered-map iteration, insertion
history or unsorted serialization equivalence. separate unsorted native traces
must match byte-for-byte original/current, along with intermediate errors and
progress. no output-byte signed-char promotion is used as a codepoint observer.

at each event, `stackSize` and a copied builder's destructive drain expose the
remaining state without consuming the original. actual copy construction,
assignment, move construction/assignment of destinations and shared native
string/array/object pointers are checked. virtual base deletion is exercised.
these are finite lifecycle probes, not destructor timing/allocation/OOM proof.

## execution and evidence

```
python3 -B source/lab/json-builder-stream/model.py
python3 -B source/lab/json-builder-stream/run.py run --output "$PWD/build/json-builder-stream-native-r1/attempt-1"
python3 -B source/lab/json-builder-stream/run.py verify --output "$PWD/build/json-builder-stream-native-r1/attempt-1"
```

outputs are exclusive fresh paths; aliases, hardlinks and overwrites are
rejected. verify is read-only; corruption overlays preserve original evidence.
the native source object is freshly compiled for current/frozen original and
three normal-exit semantic mutants (array reverse, object pop order, sentry
take). the actual ninja 113-object order is retained with exactly the builder
object replaced, plus one fixture object; remaining 112 objects are prebound
readonly, NOT freshly built. the original 113 including the unused builder are
all bound as inputs. no stale changed header is allowed.

compiler ast/manual exact-body coordinates and hashes must reconcile for both
original/current; compiler-generated default/copy/move/assignment/destructor
operations are separately reconciled against their actual fixture use. the
complete original cpp is retained, including unmodified adjacent out-of-scope
streamer bytes. original/current raw repeats and independently expected semantic
rows must match; each mutant must exit zero yet differ semantically.

reuse is source/dependency/recipe-bound to the coherent native all-25-off path
embed reference. expanded driver runtime/plugin, physical native archive members,
loaded trace, surviving map origins and whole sdk interface/settings/symlink
witnesses use unchanged `path-embed-replay` helpers. unknown origins fail.
required command argv/stdin/stdout/stderr/typed normal exits and required artifact
membership are reconstructed by the read-only verifier, not trusted from its
report dictionary. known corrupted artifact/source/command/expected clones must
be rejected BEFORE exclusive acceptance publication. failures retain partial
artifacts, exact stage and closed attempt budget; no source or model fitting.

limits: finite corpus only, apple arm64 profile only; no universal resource,
allocator/destructor timing, arbitrary-pointer, framework implementation,
interpreter/transitive-dylib, transient edit/revert, abi, rust or application
proof. no game, capture, cargo, core/header/cmake or old-helper mutation.
