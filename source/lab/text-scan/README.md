# text command scanner oracle

only `Text::processText` is under comparison. the complete `StarText.cpp` and
public header at `09f6a9a3` are frozen so surrounding dependencies stay genuine;
`TextStyle` and `stripEscapeCodes` are not claimed as rust ports. the reference
changes only the outer namespace and its header include. production must retain
the byte-exact fallback and unchanged public header.

```sh
python3 source/lab/text-scan/run.py --backend cpp --output build/text-scan-lab/fresh-cpp
python3 source/lab/text-scan/run.py --backend rust --output build/text-scan-lab/fresh-rust
```

outputs must be new directories. rust consumes, never builds,
`build/text-scan-rust/target/release/libstar_engine_ffi.a`. freeze production and
`build/behavior/reference/cmake` objects before running: any bound source,
compiler, recursive include, archive or object drift rejects the run. native
object freshness remains a parent seal obligation. no cargo or game runs occur.

comparison records byte offsets, event kinds, exact bytes observed during each
callback, boolean results, native exception identity/category, and final mutated
input. empty callbacks, stop/throw prefixes, arbitrary bytes, escape runs,
restarts, retained views, same-allocation future edits, reentry and by-value
callback copy/destructor order exercise the native façade. literal anchors are
independent of both implementations. guard pages exercise both ends of bounded
input spans without manufacturing dangling or reallocating inputs. a separately
compiled complete original produces an independently compared ordered stream;
its digest and all bindings are in `report.json`. `--reference-report` requires
an exact backend/source/stream match, not merely equal case counts.

rust runs additionally check preflight rejection without callbacks, counters or
output writes; empty null/max pointers; flag/host/output/span failures; host status
mapping; overlapping final publication; opaque null context; semantic thread-local
attempt counters including nested, stopped and throwing callbacks; unknown counter
indices; and strict c11/c++17 public-header parsing. native span and abort bridge
mutants plus suppressed rust receipts must fail a clean runtime comparison.
legacy scanner and verifier mutations must also fail comparison after compiling.
paired reference/candidate corruption is caught by independent literal anchors.
compile failures never count as successful negative controls.

finite corpus and this compiler recipe are evidence, not universal equivalence.
no forced rust panic, allocator failure, screenshot, whole-engine, performance,
or cross-platform claim is made here. raw protocol errors can leave partial
attempt counters, as the abi documents.

## implementation attempt ledger

- setup 1: initializer-list type deduction failed compilation; changed the
  fixture to an explicit native `std::vector<std::string>`. no negative credit.
- setup 2: an initial escape mutation proved equivalent because restarting at
  the next escape restores the same selection; replaced it with an actual
  off-by-one span mutation, detected at runtime. no credit for the equivalent
  control.
- `rust-frozen` passed an earlier checker; superseded by added callback-lifetime,
  strict-header and selected-bridge controls.
- `rust-frozen-v2` rejected real concurrent `StarVersion.cpp.o` drift after all
  behavioral checks passed. do not treat that directory as accepted evidence.

parent owns fresh integrated replay and native seals; no local commits here.
