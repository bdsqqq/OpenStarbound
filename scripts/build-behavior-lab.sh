#!/usr/bin/env bash
# Reference and candidates share application/capture instrumentation. Only the
# selected Rust backends change; SDKs are disabled for offline fixtures.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mode="${1:-lighting}"
if [[ $# -gt 1 || ! "$mode" =~ ^(lighting|traversal|combined|encode|encode-combined|sha256|sha256-combined|vlq|vlq-combined|bytes|bytes-combined|unicode|unicode-combined|shell|shell-combined|jsonpath|jsonpath-combined|assetpath|assetpath-combined|random-mwc|random-mwc-combined|jsonpatch|jsonpatch-combined|textscan|textscan-combined)$ ]]; then
  printf '%s\n' 'usage: build-behavior-lab.sh [lighting|traversal|combined|encode|encode-combined|sha256|sha256-combined|vlq|vlq-combined|bytes|bytes-combined|unicode|unicode-combined|shell|shell-combined|jsonpath|jsonpath-combined|assetpath|assetpath-combined|random-mwc|random-mwc-combined|jsonpatch|jsonpatch-combined|textscan|textscan-combined]'  >&2
  exit 2
fi
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
# Nix collection can invalidate cached absolute tool paths between lab runs.
ninja="$(command -v ninja)" || { printf '%s\n' 'missing ninja (run inside the build-tool Nix shell)' >&2; exit 2; }
cd "$root/source"
for backend in reference candidate; do
  rust=OFF
  blocks=OFF
  encode=OFF
  sha256=OFF
  vlq=OFF
  bytes=OFF
  unicode=OFF
  shell=OFF
  jsonpath=OFF
  assetpath=OFF
  random_mwc=OFF
  jsonpatch=OFF
  textscan=OFF
  # All modes share the identical all-C++ reference; candidates stay isolated.
  base="$root/build/behavior"
  if [[ "$backend" == candidate ]]; then
    case "$mode" in
      lighting) rust=ON ;;
      traversal) blocks=ON ;;
      combined) rust=ON; blocks=ON ;;
      encode) encode=ON ;;
      encode-combined) rust=ON; blocks=ON; encode=ON ;;
      sha256) sha256=ON ;;
      sha256-combined) rust=ON; blocks=ON; encode=ON; sha256=ON ;;
      vlq) vlq=ON ;;
      vlq-combined) rust=ON; blocks=ON; encode=ON; sha256=ON; vlq=ON ;;
      bytes) bytes=ON ;;
      bytes-combined) rust=ON; blocks=ON; encode=ON; sha256=ON; vlq=ON; bytes=ON ;;
      unicode) unicode=ON ;;
      unicode-combined) rust=ON; blocks=ON; encode=ON; sha256=ON; vlq=ON; bytes=ON; unicode=ON ;;
      shell) shell=ON ;;
      shell-combined) rust=ON; blocks=ON; encode=ON; sha256=ON; vlq=ON; bytes=ON; unicode=ON; shell=ON ;;
      jsonpath) jsonpath=ON ;;
      jsonpath-combined) rust=ON; blocks=ON; encode=ON; sha256=ON; vlq=ON; bytes=ON; unicode=ON; shell=ON; jsonpath=ON ;;
      assetpath) assetpath=ON ;;
      assetpath-combined) rust=ON; blocks=ON; encode=ON; sha256=ON; vlq=ON; bytes=ON; unicode=ON; shell=ON; jsonpath=ON; assetpath=ON ;;
      random-mwc) random_mwc=ON ;;
      random-mwc-combined) rust=ON; blocks=ON; encode=ON; sha256=ON; vlq=ON; bytes=ON; unicode=ON; shell=ON; jsonpath=ON; assetpath=ON; random_mwc=ON ;;
      jsonpatch) jsonpatch=ON ;;
      jsonpatch-combined) rust=ON; blocks=ON; encode=ON; sha256=ON; vlq=ON; bytes=ON; unicode=ON; shell=ON; jsonpath=ON; assetpath=ON; random_mwc=ON; jsonpatch=ON ;;
      textscan) textscan=ON ;;
      textscan-combined) rust=ON; blocks=ON; encode=ON; sha256=ON; vlq=ON; bytes=ON; unicode=ON; shell=ON; jsonpath=ON; assetpath=ON; random_mwc=ON; jsonpatch=ON; textscan=ON ;;
    esac
    if [[ "$mode" != lighting ]]; then base="$base/$mode"; fi
  fi
  build="$base/$backend/cmake"
  extra=()
  if [[ -d "$root/build/macos-arm-release/vcpkg_installed" ]]; then
    extra+=("-DVCPKG_INSTALLED_DIR=$root/build/macos-arm-release/vcpkg_installed")
  fi
  # Snapshot before configuration: a successful stale executable is not proof
  # that the current source was compiled. Seal only after this build succeeds.
  provenance="$root/source/lab/behavior/build_provenance.py"
  snapshot="$base/$backend/build-inputs.json"
  python3 "$provenance" begin --source-root "$root" --build-dir "$build" --snapshot "$snapshot"
  cmake --preset macos-arm-release -B "$build" \
    "-DCMAKE_C_COMPILER=$cc" "-DCMAKE_CXX_COMPILER=$cxx" "-DCMAKE_MAKE_PROGRAM=$ninja" \
    "-DCMAKE_OSX_SYSROOT=$SDKROOT" -DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON \
    -DCMAKE_VERBOSE_MAKEFILE=OFF -DBUILD_TESTING=OFF \
    -DSTAR_ENABLE_STEAM_INTEGRATION=OFF -DSTAR_ENABLE_DISCORD_INTEGRATION=OFF \
    -DSTAR_BUILD_LIGHTING_LAB=OFF "-DSTAR_USE_RUST_LIGHTING=$rust" \
    "-DSTAR_USE_RUST_BLOCKS_ALONG_LINE=$blocks" \
    "-DSTAR_USE_RUST_LINE_QUERY=OFF" "-DSTAR_USE_RUST_ENCODE=$encode" \
    "-DSTAR_USE_RUST_SHA256=$sha256" "-DSTAR_USE_RUST_VLQ=$vlq" "-DSTAR_USE_RUST_BYTES=$bytes" "-DSTAR_USE_RUST_UNICODE=$unicode" "-DSTAR_USE_RUST_SHELL=$shell" "-DSTAR_USE_RUST_JSON_PATH=$jsonpath" "-DSTAR_USE_RUST_ASSET_PATH=$assetpath" "-DSTAR_USE_RUST_RANDOM_MWC=$random_mwc" "-DSTAR_USE_RUST_JSON_PATCH=$jsonpatch" "-DSTAR_USE_RUST_TEXT_SCAN=$textscan" \
    "-DSTAR_RUNTIME_OUTPUT_DIRECTORY=$base/$backend/bin" "${extra[@]}"
  cmake --build "$build" --target starbound --parallel "${CMAKE_BUILD_PARALLEL_LEVEL:-8}"
  python3 "$provenance" seal --source-root "$root" --snapshot "$snapshot" \
    --binary "$base/$backend/bin/starbound" > /dev/null
done
