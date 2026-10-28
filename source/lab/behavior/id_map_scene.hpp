// Included once, inside namespace Star, by the opt-in client behavior laboratory.
namespace {
char const* IdMapStat = "behaviorLabIdMap";
char const* IdMapCategoryA = "behaviorLabIdMapA";
char const* IdMapCategoryB = "behaviorLabIdMapB";
struct IdMapStatusConsumer { int stage = -1; Json proof; PlayerPtr player; };
IdMapStatusConsumer& idMapConsumer() { static IdMapStatusConsumer value; return value; }
Json idMapCounters() {
  JsonArray modes;
  for (unsigned mode = 0; mode < 10; ++mode) {
    JsonArray stages;
    for (unsigned stage = 0; stage < 2; ++stage) {
#ifdef STAR_USE_RUST_ID_MAP
      stages.append(strf("{:016x}", sb_idmap_count(mode, stage)));
#else
      stages.append("0000000000000000");
#endif
    }
    modes.append(std::move(stages));
  }
  return modes;
}
}
bool BehaviorLab::idMapScene() { return enabled() && configuration().getString("scenario", "") == "id-map-room"; }
bool BehaviorLab::idMapFramePrepared(unsigned stage) { return idMapConsumer().stage == int(stage); }
void BehaviorLab::restoreIdMapStatus() {
  auto& consumer = idMapConsumer();
  if (!consumer.player) return;
  auto status = consumer.player->statusController();
  status->clearPersistentEffects(IdMapCategoryA);
  status->clearPersistentEffects(IdMapCategoryB);
  lruRequire(status->stat(IdMapStat) == 0, "BehaviorLab: IdMap stat not restored");
  auto categories = status->diskStore().getObject("persistentEffectCategories");
  lruRequire(!categories.contains(IdMapCategoryA) && !categories.contains(IdMapCategoryB), "BehaviorLab: IdMap categories not restored");
  Json restored = JsonObject{{"version", 1}, {"scenario", "id-map-room"}, {"stat", IdMapStat},
      {"value", 0}, {"ownedCategoriesAbsent", true}, {"lastPreparedStage", consumer.stage}};
  consumer.player.reset();
  File::writeFile(restored.repr(2), File::relativeTo(configuration().getString("outputDirectory"), "idmap-restoration.json"));
}
void BehaviorLab::prepareIdMapFrame(WorldRenderData& renderData, unsigned stage, PlayerPtr const& player) {
  lruRequire(idMapScene() && stage < 3 && player && !renderData.isFullbright, "BehaviorLab: invalid IdMap scene");
  auto& consumer = idMapConsumer();
  if (!idMapFramePrepared(stage)) {
    lruRequire(int(stage) == consumer.stage + 1, "BehaviorLab: skipped IdMap stage");
    auto status = player->statusController();
    if (stage == 0) {
      auto categories = status->diskStore().getObject("persistentEffectCategories");
      lruRequire(!consumer.player && !status->statNames().contains(IdMapStat)
          && !categories.contains(IdMapCategoryA) && !categories.contains(IdMapCategoryB), "BehaviorLab: IdMap fixture collision");
      consumer.player = player; // Retain the real controller through cleanup/disconnect.
    } else lruRequire(consumer.player == player, "BehaviorLab: IdMap player identity changed");
    try {
      auto assets = Root::singleton().assets();
      auto engine = LuaEngine::create(); auto context = engine->createContext();
      context.setCallbacks("status", LuaBindings::makeStatusControllerCallbacks(status));
      context.load(*assets->bytes("/behaviorlab/id-map-consumer.lua"), "/behaviorlab/id-map-consumer.lua");
      auto before = idMapCounters();
      Json visual = context.invokePath<Json>("proof", stage);
      auto after = idMapCounters();
#ifdef STAR_USE_RUST_ID_MAP
      char const* backend = "rust";
      unsigned minimum = stage == 0 ? 2 : stage == 2 ? 1 : 0;
      for (unsigned mode : {2u, 4u}) for (unsigned part = 0; part < 2; ++part) {
        auto lo = std::stoull(before.get(mode).getString(part).utf8(), nullptr, 16);
        auto hi = std::stoull(after.get(mode).getString(part).utf8(), nullptr, 16);
        lruRequire(uint64_t(hi - lo) >= minimum, "BehaviorLab: real IdMap allocation minimum missing");
      }
#else
      char const* backend = "native";
#endif
      auto image = assets->image(visual.getString("imagePath")); auto color = visual.getArray("color");
      lruRequire(image->size() == Vec2U(16, 16) && color.size() == 4, "BehaviorLab: IdMap image shape");
      Vec4B expected(color[0].toUInt(), color[1].toUInt(), color[2].toUInt(), color[3].toUInt());
      for (unsigned y = 0; y < 16; ++y) for (unsigned x = 0; x < 16; ++x)
        lruRequire(image->get(x, y) == expected, "BehaviorLab: IdMap status-driven Assets color differs");
      consumer.proof = JsonObject{{"version", 1}, {"backend", backend}, {"selector", "STAR_USE_RUST_ID_MAP"},
          {"scopeThread", "lua-calling-thread"}, {"phase", stage}, {"countersBefore", before}, {"countersAfter", after},
          {"visual", visual}, {"consumer", "normal-status.addPersistentEffects-StatusController-StatCollection-StatSet-IdMap"},
          {"imageConsumer", "normal-Assets-WorldPainter"}, {"labelConsumer", "normal-Font-TextPainter"}, {"configuration", configuration()}};
      consumer.stage = int(stage);
    } catch (...) { restoreIdMapStatus(); throw; }
  }
  auto drawable = Drawable::makeImage(consumer.proof.get("visual").getString("imagePath"), 2.0f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true; renderData.foregroundOverlays.append(std::move(drawable));
}
void BehaviorLab::renderIdMapLabel(GuiContext& gui) {
  lruRequire(idMapScene() && !idMapConsumer().proof.isNull(), "BehaviorLab: missing IdMap label proof");
  gui.clearTextStyle(); gui.setDefaultFont(); gui.setFontSize(8, 1.0f); gui.setFontColor(Vec4B(255,255,255,255));
  gui.setFontMode(FontMode::Normal); gui.setFontProcessingDirectives("");
  gui.renderText(idMapConsumer().proof.get("visual").getString("label"), TextPositioning(Vec2F(gui.windowSize()) * 0.5f + Vec2F(-35,70)));
  gui.clearTextStyle();
}
Json BehaviorLab::idMapProof() { lruRequire(!idMapConsumer().proof.isNull(), "BehaviorLab: missing IdMap proof"); return idMapConsumer().proof; }
