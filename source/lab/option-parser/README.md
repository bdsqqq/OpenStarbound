# option parser native calibration

this lab isolates the eight compiled `OptionParser` definitions before introducing a rust boundary. it does NOT qualify a production port.

```sh
python3 source/lab/option-parser/run.py --output build/option-parser-lab/your-fresh-run
```

then qualify the scalar-only C++ blueprint against the same native observations:

```sh
python3 -B source/lab/option-parser/verify_receipts.py --report build/option-parser-lab/your-fresh-run/report.json --self-test-output build/option-parser-lab/your-fresh-integrity-fixtures
python3 -B source/lab/option-parser/host_run.py --values build/option-parser-lab/your-fresh-run --output build/option-parser-lab/your-fresh-host-run
```

`host_contract.hpp` freezes eight modes, 33 native operations and 24 formatting templates. the blueprint defines the real public members against their unchanged private native records, including const factory instantiations. it is NOT the Rust implementation. no controller callback invokes a whole legacy parser/help handler. the host preserves individual original formatted insertions and native iterator semantics; see [finite evidence and limitations](EVIDENCE.md).

outputs must be fresh, owned, nonsymlink paths. the runner does not rebuild the project, run cargo, launch the game, or delete old outputs. it compiles only standalone fixtures with the existing native reference compiler, sdk flags, vendor libraries, and a private archive of sealed core/extern objects excluding `StarOptionParser.cpp.o`.

the complete originals are frozen at `0a428508`; the reference changes namespace/imports and its include only. `StarString`, collections, variants, exception classes, and `std::ostream` remain native. no private-member access or object-layout mirror is used. the current production cpp is a third independently linked observer, not the expected-output authority.

## why more than a cli golden

- independent literal anchors precede comparison. paired wrong binaries can agree while both violate an anchor.
- output is a complete ordered stream of binary-safe hex fields. switch order, parameter-map iteration, argument order, error order, exception class/message, and help bytes are not sorted away.
- help uses one formatted `std::string` insertion per original call. a real streambuf records `xsputn`, overflow, tied-stream sync, state, exception masks, width/fill/alignment, short-write prefixes, and escaped sentinel exception identity.
- stream callbacks mutate metadata and register positional definitions before the relevant next loop begins. option storage is list-backed, so inserting a new option during the active description loop is also defined and must appear later in that same loop. the first header may show old metadata while usage/descriptions must read newer values. same-parser nested help uses a different stream. iterator-invalidating positional-vector mutations are excluded, not repaired by snapshots.
- requirement mode 3 is tested within the representable 0..3 range of the unfixed enum. arbitrary negative or large values are not manufactured.
- nul/unicode strings and a native invalid-utf8 case pass through `StarString`; no unchecked rust string domain is substituted.

`report.json` binds native inputs, transitive headers, sources, generated mutants, executables, compiler flags, and observations. `receipts.json` is updated after each command so later compile/runtime failure cannot erase previous observations. stderr/stdout and generated sources remain beside each executable. markdown is intentionally outside the runtime binding set.

## limits

observable streambuf writes do not expose internal `format()` entry attempts suppressed by a failed stream. allocation/destruction timing, allocator failure, real oom, universal resource behavior, and cross-platform equivalence are unproved. finite calibration success is not permission to skip the separate host boundary, rust comparison, owned cli startup, or running-game evidence.
