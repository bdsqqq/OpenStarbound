# migration inventory

this is a scope and ownership map for `doc/rust-migration-plan.md`, **not** a count of completed ports. `modules.json` proposes contract-sized boundaries across existing directories; it does not prescribe one crate per directory. exact filename families cover first-party code, with explicit sdk, compatibility and imgui-binding exceptions. an unknown or overlapping classification fails even in write mode.

```sh
sh scripts/migration-inventory.sh --write
sh scripts/migration-inventory.sh --check
sh scripts/migration-inventory.sh --self-test
```

`--check` computes expected bytes without writing or repairing anything. run it directly in validation, never after automatic regeneration. the primary integration agent owns adding that invocation to cmake/ci; this directory does not claim that integration is already wired. `--root /path/to/fixture` supports isolated negative tests.

## inclusion and evidence

- all native headers, sources, inline implementations and existing rust under `source/`, `lib/`, `scripts/` and `attic/`; c/c++ source/header templates too. `.py`/`.sh` under `scripts/`, `attic/` and `source/lab/` are supplemental tooling/harness records.
- filesystem discovery includes untracked, inactive and header-only files. no target membership is **not** proof of dead code. inactive utility disposition is an explicit reviewed filename list; it is not inferred from absence of a target.
- builds, rust `target/`, generated inventory outputs and the inventory implementation directory are excluded before traversal. assets/lua/mod data, prebuilt sdk binaries, downloaded dependencies outside these roots and build-generated source are outside this native migration registry. missing vendored imgui references remain visible as extraction limits, not imaginary file records.
- records carry a file coordinate, classification rule, disposition and direct cmake source/target coordinates. sorted source/config/generator hashes identify the current working-tree inputs without unstable timestamps, absolute machine paths or a commit id that changes when this catalog is committed. regenerate after other agents finish editing those inputs.

## static cmake limits

cmake evidence is a union of **static alternatives**, never an evaluated configuration. the lexer handles comments, quoted/bracket arguments and nested parentheses. extraction follows file-local `set`, aliases, `list(APPEND)`, literal `foreach` values, direct `add_library`/`add_executable`/`target_sources` and relative or source-root paths. condition/loop contexts are retained as lexical text, not boolean claims. `elseif`/`else` contexts describe alternative branches, not simultaneous requirements.

includes, parent-directory variables/conditions, function/macro execution, generator expressions, cache/toolchain values, generated build paths, globs and dynamic loop expressions are not evaluated. file-local variable assignments are conservatively unioned, so overwritten values can appear as alternatives. target-object/link aggregation is deliberately not expanded into transitive source ownership. rust files are registered by filesystem scope, not falsely attributed to a native cmake source list. `configure_file` input declarations and unresolved source expressions are reported separately. these limits require configured build evidence before any retirement decision.

## archived byte codecs

legacy manifests name **raw** sha256 and size, not a compression promise. current
retention readers use `archive_blobs.py` so a later, explicitly admitted lossless
encoding change need not rewrite those manifests or historical receipts. gzip
remains the default archive writer; this reader addition does not admit conversion.

the resolver rejects two encodings for one raw hash rather than choosing a
plausible owner. xz requires crc64 on every stream, bounded decoder memory, and
valid trailing bytes; consumers still check full raw sha256 and size. codec or
byte-reconstruction success never renews archived inode/ctime, source, sdk, tool,
or native-provider origins. the certificate-pinned original lru semantic verifier
is deliberately unchanged; its current byte-retention wrapper handles codecs,
not a replay or replacement of the original verifier.

`plan_xz_blob` / `recode_xz_blob` in the existing cleanup tool preserve the exact
old gzip encoding as a second reconstruction obligation. a verified new xz file
is installed exclusively and directory-synced before the old gzip is unlinked.
interruption can leave two encodings: readers reject that ambiguity; explicit
resume verifies only the admitted names and byte contracts before finishing.
resume checks physical scratch allocation too, but cannot recover a pre-crash
allocation peak or renew the old encoding's live identity. these source APIs need
a separate bounded selected/complement/protected admission before real CAS use.

## exercised failure contract

`--self-test` uses disposable roots and the actual shell entrypoint: byte-identical replay; known match; excluded backup/build/rust-target near-matches; alias and conditional alternatives; loop targets; unknown/ambiguous names; source/body/cmake drift; corrupted and deleted output rejected **without repair**; explicit regeneration restores passing checks. it never alters the live catalog. no native build, runtime, saves or remote services are involved.
