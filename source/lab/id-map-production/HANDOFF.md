# production integration — blocked before mutation

Actual native/Rust interop is committed at `02a9fa95`; its certificate is
`9f6b9a534b5cad5c7533ced744767831d587d9a37b1b20f181195c71f373310a`.
Production IdMap and `source/CMakeLists.txt` remain byte-identical to entry.

## retained first

`build/id-map-production-r1/retained.json` records exact original source and
acquired verifier snapshots. New source-only manifests:

- WeightedPool: `source-versions-id-map-production-r1.json`,
  `840dc5a6d66ddfd94d865859c48e6571513e5d7caba70edb976ca069a3e187ef`.
- TTL: `source-versions-id-map-production-r1.json`,
  `455ef638526454ee4fc3bcca2181760561467f119e09060c17c9da5b7e0a88c2`;
  31 entries, both original literal IdMap path spellings retained.
- LRU: `manifest-id-map-production-r1.json`,
  `ea792025a1cf1921b731a6eecb0265ed8d0ab4f0f37b3e3bab5ae67567b5e9d2`;
  17 entries. Older original CMake epochs were not replaced with current bytes.

TTL/LRU pre-mutation retention replay passed. WeightedPool failed at
`verify-weighted-pool-retention.py:292`: protected `source/lab/migration/modules.json`
changed when the two IdMap classifier rules were added at `9561bf3a`.
This is a historical source-input guard, not a gameplay/interop regression.

The original inventory bytes were recovered from git and matched against the
externally pinned original auxiliary admission, not guessed. They are retained
as **metadata only**, with no resolver binding or historical-origin renewal:
`build/id-map-production-r1/inventory-blocker.json`.

## permission boundary

The approved WeightedPool resolver currently accepts code only, not JSON.
Continuing requires authorization for an exception limited to the exact
noncompiled first-party inventory path `source/lab/migration/modules.json`.
Do not silently broaden this to arbitrary JSON, scripts, tools, SDKs or products.
Preserve the acquired verifier before changing it; test exact original pins,
copy ownership/layout, rejection of other JSON and unchanged tool/product bans.
Then replay all retention gates before production mutation.

After authorization/gates: promote the qualified inline frames, keep original
OFF bodies/public declarations/three fields, add default-OFF
`STAR_USE_RUST_ID_MAP` in **source/CMakeLists.txt** (not cmake/Rust.cmake), and run
production OFF/ON/native consumer/configuration checks. Application qualification
and mandatory module cleanup remain pending; all 39 modules remain open.
