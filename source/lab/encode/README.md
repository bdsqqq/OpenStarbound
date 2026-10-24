# frozen encode calibration

this is exact byte/count calibration, NOT game proof. no expected-data regeneration or tolerance exists. the candidate is the actual `source/core/StarEncode.cpp`, compiled independently of shared builds.

## frozen authority and adaptation

`StarEncode.original.{hpp,cpp}` are verbatim `git show b36026ec:source/core/StarEncode.{hpp,cpp}` snapshots, not copies of an active worker's files.

- cpp sha256: `75271b7d7db92682250259ceed417f714a9f55f1d428d37b354398ad808cec0c`
- hpp sha256: `3610df48913a01098c9846d363182ce994b1726ab66ea66ec062205f95b90723`
- adapted primitive prefix sha256: `0b24920f26d6eae1a44b6756b1ff68bdff3b5a9b64a25aae5d273cac37971a3d`

the generated reference preserves cpp lines 1–198, changing only `namespace Star` to `namespace FrozenReference` plus `using namespace Star`, then closes that namespace. all five complete primitive bodies, both alphabet strings, and both decoder helpers remain verbatim. the exact excluded boundary is `String hexEncode(char const* data, size_t len) {` at line 199. actual project String/ByteArray declarations are included, not reimplemented. the live public header must equal its frozen snapshot. full frozen files remain available for independent inspection.

the standalone linker dead-strips uncalled allocating facades; real String/ByteArray allocation implementations are NOT linked/tested here. the six original facade bodies are nevertheless gated byte-for-byte against production. no claim about eliminated alphabet-copy allocations or allocation-failure behavior follows from this lab.

## source-traced contract (verified by frozen source)

all eleven declarations: original hpp lines 8–22.

- cpp 5: hex encoding is lowercase; capacity consumes whole pairs only.
- cpp 17: hex decoding accepts upper/lowercase, substitutes zero independently for each invalid nibble, ignores an odd tail.
- cpp 46: nibble decoding emits one byte per character, invalid characters become zero.
- cpp 69: standard base64 pads; url base64 does not. capacity may cut at any output byte. input length narrows to int.
- cpp 135–196: decoding accepts both alphabets and locale-sensitive `isalnum(unsigned char)`. stops on the first nonaccepted byte, including whitespace, nul, or equals. two/three trailing symbols produce one/two bytes; one produces none. noncanonical padding bits are accepted. accepted nonalphabet symbols map through string npos to unsigned byte 255; byte arithmetic wraps.
- cpp 199,207: two pointer-input allocating encoders preserve their std::string sizing/resizing.
- cpp 216,228: two ByteArray allocating encoders borrow ptr/size and return owned String results.
- cpp 220,232: two allocating decoders allocate by String::size, read by utf8Ptr/utf8Size, and return owned ByteArray. base64 shrinks the result; hex asserts its allocated count. these are intentionally NOT normalized to utf8 byte length.

`NPos` is a public capacity bound, not proof of an allocation that large. the harness supplies bounded inputs with buffers large enough for maximum actual output. alias cases compare original ordered reads/writes using separate identical backing buffers. Rust receipts must be zero on actual overlapping output prefixes and on guarded range/length fallbacks; disjoint normal calls, including capacity zero and NPos, require one successful receipt for that operation.

## replay

```sh
python3 source/lab/encode/run.py --output build/encode-lab/cpp-final-r3
python3 source/lab/encode/run.py --define STAR_USE_RUST_ENCODE \
  --archive build/encode-rust/implementation-target/release/libstar_engine_ffi.a \
  --output build/encode-lab/rust-final-r3
```

use a fresh output suffix for a new artifact. the compiler/SDK/vcpkg flags are borrowed from the real reference compile database's StarEncode.cpp entry, retaining production O3/fast-math/arm64/native SDK settings. only original source/output operands are replaced; standalone dead-strip and undefined-behavior sanitizer flags are added. the sole allowed backend define must be paired with an archive. arbitrary primitive defines and outputs outside `build/encode-lab` are rejected. no CMake/Ninja/Cargo invocation or shared build mutation occurs.

`report.json` records every exact command, binary hash, input hashes and negative controls. `before.json` and `after.json` bind the checker, harness, raw snapshots, production cpp/public header, compile database and (when selected) C ABI header/archive. any input drift invalidates the run. baseline execution is repeated before mutants can count.

## inspected evidence

final `cpp-final-r3` and `rust-final-r3` each passed **325,073 cases** with zero failures. counts and all 2,048 buffer bytes are exact; additional individual canary checks account for most of the 629 million checks, not that many independent inputs.

- all 256 single input bytes across five operations and capacities 0–6;
- all 65,536 hex pairs at capacities 0,1,2,NPos;
- lengths 0–64, both encoding alphabets, capacity 0 through oversized, NPos;
- disjoint buffers and offsets -7,-1,0,1,7, including exact alias;
- explicit stop/padding/cross-alphabet cases, nul/high bytes, deterministic random seed `0x5eed1234`;
- independent anchors `g1F? -> 01f0`, `Gaf -> 000a0f`, `Zh== -> f`, `Zg$anything -> f`, `Z -> empty`, standard/url encoding of `f`, lowercase hex of ff;
- C, en_US.ISO8859-1, en_US.UTF-8 locale passes on this host;
- seven zero-capacity no-read probes exercising SIZE_MAX declared-length fallbacks and base64 INT_MAX+1 fallback. these do not pretend to allocate huge objects.

Rust successful per-op normal-call receipts: `[12173,274333,12178,12173,12695]`. fallback receipts checked separately against zero. the tested archive sha256 is `254c5d90242c0f23fc5bb09868b1b504a67519b00f9e8f3a12f73ee406968a94`; production cpp sha256 is `d9a4f71b0556ca134b58e9e79769c719f8d62824c49a8820d0d2c809d9f41e19`.

cpp has 12 negative controls; Rust has 13 (including receipt suppression). isolated invalid-hex-policy, url-padding, and whitespace-skipping algorithm mutations all compile and exit 1 through `COMPARISON`, not crashes or compilation failures. numeric byte, returned count, canary, provenance, unauthorized adaptation, facade size-policy and CLI restrictions also reject. receipt suppression preserves algorithm output and fails receipt comparisons specifically. algorithm mutants are frozen-source candidate copies in isolated output, never edits to production/reference.

one intermediate r2 verifier attempt exposed that adding early range probes displaced the old `cases==1` mutation trigger. no mutants were counted as passing in that failed attempt. the trigger now targets the first normal comparison independently of unrelated probe ordering; final r3 passes all controls.

## limits

allocation facades are source-preservation-gated, not runtime exercised. C ABI invalid-input, thread, panic tests belong to the kernel worker. synthetic acceptance-table behavior is not independently exercised here; locale passes cover classifications the installed locales actually provide. no huge real allocations, fault injection, sanitizer beyond UBSan, other-platform run, game, asset, image or visual claim. the parent separately produced and inspected bounded actual-game matrices: see [EVIDENCE.md](EVIDENCE.md). those image-path checks do not turn this standalone lab into universal game or convenience-overload proof.
