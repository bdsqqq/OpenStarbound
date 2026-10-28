# native idmap edge results

`EDGES.md` and its model retain the pre-execution epoch. source/model literals
were fixed before compilation; production headers are unchanged.

report `build/id-map-edges-r1/report.json`, sha256
`3fd3e401855ae642719c65a8d478dd45c2b102bc45955c7b6affae8da2ad0143`.

```sh
python3 -B source/lab/id-map/edge_verify.py --report-sha 3fd3e401855ae642719c65a8d478dd45c2b102bc45955c7b6affae8da2ad0143
```

nine terminal commands pass their declared roles.12 literal cases and6 properties
match twice across ordered/hash maps. a native transactional-scalar-read mutant
fails precisely where partial primitive overwrite differs from the original;
four isolated corruptions are rejected. combined baseline/edge42 hermetic tests
pass; the original baseline certificate still replays without modification.

observations include unchanged cursor after an outer argument-copy throw,
first-wins duplicate stream keys, unvalidated cursor99 then10, little-endian
partial scalar value`0x11220201` before EOF/conversion, printable byte key`'A'`,
and exhaustion caused by out-of-range explicit entries. no behavior was repaired.

this is native characterization under the admitted little-endian release
profile, not Rust/ABI integration, gameplay, full integer-domain equivalence or
full39 completion. no Cargo, production selector, source flag or game changed.
