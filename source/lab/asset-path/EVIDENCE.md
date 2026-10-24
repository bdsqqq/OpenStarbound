# asset-path byte-kernel oracle

scope: exactly two ported algorithms, `AssetPath::split` byte grammar and static `findFilenameRange`. NOT the full AssetPath class or assets service. all other public observations below are dependency regressions.

## replay

```
python3 source/lab/asset-path/run.py --output build/asset-path-lab/cpp-final-r2
python3 source/lab/asset-path/run.py --output build/asset-path-lab/rust-final-r2 --define STAR_USE_RUST_ASSET_PATH --archive build/assetpath-rust/target/release/libstar_engine_ffi.a --reference-report build/asset-path-lab/cpp-final-r2/report.json
```

`report.json` is the executable evidence: exact commands, compiler/flags, before/after hashes of sources, scanned headers, compiler, native objects/libraries, and Rust archive; binary identity; ordered observation SHA256; counts; negative controls. parent must replay after its native build freezes; stale StarVersion/native object bindings cause rejection, never substitution. this agent never builds Cargo or native production targets. native-core.a is merely packaging existing reference objects in its owned output; archive timestamps may differ even for identical bound objects.

## oracle contract

complete cpp+hpp frozen from `be016305`, original and adapted hashes in `freeze.json`. adaptation only namespace/import/include rebinding: the local hash primary forwards to the real Star hash and fmt specialization names the reference type. initial calibration compilation exposed the imported-template specialization namespace conflict; this single harness adaptation repair retained all original function bodies. subsequent calibrations passed, no kernel repair or expectation fitting.

runner verifies original fallback bodies, public header and excluded methods remain unchanged. real String, Unicode, Encode, Directives, lexical, Json and DataStream dependencies come from actual reference core/extern objects and actual headers, never local algorithm stand-ins. the small Wire DataStream subclass supplies in-memory transport only; production stream codecs remain real.

observations: base bytes, optional presence/value, directive raw entries/offsets/lazy operation type, group prefix/string/size, join, directory, legacy filename/extension, set/remove subpath (including explicitly present empty), get/remove/add directives, relative path, embedded/remote classification, stream bytes/consumed position/readback. malformed UTF8 and NUL remain bytes, with full binary-safe exceptions via `printException(e,false)`. exact directive-string lengths 998/999/1000/1001/1024 cross lazy-preload threshold. ordered CPP-only observations are independently compared with Rust so shared candidate dependencies cannot silently normalize both sides.

raw ABI checks compare all metadata before substring clamping with literal anchors and an independent forward scan for every case; this catches the otherwise invisible NPos-versus-clamped-count difference. `/a/b:c?d` intentionally retains `b:c?`; `/a/f.ext:q?d` retains `ext:q?`. exact success-only per-operation deltas, separate-thread zero receipts, null/zero and null/nonzero, alignment, complete input-span overlap, integer/address overflows, transactional invalid outputs and unknown receipt op are checked.

negative controls are executed isolated fixtures: real C++ candidate algorithm mutations, real Rust-selected C++ adapter mutations, clamped raw counts, invalid overflow/overlap success shims, TLS leak and zero-receipt shims, truncated-NUL error formatter, corrupt original/adaptation, selector/archive/output rejection, independent source-binding/observation corruption. paired matching-but-wrong getDirectives implementations pass in-process equality but MUST change the independent stream.

## limitations

finite tests and SHA256 are not universal equivalence proofs. filenameStart==NPos is unreachable for fully readable inputs constrained to len<=PTRDIFF_MAX; no impossible giant allocation or forged readable span is claimed. invalid-pointer probes are rejection-only. no injected Rust panic/OOM or C++ allocation/error-format failure timing, allocator identity, performance, game screenshot, platform beyond this macOS arm64 compiler, filesystem normalization, security-policy, network or user-save claim. production dependency freshness still requires the parent's native build seal. no production changes, commits, Cargo builds, game runs, storage/Steam changes or remote actions performed by this test agent.
