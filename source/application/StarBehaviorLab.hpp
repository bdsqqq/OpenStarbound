#pragma once

#include "StarJson.hpp"
#include "StarVector.hpp"

namespace Star {

struct WorldRenderData;
class GuiContext;

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

  // issue-scoped real Root/Lua consumer; caller submits only settled world frames.
  static void prepareLruFrame(WorldRenderData& renderData, unsigned stage);
  static void renderLruLabel(GuiContext& gui);
  static Json lruProof();
  static bool ttlScene();
  static bool ttlReady(unsigned stage);
  static bool ttlFramePrepared(unsigned stage);
  static void prepareTtlFrame(WorldRenderData& renderData, unsigned stage);
  static void renderTtlLabel(GuiContext& gui);
  static Json ttlProof();
  static bool weightedPoolScene();
  static bool weightedPoolFramePrepared(unsigned stage);
  static void prepareWeightedPoolFrame(WorldRenderData& renderData, unsigned stage);
  static void renderWeightedPoolLabel(GuiContext& gui);
  static Json weightedPoolProof();
};

}
