# native-owned controller blueprint

this is a lab-only c++ prototype, not a rust port or game qualification. production `StarIODevice.cpp/.hpp`, selectors, cargo, cmake and the qualified Buffer game artifacts remain unchanged.

## contract

`host_contract.hpp` exposes 22 source-order modes and 26 scalar callback operations. c++ owns the real IODevice/private atomic, virtual objects, ByteArray/String temporaries, borrowed input views and native exception objects. the controller owns branches, loops, count/index progress and seek/error sequencing. virtual full-I/O callbacks are leaves only where the native source itself dispatches virtually; base dispatch reenters a fresh controller context.

constructor contexts never load an uninitialized destination mode. destructor dispatch is qualified base close. `size` queries pending exception kind and wraps only IOException, including EOF, with the native cause constructor; other failures retain exception identity. no failed absolute operation restores the cursor. single full-I/O calls occur even at length zero; full-absolute loops do not. requested length is not an invented physical buffer capacity. null-plus-zero is defined in c++17; null memory-routine calls are not.

input lifetime matters: a full virtual override can destroy a separately owned input ByteArray after receiving its pointer/count and return without using that view. the source wrapper does not access that object again. `bindParam` prepares its pointer/count and numeric object/storage exclusions once, before dispatch. CAPTURE_INPUT_BYTES activates this saved view once; guards never reread the parameter. native context-owned temporaries and exception slots remain alive. the protocol test exercises destruction in both public write wrappers, and separately exercises finish after input destruction.

native guards reject selected null/alignment/nonwrapping/output-alias, busy, finished, pending, capability, upper-bit and unused-argument errors. they are not arbitrary-pointer validation or an exhaustive protocol automaton. callback state is per context, not per owner. status 3 is c++ prototype foreign-throw containment ONLY; it is not a rust unwind contract.

## staged evidence

compiler-only acquisition precedes pre-execution integrity gates and execution. the current recipe must bind the unchanged 202-input/113-object native profile and audited native calibration. maps exclude the legacy archive IODevice object; all 22 actual member definitions are compiled against the unchanged public header. strict c11 consumer and assertion-active native protocol tests are separate executables. source exercise maps are not instrumented coverage.

```sh
python3 -B source/lab/io-device/host_stage.py acquire --output build/io-device-lab/host-acquire-NEW
python3 -B source/lab/io-device/host_stage.py execute --acquisition /absolute/host-acquire-NEW/acquisition.json --output build/io-device-lab/host-execute-NEW
python3 -B source/lab/io-device/host_stage.py verify --report /absolute/host-execute-NEW/report.json
python3 -B source/lab/io-device/host_controls.py acquire --base /absolute/host-acquire-NEW/acquisition.json --output build/io-device-lab/host-controls-acquire-NEW
python3 -B source/lab/io-device/host_controls.py execute --acquisition /absolute/host-controls-acquire-NEW/acquisition.json --output build/io-device-lab/host-controls-execute-NEW
python3 -B source/lab/io-device/host_controls.py verify --report /absolute/host-controls-execute-NEW/report.json
```

acceptance requires two exact 8,021-row frozen replays, two six-trace replays, c11 and native protocol executions, and three normally exiting controller controls. controls change only EOF-versus-IO selection, pending size wrapping, or zero-length single-call dispatch; the checker permits only the corresponding scoped observation differences. synthetic malformed/truncated/type/state-corrupted controls are rejected separately, not counted as native semantic negatives.

## retained review history

- primary writer: one syntax failure repaired, no scratch runtime failures; frozen worker output retained in `build/io-device-lab/host-prototype-r1`.
- acquisition r1 completed without candidate execution. independent review traced post-dispatch parameter dereferences. its exact three source files are archived under `host-parent-lifetime-r1`; r1 is historical, not current acceptance.
- parent repair 1: save numeric ranges during capture and clear the parameter pointer; destruction tests added. acquisition r2 and execution r1 passed 8,021/6/c11/protocol. second review found pre-capture storage aliases were still accepted by raw ARG. normal controllers capture first, but the documented raw guard was incomplete.
- parent repair 2: prepare the view/exclusions at bind time; add pre-capture storage-alias/no-write regression. acquisition r3 and execution r2 are the final replay paths. earlier r2/r1 evidence and controller-control acquisition r1 are historical after this legitimate source change.

no old 998-case simulator or monolithic ledger retry was performed. no reference, golden, domain, compiler flags, timeouts or tolerances were fitted. no sanitizer, universal allocation/OOM/destructor/performance/platform, rust or application qualification follows from this prototype. see the current migration-plan handoff for final execution status and exact accepted paths.
