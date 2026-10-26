# iodevice migration lab

current finite Rust-controller checkpoint: **45aaaba9**, default OFF; actual-game qualification remains open.

- [TRACE.md](TRACE.md): accepted independent 8,021-case / 22-definition native calibration.
- [HOST.md](HOST.md): native-owned opaque controller blueprint and retained lifetime/alias reviews.
- [RUST.md](RUST.md): Rust integration, two qualified aggregate artifacts, replay commands and limits.

## closed legacy calibration — historical draft, unaccepted

this section describes the earlier rejected approach, not the current checkpoint. its failed-attempt budget stays closed.

all 22 compiled definitions and the full header are frozen from `c233825b`.
reference adaptation changes only namespace open/close and the cpp header include.
production sources, public header, rust, cmake and selectors were untouched during that attempt.

full calibration exhausted two attempts; do not rerun the same repair approach.
see EVIDENCE.md. no report claims FINITE_NATIVE_CALIBRATION_PASS.

commands used:

```
python3 -B source/lab/io-device/run.py --output build/io-device-lab/oracle-r1 --identity-manifest build/buffer-lab/native-identity-r1/manifest.json
python3 -B source/lab/io-device/run.py --output build/io-device-lab/oracle-r2 --identity-manifest build/buffer-lab/native-identity-r1/manifest.json
python3 -B source/lab/io-device/zero_run.py
```

null plus zero is defined pointer arithmetic under C++17 n4659 expr.add/7:
https://timsong-cpp.github.io/cppwp/n4659/expr.add#7
this does not make null valid for memcpy/memset. zero.cpp uses a real virtual
subclass that records pointer nullness and returns zero without memory routines.
default empty ByteArray write is observed without copying the empty object.
reserved nonnull empty is separately covered. positive I/O is preinitialized and
bounded; failed readBytes temporaries are never inspected after destruction.

`atEnd` operand evaluation order is unspecified in C++17. model.py records the
frozen native Apple clang production profile's observed order; it is not a
universal source contract. size's separate statements retain source order.

no rust, game, allocator/OOM, sanitizer, other-platform or universal equivalence
qualification follows from these finite observations.
