#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The ABI owns no memory. All slices are borrowed only for the call; RGB cells
 * are column-major (x * height + y). Scalar mode uses channel zero. */
typedef struct StarLightingParameters {
  uint32_t spread_passes;
  float spread_max_air;
  float spread_max_obstacle;
  float point_max_air;
  float point_max_obstacle;
  float point_obstacle_boost;
  uint32_t point_additive;
} StarLightingParameters;

typedef struct StarLightingCell {
  float light[3];
  uint32_t obstacle;
} StarLightingCell;

typedef struct StarLightingSpreadLight {
  float position[2];
  float value[3];
} StarLightingSpreadLight;

typedef struct StarLightingPointLight {
  float position[2];
  float value[3];
  float beam;
  float beam_angle;
  float beam_ambience;
  uint32_t as_spread;
} StarLightingPointLight;

/* Returns 0 on success, 1 for invalid arguments, 2 if a Rust panic was caught.
 * channels must be 1 or 3; cells_len must equal width * height. Empty source
 * slices may have null pointers. Inputs must be finite, attenuation distances
 * positive, bounds within a nonempty grid. Obstacle boost may be negative,
 * matching the C++ parameter's reduced-shadowing behavior.
 * No exception or unwind may cross this boundary. */
int32_t star_lighting_calculate(
    uint32_t channels, size_t width, size_t height,
    StarLightingParameters const* parameters,
    StarLightingCell* cells, size_t cells_len,
    StarLightingSpreadLight const* spread_lights, size_t spread_len,
    StarLightingPointLight const* point_lights, size_t point_len,
    size_t x_min, size_t y_min, size_t x_max, size_t y_max);

#ifdef __cplusplus
}
#endif
