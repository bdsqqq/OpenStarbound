# historical game products — exact contract applied

source epochs cannot retire executable products. a separate opt-in
`--retired-products MANIFEST SHA256` contract now conserves exactly the original
reference/candidate `bin/starbound` outputs under the weighted-pool pair.

the default remains strict. the optional manifest must be externally pinned,
physical, verified/pruned, and contain both exact original protected hashes with
bounded reconstruction. originals must be absent: it cannot hide a changed live
executable. current tools, sdk, source epochs, other products, aliases and live
complement stay strict. archived output origins are reported
`UNAVAILABLE_ARCHIVED`; no original execution/qualification is renewed.

77 hermetic tests pass, including12 historical-product cases. the initial
capability checkpoint passed default Weighted/TTL/LRU retention while both games
were live; independent review found no actionable defect. after actual retirement,
default Weighted correctly rejects absent originals; the pinned exact-two option
passes. original limits are reported as historicalClosureLimits, not renewed live
pair claims. no acceptance guard was relaxed.

completion: `build/id-map-protected-products-r1/completion.json`, sha256
`314df955f81c7596c250a4d60fa905900c91fb41ae6114975568bdb1d0105709`.
acquired verifier/test sources were copied before modification; these are
metadata, never producer-tool replacements.

the exact contract was applied at21:44 utc after successor source gates and
native-product accounting: both old binaries reconstructed BEFORE pruning;
1,037 complement/provider files unchanged. manifest sha256
`0410f3f45507c7cd5b1ac7c4ab87b7ab44cddcf8b5ca0e99610f079d4dcaa1aa`.
`CLEANUP.md` records the separate byte-conservation evidence and reservation gate.
no actual new game build or module qualification is inferred.
