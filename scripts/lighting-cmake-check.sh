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
if(PROBE_CROSS)
  set(CMAKE_CROSSCOMPILING TRUE)
endif()
if(PROBE_NEUTRAL)
  include("${STAR_REPOSITORY_SOURCE}/../cmake/Rust.cmake")
  get_directory_property(probe_definitions COMPILE_DEFINITIONS)
  if("STAR_USE_RUST_LIGHTING" IN_LIST probe_definitions)
    message(FATAL_ERROR "neutral Rust module selected lighting")
  endif()
  add_library(star_rust_lighting ALIAS star_rust_engine_ffi)
else()
  include("${STAR_REPOSITORY_SOURCE}/../cmake/RustLighting.cmake")
  get_target_property(legacy_archive star_rust_lighting IMPORTED_LOCATION)
  if(NOT legacy_archive STREQUAL STAR_RUST_ARCHIVE OR
      NOT STAR_RUST_LIGHTING_ARCHIVE STREQUAL STAR_RUST_ARCHIVE)
    message(FATAL_ERROR "legacy archive does not resolve to the aggregate")
  endif()
endif()
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
  uint64_t before = star_lighting_call_count();
  int status = star_lighting_calculate(1, 3, 3, &p, cells, 9, NULL, 0, NULL, 0, 1, 1, 2, 2);
  if (status != 0 || cells[4].light[0] != 1) return 1;
  status = star_lighting_calculate_arm_fast(1, 3, 3, &p, cells, 9, NULL, 0, NULL, 0, 1, 1, 2, 2);
  if (status != 0 || cells[4].light[0] != 1) return 2;
  if (star_lighting_call_count() != before + 2) return 3;
  puts("C ABI invocation (all three exports): ok");
  return 0;
}
C
export CARGO_BUILD_TARGET="$conflicting"
cmake -S "$fixture" -B "$fixture/native" -G Ninja \
  "-DSTAR_REPOSITORY_SOURCE=$root/source" "-DPROBE_ARCH=$arch"
cmake --build "$fixture/native"
"$fixture/native/probe"
if grep -Eq 'libstar_lighting\.a|star_lighting\.lib' "$fixture/native/build.ninja"; then
  printf '%s\n' 'ERROR: obsolete lighting archive is still linked' >&2
  exit 1
fi
cmake -S "$fixture" -B "$fixture/neutral" -G Ninja \
  "-DSTAR_REPOSITORY_SOURCE=$root/source" "-DPROBE_ARCH=$arch" -DPROBE_NEUTRAL=ON
cmake --build "$fixture/neutral"
"$fixture/neutral/probe"
if cmake -S "$fixture" -B "$fixture/universal" -G Ninja \
  "-DSTAR_REPOSITORY_SOURCE=$root/source" '-DPROBE_ARCH=x86_64;arm64' > "$fixture/universal.log" 2>&1; then
  printf '%s\n' 'ERROR: unsupported universal architecture was accepted' >&2
  exit 1
fi
grep -q 'does not yet support universal/multi-architecture' "$fixture/universal.log"
reject_configuration() {
  local name="$1" diagnostic="$2"
  shift 2
  if cmake -S "$fixture" -B "$fixture/$name" -G Ninja \
    "-DSTAR_REPOSITORY_SOURCE=$root/source" "-DPROBE_ARCH=$arch" "$@" \
    > "$fixture/$name.log" 2>&1; then
    printf 'ERROR: unsupported %s configuration was accepted\n' "$name" >&2
    exit 1
  fi
  grep -q "$diagnostic" "$fixture/$name.log"
}
reject_configuration osx-universal 'does not yet support universal/multi-architecture' \
  '-DCMAKE_OSX_ARCHITECTURES=arm64;x86_64'
reject_configuration cross 'supports native builds only' -DPROBE_CROSS=ON
reject_configuration unsupported 'supports native arm64 and x86_64 builds only' -DPROBE_ARCH=mips
case "$arch" in
  arm64) mismatch=x86_64 ;;
  x86_64) mismatch=arm64 ;;
esac
reject_configuration mismatch 'architecture mismatch' "-DPROBE_ARCH=$mismatch"
printf 'aggregate C ABI, cargo-target isolation and platform rejection checks: ok (fixture %s)\n' "$fixture"
