#pragma once

#include "StarJson.hpp"
#include "StarVector.hpp"

namespace Star {

// Test-only process opt-in. No filesystem reads/capture/work in ordinary runs.
// The client queues captures on the main thread; the SDL host fulfills them
// after the final UI composite and before presentation. Requests cannot overlap.
class BehaviorLab {
public:
  // STAR_BEHAVIOR_LAB names a JSON configuration file, with outputDirectory.
  static bool enabled();
  static Json const& configuration();
  static void queueFrame(String const& name, Json metadata);
  static bool frameCaptured(String const& name);
  static bool hasPendingFrame();
  static void captureFrame(Vec2U drawableSize);
};

}
