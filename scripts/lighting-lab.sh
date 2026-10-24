#!/usr/bin/env bash
# Keep the lab on the same compiled archive as the real client. No game assets
# or saves are needed for differential tests; configure the native build first.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build="${1:-$root/build/macos-arm-release}"
if [[ ! -f "$build/CMakeCache.txt" ]]; then
  printf '%s\n' "configure with STAR_USE_RUST_LIGHTING=ON and STAR_BUILD_LIGHTING_LAB=ON first" >&2
  exit 2
fi
python3 "$root/source/lab/lighting/verify_oracle.py" --self-test
cargo fmt --manifest-path "$root/source/rust/lighting/Cargo.toml" --check
CARGO_TARGET_DIR="$build/rust-lighting" cargo test --manifest-path "$root/source/rust/lighting/Cargo.toml" --locked --offline
CARGO_TARGET_DIR="$build/rust-lighting" cargo test --manifest-path "$root/source/rust/lighting/Cargo.toml" --release --locked --offline
cmake --build "$build" --target lighting_lab lighting_lab_fastmath lighting_lab_cpp --parallel "${CMAKE_BUILD_PARALLEL_LEVEL:-8}"
ctest --test-dir "$build" --output-on-failure -R '^lighting_lab'
for mode in lighting_lab lighting_lab_fastmath lighting_lab_cpp; do
  "$root/dist/$mode" --seed "${LIGHTING_LAB_SEED:-1592594996}" --random "${LIGHTING_LAB_RANDOM_CASES:-4096}" --benchmark
done
bash "$root/scripts/lighting-cmake-check.sh"
