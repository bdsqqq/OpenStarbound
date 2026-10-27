# sdk interface witness — current prototype

`sdk_witness.py` is a stdlib-only, read-only SDK interface byte witness. it is not a TAPI parser, architecture resolver, linker input acquisition tool, or native acceptance gate. opaque `.tbd` bytes are bound without claiming their format is valid.

```python
before = capture(requested_root, independently_configured_canonical_root)
# retain before independently, before the future compiler/linker run
verify(before, requested_root, independently_configured_canonical_root)
records = reconcile_consumed(
    before, observed_absolute_paths,
    requested_root=requested_root,
    expected_canonical_root=independently_configured_canonical_root,
)
verify(before, requested_root, independently_configured_canonical_root)
```

all three functions require the independently configured canonical root. reconciliation deliberately extends the proposed two-argument API so an untrusted manifest cannot choose its own anchor. it verifies the complete current snapshot before reconciling paths. the caller must preserve the frozen baseline and bind actual compiler/linker invocations and traces independently; generating a replacement manifest after changing bytes is not verification against the original baseline.

capture inventories every physical regular `.tbd` under the canonical root, both top-level settings files when present, and every SDK symlink without following directory links during enumeration. settings aliases are resolved and their physical bytes bound. symlinks outside the consumed graph remain metadata, including dangling, cyclic, or external links. consumed resolution checks every component, including `Versions/Current` and the configured root alias chain. escaping the SDK and returning is rejected. absolute internal aliases are supported. only the requested root and canonical root are accepted as consumed-path anchors; additional root aliases need explicit configuration in a future integration.

manifest records have exact field sets and types; bool does not count as an integer. relative canonical paths and raw link targets use filesystem strings with surrogateescape. persist with `json.dumps(..., ensure_ascii=True)` for byte-preserving JSON transport. file records bind byte length and sha256. returned consumed records preserve input order and duplicates, and contain requested/canonical/relative paths, digest, size, and every symlink hop. malformed inputs raise `WitnessError`; operating-system read/permission errors may also propagate and must fail the caller's gate.

this is a static witness, not a race-proof filesystem capability: parent-directory replacement and transient edit/revert are not detected reliably. final file opens use `O_NOFOLLOW`, `O_NONBLOCK`, and regular-file checks, but these do not justify a broader race claim. more than 256 symlink hops is explicitly unsupported and rejected. expected canonical roots must have no symlink components. headers, framework implementation binaries, non-interface regular files, linker selection rules, and runtime load behavior are not attested.

## retained validation

run `python3 -B source/lab/path-embed-replay/test_sdk_witness.py`. each run creates fresh retained fixtures under `build/path-embed-sdk-witness-r1`; nothing is cleaned up. final run: 14 tests, 13 pass and one explicit platform skip. the skipped filesystem case encountered APFS `errno 92` for a non-UTF8 filename; the lossless JSON filesystem-byte roundtrip was exercised before that skip. `tests-r1.log` retains the initial failure, `tests-r2.log` the corrected platform classification, and `tests-final.log` the expanded final suite.

controls cover exact membership/digests, root and intermediate aliases, settings, coherent rehash versus an independent frozen baseline, omitted/duplicate/reordered records, file-to-alias replacement, wrong roots and prefix siblings, escapes/cycles/dangling links, unsupported non-interface/nonregular inputs, and strict JSON types. FIFO settings/interface controls fail without blocking.

`build/path-embed-sdk-witness-r1/current-scan-r2/` binds the final tool/test bytes and the current configured macOS 27.0 SDK. it contains identical before/after manifests for 3,683 canonical regular interface files, 8,142 symlinks, and both settings files; 35 historical map path spellings reconcile to 33 current canonical interfaces. inventory was captured before the historical map was read and was not derived from its path list. r1 is retained but binds the earlier tool/test revision.

**historical r3 remains unaccepted.** current hashes cannot recover its missing acquisition-time SDK bindings. no native acquisition, compiler, linker, Cargo, game, production Rust/C++, or shared integration was run or changed by this component. parent integration/review and future expanded invocation/input-trace contracts remain required.
