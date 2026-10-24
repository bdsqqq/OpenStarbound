# opt-in rust OptionParser qualification

## scope

all eight compiled definitions in `StarOptionParser.cpp` dispatch through Rust: three metadata assignments, three registration APIs, `parseOptions`, and `printHelp`. Rust owns registration duplicate decisions, token consumption, error ordering, positional cardinality and help traversal/layout selection. native storage assignments and record/container/formatting full expressions remain native leaves—not callbacks to the old parser/help handlers.

`STAR_USE_RUST_OPTION_PARSER` defaults OFF and links the existing sole aggregate FFI archive. the complete fallback namespace remains byte-exact against `0a428508`; `StarOptionParser.hpp`, private record types, native strings/collections, public options, ostream and exception ownership remain unchanged. this is the compiled parser module, NOT all foundation/runtime services or the full engine.

## finite native and raw-rust gates

- original, namespace-only reference, current OFF fallback and repeat: 295 scenarios, ordered sha256 `056b5d907385bcb6266b86623b249c1deaa862263fd2ff4bf8232864ff290e4b`.
- actual selected production C++ bridge plus Rust archive matches the complete stream and independent literals; raw Rust host replay exercises all 33 operations and 24 formatting templates.
- real callback exception identity, pending preservation, partial writes, stream state/width/tie, lazy metadata and safe active-list insertion, const/private-type factories, invalid output/phase checks and custom opaque scalar scripts are exercised. exhaustive invalid-phase coverage is NOT claimed.
- four successfully compiled, normally exiting controls reject native bypass, suppressed receipts, wrong pending-status routing and selected-dispatch corruption. paired native corruption and 13 native semantic/stream mutants remain calibrated independently.
- final post-native-build acquisition: `build/option-parser-lab/{cpp-postbuild-r1,rust-postbuild-r1}/report.json`. production report: 1,136 bindings, six binaries, 17 command receipts. `verify_candidate.py` rehashes inputs, generated sources, counters, binaries and stdout/stderr; six integrity corruptions and ten verifier tests passed.
- the verified all-C++ game rebuild changed only `StarVersion.cpp.o` among the 201 sealed native archive/tool/link inputs. the new seal and explicit allowed-change receipt are in `build/option-parser-lab/postbuild-identity/`. prebuild reports remain historical, not current-object seals.
- parent debug/release each passed 83 FFI plus 14 lighting tests (97/profile), with formatting passing. canonical archive sha256 `11dae6d55246d785f40bfa6fdcd70aca423a6f30363c7b47157a3192cf3d1fbd`.
- independent read-only source review found no actionable findings; it is not runtime certification.

## actual client startup and rendering

`build/behavior/option-parser-actual-r1/report.json` passes two all-C++ baselines and the combined candidate with exact pixels/state at all three stages. all three candidate PNGs were inspected: normal blue64x64 image, white `OPTIONS` Font label, visible occlusion and exact restoration. no standalone isolated-parser game build is claimed.

actual flow:

`ClientApplication::startup → RootLoader::initOrDie → VersionOptionParser::parseOrDie → OptionParser::parseOptions → real owned -bootconfig file → Root::Settings/defaultConfiguration → normal Lua root.getConfiguration → normal Assets image/directive → normal Font/TextPainter`.

normal Lua reads the loaded `{color:[48,176,240,255],label:"OPTIONS"}`. it derives `/behaviorlab/option-parser.png?multiply=30b0f0ff`; normal Assets supplies the16x16 image and rendering displays64x64. there is no additional parser invocation or synthetic result used as a scene proxy.

main-thread Rust `[attempt,success,nativeException]` rows are exactly:

```text
metadata0/1/2: [0,0,0] each
switch registration3: [5,5,0]
parameter registration4: [3,3,0]
argument registration5: [0,0,0]
parse6: [1,1,0]
help7: [0,0,0]
```

two switches originate in `VersionOptionParser`, three switches/three parameters in `RootLoader`. normal successful client startup does not exercise unused metadata/positional/help APIs; those have separate complete native/raw-host coverage. C++ reference FFI rows are zero, with positive actual parse and Root-settings observations and identical consumed results.

`option_parser_proof.py` validates exact parsed arguments/parameters/errors, loaded source JSON, Root settings, Lua configuration, consumers, geometry and counters. absolute boot/storage paths are projected ONLY after binding them to the actual sentinel-owned launcher file and its complete JSON. backend-specific counters are removed only after exact source-derived validation. no pixel masks, tolerances or fitted golden changes exist.

all eight isolated mutations of the ACTUAL native receipt were rejected, including a self-consistent foreign boot path rejected by launcher binding. `native-negative-controls.json` binds the untouched original receipt sha256 `5e9534408f8e75efa57159afe59b5469f36a7ececd94c12a8d7c98025356780e`.

## actual early CLI exits

`build/behavior/option-parser-cli-r2/report.json`:12 actual client executions pass independently literal stdout and exit codes for help, help with a parse error, unknown option, missing parameter, duplicate boot parameter and repeated end markers. help-with-error still exits0; ordinary errors print to STDOUT then help and exit1. no version-string/source-ID projection is used, and no early-exit counter receipt is claimed.

first C++-only CLI acquisition failed because the harness omitted two upstream application log lines. source tracing established `StarMainApplication_sdl.cpp:465/476` and `StarLogging.cpp:28` produce them BEFORE parser entry. the second fixture includes both exact literals rather than stripping/masking output; no Rust CLI observation had yet been accepted and the parser/help literals were unchanged. the failed `option-parser-cli-r1` remains. the known-bad literal verifier fixture and exit-precedence unit controls pass.

## regressions and remaining gate

all16 actual matrices passed. `build/behavior/option-parser-historical-pixels.json` asserts every new/old report pass flag and all15 previous candidate sequences (45 decoded RGBA frames) remain byte-identical to the qualified Zstd checkpoint. this includes the real Zstd TCP/image scene. no extra isolated game build is counted.

156 behavior tests, ten candidate-verifier tests and the1,598-file/39-module catalog with eight inventory drift controls passed. final native source/binary seals passed before commit; postcommit checks are in the handoff. executable sha256: C++ `ac60e48c6f070d69bbf11621351d7c75e3f33787b25604f801d91d583163e045`, combined `718c27e1d4fa7e6e5600cac0d05b375ba19b49cafa01c53adea5feb281d88f78`. producing reports alone is not the acceptance evidence: pass assertions, decoded-pixel equality and the inspected new PNGs are separate gates.

fresh native/combined mono PCM16 WAV replay passes8000Hz/eight exact samples, seek/EOF and17 byte receipts, with corrupt expected PCM rejected. this is not audible playback or an audio-module port.

## limits and retained failures

Apple Silicon/macOS27/Xcode clang21 only; no universal equivalence, performance, actual OOM, allocator/destructor/resource timing, other platform, server startup, Universe negotiation, remote gameplay or full-engine claim. real client argv/startup is qualified—not a new network/save contract.

P1 full undefined-behavior instrumentation failed existing `StarFlatHashTable.hpp:309` empty-end pointer arithmetic; it remains unchanged. separate enum-only instrumentation passed295 cases; no whole-engine UB-clean claim. defined non-enumerator3 is retained, not arbitrary out-of-range enum values.

one verifier relative-path acquisition bug was repaired before the worker's complete `rust-production-r2` replay. a parent verifier invocation initially omitted `--report` and stopped BEFORE any native project build; the correct invocation passed before the successful build. neither operational failure is algorithm parity evidence. original goldens, reference flags and native algorithms were not adjusted.
