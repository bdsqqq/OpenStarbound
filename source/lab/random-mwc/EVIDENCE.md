# random MWC integer-kernel oracle

scope: only seeded `init`, seeded `addEntropy`, and `gen32`. unchanged public façades are exact regressions, not additional rust ports. no global/default/no-argument seeding is called.

## replay

```
python3 source/lab/random-mwc/run.py --output build/random-mwc-lab/cpp-final-r3
python3 source/lab/random-mwc/run.py --output build/random-mwc-lab/rust-final-r3 --define STAR_USE_RUST_RANDOM_MWC --archive build/random-mwc-rust/target/release/libstar_engine_ffi.a --reference-report build/random-mwc-lab/cpp-final-r3/report.json
```

`report.json` binds compiler, commands, dependency-scanned headers, complete lab sources, core sources, existing native objects/libraries, executable, rust archive and observation streams. before/after drift rejects a run. parent must replay both commands after native builds freeze: changing `StarVersion.cpp.o` invalidates the independent reference, never authorizes dropping its binding. native archives here only package existing real objects; no production or cargo builds occur.

complete cpp/hpp are frozen from `98a07508`. only namespace/import/include changes distinguish the reference; fallback and excluded-method bodies remain byte-exact. real String/ByteArray/Time/Mutex/Math implementations and actual headers are linked, not stand-ins.

## evidence contract

nine seeds include zero, maximum u64, high-half-only and multiplier boundary. every tested operation compares all 256 words, carry and index. repeated entropy, index wrap, long runs, reinitialization over old state and copied forks are covered. an independent python recurrence verifies 22,518 complete states per flag mode, including the copy branches. ten existing `random_test.cpp` literals plus its 100,000-draw continuation are fixed anchors.

the byte observer is deliberately target-bound, not a portable C++ reflection mechanism: frozen header, standard-layout, sizeof 1032 and alignof 4 guard the tested macOS arm64 ABI. memcpy reads only initialized semantic bytes at offsets 0..1023, 1024..1027 and 1028. it never reads the three tail padding bytes, mirrors the enclosing object, uses private macros or inspects an uninitialized C++ object.

three independent compiler modes retain production recipe optimization while selecting uncontracted (`-ffp-contract=off`, no fast-math), compiler-default (no fast-math), or original production (`-ffast-math`). exact bits are compared separately per mode for f32/f64, ranged floats, normal distributions, stochastic rounding, signed/unsigned integers, booleans and allocating/nonallocating bytes. ordered SHA256 streams compare separate CPP-only executions with rust executions; different flag modes intentionally have distinct floating-point streams. no tolerance or golden adjustment.

raw ABI probes cover uninitialized init storage, full initialized init/entropy state, arbitrary carry/index next states, all state pair overlaps and state/output overlaps, null, alignment and address-overflow rejection, unchanged memory/counters on invalid calls, exact per-op receipts, internal warmup/entropy draw non-counting, fresh-thread isolation and unknown getter operation. pointer rejection fixtures do not claim those forged addresses are readable.

isolated negative controls execute genuine omitted-warmup, post-index, reversed entropy u64, carry-before-modulo narrowing, and old-array XOR mutations. the latter snapshots state BEFORE any XOR and intentionally uses stale recurrence inputs. adapter seed/output mutations, zero receipt, invalid-success and TLS-leak shims exercise the C++/ABI gates. corrupt state fixtures must fail python verification; corrupt frozen sources, independent digest and source bindings must fail provenance checks. paired matching-but-wrong signed façades pass local equality/state checks but must alter the independent CPP stream. compilation failure is never credited as verifier success.

## limits

finite tests and SHA256 do not prove universal equivalence. raw init uninitialized-storage acceptance is observed; absence of reads still requires source tracing/sanitizers, not merely matching output. no injected rust panic, OOM, allocator-failure timing, secure-RNG, performance, other-platform, game screenshot, user-save or network claim. undefined domains (u64 maximum single-bound denominator zero, signed-range overflow, nonfinite-to-integer conversion) remain excluded and unrepaired. binary-safe errors use `printException(e,false)`; legacy algorithm exception formatting remains unchanged.

initial background CPP calibration was interrupted by the tool's ten-second process timeout; it is not evidence. synchronous calibration and CPP/rust replays passed without production repairs. final report paths above are the acceptance artifacts; parent native freshness seals remain required.
