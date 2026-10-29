// Included once inside namespace Star, after the normal world/writer APIs.
namespace {
struct StaticVectorSceneState {
  int stage = -1;
  uint64_t preparedSequence = 0, queuedSequence = 0;
  bool painterSubmitted = false, owned = false;
  String queuedName;
  Json proof;
};
StaticVectorSceneState& staticVectorSceneState() { static StaticVectorSceneState value; return value; }
Json staticVectorCounters(TileSectorArrayObserver::Counters const& counters) {
  JsonArray modes;
  for (auto const& mode : counters) {
    JsonArray stages;
    for (auto value : mode) stages.append(strf("{:016x}", value));
    modes.append(std::move(stages));
  }
  return modes;
}
template <size_t N> Json staticVectorInts(std::array<int, N> const& values) {
  JsonArray result;
  for (auto value : values) result.append(value);
  return result;
}
}
bool BehaviorLab::staticVectorScene() {
  return enabled() && configuration().getString("scenario", "") == "static-vector-room";
}
bool BehaviorLab::staticVectorFramePrepared(unsigned stage) {
  auto const& scene = staticVectorSceneState();
  return scene.stage == int(stage) && scene.preparedSequence == TileSectorArrayObserver::state.frameSequence
      && scene.painterSubmitted && !scene.proof.isNull();
}
void BehaviorLab::prepareStaticVectorFrame(WorldRenderData& data, unsigned stage, WorldClient* world, unsigned material) {
  auto& scene = staticVectorSceneState();
  auto const& observed = TileSectorArrayObserver::state;
  lruRequire(staticVectorScene() && world && stage < 3 && !data.isFullbright
      && !TileSectorArrayObserver::armed, "BehaviorLab: StaticVector invalid preparation scope");
  lruRequire(int(stage) == scene.stage || int(stage) == scene.stage + 1, "BehaviorLab: StaticVector non-monotonic stage");
  auto const& range = observed.tileRange;
  int width = range[2] - range[0];
  lruRequire(observed.worldSize[0] == 128 && observed.worldSize[1] == 96
      && width > 0 && width < 128 && pmod(range[0], 128) + width > 128
      && range[0] >= -128 && range[2] <= 256
      && observed.callsiteCalls == 1 && observed.splitCalls == 1 && observed.returned
      && observed.returnedRects == 2 && !observed.overflow,
      "BehaviorLab: StaticVector real tile range did not take two-split route");
#ifdef STAR_USE_RUST_STATIC_VECTOR
  char const* backend = "rust";
  // StaticList(initializer_list) default-constructs its base, then append calls
  // push_back -> emplace_back twice. This is NOT the range-copy constructor.
  for (auto mode : {0u, 13u, 19u})
    lruRequire(uint64_t(observed.after[mode][0] - observed.before[mode][0]) == (mode == 0 ? 1u : 2u),
        "BehaviorLab: StaticVector constructor route differs");
  for (unsigned mode = 0; mode < 26; ++mode)
    lruRequire(observed.after[mode][1] == observed.before[mode][1], "BehaviorLab: StaticVector unexpected continuation");
#else
  char const* backend = "native";
#endif
  lruRequire(data.tileMinPosition == Vec2I(range[0], range[1])
      && int(data.tiles.size(0)) == width && int(data.tiles.size(1)) == range[3] - range[1],
      "BehaviorLab: StaticVector render buffer range differs");
  JsonArray samples;
  auto sample = [&](int x, int y, unsigned foreground, unsigned background) {
    Vec2I pos(x, y);
    // Same wrapped mapping used by the real WorldClient predicted-tile path.
    Vec2I index(data.geometry.pdiff(x, data.tileMinPosition[0]), y - data.tileMinPosition[1]);
    lruRequire(index[0] >= 0 && index[1] >= 0 && index[0] < int(data.tiles.size(0))
        && index[1] < int(data.tiles.size(1)), "BehaviorLab: StaticVector sample outside real render tiles");
    auto const& rendered = data.tiles(index[0], index[1]);
    auto fg = world->material(pos, TileLayer::Foreground);
    auto bg = world->material(pos, TileLayer::Background);
    lruRequire(fg == foreground && bg == background && rendered.foreground == fg && rendered.background == bg,
        "BehaviorLab: StaticVector replicated/rendered tile mismatch");
    samples.append(JsonObject{{"world", jsonFromVec2I(pos)}, {"renderIndex", jsonFromVec2I(index)},
        {"worldForeground", fg}, {"worldBackground", bg},
        {"renderedForeground", rendered.foreground}, {"renderedBackground", rendered.background}});
  };
  for (int x : {126, 2}) for (int y = 33; y <= 59; ++y)
    sample(x, y, stage == 1 ? material : unsigned(EmptyMaterialId), material);
  for (int x : {116, 12}) sample(x, 48, EmptyMaterialId, material);
  JsonArray splits;
  for (auto const& split : observed.splits)
    splits.append(JsonObject{{"rect", JsonArray{split[0], split[1], split[2], split[3]}}, {"xOffset", split[4]}});
  scene.proof = JsonObject{{"version", 1}, {"scenario", "static-vector-room"}, {"stage", stage},
      {"backend", backend}, {"selector", "STAR_USE_RUST_STATIC_VECTOR"},
      {"frameSequence", observed.frameSequence}, {"scopeId", observed.scopeId},
      {"identityNotParity", JsonObject{{"array", strf("{}", observed.array)},
          {"thread", strf("{}", std::hash<std::thread::id>{}(std::this_thread::get_id()))}}},
      {"route", "WorldClient::render/tileEachTo/splitRect/StaticList/StaticVector"},
      {"worldSize", staticVectorInts(observed.worldSize)}, {"clientWindow", staticVectorInts(observed.clientWindow)},
      {"tileRange", staticVectorInts(observed.tileRange)}, {"bufferTiles", observed.bufferTiles},
      {"callsiteCalls", observed.callsiteCalls}, {"splitCalls", observed.splitCalls},
      {"returnedRects", observed.returnedRects}, {"splits", std::move(splits)},
      {"countersBefore", staticVectorCounters(observed.before)}, {"countersAfter", staticVectorCounters(observed.after)},
      {"tileMinPosition", jsonFromVec2I(data.tileMinPosition)}, {"samples", std::move(samples)},
      {"occluderColumns", JsonArray{126, 2}}, {"painterSubmitted", false}, {"configuration", configuration()}};
  scene.stage = int(stage);
  scene.preparedSequence = observed.frameSequence;
  scene.painterSubmitted = false;
}
void BehaviorLab::staticVectorPainterSubmitted() {
  auto& scene = staticVectorSceneState();
  if (scene.preparedSequence != TileSectorArrayObserver::state.frameSequence || scene.proof.isNull()) return;
  scene.painterSubmitted = true;
  scene.proof = scene.proof.set("painterSubmitted", true);
}
Json BehaviorLab::staticVectorProof() { return staticVectorSceneState().proof; }
void BehaviorLab::staticVectorQueued(String const& name) {
  auto& scene = staticVectorSceneState();
  lruRequire(staticVectorFramePrepared(scene.stage), "BehaviorLab: StaticVector stale queued proof");
  scene.queuedSequence = scene.preparedSequence;
  scene.queuedName = name;
}
void BehaviorLab::restoreStaticVectorScene(UniverseServer* server, WorldClient* world, bool complete) {
  bool const wasDisarmed = !TileSectorArrayObserver::armed;
  TileSectorArrayObserver::disarm();
  auto& scene = staticVectorSceneState();
  if (complete) {
    lruRequire(wasDisarmed && world && scene.stage == 2 && scene.queuedSequence == scene.preparedSequence
        && scene.queuedSequence != 0 && frameCaptured(scene.queuedName) && !hasPendingFrame(),
        "BehaviorLab: StaticVector missing final capture association");
    for (int x : {126, 2}) for (int y = 33; y <= 59; ++y)
      lruRequire(world->material(Vec2I(x, y), TileLayer::Foreground) == EmptyMaterialId,
          "BehaviorLab: StaticVector replicated occluder not restored");
  }
  bool restored = !scene.owned;
  if (scene.owned && server && world) {
    try {
      server->executeForClient(world->connection(), [&](WorldServer* authority, PlayerPtr) {
        if (authority->worldId() != printWorldId(CustomWorldId("behavior-static-vector-room"))) return;
        DungeonGeneratorWorld writer(authority, false);
        for (int x : {126, 2}) for (int y = 33; y <= 59; ++y) {
          // Completion must verify the acknowledged removal, not repair it.
          if (!complete)
            writer.setForegroundMaterial(Vec2I(x, y), EmptyMaterialId, 0, DefaultMaterialColorVariant);
          lruRequire(authority->material(Vec2I(x, y), TileLayer::Foreground) == EmptyMaterialId,
              "BehaviorLab: StaticVector authoritative restoration failed");
        }
        restored = true;
      });
    } catch (...) {
      // Preserve the original failure during abort; keep ownership for the
      // shutdown retry, and never emit a completion receipt on this path.
      if (complete) throw;
    }
  }
  if (complete) {
    lruRequire(restored && !TileSectorArrayObserver::armed, "BehaviorLab: StaticVector restoration incomplete");
    File::writeFile(Json(JsonObject{{"version", 1}, {"scenario", "static-vector-room"}, {"complete", true},
        {"ownedOccludersAbsent", true}, {"occluderColumns", JsonArray{126, 2}}, {"yRange", JsonArray{33, 59}},
        {"observerDisarmed", true}, {"lastStage", scene.stage},
        {"lastCapturedFrameSequence", scene.queuedSequence}, {"capture", scene.queuedName}}).repr(2),
        File::relativeTo(configuration().getString("outputDirectory"), "static-vector-restoration.json"));
  }
  if (restored) scene.owned = false;
}
