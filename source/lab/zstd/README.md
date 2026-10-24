# zstd controller boundary

native-only calibration for two persistent streaming controllers and two one-shot controllers. vendor zstd, public types, handle ownership, constructors/destructors and forwarding facades stay native. this lab does not itself migrate production code.

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

`--values-only` deliberately cannot qualify a port. bare `run.py` retains the historical output-only experiment; do not restart that exhausted approach. the host report alone also remains insufficient without the independent actual-call trace gate.

streaming resize leaves new tail bytes uninitialized. error-state fixtures initialize real backing capacity before shrinking, then check allocation stability and extents before inspecting bytes. unsafe reallocating aliases and full-corpus early-shrink mutants are excluded, not repaired by snapshots or weaker expectations.

large stdout is retained losslessly as gzip; receipt verification checks both stored bytes and decoded bytes. known-corrupt fixtures run in isolated temporary directories. source snapshots keep original whitespace and are byte-gated against the frozen revision; never format them.
