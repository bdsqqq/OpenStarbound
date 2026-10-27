# frozen lru auxiliary acquisition

these three python files are the **byte-frozen acquisition inputs**, not a ready-to-rerun pipeline. `acquire.py` defaults to the existing r2 tree and deliberately rejects reuse. do not run it or `test_verify.py` against retained evidence.

r1 stopped at apple nm's unsupported rust bitcode. r2 completed all 36 actual commands, including expected error exits, but its finalizer failed while decoding non-utf-8 link-map symbols. both failures remain failed. no pcm or cli execution was repeated to hide the finalizer failure.

## accepted read-only reconstruction

```sh
python3 -B build/lru-auxiliary-r1/replay/verify.py
```

the separately bound replay adapter reads raw link-map bytes through a bijective latin-1 representation for ASCII syntax and resolves duplicate archive member names by surviving symbols and physical BSD ranlib offsets. it does not change native outputs or expected values. its isolated controls reject seven known corruptions, including coherently rehashed wrong pcm/help and missing process identity. do not rerun its fixture writer against existing control trees.

- report: `build/lru-auxiliary-r1/replay/report.json`
- sha256: `477ab5f111a7ec58e99491428852192702954b246bd0b6a07d72675a0cbc1d35`
- controls: `build/lru-auxiliary-r1/controls-r4/report.json`
- detailed process/tool/source bindings and failure history: `build/lru-auxiliary-r1/HANDOFF.md`

parent independently ran the strict read-only replay successfully. the finite result covers literal 60-byte wav → 16-byte pcm, repeat/seek/eof, 17 rust conversion calls, two corrupt-pcm errors, and 12 exact early-exit client cli cases using production builds frozen at `5074db1a`. it does **not** qualify audible output, mixer/device/ogg, tcp, save/btree compatibility, or the complete lru application gate. those remain separate evidence in the migration plan.

local build evidence is not a published or independently reproducible artifact. preserving these original sources explains the failed acquisitions and authenticates their later read-only reconstruction; silently replacing them with the repaired parser would invalidate that history.
