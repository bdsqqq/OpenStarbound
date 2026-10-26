# empty fill: defined no-op repair

The coherent diagnostic startup in `build/behavior/byte-array-diagnostic-r1`
records mode14/op15/status2, through Assets → Buffer::takeData → reset(0).
Moving the bytes out leaves null storage and zero size/capacity. The old native
fallback nevertheless called `memset(nullptr, byte, 0)`, outside its valid argument
contract. This is not evidence of equivalence on that undefined domain.

Empty fill now performs no memory operation in BOTH native fallback and native
FFI leaf. Resize still happens first; leaf argument, role and preflight checks
still run. Every nonzero fill retains the original span guard. Rust controller,
archive, public layout/API, legacy 987+14 contracts/digests and expected game
values are unchanged. `span()` is NOT weakened.

`empty_fill.cpp` was frozen before the repair. Default-empty, moved-from,
Buffer take/reuse and one-byte DataStream serialization fail with the old Rust
bridge; reserved-empty is the contrasting passing control. Both repaired
backends pass all five. `empty_fill_leaf.cpp` also checks malformed role/byte/
reserved args and nonempty null/over-capacity rejection without writes.

The attempted old-native UBSan run did NOT discriminate the null-zero call;
its default-empty test exited zero. Retain that failure and do not claim sanitizer
proof. Repaired native instrumented cases pass, but source reasoning and the
old-bridge regression—not nondiscriminating UBSan—establish the repair boundary.

Replay `empty_fill_run.py --cmake <coherent fresh profile> --output <fresh owned
output> --expect post`; native instrumentation is optional `--sanitize`.
Current bound evidence lives under `build/behavior/empty-fill-*` and
`build/byte-array-rust/empty-fill-*`. Historical compiler receipts are untouched;
new independent seals reconstruct the exact fill edits plus pinned earlier
consumer fixtures/build-mode changes. No arbitrary binding exclusions.

The repaired game gets through asset loading and database initialization, then
hits another protocol rejection near title-world startup. Application remains
OPEN. Do not repair another primitive without its own traced contract and tests.
