# text-command scanner — parent acceptance, 2026-10-24

VERIFIED: only the complete `Text::processText` byte state machine migrates, behind default-OFF `STAR_USE_RUST_TEXT_SCAN` in the existing Rust archive. public `StarText.hpp`, callback types, native ownership and the reconstructed OFF source remain byte-exact at `09f6a9a3`. `TextStyle`, stripping, line wrapping, Unicode decoding, Font and the rest of `StarText.cpp` remain native; this is not foundation-text or engine completion.

## independent replay

```sh
python3 source/lab/text-scan/run.py --backend cpp --output build/text-scan-lab/NEW-CPP
python3 source/lab/text-scan/run.py --backend rust --output build/text-scan-lab/NEW-RUST
```

parent `cpp-primary-r1` and `rust-primary-r1` pass 16,689 cases each and 13/16 genuine detected controls. both repeat their selected binaries and independently compare the complete ordered observation stream to a separately compiled immutable original. stream SHA256: `03807c6141b64d4c70976a7a2e17aa0366fa626fa714c475f405370e77543f91`.

selected binary SHA256: CPP `700c4207af470d3cb351360f16633de6a74f3db85cc3c11cb87f6d4d78ccc5e3`; Rust `f61e88e5f4337fa348d265fcf07ff4f5263adbc33330952abea3584b5822bc6b`. source/checker/compiler/recipe/native object/dependency/archive before/after bindings pass. no check count is reported or inferred from case counts.

literal events, exact offsets/current bytes, return values, stop/throw prefixes, retained native views, same-exception identity, callback copy/destructor order, same-allocation future mutation and reentry are exercised. both protected-memory boundaries pass. command boundaries must be found before the preceding text callback, while callback payloads and subsequent scans observe permitted edits. Rust holds no input reference/slice across a callback and never stages the whole input.

raw ABI preflight/status mapping, empty null/max pointers, input/output overlap with final-only publication, null opaque custom context, semantic attempt counters, unknown getters and strict C11/C++17 header parsing pass. missing native text callbacks retain late `bad_function_call`; optional command callbacks remain optional. selected native span/abort mutations and suppressed receipts fail clean runtime comparisons, not compilation. paired reference/candidate corruption fails independent literal anchors. setup failures and obsolete source-drift runs remain recorded in [README.md](README.md); neither is credited as a passing negative. no production algorithm repair, tolerance or reference-flag change was needed. an initial worker fmt invocation used an unsuitable virtual-manifest command; the corrected invocation and parent full FFI fmt check pass.

parent workspace debug/release each pass 79 tests (65 FFI plus 14 lighting). behavior verifier 129 tests and eight inventory drift controls pass; catalog 1,536 files/39 modules. independent source review found no actionable callback/alias/routing issue and bound five unchanged production source hashes; that review itself did not run the implementation.

## actual normal glyph rendering

`build/behavior/textscan-actual-r1` and `textscan-combined-text-room-r1` pass all three 1000×600 frames, state and receipts. normal single-line left-anchored GUI rendering consumes literal `^red;TEXT^reset;` (hex `5e7265643b544558545e72657365743b`). a native fixed-capacity scope observes actual TextPainter callback spans and final foreground glyph quad colors after colored-font adjustment, without a Lua receipt or proxy image.

- actual event sequence: command `red`, text `TEXT`, command `reset`;
- Rust attempt deltas `[invocations,text callbacks,command callbacks] = [1,1,2]`; CPP `[0,0,0]`;
- actual emitted glyph codepoints `[84,69,88,84]`, each native RGBA `[255,73,66,255]`;
- native completed-scope checks and independent red-ink checks pass.

these are unchanged pre-execution predictions. named red is not generic `[255,0,0]`. antialiased framebuffer ink may blend with the room; the exact RGBA anchor describes actual quad state, not every glyph pixel. the fixture uses normal font size 8, so the visible label is intentionally small. parent inspected all three isolated full frames and the combined occluded frame. width measurement and the separate wrapping parser are not counted as this Rust execution.

all twelve earlier scenes are rerun against combined Rust: total 14 native matrices, exact baseline/candidate framebuffer/state and unchanged historical decoded pixels for all twelve sequences. newly built CPP/combined objects also pass literal mono-PCM WAV samples `[-32768,-12345,-1,0,1,12345,32767,0]`, 8000 Hz, seek/EOF, 17 Rust byte receipts and the corrupt-PCM comparison control. three final native source/binary seals pass (`/tmp/openstarbound-text-scan-final-source.log`).

finite Apple-clang/native-content evidence only: no universal equivalence, allocation-fault timing, forced Rust panic, other-platform, performance, audible playback, live network/save interoperability or server gameplay claim. raw panic/protocol aborts after entry may leave partial attempt counters. output/context allocation validity remains a caller precondition. selectors remain default OFF.
