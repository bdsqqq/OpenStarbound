#!/usr/bin/env bash
# Both executables use the same application and capture instrumentation. Only
# the lighting implementation changes; SDKs are disabled for offline fixtures.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  printf '%s\n' 'this build recipe is verified for native apple silicon only' >&2
  exit 2
fi
export VCPKG_ROOT="${VCPKG_ROOT:-$HOME/.cache/openstarbound-vcpkg}"
if [[ ! -f "$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake" ]]; then
  printf 'missing vcpkg toolchain: %s\n' "$VCPKG_ROOT" >&2
  exit 2
fi
unset SDKROOT DEVELOPER_DIR
export PATH="/usr/bin:/bin:$PATH"
export SDKROOT="$(/usr/bin/xcrun --sdk macosx --show-sdk-path)"
cc="$(/usr/bin/xcrun --find clang)"
cxx="$(/usr/bin/xcrun --find clang++)"
cd "$root/source"
for backend in reference candidate; do
  rust=OFF
  if [[ "$backend" == candidate ]]; then rust=ON; fi
  build="$root/build/behavior/$backend/cmake"
  extra=()
  if [[ -d "$root/build/macos-arm-release/vcpkg_installed" ]]; then
    extra+=("-DVCPKG_INSTALLED_DIR=$root/build/macos-arm-release/vcpkg_installed")
  fi
  # Snapshot before configuration: a successful stale executable is not proof
  # that the current source was compiled. Seal only after this build succeeds.
  provenance="$root/source/lab/behavior/build_provenance.py"
  snapshot="$root/build/behavior/$backend/build-inputs.json"
  python3 "$provenance" begin --source-root "$root" --build-dir "$build" --snapshot "$snapshot"
  cmake --preset macos-arm-release -B "$build" \
    "-DCMAKE_C_COMPILER=$cc" "-DCMAKE_CXX_COMPILER=$cxx" \
    "-DCMAKE_OSX_SYSROOT=$SDKROOT" -DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON \
    -DCMAKE_VERBOSE_MAKEFILE=OFF -DBUILD_TESTING=OFF \
    -DSTAR_ENABLE_STEAM_INTEGRATION=OFF -DSTAR_ENABLE_DISCORD_INTEGRATION=OFF \
    -DSTAR_BUILD_LIGHTING_LAB=OFF "-DSTAR_USE_RUST_LIGHTING=$rust" \
    "-DSTAR_RUNTIME_OUTPUT_DIRECTORY=$root/build/behavior/$backend/bin" "${extra[@]}"
  cmake --build "$build" --target starbound --parallel "${CMAKE_BUILD_PARALLEL_LEVEL:-8}"
  python3 "$provenance" seal --source-root "$root" --snapshot "$snapshot" \
    --binary "$root/build/behavior/$backend/bin/starbound" > /dev/null
done
