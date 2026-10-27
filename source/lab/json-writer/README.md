# json writer — native calibration only

scope: the 21 explicit bodies of `JsonWriter<OutputIterator>` in
`source/core/StarJsonParser.hpp:563–799`. this is neither a parser/header/module
port nor a rust, abi or running-application qualification. production is frozen.

```sh
python3 -B source/lab/json-writer/run.py run --output "$PWD/build/json-writer-native-r1/attempt-1"
python3 -B source/lab/json-writer/run.py verify --output "$PWD/build/json-writer-native-r1/attempt-1"
python3 -B source/lab/json-writer/run.py controls --output "$PWD/build/json-writer-native-r1/attempt-1"
```

`verify` reads only. generation paths must be new, direct children of the owned
build directory; writable trees reject symlinks and external/internal hardlinks.
compiler/tool aliases are read-only inputs with requested-path/chain/payload
bindings. a pass file is published exclusively only after validation; failures
retain their output and do not acquire a pass label. two failed attempts close
this approach. diagnostic handoff files are not compiler/model inputs.

## independent expectations

`model.py` defines codepoints as integers, not python/rust unicode scalar values.
its literal tests and entire finite event corpus/expected stream are frozen
before compiler ast, object compilation, links or native runs. no observed native
output becomes an oracle. each event records accumulated output, ordered iterator
assignment/increment/proxy-destruction/callback traces, dynamic exception type and
`what()` bytes; continuation after catch exposes state and iterator effects.
non-json streams are intentional: mismatched/repeated ends drain stacks rather
than validate structure; commas are caller events. all input arrays, including
length zero, have valid backing storage and an extra readable sentinel.

real ordinary raw utf-32 and `Utf8OutputIterator` instances run beside instrumented
raw and utf-8 base iterators. utf-8 uses the actual header's 1–4 separate
`*m_position++ = byte` expressions; its outer increment is a no-op. it passes
surrogates through and substitutes values above 0x10ffff, unlike the separately
named `utf8EncodeChar` function. raw numeric tokens are copied, not parsed.
key nul termination/raw quotes and backslashes are distinct from string escaping.

native assignment/increment/proxy-destructor failures are separate one-shot
faults; proxy destruction can prevent the following raw increment. callbacks
legally mutate live input, reenter the same writer, construct an independent
writer, pop/push state, or replace the active writer by native move assignment.
the active proxy retains its own shared context/value position when the iterator
is replaced. callbacks are one-shot and cleared before input/writer destruction.
these are finite valid examples, NOT universal callback/lifetime/OOM proofs.

`indent` reloads stack size and pretty at their native loop conditions. local
`c` and `endObject::isNotEmpty` remain cached. `hex` remains a native local and
the actual full expressions/temporary lifetimes are not replaced. the eight-hex
and substring loops are unreachable with the real printable/helper domain:
valid supplementary codepoints are printable; escaped controls have hex4;
above-range values throw first. those branches are inventoried, not claimed as
runtime covered. exception `what()` formatting is derived from
`StarException_unix.cpp:69–86`, not a captured exception golden.

## inventory and provenance

manual declaration ranges plus exact bytes reconcile with compiler ast bodies;
implicit copy/move constructors, assignments and virtual destruction are listed
separately, never counted among 21. the full original header is byte frozen;
parser/base code is not a claimed calibrated component. consumer contracts were
read at `StarJsonBuilder.hpp:72–99`; no consumer/mock/controller is introduced.

actual evaluated native cmake flags and ordered ninja core/extern objects/libs
are reconstructed from `build/behavior/path-embed-combined-r1/reference/cmake`.
113 retained native objects are prebound read-only link inputs, NOT fresh builds.
all 25 rust selectors must be off. the existing 1495 source/472 configured-source
maps are independently rechecked; ninja's per-object dependencies and fixture
compiler dependencies join the before/after binding set. project source and
helper inputs have independent copied snapshots. driver expansion precedes every
link; implicit compiler runtime, lto plugin, physical archive members and every
map/trace sdk origin are reconciled using unchanged mature helpers. unknown
origins fail, not a fitted allowlist. whole sdk interfaces/links/settings are
bound, not framework implementations. interpreter/dylib transitive closure,
transient edit/revert attestation, other platforms, oom and universal resource
claims remain open.

five separately compiled normally exiting semantic mutants exercise key nul,
escaping, array pretty spacing, indentation and container popping. semantic
stdout must differ from the independent model despite exit zero. repeat runs
must match. verifier controls use malformed/missing/false-bool receipts and
corrupted source/object clones without editing acquired inputs.

future application evidence belongs to the parent: normal lua/assets repr/json,
text-frame world painter crops and sandbox configuration write/reload. none is
run or claimed here. acceptance by the parent precedes abi design/adoption.
