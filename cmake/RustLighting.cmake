# Cargo builds a dependency-free static library; the public C++ facade stays in
# star_base. Keep the target directory in the CMake build, not the source tree.
find_program(STAR_CARGO_EXECUTABLE cargo REQUIRED)
find_program(STAR_RUSTC_EXECUTABLE rustc REQUIRED)

if(CMAKE_CROSSCOMPILING)
  message(FATAL_ERROR "Rust lighting currently supports native builds only; use STAR_USE_RUST_LIGHTING=OFF for cross builds")
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
  message(FATAL_ERROR "Rust lighting does not yet support universal/multi-architecture builds; use STAR_USE_RUST_LIGHTING=OFF")
endif()
if(NOT STAR_ARCHITECTURE MATCHES "^(arm64|aarch64|x86_64)$")
  message(FATAL_ERROR "Rust lighting supports native arm64 and x86_64 builds only; use STAR_USE_RUST_LIGHTING=OFF")
endif()
if((STAR_ARCHITECTURE STREQUAL "arm64" OR STAR_ARCHITECTURE STREQUAL "aarch64") AND NOT STAR_RUST_HOST MATCHES "^aarch64-")
  message(FATAL_ERROR "Rust host ${STAR_RUST_HOST} does not match ${STAR_ARCHITECTURE}; cross-language architecture mismatch")
elseif(STAR_ARCHITECTURE STREQUAL "x86_64" AND NOT STAR_RUST_HOST MATCHES "^x86_64-")
  message(FATAL_ERROR "Rust host ${STAR_RUST_HOST} does not match x86_64; cross-language architecture mismatch")
endif()

set(STAR_RUST_LIGHTING_SOURCE "${PROJECT_SOURCE_DIR}/rust/lighting")
set(STAR_RUST_LIGHTING_TARGET_DIR "${CMAKE_BINARY_DIR}/rust-lighting")
if(MSVC)
  set(STAR_RUST_LIGHTING_ARCHIVE "${STAR_RUST_LIGHTING_TARGET_DIR}/${STAR_RUST_HOST}/release/star_lighting.lib")
else()
  set(STAR_RUST_LIGHTING_ARCHIVE "${STAR_RUST_LIGHTING_TARGET_DIR}/${STAR_RUST_HOST}/release/libstar_lighting.a")
endif()
file(GLOB_RECURSE STAR_RUST_LIGHTING_SOURCES CONFIGURE_DEPENDS "${STAR_RUST_LIGHTING_SOURCE}/src/*.rs")
add_custom_command(
  OUTPUT "${STAR_RUST_LIGHTING_ARCHIVE}"
  COMMAND "${CMAKE_COMMAND}" -E env "CARGO_TARGET_DIR=${STAR_RUST_LIGHTING_TARGET_DIR}"
    "${STAR_CARGO_EXECUTABLE}" build --manifest-path "${STAR_RUST_LIGHTING_SOURCE}/Cargo.toml"
    --target "${STAR_RUST_HOST}" --release --locked --offline
  DEPENDS ${STAR_RUST_LIGHTING_SOURCES}
    "${STAR_RUST_LIGHTING_SOURCE}/Cargo.toml" "${STAR_RUST_LIGHTING_SOURCE}/Cargo.lock"
  COMMENT "Building Rust cellular lighting (${STAR_RUST_HOST})"
  VERBATIM)
add_custom_target(star_rust_lighting_build DEPENDS "${STAR_RUST_LIGHTING_ARCHIVE}")
add_library(star_rust_lighting STATIC IMPORTED GLOBAL)
set_target_properties(star_rust_lighting PROPERTIES IMPORTED_LOCATION "${STAR_RUST_LIGHTING_ARCHIVE}")
add_dependencies(star_rust_lighting star_rust_lighting_build)
# All consumers of the header must agree on the template's layout and backend.
add_compile_definitions(STAR_USE_RUST_LIGHTING)
list(APPEND STAR_EXT_LIBS star_rust_lighting)
if(WIN32)
  list(APPEND STAR_EXT_LIBS userenv bcrypt ntdll)
endif()
message(STATUS "Cellular lighting backend: Rust (${STAR_RUST_HOST})")
