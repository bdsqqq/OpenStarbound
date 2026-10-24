#!/usr/bin/env bash
# Exercise the build boundary in isolation: inherited Cargo target settings must
# not change the archive CMake links, and unsupported universal builds fail early.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$root/build"
fixture="$(mktemp -d "$root/build/lighting-cmake-check.XXXXXX")"
host="$(rustc -vV | awk '/^host: / {print $2}')"
case "$host" in
  aarch64-*) arch=arm64; conflicting=x86_64-apple-darwin ;;
  x86_64-*) arch=x86_64; conflicting=aarch64-apple-darwin ;;
  *) printf 'unsupported Rust host: %s\n' "$host" >&2; exit 2 ;;
esac
cat > "$fixture/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.23)
project(lighting_cmake_probe LANGUAGES C)
set(PROJECT_SOURCE_DIR "${STAR_REPOSITORY_SOURCE}")
set(STAR_ARCHITECTURE "${PROBE_ARCH}")
include("${STAR_REPOSITORY_SOURCE}/../cmake/RustLighting.cmake")
add_executable(probe main.c)
target_include_directories(probe PRIVATE "${PROJECT_SOURCE_DIR}/base")
target_link_libraries(probe PRIVATE star_rust_lighting)
CMAKE
cat > "$fixture/main.c" <<'C'
#include "StarRustLighting.h"
#include <stdio.h>
_Static_assert(sizeof(StarLightingParameters) == 28, "parameters ABI");
_Static_assert(sizeof(StarLightingCell) == 16, "cell ABI");
_Static_assert(sizeof(StarLightingSpreadLight) == 20, "spread ABI");
_Static_assert(sizeof(StarLightingPointLight) == 36, "point ABI");
int main(void) {
  StarLightingParameters p = {0, 5, 2, 5, 2, 0, 0};
  StarLightingCell cells[9] = {0};
  cells[4].light[0] = 1;
  int status = star_lighting_calculate(1, 3, 3, &p, cells, 9, NULL, 0, NULL, 0, 1, 1, 2, 2);
  if (status != 0 || cells[4].light[0] != 1) return 1;
  puts("C ABI invocation: ok");
  return 0;
}
C
export CARGO_BUILD_TARGET="$conflicting"
cmake -S "$fixture" -B "$fixture/native" -G Ninja \
  "-DSTAR_REPOSITORY_SOURCE=$root/source" "-DPROBE_ARCH=$arch"
cmake --build "$fixture/native"
"$fixture/native/probe"
if cmake -S "$fixture" -B "$fixture/universal" -G Ninja \
  "-DSTAR_REPOSITORY_SOURCE=$root/source" '-DPROBE_ARCH=x86_64;arm64' > "$fixture/universal.log" 2>&1; then
  printf '%s\n' 'ERROR: unsupported universal architecture was accepted' >&2
  exit 1
fi
grep -q 'does not yet support universal/multi-architecture' "$fixture/universal.log"
printf 'cargo-target isolation and universal-build rejection: ok (fixture %s)\n' "$fixture"
