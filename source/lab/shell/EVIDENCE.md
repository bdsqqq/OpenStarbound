# shell parser behavioral oracle

frozen entry revision: `40d9189f941b1b49cd93a72cd98443824998dbc0`.
`freeze.json` binds complete original cpp/hpp; reference changes ONLY namespace/import and include name. `run.py` verifies snapshots directly against git, pins active public/private header and every original fallback/helper body, and pins real String/Unicode/Encode dependencies. no simplified String/Unicode implementation.

## replay

```
python3 source/lab/shell/run.py --output build/shell-lab/cpp-final-r2
python3 source/lab/shell/run.py --output build/shell-lab/rust-final-r2 --define STAR_USE_RUST_SHELL --archive build/shell-rust/target/release/libstar_engine_ffi.a --reference-report build/shell-lab/cpp-final-r2/report.json
```

observed 2026-10-24, apple silicon macOS: BOTH PASS, 17,867 cases each. cpp 162,050 checks/12 negative controls; rust 162,071 checks/14 negative controls/53,679 executing-thread receipts. independent native-only observable digest `8402825b98c9ed85`, matching candidate. digest is finite 64-bit FNV, NOT cryptographic equivalence proof. reports contain exact commands, source/compiler/transitive-header/objects/archive before/after bindings and executable hashes. original source freeze preceded candidate execution.

coverage: both public methods, Word type, exact UTF8 bytes including NUL, parser reuse, 35 independent literal cases, 18^3 grammar concatenations, 12,000 seeded ASCII-domain random inputs. unicode non-ASCII ordinary words/BOM tested separately, never random invalid ctype inputs. literals cover whitespace-only/trailing-empty policy, quotes/adjacency/unmatched quote, all escape switches, unknown/trailing slash, unicode short/empty/rejected consumption, valid pair/lead lookahead/backtrack, invalid pair and isolated trail replacement. compiled StarUnicode.cpp:302 explicitly maps surrogate scalar append to replacement, not empty output.

raw ABI: ordered append/end events, classify-first abort, append abort, token-boundary abort without incrementing completed count, future input mutation, synchronous reentry, final quote, null root context, missing callback/input/output validation with unchanged outputs, invalid calls uncounted, exact top-level/nested receipts and fresh-thread zero receipt. C++ same exception identity and allocation fault timing NOT injected/tested.

negative controls compile isolated actual lexical candidate mutations: whitespace empty-token suppression, unknown escape, unmatched quote, unicode rejected-character backtrack, lead-pair lookahead backtrack. each exits exactly 1 with COMPARISON, never compiler failure or crash. snapshot/adaptation corruption, arbitrary selector/archive/output placement, corrupted independent digest and missing receipt also rejected. no frozen reference/expected tolerance edits to fit Rust.

first calibration caught an incorrect isolated-trail expectation in this lab; corrected by tracing existing compiled encoder replacement policy BEFORE Rust comparison. first ABI run caught lab receipt expectation missing the deliberately nested reentrant call; fixed to expect two calls, not by changing kernel. historical r1 reports are superseded by final-r2.

## limits / handoff

native objects packaged into owned lab archive only; no native rebuild/shared Cargo/game/storage/remote/commits/nested workers. parent MUST bind existing objects to current native build seal; before/after byte seals do not prove source freshness. parent native rebuild/source changes invalidate report bindings; rerun after source freeze. no C++ allocation-fault injection, no exhaustive raw ABI overlap/range/overflow validation, no panic injection, no retained-pointer lifetime sanitizer test, no screenshot/game/performance/other-platform/universal equivalence claim. complete module migration and actual native-consumer behavior remain parent's integration responsibility.
