# rust engine boundary

one final static archive owns the rust runtime and unmangled c exports. kernel
crates are rlibs; linking a second kernel must not introduce a second static
archive or allocator/runtime ownership boundary.

- `ffi/`: `star-engine-ffi`, the sole staticlib. forwards the existing lighting
  exports and reexports their actual types instead of copying abi declarations.
- `lighting/`: dependency-free kernel and validation/precision policies; rlib only.
- `Cargo.lock` and release panic/unwind policy belong to this workspace.

`cmake/Rust.cmake` builds the aggregate with an explicit native target and a
per-cmake-build cargo output directory. `RustLighting.cmake` preserves the old
selection/target/variable interface, but aliases the aggregate rather than
building another archive. only the lighting shim defines its backend macro.

```sh
cargo test --manifest-path source/rust/Cargo.toml --workspace --locked --offline
cargo test --manifest-path source/rust/lighting/Cargo.toml --locked --offline
```

use `scripts/lighting-lab.sh` for the numerical/configuration checks and
`scripts/build-behavior-lab.sh` plus the behavior runner for real-game evidence.
workspace tests alone do not establish native linking or gameplay parity.
