# static vector production wiring — source only

`STAR_USE_RUST_STATIC_VECTOR` defaults to `OFF`. this change exposes the qualified
lab definitions through the production header; it does **not** qualify a production
configuration or mark the module complete. all 39 migration areas remain open.

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

## pending parent qualification

- fresh production cmake configuration: default/off and explicit on, including
  real consumers and the same existing aggregate/provider (no cached-root rewrite);
- actual on/off compile/link/run, layout/alignment and lazy generic constraints,
  including the original negative initializer-list-assignment constraint;
- current same-aggregate emitted-code/counter/exception-edge evidence;
- actual game adoption and frame/state/audio/save/network behavior;
- auxiliary/cli regression gates and final module conservation/cleanup.

no native/configuration/consumer claim follows from these source tests. the parent
owns those admissions, catalog registration of the new core host and any commit.
