# Compatibility entrypoint: lighting selects its facade, not a second Rust archive.
include_guard(GLOBAL)
include("${CMAKE_CURRENT_LIST_DIR}/Rust.cmake")
add_library(star_rust_lighting ALIAS star_rust_engine_ffi)
add_custom_target(star_rust_lighting_build DEPENDS star_rust_engine_ffi_build)
set(STAR_RUST_LIGHTING_SOURCE "${STAR_RUST_SOURCE}/lighting")
set(STAR_RUST_LIGHTING_TARGET_DIR "${STAR_RUST_TARGET_DIR}")
set(STAR_RUST_LIGHTING_ARCHIVE "${STAR_RUST_ARCHIVE}")
# All consumers of the lighting header must agree on layout and backend.
# Keep this definition out of the neutral module for future non-lighting kernels.
add_compile_definitions(STAR_USE_RUST_LIGHTING)
message(STATUS "Cellular lighting backend: Rust (${STAR_RUST_HOST})")
