# path embed production integration — incomplete qualification

base: `80e10b73ae2f464e04f1dd9e96f1a4eb14fa782f`, apple silicon macOS,
`/Users/bdsqqq/www/OpenStarbound`. implementation is uncommitted; no owned process
remains active. parent owns integration, checkpoint and application qualification.

- production implements both logical functions under default-off
  `STAR_USE_RUST_PATH_EMBED`, in the sole existing Rust aggregate. c++ retains
  native codec leaves, allocation, ownership and exceptions after Rust returns.
- public header bytes are unchanged. off projection reconstructs the original
  cpp exactly (`4ac003690deacb5d18e4fed72d990326b02214bd7a84d84998925614cbfbc84d`).
- four Rust tests passed in debug and release; aggregate release build and
  module-only rustfmt check passed. tests exercise all byte values, binary
  literals, rejected spans, TLS/wrap and the panic-containment helper.
- `build/path-embed-rust/compile-smoke-r2/report.json` is a finite compile/raw ABI
  smoke PASS (`a70ba7f82a8e2c6ad524c9675c5a761a4ffba0a9147d7cfc72efa886b9c7d24d`).
  actual production cpp compiled OFF and ON; strict C11 compiled/linked/executed
  twice against the actual aggregate; 26 raw ABI/TLS checks ran twice. no
  coherent Core linkage or production corpus comparison is claimed from this.

## closed attempts and remaining work

full acquisition attempt 1 stopped before compilation because its safety guard
rejected cargo's internal hardlinks. the guard now counts inode references within
the owned tree and rejects external links. attempt 2 stopped before compilation:
`ModuleNotFoundError: No module named 'tomllib'` on the host's Python 3.9.6.
`generation-1` and `generation-2`, their logs and generated inputs remain intact.
this approach's two-attempt budget is CLOSED. `run.py` is an unaccepted draft;
its verification path and declared gate status have never executed.

separate bounded smoke attempt 1 compiled all four translation units but its
symbol assertion used `nm -U`, which suppresses undefined imports. preserved
attempt 2 uses `nm -gC`, and passed. no production source changed between smoke
attempts. both scripts and receipts remain under the owned build directory.

still required: 113 fresh coherent objects per selector, all 357 frozen-oracle
production rows and repeats, native Gzip exact type/message/continuation, normal
wrong-action/wrong-escape/native-bypass rejection, dynamic layout comparison,
complete source/tool/archive-member/SDK/driver input witnesses, independent
report-corruption controls, and parent replay. corruption controls are not yet
implemented in the draft runner. CMake wiring has source and compiler evidence,
not a fresh CMake configuration evaluation. no game build or capture occurred.

old participating Core/CMake/lib source closures are historical after these
changes; no receipt was refreshed, retagged or exempted. original before-copies
and hashes are in `build/path-embed-rust/before-r1/manifest.json`; exact current
hashes, aggregate identity, statuses and next action are in
`build/path-embed-rust/HANDOFF.json`. preserve the existing failed budgets and
artifacts. no commit, push, cleanup, storage or Steam mutation was performed.
