# bounded byte-codec evidence

VERIFIED on apple M2 Pro, native arm64, apple clang 21 / macOS 27 SDK, 2026-10-24. tested source was the working tree based on `b36026ec`; exact compile inputs are bound by each native binary's local before/after build receipt. no pushes or remote CI. this is the five `StarEncode` algorithms and retained C++ ownership facades, **not the entire serialization module or full-game compatibility**.

## numerical and ABI boundary

- primary `build/encode-lab/cpp-primary-r1` and `rust-primary-r1`: each 325,073 exact byte/count/buffer cases; independent anchors, exhaustive bytes/hex pairs, malformed text, capacity/NPos, overlap fallback, installed locales and deterministic random inputs. 12 C++ / 13 Rust negative controls, including real algorithm mutants and output-preserving receipt suppression.
- frozen source/adaptation hashes and replay recipes: [README](README.md). no golden, formula, reference flag or tolerance adjustments.
- primary workspace: 24 tests each debug/release, formatting; 57 behavior/provenance/encoding-verifier tests. independent source review found no actionable ABI/byte-contract defect; review is not runtime proof.
- input/output overlap, guarded address ranges and base64 lengths above `INT_MAX` retain the original C++ implementation. no Rust receipt is claimed there. locale classification is supplied per call; malformed text remains ordinary successful decoding.

## actual production path

only `encoding-room` loads the additional test overlay. normal Assets postLoad Lua loads an independently specified 16×16 PNG, runs color replacement with 3/4/6/8-character colors, URL-embeds a real PNG, reloads the embedded path through Assets/base64/PNG decoding, emits a standard padded data URI, then registers the decoded image as memory assets. the fixture object and a normal WorldPainter foreground image drawable display it. native `Color::toHex` serialization supplies that drawable's white-multiply directive.

the comparator independently verifies canonical URL and standard base64 of the **same native PNG bytes**, decoded RGBA against the literal rotated pattern, scoped operation receipts, visible palette ink, every full-frame RGBA pixel, strict native world state, and three-stage restoration. no pixel masks. paired wrong encode/decode output cannot pass merely by round-tripping.

Rust receipts observed in the actual startup/draw scopes (operation order: hex encode, hex decode, nibble decode, base64 encode, base64 decode):

- directives: `[0,6,2,0,0]`;
- URL embed and standard data URI: each `[0,0,0,1,0]`;
- embedded Assets decode: `[0,0,0,0,1]`;
- actual draw directive serialization: `[1,0,0,0,0]`.

C++ scopes are all zero. startup scopes run once per launch, not once per captured frame; the receipt is retained in each frame. swallowed Lua errors, missing memory assets, cached-away decoding, missing counts and invisible patterns reject acceptance.

## inspected matrices

all listed matrices passed independent C++ repeatability **before** candidate comparison, exact state/pixels, and action/restoration checks:

- `build/behavior/encode-actual-r1/final-comparison`: encoding-only Rust, C++ lighting/traversal. primary inspected all three candidate PNGs; the 64×64 foreground checker and ordinary fixture sprite are visible, the real occluder changes room lighting, restoration is exact.
- `build/behavior/encode-combined-r1/final-comparison`: encoding + verified Rust lighting/traversal; experimental line queries OFF. all three candidate pixel arrays equal the inspected encoding-only frames.
- `build/behavior/encode-lighting-regression-r1`: existing lighting-room gate, all three supported Rust backends enabled. inspected occluded frame; all three C++ baseline pixel arrays equal `lighting-combined-r2`.
- `build/behavior/encode-raycast-regression-r1`: existing raycast gate, all three supported Rust backends. inspected clear/blocked/restored frames: cyan ray and yellow returned-point marker shorten and restore. all three C++ baseline pixel arrays equal `raycast-visible-r2`.

native captures are 1000×600 RGBA8, final default framebuffer after ImGui/before swap, Apple OpenGL 4.1 Metal. reports intentionally leave automatic `parityCertified` false pending inspection; the observations above record the performed inspection, not a changed machine gate.

## tested artifacts

binary SHA256:

- reference: `6e9e2f22e70fa93f52b03e56c520180b3fc6d7d2841d0c557d8ee1dd8faa4be6`;
- encoding-only: `a2b2e24007c9b025a33ed27c1bc5903e724c2b0b7c4986edb77203e9a9d0bac9`;
- combined: `addd49479af6ff7c47556064559ef14a59432b55dd5818ebd5f6e516d4ab6def`.

all three source maps have SHA256 `6fedf2099920f75d8eec7d18896e5148c4afa1fa5a52861fe9a1e105ece078df`, computed over UTF-8 `json.dumps(source_files, sort_keys=True, separators=(',', ':'))`. receipts bind compiler/cache/link inputs and binary hashes, not a reproducible-build or complete external-dependency attestation. seed PNG SHA256: `a6770a0a366304b6ecbef769dd8fc1c3ccd93893d23e20dc5178d53f241e4f10`.

build with `scripts/build-behavior-lab.sh encode` and `encode-combined` inside the native Nix build-tool shell. capture/compare with `scripts/behavior-lab.sh` and `--scenario encoding-room`; old lighting/raycast scenarios deliberately omit the encoding overlay. use new output directories and the explicit packed.pak path; never user storage. all encoding/reference/combined clients built and exited; the pre-existing unrelated smoke PID92430 was left untouched.

## not established

other platforms/optimization contexts, allocation-fault equivalence (the old base64 alphabet-copy allocation is removed), concurrent global locale changes, huge real allocations, universal byte-domain proof, exhaustive convenience-overload runtime coverage, save/network/audio compatibility, dedicated-server gameplay and performance. this finite image path does not close those roadmap gates. experimental line-query fast-math remains blocked and OFF.
