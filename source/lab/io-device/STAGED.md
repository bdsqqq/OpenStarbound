# staged native fault witness

finite six-case witness accepted through `audit_stage.py`; **not** full IODevice,
ABI, Rust, or game qualification. production cpp/header and all closed runners,
fixtures and expectations remain unchanged.

## why stages are separate

old whole-device simulation and monolithic acquisition each exhausted two
attempts. they stay closed. `stage.py acquire` only compiles and fingerprints;
no generated native probe may execute there. configured archive objects are
validated separately from provenance-input counts, and link maps are parsed as
bytes. five acquisition-manifest corruptions must reject before `execute` can
run a probe. execution and independent acceptance audit have separate receipts.

accepted artifacts:

- `build/io-device-lab/staged-acquire-r2/acquisition.json`: compiler-only seal.
- `build/io-device-lab/staged-execute-r2/report.json`: original/reference/current/
  repeat, plus two normally exiting semantic controls.
- `build/io-device-lab/staged-execute-r2/audit.json`: authoritative acceptance;
  checks full202-input profile, actual113 extracted objects, complete command
  routes, reference namespace, and six well-formed observations per execution.

four positive executions match the source-fixed six-case ledger. after a second
leaf I/O mutates and throws, AABB/abcd and cursor0 remain; pre-mutation failure
retains AA/ab and cursor−2. successful chunked I/O restores cursor6. removing
pointer advancement and restoring on failure both exit normally and are rejected.
these are initialized eight-byte buffers, not uninitialized ByteArray tails.

independent implementation review found three acceptance gaps in the frozen
builder's verifier: malformed control output could count as rejection; archive/
member/dependency/namespace receipts could be omitted; profile object bindings
were not all mandatory. `audit_stage.py` supplements—not silently rewrites—the
frozen builder with those checks. eight isolated in-memory corruptions reject;
these are synthetic integrity evidence, not native semantic controls.

## retained failures

acquisition-r1 resolved clang++ to clang, losing C++ driver mode during object-only
linking. the exact failed source is archived and hash-checked beside its receipts.
r2 preserves cached compiler argv0 while hashing resolved executable bytes; no
reference/algorithm/flags changed. execution-r1 received a relative acquisition
path and failed its pre-execution corruption test before creating native output;
r2 uses the required absolute acquisition path. no failure gets semantic credit.

```sh
python3 -B source/lab/io-device/stage.py verify --report build/io-device-lab/staged-execute-r2/report.json
python3 -B source/lab/io-device/audit_stage.py --report build/io-device-lab/staged-execute-r2/report.json
```

the frozen builder's pass alone is insufficient; use the independent audit.
full callback-stage coverage for all22 definitions is still a separate gate.
