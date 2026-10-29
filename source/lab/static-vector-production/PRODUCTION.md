# static vector production wiring and finite qualification

`STAR_USE_RUST_STATIC_VECTOR` defaults to `OFF`. the production header passed the
finite native/configuration gates below at source checkpoint
`b27f66a3742a600e97283c8cb954fcfb3147cb5e`. this is **not** game adoption or module
completion. all 39 migration areas remain open.

## preserved contracts

- one original public class declaration, exception declaration, aliases, default
  arguments, `MaximumSize` and two inline fields remain byte-identical.
- the off branch retains all 41 original definitions verbatim. the on branch
  copies all 41 qualified lab definitions verbatim, including the ten identical
  typed views and the original destructor. dependent initializer-list assignment
  remains uninstantiable; this wiring does not repair that api.
- `StarStaticVectorHost.hpp` is an exact copy of the qualified `frame.hpp`.
  its include is guarded before the public header opens `namespace Star`, since
  the helper defines that namespace itself. off does not include the rust helper
  or abi header through this header.
- production includes no lab files. per-method lambdas, full expressions, named
  locals and exception-pointer handling are copied, not rewritten here.
- cmake adds only an off option, membership in the existing aggregate-enable OR
  gate, and a conditional compile definition. no crate, archive, runtime, linker
  settings or target directory is added. other selectors/defaults are unchanged.
  existing cached 29-selector game roots were not regenerated or rebound.

## source evidence and limits

run from the repository root:

```sh
python3 -B source/lab/static-vector-production/test_source.py
```

this hermetic standard-library suite reads source bytes and the parent's retained
`build/static-vector-production-source-r1/before/*.data` snapshots. those snapshots
are hash-pinned DATA, never executable source/tool/sdk replacements. no compiler,
preprocessor, cmake, cargo or native executable is invoked. the snapshots must
remain available to replay these checks; missing data is a failure, not a fallback.

20 tests pass: ten positive source checks and ten isolated in-memory known-bad
controls. controls alter a field, off body, on body, helper, option default, root
enablement, define guard, include guard, production lab include, or runtime setting.
each must fail its corresponding check with the expected reason. exact reversal of
the three cmake edits checks unchanged surrounding configuration, rather than
assuming a generic count of `if` statements proves a gate is correct.

logs: `build/static-vector-production-source-r1/text-tests-r2.log` is the passing
run. `text-tests-r1.log` preserves an initial test-delimiter failure: the first
split confused the helper include guard with the method branch. the checker now
anchors the method branch to its first template; production bytes did not change
for that repair.

text equality establishes source preservation only, not c++ parsing, evaluated
layout, generic behavior, lazy instantiation, emitted-code identity or runtime
adoption. prior finite lab interop and rust test evidence remains separate; this
pass neither reruns nor renews its archived live-path/provider provenance. the
old lab, rust, abi and native oracles are untouched, including the retained
unexpected guard-fixture failure documented in `doc/rust-migration-plan.md`.

## finite native/configuration evidence

fresh admission `cacc43ce7e145f11bd8e0d239b74f0fd0cd478edffdf305b67107278df3e8161`
retained its original 2026-10-29 06:03–06:38 utc window. all 36 native commands
passed; the last child receipt ended at 06:27:45.632570 utc. the full independent
pure replay passed at 06:48:33. an earlier 120-second replay-wrapper timeout is
retained; no accepted native command was repeated and no admission was renewed.

- two fresh cmake configurations evaluated all **30** exact selectors: default
  off, and only StaticVector on. four real consumer rows had the corresponding
  guarded definition. only on generated the existing single aggregate target;
  neither configuration built a game or another rust archive. manifest install
  was disabled and old game cmake roots were not regenerated.
- six actual public-header programs ran **186 literal cases per backend**:
  151 values/layout observations, 18 traces and 17 mutation/lifetime supplements.
  off/on results matched exactly. a seventh on program checked 25 usable public
  roots, less continuation, 15 denials, one effect and nonstandard exception
  identity. LIST_ASSIGN remains a native compile-negative, not a usable 26th root.
- eight syntax probes passed their expected outcomes: move-only and over-aligned
  positives, and specific no-default-copy and initializer-list-assignment
  negatives, for each backend. normal, unaliased WorldGeometry, WorldClient,
  WorldServer and TilePainter sources parsed with the production on selector.
- dependency checks selected the actual core header and, only on, its core host
  and abi header. no lab adapter was compiled. isolated programs consistently
  renamed the template to prevent old weak Core instantiations masking a failure;
  this is distinct from the normal consumer syntax checks and future game build.
- three off images contained no rust archive/run symbol. four on images used the
  physically sealed existing aggregate
  `b3a5813922b29768a60604e22225704b99375b3c8c98de0b37498809da4fac22`, with unique
  providers, strict emitted-code identity and respectively **84/20/33/40** encoded
  native-to-rust edges. the existing 113 native Core/extern objects and reference
  consumer flag recipes were inputs, **not** a freshly rebuilt game closure.

report: `cf6a2cc6c58bcbb862a3695e98b0696fdb37abc5d3692cb01c5e2e1036d3f3e1`.
provider proof: `274835e1174c3503210a3a078e61f80ee6d6e581854c48d3039944f76bf87196`.
cmake's disabled-PCH/reuse warnings and duplicate png/zstd link warnings remain in
the raw logs; flags were not adjusted to suppress them.

## conservation and remaining application work

all 270 completed scratch entries, including seven images and both configuration
trees, were reconstructed **before** pruning with the existing archiver.
185,569,280 unique allocated bytes were retired; 8,518 protected identities/bytes
and 44,676 outside-selected origins were unchanged. parent post-prune checks also
passed. completion:
`0e8d271ec20bf373197e24f063bddae86359dac1494160639add85100d11ab7b`.

compact report/proof/driver/admission-summary **DATA** remains under
`build/static-vector-production-retention-r1/evidence/`. archive manifest:
`build/migration-evidence-archive/runs/20261029-static-vector-completed-production-scratch-r1/manifest.json`,
sha256 `49481e5c0fae627fb9e3090b73a35130836ff107e26344dd8189b5356927fe49`.
original production live-path/inode/ctime/provider/configuration replay is
**UNAVAILABLE_ARCHIVED**. archived source/reader bytes are not tool, sdk or
executable replacements. these conservation results do not renew older origins.

actual game adoption, the new ordinary tile-rendering scene, old25 regression,
frame/state/audio/save/network/cli gates and final module cleanup remain pending.
additional resource conservation must precede a fresh game admission: the game
root reservation stays 1536 MiB and the live/archive caps stay 4/16 GiB. neither
source equality nor the finite programs establish whole-game equivalence.
