# One archive owns all Rust C exports and the runtime. Kernel crates are rlibs.
# Isolate by default; callers may share a Cargo cache across compatible native builds.
include_guard(GLOBAL)
find_program(STAR_CARGO_EXECUTABLE cargo REQUIRED)
find_program(STAR_RUSTC_EXECUTABLE rustc REQUIRED)

if(CMAKE_CROSSCOMPILING)
  message(FATAL_ERROR "Rust engine currently supports native builds only; disable all selected Rust backends for cross builds")
endif()
execute_process(COMMAND "${STAR_RUSTC_EXECUTABLE}" -vV
  OUTPUT_VARIABLE STAR_RUST_VERSION RESULT_VARIABLE STAR_RUST_VERSION_RESULT)
if(NOT STAR_RUST_VERSION_RESULT EQUAL 0)
  message(FATAL_ERROR "Cannot query the Rust toolchain")
endif()
string(REGEX MATCH "host: ([^\n\r]+)" _rust_host "${STAR_RUST_VERSION}")
set(STAR_RUST_HOST "${CMAKE_MATCH_1}")
list(LENGTH STAR_ARCHITECTURE STAR_RUST_ARCH_COUNT)
list(LENGTH CMAKE_OSX_ARCHITECTURES STAR_RUST_OSX_ARCH_COUNT)
if(STAR_RUST_ARCH_COUNT GREATER 1 OR STAR_RUST_OSX_ARCH_COUNT GREATER 1)
  message(FATAL_ERROR "Rust engine does not yet support universal/multi-architecture builds; disable all selected Rust backends")
endif()
if(NOT STAR_ARCHITECTURE MATCHES "^(arm64|aarch64|x86_64)$")
  message(FATAL_ERROR "Rust engine supports native arm64 and x86_64 builds only; disable all selected Rust backends")
endif()
if((STAR_ARCHITECTURE STREQUAL "arm64" OR STAR_ARCHITECTURE STREQUAL "aarch64") AND NOT STAR_RUST_HOST MATCHES "^aarch64-")
  message(FATAL_ERROR "Rust host ${STAR_RUST_HOST} does not match ${STAR_ARCHITECTURE}; cross-language architecture mismatch")
elseif(STAR_ARCHITECTURE STREQUAL "x86_64" AND NOT STAR_RUST_HOST MATCHES "^x86_64-")
  message(FATAL_ERROR "Rust host ${STAR_RUST_HOST} does not match x86_64; cross-language architecture mismatch")
endif()

set(STAR_RUST_SOURCE "${PROJECT_SOURCE_DIR}/rust")
set(STAR_RUST_TARGET_DIR "${CMAKE_BINARY_DIR}/rust-engine-ffi" CACHE PATH
  "Cargo target directory for the single Rust engine archive")
if(MSVC)
  set(STAR_RUST_ARCHIVE "${STAR_RUST_TARGET_DIR}/${STAR_RUST_HOST}/release/star_engine_ffi.lib")
else()
  set(STAR_RUST_ARCHIVE "${STAR_RUST_TARGET_DIR}/${STAR_RUST_HOST}/release/libstar_engine_ffi.a")
endif()
file(GLOB_RECURSE STAR_RUST_SOURCES CONFIGURE_DEPENDS
  "${STAR_RUST_SOURCE}/*/src/*.rs" "${STAR_RUST_SOURCE}/*/Cargo.toml")
add_custom_command(
  OUTPUT "${STAR_RUST_ARCHIVE}"
  COMMAND "${CMAKE_COMMAND}" -E env "CARGO_TARGET_DIR=${STAR_RUST_TARGET_DIR}"
    "RUSTC=${STAR_RUSTC_EXECUTABLE}"
    "${STAR_CARGO_EXECUTABLE}" build --manifest-path "${STAR_RUST_SOURCE}/Cargo.toml"
    --package star-engine-ffi --target "${STAR_RUST_HOST}" --release --locked --offline
  DEPENDS ${STAR_RUST_SOURCES}
    "${STAR_RUST_SOURCE}/Cargo.toml" "${STAR_RUST_SOURCE}/Cargo.lock"
  COMMENT "Building Rust engine FFI (${STAR_RUST_HOST})"
  VERBATIM)
add_custom_target(star_rust_engine_ffi_build DEPENDS "${STAR_RUST_ARCHIVE}")
add_library(star_rust_engine_ffi STATIC IMPORTED GLOBAL)
set_target_properties(star_rust_engine_ffi PROPERTIES IMPORTED_LOCATION "${STAR_RUST_ARCHIVE}")
add_dependencies(star_rust_engine_ffi star_rust_engine_ffi_build)
list(APPEND STAR_EXT_LIBS star_rust_engine_ffi)
if(WIN32)
  set_property(TARGET star_rust_engine_ffi APPEND PROPERTY
    INTERFACE_LINK_LIBRARIES userenv bcrypt ntdll)
endif()
message(STATUS "Rust engine archive: ${STAR_RUST_ARCHIVE}")
