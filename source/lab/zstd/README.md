# zstd controller boundary

calibration and selected-production qualification for two persistent streaming controllers and two one-shot controllers. vendor zstd, public types, handle ownership, constructors/destructors and forwarding facades stay native. `EVIDENCE.md` describes native calibration; `CANDIDATE_EVIDENCE.md` binds the Rust/real-game evidence.

byte equality was insufficient to distinguish some completion predicates under the installed codec. the accepted gate therefore checks source-bound native codec/resize traces too, with explicitly controlled fixtures for otherwise unobserved conditions. see `EVIDENCE.md` for accepted artifacts and the exhausted earlier approaches.

## replay

requires the sealed native reference build, its installed vendor dependencies, and `/opt/homebrew/bin/zstd`. all output names must be fresh:

```sh
python3 -B source/lab/zstd/run.py --values-only \
  --output build/zstd-lab/replay-values
python3 -B source/lab/zstd/host_run.py replay-host \
  --identity-manifest build/zstd-lab/replay-values/before.json
python3 -B source/lab/zstd/trace_run.py \
  --values build/zstd-lab/replay-values \
  --output build/zstd-lab/replay-trace
python3 -B source/lab/zstd/verify_receipts.py --self-test \
  --report build/zstd-lab/replay-trace/report.json
```

`--values-only` deliberately cannot qualify a port. bare `run.py` rejects the closed historical output-only experiment. the host report alone also remains insufficient without the independent actual-call trace gate.

for the selected implementation, acquire with `--backend rust`; use `candidate_host_run.py`, `candidate_trace_run.py` and `candidate_controls.py --values <values-dir> --output <fresh-dir>`. these link the canonical aggregate at `build/zstd-rust/target/release/libstar_engine_ffi.a`, not a new codec crate. `candidate_host_run.py` takes a fresh simple output name and `--identity-manifest <values-dir>/before.json`.

replays may pass `--fixture-template <existing-values-dir>/cases.tsv`: every case is independently regenerated and the complete digest compared before a hardlink shares immutable storage. unequal fixtures fail before compilation. identical named stdout artifacts also share storage only after exact decoded SHA256 equality. no expected bytes or independent anchors are substituted.

streaming resize leaves new tail bytes uninitialized. error-state fixtures initialize real backing capacity before shrinking, then check allocation stability and extents before inspecting bytes. unsafe reallocating aliases and full-corpus early-shrink mutants are excluded, not repaired by snapshots or weaker expectations.

large stdout is retained losslessly as gzip; receipt verification checks both stored bytes and decoded bytes. known-corrupt fixtures run in isolated temporary directories. source snapshots keep original whitespace and are byte-gated against the frozen revision; never format them.
