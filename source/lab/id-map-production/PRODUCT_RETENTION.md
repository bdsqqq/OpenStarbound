# historical game products — capability only

source epochs cannot retire executable products. a separate opt-in
`--retired-products MANIFEST SHA256` contract now conserves exactly the original
reference/candidate `bin/starbound` outputs under the weighted-pool pair.

the default remains strict. the optional manifest must be externally pinned,
physical, verified/pruned, and contain both exact original protected hashes with
bounded reconstruction. originals must be absent: it cannot hide a changed live
executable. current tools, sdk, source epochs, other products, aliases and live
complement stay strict. archived output origins are reported
`UNAVAILABLE_ARCHIVED`; no original execution/qualification is renewed.

77 hermetic tests pass, including 12 new historical-product cases. actual
weighted/ttl/lru default retention and prior cache conservation still pass.
read-only independent review found no actionable defect.

completion: `build/id-map-protected-products-r1/completion.json`, sha256
`314df955f81c7596c250a4d60fa905900c91fb41ae6114975568bdb1d0105709`.
acquired verifier/test sources were copied before modification; these are
metadata, never producer-tool replacements.

**neither game binary was pruned.** keep the sole pair until successor harness,
remaining artifact accounting and the unchanged 1536mib reservation are ready.
actual retirement still requires the existing archiver's complete reconstruction
before pruning, exact selection/live-complement checks and post-prune audit.
