# idmap canonical ABI and Rust policy

The native key stays native: copying it early would change failure ordering,
while moving it into Rust would lose generic key and named-local return rules.
`StarRustIdMap.h` therefore carries only void/bool replies and an opaque frame.
Ten modes, two stages and 22 leaves separate policy from typed full expressions.
The second stage is valid only for next-id and automatic insertion.

## acquired evidence

- `build/id-map-abi-r1/report.json`
- sha256 `397fd26f6391b14f0e46eceb4438d2eae74a0f2177bd739c2bf7841264bd23af`
- fresh C11/C++17 syntax checks; actual existing aggregate **201 debug + 201
  release unit tests**, including 29 IdMap mock tests per profile.
- reader: `python3 -B source/lab/id-map-boundary/verify_policy.py --report-sha <sha>`
- schema drift and reader membership negatives: `python3 -B -m unittest discover
  -s source/lab/id-map-boundary -p 'test_*.py'`.

The exact parent acquisition driver is retained and hashed at
`build/id-map-abi-r1/test.py`. It used an isolated offline Cargo home/target,
explicit selected compiler/linker, fresh source/tool/SDK witnesses and bounded
owned processes. The old game plan selects tool/SDK paths only; it is not renewed.
The report binds every admitted source and all four command plans/receipts/logs.

Before wiring `lib.rs`, its historical bytes were retained. WeightedPool's
source-only manifest is now
`build/weighted-pool-source-epoch-r1/source-versions-id-map-r1.json`, sha256
`80834065a9486db6ed4dede89942a3479676436e7f070ed33b8b46799bca8000`.
WeightedPool, TTL and LRU historical byte-retention replay passed after wiring;
TTL/LRU already retained their older original `lib.rs` epochs. No old source
origin, executable or tool proof was rebound.

## limits / next gate

These are Rust mock-policy executions, **not native IdMap interop, canonical
static-archive/provider, production adoption or gameplay evidence**. The original
production IdMap remains unchanged; no selector was added. Native frames must
still preserve full-before-local-copy, original named locals/NRVO, per-method
lazy constraints, const dispatch, native partial-read mutation, and exceptions
captured/rethrown outside Rust. No key bits, mapped storage or streams cross Rust.

Retained current outputs are proof/counterexamples, not obsolete cleanup
candidates. Module-completion cleanup and all application gates remain pending.
