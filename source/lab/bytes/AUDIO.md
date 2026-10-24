# independent production Audio consumer verification

status: VERIFIED execution on apple silicon macOS, 2026-10-24; PCM decoding only.

## state matrix

| input/state | production action | independent assertion |
|---|---|---|
| literal 60-byte mono PCM16 WAV | `Audio(make_shared<Buffer>(ByteArray(...)), "byteslab.wav")` | Python `wave`/`struct` FIRST confirms 1 channel, 8000 Hz, 8 frames and literal PCM |
| constructed decoder | `read(...,10)` | exactly 8 samples: `[-32768,-12345,-1,0,1,12345,32767,0]` |
| exhausted | `read(...,1)`, position/time | 0 read, sample 8, time 0.001 |
| seek sample 3 | read 3 | `[0,1,12345]`, position 6 |
| seek sample 8 | read 3 | 0 read, position 8 |
| same-thread constructor/read scope | byte-operation counters before/after | C++ all zero; Rust `[0,0,0,0,17,0]` |
| deliberately corrupted expected PCM | same executable with extra argument | exit **1**, explicit `COMPARISON pcm/metadata/end/seek/receipt mismatch`; not a crash or compile failure |

Source trace: `source/core/StarAudio.cpp` `readLEType` invokes in-place `fromByteOrder(LittleEndian)` once per numeric field. `parseWav` reads 9 numeric headers and converts 8 PCM16 samples in its non-streaming path. This really exercises Rust even though endian conversion is a no-op on this little-endian host. Seek/read itself subsequently accesses the already-decoded memory; no claim of repeated per-read conversions.

## commands and observed results

```sh
python3 source/lab/bytes/audio_run.py --cmake build/behavior/reference/cmake --backend cpp --output build/bytes-audio/cpp-r2
python3 source/lab/bytes/audio_run.py --cmake build/behavior/bytes/candidate/cmake --backend rust --output build/bytes-audio/rust-r1 --reference-report build/bytes-audio/cpp-r2/report.json
```

Both PASS, including repeatability and the isolated wrong-PCM expectation comparison control. Rust run additionally compares every non-receipt observable against the C++ report. Expected bytes and PCM were never re-encoded using a candidate algorithm; no tolerance or reference changes.

- C++ binary SHA256 `f963cde745334d277473121428475036a9079574cc40be930be5bcda3f6dfcd5`.
- Rust binary SHA256 `470dc45e5c9053b17faed26abbda5bcafe8fd36b6645af4ea3cd779aefeece22`.
- Machine reports: `build/bytes-audio/{cpp-r2,rust-r1}/report.json`.
- Exact commands/compiler recipe, runtime output, negative output: adjacent `compile.log`, `decode.log`, `repeat.log`, `negative-pcm.log`, `archive.log`.
- Source/helper/compiler/object/archive/library bindings: adjacent `before.json`, `after.json`; each matched exactly. Report additionally records generated archive and executable SHA256 before/after execution.

## provenance boundary and limits

The native CMake `star_core` and `star_extern` targets are **OBJECT libraries**, not static archives. This verifier packages their existing compiled objects into an isolated `build/bytes-audio/.../native-core-extern.a`, then links the helper with the exact native compiler flags and starbound link-library recipe. It does not compile production files, invoke a shared build, modify shared artifacts, use a substitute Rust archive, run a game, or touch storage/Steam. The Rust candidate uses exactly CMake's `rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a`; its bytes are bound with all linked static libraries.

**Compiled core built from current source is NOT independently proven by these hashes.** They bind existing native object bytes and current sources before/after verification, not a historical build association. Parent must retain its build source seal to close that claim. This limitation is explicitly included in each report. The helper and all core C++ headers/sources and FFI Rust sources are drift-checked during each run.

No audible playback, audio device, mixer, Ogg, resampling, performance, big-endian host, screenshot, or complete audio-module port claim. PCM decoding is an appropriate nonvisual oracle here; a screenshot would not establish sample correctness.

## parent build association and independent replay

VERIFIED — parent replays `build/bytes-audio/{cpp-primary-r1,rust-primary-r1}/report.json` reproduce every sample/metadata/EOF/seek/receipt assertion and both comparison-negative exits. Binary hashes equal the worker results above. The parent completed its source-bound native reference/bytes builds and verified BOTH sealed manifests immediately before and after the audio replays (`/tmp/openstarbound-bytes-audio-source-{before,after}.log`). Their common canonical source-map SHA256 is `782c6cab57d3436a686ebf6494c6f875caf6b33463d0f1882bfcc31958f1e671`; native build log `/tmp/openstarbound-bytes-native-build-r1.log` records the actual Audio compilation. The helper binds the object files from those same build directories before/after linking. This closes the local stale-build association for these replays, not a hermetic or signed attestation. The original worker reports deliberately retain their narrower provenance statement.

The observed 17 Rust bridge calls include little-endian no-op sample conversions. Loading cost/performance remains unmeasured and is a rollout gate before default enablement; PCM correctness does not prove unchanged timing.

Owned source frozen by the worker: `audio.cpp`, `audio_run.py`, `AUDIO.md` only. No existing laboratory files edited; no commits or nested tasks.
