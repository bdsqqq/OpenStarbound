# finite native bytearray calibration

native only: no rust implementation, selector, public-header, production, game,
asset, save, or network algorithm changed. `CONTRACT.md` is the immutable
pre-execution source contract; its SOURCE ONLY label records that earlier phase.
this receipt does not qualify bytearray application consumers or the full engine.

## accepted finite observations

- source-frozen oracle: **987 cases**, canonical sha256
  `05258a405c475acc6d46ec78c74ac67270d70d730ab2cf757ab2ef45f9918d8c`.
- **33 compiled definitions**: 32 members plus ostream; **23 header definitions**,
  including `combineWith`, allocation/copy operations, and signed-char hashing.
  the 56-definition case map is source exercise, NOT instrumented coverage.
- separately linked original/reference/current and current repeat: all 987 rows
  match the unchanged python contract. original/reference use byte-exact whole
  native cpp and the same real public class, not a namespace/type model.
- three source-mutated, normally exiting native controllers independently match
  the auditor's wrong-controller models and fail the correct frozen oracle:
  reserve doubling removal changes 22 cases; signed comparison changes 16;
  iterator insertion returning the inserted element changes 18.
- all 113 configured native objects are archived in order and byte-checked both
  through extracted members and an independent BSD archive parser. maps bind
  probe/body objects and exclude the archive's old `StarByteArray.cpp.o`.
- before/after inputs, compiler/tool identities, new probe/body transitive
  dependencies, executable bytes, and stdout/stderr are sealed. the existing
  all-native IODevice reference game's current build receipt supplies the profile;
  no redundant full-project/game build was performed.

native profile is apple signed-char/64-bit only. initialized physical backing is
kept distinct from logical size: the native sub/right quirks may copy beyond
logical size only within the explicitly initialized allocation. no uninitialized
tail, freed object, invalid null memory-routine argument, or realloc-invalidated
self-append is observed. callback exceptions retain token identity and mutated
live inputs without inspecting destroyed partial results.

## authoritative local artifacts

under `build/byte-array-lab/`:

- `source-freeze-r1/freeze.json`: oracle and fixture/builder hashes BEFORE native
  compilation; the source-only author never acquired native output.
- `acquire-r1/acquisition.json`: compiler-only stage; six executables, zero corpus
  executions. five copied-manifest corruptions reject before execution.
- `execute-r1/report.json`: four positive streams and three normal semantic
  controls; all seven processes exit zero.
- `audit-r2/audit.json`: independent artifact/member/source/stream replay,
  `AUDITED_FINITE_NATIVE_BYTEARRAY_PASS`.

replay without compilation:

```sh
python3 -B source/lab/byte-array/stage.py verify --report build/byte-array-lab/execute-r1/report.json
python3 -B -m unittest discover -s source/lab/byte-array -p 'test_*.py' -v
# choose a fresh owned audit directory; existing evidence is never overwritten.
python3 -B source/lab/byte-array/audit.py --report build/byte-array-lab/execute-r1/report.json --output build/byte-array-lab/audit-replay-N
```

17 synthetic/source tests pass, including malformed archives, duplicate/nonfinite
JSON, missing cases, typed bool/int substitutions, forged controls, and the
source-derived resize-growth regression. these checks and five manifest
corruptions are integrity/sensitivity evidence, not native semantic-negative
credit. the CI workflow runs python tests only, not macOS compilation or gameplay;
remote CI was not run.

## retained failures and review

source author corrected two synthetic mistakes before the freeze: python
self-extension and multiline constructor-inventory matching. no native oracle
output, reference, domain, or correct expected row was changed afterward.

`audit-rejected-r1/` preserves the first auxiliary auditor and its rejection. its
wrong-growth-controller projection covered explicit reserve calls but omitted
filled resize, although `StarByteArray.cpp:102–109` calls reserve before filling.
the one parent repair adds that source-derived action to the auxiliary wrong
controller, with wrong-capacity 65 / correct-capacity 128 regression anchors. the
correct 987-case oracle, native sources, fixtures, acquisition builder, binaries,
and execution outputs remain byte-identical. failed audit gets NO semantic
negative credit; do not reset its attempt history or erase the old artifact.

read-only source review traced the full defined domain and found no actionable
findings. a second read-only artifact review checked current bindings and all
seven stream counts/differences, also without actionable findings. both reviews
are terminal, without children. parent owns acceptance, independent replay, and
integration; reviewer agreement alone is not runtime evidence.

## next boundary

native-owned opaque blueprint first, including substantive header algorithms;
then rust decisions/loops in the sole aggregate and actual linked consumers.
retain native allocation/object/exception ownership and public layout/API.
callback size mutation/reentry, arbitrary aliases, OOM, free tracking, exhaustive
protocols, sanitizers, other platforms, and performance remain unqualified.
external SDK/package transitive inputs are not fully verified by the game build
receipt; local seals are not reproducible-build proofs or signed attestations.
