# portable file native calibration — finite domain only

macos/main, production revision `95b67f727b63c62a7aa0a786f3662722b09bb652`.
only this new laboratory and `build/file-lab/native-worker-r1/` were written.
no rust, production, cmake, catalog, commit, deletion, or game work.

## observed evidence

`acquire-r1/report.json` records 113 freshly compiled core/extern objects,
all selectors off, 34 unique compiled portable File symbols, 139 ordered
source-derived observations, exact repeat, and 1789 before/after bindings.
all 232 scan/compile/link/symbol/execution commands exited normally.
the original cpp is compiled byte-exact, using the actual native classes,
public header, and unix platform leaves. each platform source has 30 additional
definitions; this is not a 64-definition filesystem qualification.

`contract.py` freezes lengths 0/1/1023/1024/1025/2049 and byte sequences before
native execution. functional files are exclusive-created in fresh roots; initial
input snapshots are retained outside those roots. output audits reject symlinks,
multiple hardlinks, extra/missing files, or wrong bytes. `.new`/`.tmp` paths are
absent in the fresh initial inventories. successful rename/write/truncate/copy
consume only functional fixture bytes. nothing is cleaned up.

`audit-r1.log` / `controls-r1/results.json` record five corrupted receipt
rejections plus missing-row and changed-observation rejection. these are
synthetic receipt/oracle controls, NOT compiled semantic mutants.

`supplement-r1/report.json` records byte-exact readFile/readFileString outputs,
safe virtual close reentry through fileName on another live object, a bounded
derived-close counter across base destruction, partial descending backup effects,
non-readable/non-writable guards and native pwrite error conversion, with exact
repeat. the supplement reuses only this acquisition's fresh coherent objects.
its own sources/expected bytes/objects were frozen before compilation/execution.
it does not independently seal all supplement compiler dependencies or prove OS
close timing; do not promote it to that claim.

## hard stops and limitations

- **overall acceptance remains open.** the receipt's status remains
  `FINITE_NATIVE_FILE_CALIBRATION_WITH_GAPS`, not an accepted whole-module gate.
- after acquisition/audit/supplement completed, the copied run.py docstring was
  corrected from StringView to File. this intentionally invalidates current-source
  replay of the old receipt. original run.py bytes remain in
  `acquire-r1/snapshots/source/lab/file/run.py`; no binding was rewritten.
- inventory's first attempt counted indented calls (42 instead of 34), retained
  as `inventory-attempt1.py` and `failed-source-map-attempt1.json`. one repair
  rejects indentation. the later isolated comment near-match test still fails:
  `// void File::nearMatch() {}` is misclassified and reports an unclosed definition.
  both failures remain retained. no third extractor attempt or count fitting.
  a genuinely different parser approach requires parent integration; the current
  exact-source 34/30/30 map is reproducible but the inventory validation gate fails.
- successful remove and recursive deletion branches are **UNEXERCISED**. only
  empty-name/missing-path/virtual-close-throw paths run. no successful deletion.
- null m_file is legitimate default state: unix maps it to fd0. the runner supplies
  an owned nonseekable stdin pipe. observed size=-1 and absolute I/O=size_t(-1)
  are pipe-specific, not universal closed-file guarantees. no fabricated handles.
- virtual close exceptions are native-protocol mocks with original exception_ptr
  identity, not genuine OS close failures. native fclose failure and allocation
  failure remain unexercised. no private-field/layout/vtable replacement.
- 34 symbol presence and source exercise do not establish instrumented branch
  coverage, universal destructor/noexcept behavior, or full OS/platform equivalence.
- SDK implementation binaries are unbound. no sanitizer/performance/Rust/application
  or full-engine claim. no historical game receipt rebinding.

## parent hardening (before fresh acceptance)

The two failed whitespace/line-regex extraction attempts are closed. The parent
changed approach to lexical comment/literal masking with balanced braces. It
also found the old constructor extent incorrectly included the next destructor:
`File(String)` ends at line127, not131. The regenerated map keeps34/30/30 logical
definitions; isolated line/block/raw-string near-matches, missing output, drift,
non-writing checks and deterministic writes now exercise the bounded grammar.
This is not a general C++ parser; column-zero non-template definitions are the
frozen source contract, independently challenged by native compiled symbols.

`run.verify` now uses the strict `audit.validate`: exact current recipes and all
scan/compile/link/symbol/run argv, original source pins, complete source/dependency
and artifact memberships, native snapshots, mirrored command receipts, typed
normal exits, stdout/stderr/executable identities and required preexecution
objects are reconstructed. Native runs explicitly record empty owned-pipe stdin;
closed `File::size`/absolute observations must not be generalized beyond it.
The frozen historical acquisition and supplement above are not rebound. A fresh
parent acquisition and isolated controls must pass before finite acceptance.
Successful deletion remains UNEXERCISED, and no Rust/application claim follows.

## historical worker next action (superseded by parent hardening)

preserve all current artifacts. finish verifier hardening BEFORE new acquisition:
`run.verify` currently checks only a subset; `audit.validate` adds status, exact
139 observations, 34 compiled symbols, source-map check, before==after==bindings,
current recipes/libraries, complete command-name list, compile argv, executable
hashes, normal exits, mirrored command JSON/stdout/stderr, and preexecute hashes.
it still needs exact source/dependency closure membership (reject omitted entries),
required 113 object/preexecution/link artifacts and complete link/scan/run command
argv reconstruction, verification-time original cpp/hpp/platform byte checks,
and a source-map scope binding independent of caller-provided dictionaries.
exercise isolated omitted-object/dependency/command/link/source-map corruptions.
then use a new explicitly frozen acquisition, never rebind this old receipt.

commands actually executed:

```sh
python3 -B source/lab/file/inventory.py --write
python3 -B source/lab/file/run.py run --output build/file-lab/native-worker-r1/acquire-r1
python3 -B source/lab/file/audit.py build/file-lab/native-worker-r1/acquire-r1 build/file-lab/native-worker-r1/controls-r1
python3 -B source/lab/file/supplement.py build/file-lab/native-worker-r1/supplement-r1 build/file-lab/native-worker-r1/acquire-r1
python3 -B source/lab/file/test_inventory.py build/file-lab/native-worker-r1/inventory-tests-r1
```

last command FAILS the near-match fixture; preceding positive, catalog-drift and
source-drift CLI fixtures behaved as expected and did not repair their outputs.
all failed artifacts retained. source-map generation uses exclusive creation;
run verification/check modes do not modify the acquisition.
