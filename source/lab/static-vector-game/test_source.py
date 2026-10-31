#!/usr/bin/env python3
"""source contracts only; before bytes are DATA, never compiler inputs."""
import hashlib
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
BEFORE = ROOT / 'build/static-vector-game-source-r1/before'
CLIENT = 'source/client/StarClientApplication.cpp'
WORLD = 'source/game/StarWorldClient.cpp'
TILE = 'source/game/StarTileSectorArray.hpp'
LAB = 'source/application/StarBehaviorLab.hpp'
OBSERVER = 'source/core/StarTileSectorArrayObserver.hpp'
SCENE = 'source/lab/behavior/static_vector_scene.hpp'
BEFORE_HASHES = {
    CLIENT: 'ba3d8d1e23e0376d8d6022ea9ab665415e12ca3648991d7a96d8e9e729913029',
    WORLD: 'b8785564b6caa5536243902c775bda4c11e099fdb89509975fad3b45394696df',
    TILE: '91b9ac00b0791da5e20f481dfd2fcc467c5537eeec6ea14495dbae90fb56acf6',
    LAB: 'fcb8d23877c5e64fb2d1d02b6168df9a610bfcd94ce675f2c70ce650ca41c0d3',
}
PROTECTED = {
    'source/client/StarClientApplication.hpp': '388ed37e6450b0208f709fcec823ce04054f39e4898e6d23ae3ed6836dc75784',
    'source/CMakeLists.txt': 'c90560247c829ba19183cdd26ca88eb3d2f067daade3d2c1d17dfb7411ef42d0',
    'source/core/StarStaticVector.hpp': '21539d9cebc66e22ba78b501235da25ee26c8bd44dcedd619a362c01c78b36f7',
    'source/core/StarStaticVectorHost.hpp': '44ab391179b113f5aa3223fcdf21573eab11c8a93142f27c2d4ee4a7a1eebbbc',
    'source/core/StarRustStaticVector.h': 'e6ed5a1ed2986ec908879cebcb6c190c581a483074c65e3c3fbf4b4b461b41f4',
    'source/rust/ffi/src/static_vector.rs': '80f15789cb41f398c5da7d6de66421ce1a7203a2ca352824cfeaebb39c92cc4d',
    'source/lab/behavior/behavior_lab.py': 'f59670736610be310b6b591b78cc7e4ade2e3c9bfb20b9ba5b6b53eabc05fe32',
    'source/lab/behavior/test_native_scenario_contract.py': '67c8df97ee69a4d6f79c8b8afa934f83192fb5e25f9b09270447397d40653391',
}

def replace(text, old, new='', count=1):
    assert text.count(old) == count, ('unexpected source multiplicity', old)
    return text.replace(old, new)


def project_client(text):
    """remove named opt-in seams, projecting old branches back to before DATA."""
    for seam in (
        "#ifdef STAR_USE_RUST_NET_GROUP\n#include \"StarRustNetGroup.h\"\n#endif\n",
        "#ifdef STAR_USE_RUST_NET_GROUP\n  uint64_t groupMain[SB_NET_GROUP_COUNT], groupAll[SB_NET_GROUP_COUNT], groupLeaves[SB_NET_GROUP_OP_COUNT];\n  for (uint32_t mode = 0; mode != SB_NET_GROUP_COUNT; ++mode) {\n    groupMain[mode] = sb_net_group_count(0, mode);\n    groupAll[mode] = sb_net_group_count(1, mode);\n  }\n  for (uint32_t op = 0; op != SB_NET_GROUP_OP_COUNT; ++op)\n    groupLeaves[op] = sb_net_group_count(2, op);\n  JsonArray groupMainJson, groupAllJson, groupLeafJson;\n  for (uint32_t mode = 0; mode != SB_NET_GROUP_COUNT; ++mode) {\n    groupMainJson.append(groupMain[mode]);\n    groupAllJson.append(groupAll[mode]);\n  }\n  for (uint32_t op = 0; op != SB_NET_GROUP_OP_COUNT; ++op)\n    groupLeafJson.append(groupLeaves[op]);\n  metadata = metadata.set(\"rustNetGroup\", JsonObject{\n      {\"main\", groupMainJson}, {\"allThreads\", groupAllJson}, {\"attemptedLeaves\", groupLeafJson}});\n#endif\n",
        "#ifdef STAR_USE_RUST_NET_FIELD\n#include \"StarRustNetScalar.h\"\n#endif\n",
        "#ifdef STAR_USE_RUST_NET_FIELD\n  uint64_t scalarMain[SB_NET_SCALAR_COUNT], scalarAll[SB_NET_SCALAR_COUNT];\n  for (uint32_t mode = 0; mode != SB_NET_SCALAR_COUNT; ++mode) {\n    scalarMain[mode] = sb_net_scalar_count(0, mode);\n    scalarAll[mode] = sb_net_scalar_count(1, mode);\n  }\n  JsonArray scalarMainJson, scalarAllJson;\n  for (uint32_t mode = 0; mode != SB_NET_SCALAR_COUNT; ++mode) {\n    scalarMainJson.append(scalarMain[mode]);\n    scalarAllJson.append(scalarAll[mode]);\n  }\n  metadata = metadata.set(\"rustNetScalar\", JsonObject{\n      {\"main\", scalarMainJson}, {\"allThreads\", scalarAllJson}});\n#endif\n",
        "#ifdef STAR_USE_RUST_NET_FIELD\n#include \"StarRustNetField.h\"\n#endif\n",
        "#ifdef STAR_USE_RUST_NET_FIELD\n  uint64_t fieldMain[SB_NET_FIELD_COUNT], fieldAll[SB_NET_FIELD_COUNT], fieldLeaves[SB_NET_FIELD_OP_COUNT];\n  for (uint32_t mode = 0; mode != SB_NET_FIELD_COUNT; ++mode) {\n    fieldMain[mode] = sb_net_field_count(0, mode);\n    fieldAll[mode] = sb_net_field_count(1, mode);\n  }\n  for (uint32_t op = 0; op != SB_NET_FIELD_OP_COUNT; ++op)\n    fieldLeaves[op] = sb_net_field_count(2, op);\n  JsonArray fieldMainJson, fieldAllJson, fieldLeafJson;\n  for (uint32_t mode = 0; mode != SB_NET_FIELD_COUNT; ++mode) {\n    fieldMainJson.append(fieldMain[mode]);\n    fieldAllJson.append(fieldAll[mode]);\n  }\n  for (uint32_t op = 0; op != SB_NET_FIELD_OP_COUNT; ++op)\n    fieldLeafJson.append(fieldLeaves[op]);\n  metadata = metadata.set(\"rustNetField\", JsonObject{\n      {\"main\", fieldMainJson}, {\"allThreads\", fieldAllJson}, {\"attemptedLeaves\", fieldLeafJson}});\n#endif\n",
        "#ifdef STAR_USE_RUST_NET_SIGNAL\n#include \"StarRustNetSignal.h\"\n#endif\n",
        "#ifdef STAR_USE_RUST_NET_SIGNAL\n  uint64_t signalMain[SB_NET_SIGNAL_COUNT], signalAll[SB_NET_SIGNAL_COUNT], signalLeaves[SB_NET_SIGNAL_OP_COUNT];\n  for (uint32_t mode = 0; mode != SB_NET_SIGNAL_COUNT; ++mode) {\n    signalMain[mode] = sb_net_signal_count(0, mode);\n    signalAll[mode] = sb_net_signal_count(1, mode);\n  }\n  for (uint32_t op = 0; op != SB_NET_SIGNAL_OP_COUNT; ++op)\n    signalLeaves[op] = sb_net_signal_count(2, op);\n  JsonArray signalMainJson, signalAllJson, signalLeafJson;\n  for (uint32_t mode = 0; mode != SB_NET_SIGNAL_COUNT; ++mode) {\n    signalMainJson.append(signalMain[mode]);\n    signalAllJson.append(signalAll[mode]);\n  }\n  for (uint32_t op = 0; op != SB_NET_SIGNAL_OP_COUNT; ++op)\n    signalLeafJson.append(signalLeaves[op]);\n  metadata = metadata.set(\"rustNetSignal\", JsonObject{\n      {\"main\", signalMainJson}, {\"allThreads\", signalAllJson}, {\"attemptedLeaves\", signalLeafJson}});\n#endif\n",
        "#ifdef STAR_USE_RUST_TIME\n#include \"StarRustTime.h\"\n#endif\n",
        "#ifdef STAR_USE_RUST_TIME\n  uint64_t timeMain[SB_TIME_COUNT], timeAll[SB_TIME_COUNT], timeDomains[SB_TIME_COUNT];\n  for (uint32_t op = 0; op != SB_TIME_COUNT; ++op) {\n    timeMain[op] = sb_time_count(0, op);\n    timeAll[op] = sb_time_count(1, op);\n    timeDomains[op] = sb_time_count(2, op);\n  }\n  JsonArray timeMainJson, timeAllJson, timeDomainJson;\n  for (uint32_t op = 0; op != SB_TIME_COUNT; ++op) {\n    timeMainJson.append(timeMain[op]);\n    timeAllJson.append(timeAll[op]);\n    timeDomainJson.append(timeDomains[op]);\n  }\n  metadata = metadata.set(\"rustTime\", JsonObject{\n      {\"main\", timeMainJson}, {\"allThreads\", timeAllJson}, {\"unsupportedAllThreads\", timeDomainJson}});\n#endif\n",
        "#ifdef STAR_USE_RUST_WORKER_POOL\n#include \"StarRustWorkerPool.h\"\n#endif\n",
        "#ifdef STAR_USE_RUST_WORKER_POOL\n  uint64_t workerMain[SB_WORKER_POOL_COUNT], workerAll[SB_WORKER_POOL_COUNT];\n  uint64_t workerLeaves[SB_WORKER_POOL_OP_COUNT];\n  for (uint32_t mode = 0; mode != SB_WORKER_POOL_COUNT; ++mode) {\n    workerMain[mode] = sb_worker_pool_count(0, mode);\n    workerAll[mode] = sb_worker_pool_count(1, mode);\n  }\n  for (uint32_t op = 0; op != SB_WORKER_POOL_OP_COUNT; ++op)\n    workerLeaves[op] = sb_worker_pool_count(2, op);\n  JsonArray workerMainJson, workerAllJson, workerLeafJson;\n  for (uint32_t mode = 0; mode != SB_WORKER_POOL_COUNT; ++mode) {\n    workerMainJson.append(workerMain[mode]);\n    workerAllJson.append(workerAll[mode]);\n  }\n  for (uint32_t op = 0; op != SB_WORKER_POOL_OP_COUNT; ++op)\n    workerLeafJson.append(workerLeaves[op]);\n  metadata = metadata.set(\"rustWorkerPool\", JsonObject{\n      {\"main\", workerMainJson}, {\"allThreads\", workerAllJson}, {\"leafAllThreads\", workerLeafJson}});\n#endif\n",
        "#ifdef STAR_USE_RUST_PERIODIC\n#include \"StarRustPeriodic.h\"\n#endif\n",
        "#ifdef STAR_USE_RUST_PERIODIC\n  uint64_t periodicCalls[2][SB_PERIODIC_COUNT];\n  for (uint32_t kind = 0; kind != 2; ++kind)\n    for (uint32_t op = 0; op != SB_PERIODIC_COUNT; ++op)\n      periodicCalls[kind][op] = sb_periodic_count(kind, op);\n  JsonArray periodicMain, periodicAll;\n  for (uint32_t op = 0; op != SB_PERIODIC_COUNT; ++op) {\n    periodicMain.append(periodicCalls[0][op]);\n    periodicAll.append(periodicCalls[1][op]);\n  }\n  metadata = metadata.set(\"rustPeriodic\", JsonObject{{\"main\", periodicMain}, {\"allThreads\", periodicAll}});\n#endif\n",
        "#ifdef STAR_USE_RUST_MAP\n#include \"StarRustMap.h\"\n#endif\n",
        "#ifdef STAR_USE_RUST_MAP\n  uint64_t mapMainLoops[SB_MAP_COUNT], mapAllLoops[SB_MAP_COUNT];\n  uint64_t mapMainSelect[SB_MAP_SELECT_COUNT], mapAllSelect[SB_MAP_SELECT_COUNT];\n  for (uint32_t mode = 0; mode != SB_MAP_COUNT; ++mode) {\n    mapMainLoops[mode] = sb_map_count(mode);\n    mapAllLoops[mode] = sb_map_global_count(0, mode);\n  }\n  for (uint32_t mode = 0; mode != SB_MAP_SELECT_COUNT; ++mode) {\n    mapMainSelect[mode] = sb_map_select_count(mode);\n    mapAllSelect[mode] = sb_map_global_count(1, mode);\n  }\n  JsonArray mapLoops, mapSelections, allMapLoops, allMapSelections;\n  for (uint32_t mode = 0; mode != SB_MAP_COUNT; ++mode) {\n    mapLoops.append(mapMainLoops[mode]);\n    allMapLoops.append(mapAllLoops[mode]);\n  }\n  for (uint32_t mode = 0; mode != SB_MAP_SELECT_COUNT; ++mode) {\n    mapSelections.append(mapMainSelect[mode]);\n    allMapSelections.append(mapAllSelect[mode]);\n  }\n  metadata = metadata.set(\"rustMap\", JsonObject{\n      {\"main\", JsonObject{{\"loops\", mapLoops}, {\"selections\", mapSelections}}},\n      {\"allThreads\", JsonObject{{\"loops\", allMapLoops}, {\"selections\", allMapSelections}}}});\n#endif\n",
        '#ifdef STAR_USE_RUST_FLAT_HASH_TABLE\n#include "StarRustFlatHashTable.h"\n#endif\n',
        '#ifdef STAR_USE_RUST_FLAT_HASH_TABLE\n  uint64_t flatHashCalls[2][SB_FLAT_HASH_COUNT];\n  for (uint32_t kind = 0; kind != 2; ++kind)\n    for (uint32_t mode = 0; mode != SB_FLAT_HASH_COUNT; ++mode)\n      flatHashCalls[kind][mode] = sb_flat_hash_count(kind, mode);\n  JsonArray flatHashMain, flatHashAll;\n  for (uint32_t mode = 0; mode != SB_FLAT_HASH_COUNT; ++mode) {\n    flatHashMain.append(flatHashCalls[0][mode]);\n    flatHashAll.append(flatHashCalls[1][mode]);\n  }\n  metadata = metadata.set("rustFlatHashTable", JsonObject{{"main", flatHashMain}, {"allThreads", flatHashAll}});\n#endif\n',
        '#ifdef STAR_USE_RUST_SET\n#include "StarRustSet.h"\n#endif\n',
        '#ifdef STAR_USE_RUST_SET\n  JsonArray setLoops, setSelections, allSetLoops, allSetSelections;\n  for (uint32_t mode = 0; mode != SB_SET_COUNT; ++mode) {\n    setLoops.append(sb_set_count(mode));\n    allSetLoops.append(sb_set_global_count(0, mode));\n  }\n  for (uint32_t mode = 0; mode != SB_SET_SELECT_COUNT; ++mode) {\n    setSelections.append(sb_set_select_count(mode));\n    allSetSelections.append(sb_set_global_count(1, mode));\n  }\n  metadata = metadata.set("rustSetMain", JsonObject{{"loops", setLoops}, {"selections", setSelections}});\n  metadata = metadata.set("rustSetAllThreads", JsonObject{{"loops", allSetLoops}, {"selections", allSetSelections}});\n#endif\n',
        '#ifdef STAR_USE_RUST_ORDERED_SET\n#include "StarRustOrderedSet.h"\n#endif\n',
        '#ifdef STAR_USE_RUST_ORDERED_SET\n  JsonArray orderedSetCalls;\n  for (uint32_t mode = 0; mode != SB_ORDERED_SET_COUNT; ++mode)\n    orderedSetCalls.append(sb_ordered_set_count(mode));\n  metadata = metadata.set("rustOrderedSetCalls", orderedSetCalls);\n  JsonArray orderedSetSelections;\n  for (uint32_t mode = 0; mode != SB_ORDERED_SET_SELECT_COUNT; ++mode)\n    orderedSetSelections.append(sb_ordered_set_select_count(mode));\n  metadata = metadata.set("rustOrderedSetSelections", orderedSetSelections);\n#endif\n',
        '#ifdef STAR_USE_RUST_UUID\n#include "StarRustUuid.h"\n#endif\n',
        '#ifdef STAR_USE_RUST_UUID\n  metadata = metadata.set("rustUuidCalls", JsonArray{sb_uuid_count(0), sb_uuid_count(1), sb_uuid_count(2)});\n#endif\n',
        '#ifdef STAR_USE_RUST_BIMAP\n#include "StarRustBiMap.h"\n#endif\n',
        '#include "../lab/behavior/bimap_scene.hpp"\n',
        '      if (biMapUniqueIdProbe()) lamp->setUniqueId(biMapLampId(0));\n',
        '      renameBiMapLamp(server, player, m_behaviorLightId, m_behaviorStage);\n',
        '''  if (biMapUniqueIdProbe()) {
    Json proof;
    if (!m_universeServer->executeForClient(world->connection(), [&](WorldServer* server, PlayerPtr player) {
      proof = observeBiMapLamp(server, player, m_behaviorLightId, m_behaviorStage);
    })) throw StarException("BehaviorLab: lost BiMap fixture world before observation");
    metadata = metadata.set("biMapProof", proof);
  }
'''):
        text = replace(text, seam)
    text = replace(text,
        '    bool changed = false;\n    m_universeServer->executeForClient(world->connection(), [&](WorldServer* server, PlayerPtr player) {',
        '    bool changed = false;\n    m_universeServer->executeForClient(world->connection(), [&](WorldServer* server, PlayerPtr) {')
    for include in ['#include <functional>\n', '#include <thread>\n', '#include "StarTileSectorArrayObserver.hpp"\n',
                    '#include "../lab/behavior/static_vector_scene.hpp"\n']:
        text = replace(text, include)
    cleanup = ('  if (BehaviorLab::staticVectorScene())\n'
               '    BehaviorLab::restoreStaticVectorScene(m_universeServer.get(), m_universeClient ? m_universeClient->worldClient().get() : nullptr, false);\n')
    for operation in ('update', 'render'):
        guarded = ('catch (...) {\n  try {\n' + ''.join('  ' + line + '\n' for line in cleanup.splitlines())
                   + '  } catch (...) {\n    // Diagnostic cleanup must not replace the original ' + operation + ' failure.\n'
                   + '  }\n  throw;\n}\n\n')
        text = replace(text, guarded)
    text = replace(text, cleanup)
    text = replace(text, '    ' + cleanup.replace('\n    ', '\n        '))
    text = replace(text, 'void ClientApplication::update() try {', 'void ClientApplication::update() {')
    text = replace(text, 'void ClientApplication::render() try {', 'void ClientApplication::render() {')
    text = replace(text, '''      {
        TileSectorArrayObserver::Frame frame(BehaviorLab::staticVectorScene(),
            m_behaviorReady && !BehaviorLab::hasPendingFrame());
        worldClient->render(m_renderData, TilePainter::BorderTileSize);
      }
      if (BehaviorLab::staticVectorScene() && m_behaviorReady
          && !BehaviorLab::hasPendingFrame() && !m_renderData.isFullbright)
        BehaviorLab::prepareStaticVectorFrame(m_renderData, m_behaviorStage, worldClient.get(), m_behaviorMaterial);''',
        '      worldClient->render(m_renderData, TilePainter::BorderTileSize);')
    text = replace(text, '      if (BehaviorLab::staticVectorScene()) BehaviorLab::staticVectorPainterSubmitted();\n')
    text = replace(text, ' && scenario != "static-vector-room"')
    text = replace(text, '''  bool const staticVector = BehaviorLab::staticVectorScene();
  auto fixtureX = [staticVector](int x) { return staticVector ? pmod(x - 64, 128) : x; };
''')
    text = replace(text, 'staticVector ? "behavior-static-vector-room" : ')
    text = replace(text, '''      if (staticVector) {
        server->generateRegion(RectI(0, 0, 40, 66));
        server->generateRegion(RectI(96, 0, 128, 66));
      } else {
        server->generateRegion(RectI(6, 0, 90, 66));
      }''', '      server->generateRegion(RectI(6, 0, 90, 66));')
    text = replace(text, 'fixtureX(x)', 'x', 3)
    text = replace(text, 'fixtureX(52)', '52')
    text = replace(text, 'fixtureX(40)', '40')
    text = replace(text, 'fixtureX(64)', '64')
    text = replace(text, '      if (staticVector) BehaviorLab::restoreStaticVectorScene(m_universeServer.get(), world.get(), true);\n')
    text = replace(text, 'staticVector ? "static-vector-room" : ')
    text = replace(text, '    if (staticVector) staticVectorSceneState().owned = true;\n')
    text = replace(text, ' && !staticVector', '', 2)
    text = replace(text, '        int column = staticVector ? (x == 62 ? 126 : 2) : x;\n')
    text = replace(text, '      int column = staticVector ? (x == 62 ? 126 : 2) : x;\n')
    text = replace(text, 'Vec2I(column, y)', 'Vec2I(x, y)', 2)
    text = replace(text, '''        && (!staticVector || (world->material(Vec2I(24, 48), TileLayer::Foreground) == m_behaviorMaterial
            && world->material(Vec2I(116, 48), TileLayer::Background) == m_behaviorMaterial))
''')
    text = replace(text, '''  if (BehaviorLab::staticVectorScene() && !BehaviorLab::staticVectorFramePrepared(m_behaviorStage))
    return;
''')
    text = replace(text, '''  if (BehaviorLab::staticVectorScene() && lamp->position() != Vec2F(116, 33))
    throw StarException("BehaviorLab: StaticVector lamp replicated at unexpected position");
''')
    text = replace(text, '''  if (BehaviorLab::staticVectorScene()) {
    metadata = metadata.set("staticVectorProof", BehaviorLab::staticVectorProof());
    metadata = metadata.set("scenario", "static-vector-room");
    metadata = metadata.set("changedTileMin", JsonArray{2, 33}).set("changedTileMax", JsonArray{126, 59});
    metadata = metadata.set("changedColumns", JsonArray{126, 2});
    auto observed = world->material(Vec2I(126, 48), TileLayer::Foreground);
    metadata = metadata.set("observedOccluderMaterial", observed);
    metadata = metadata.set("worldState", metadata.get("worldState").set("observedOccluderMaterial", observed));
    BehaviorLab::staticVectorQueued(m_behaviorCapture);
  }
''')
    text = replace(text, '''m_worldPainter->setCameraPosition(m_universeClient->worldClient()->geometry(),
        BehaviorLab::staticVectorScene() ? Vec2F(0, 48) : Vec2F(64, 48));''',
        'm_worldPainter->setCameraPosition(m_universeClient->worldClient()->geometry(), Vec2F(64, 48));')
    return text


def off_projection(text):
    """only the observer's single-feature #ifdef grammar, not a C++ parser."""
    stack = []
    result = []
    for line in text.splitlines():
        if line == '#ifdef STAR_USE_RUST_STATIC_VECTOR':
            stack.append(False)
        elif line == '#else':
            assert stack
            stack[-1] = not stack[-1]
        elif line == '#endif':
            assert stack
            stack.pop()
        elif all(stack):
            result.append(line)
    assert not stack
    return '\n'.join(result)


def validate(files, before):
    tile = replace(files[TILE], '#include "StarTileSectorArrayObserver.hpp"\n')
    tile = replace(tile, '    TileSectorArrayObserver::observe(this, split.rect, split.xOffset);\n')
    tile = replace(tile, '  TileSectorArrayObserver::Split splitProbe(this);\n')
    assert tile == before[TILE], 'original TileSectorArray changed (including collection layout/returns)'
    world = replace(files[WORLD], '#include "StarTileSectorArrayObserver.hpp"\n')
    world = replace(world, '  {\n  TileSectorArrayObserver::Callsite tileProbe(m_tileArray.get(), m_geometry.size(), window, tileRange, bufferTiles);\n')
    world = replace(world, '      renderTile.liquidLevel = floatToByte(clientTile.liquid.level);\n    });\n  }',
                    '      renderTile.liquidLevel = floatToByte(clientTile.liquid.level);\n    });')
    assert world == before[WORLD], 'original WorldClient statements changed'
    assert project_client(files[CLIENT]) == before[CLIENT], 'old scene source projection differs'
    lab = replace(files[LAB], 'class WorldClient;\nclass UniverseServer;\n')
    lab = replace(lab, '''
  static bool staticVectorScene();
  static bool staticVectorFramePrepared(unsigned stage);
  static void prepareStaticVectorFrame(WorldRenderData& renderData, unsigned stage, WorldClient* world, unsigned material);
  static void staticVectorPainterSubmitted();
  static Json staticVectorProof();
  static void staticVectorQueued(String const& name);
  static void restoreStaticVectorScene(UniverseServer* server, WorldClient* world, bool complete);
''', '\n')
    assert lab == before[LAB], 'existing lab declarations changed'
    observer = files[OBSERVER]
    off = off_projection(observer)
    assert 'sb_static_vector_count' not in off and 'StarRustStaticVector.h' not in off
    assert 'out[mode][stage] = 0;' in off
    assert 'inline thread_local State* armed = nullptr;' in observer
    assert '~Frame() noexcept { if (observing) disarm(); }' in observer
    assert 'inline void disarm() noexcept { armed = nullptr; state.callsiteActive = false; }' in observer
    assert 'armed->callsiteActive && armed->array == array' in observer
    assert 'std::array<std::array<uint64_t, 2>, 26>' in observer
    assert 'std::is_trivial<State>::value && std::is_standard_layout<State>::value' in observer
    assert 'snapshot(probe->before)' in observer and 'snapshot(probe->after)' in observer
    for guard in ('Frame', 'Callsite', 'Split'):
        assert guard + '(' + guard + ' const&) = delete;' in observer
        assert guard + '& operator=(' + guard + ' const&) = delete;' in observer
    assert not re.search(r'\b(StaticList|StaticVector|Json|String|vector|malloc|new|Logger)\b', observer)
    scene = files[SCENE]
    for field in ['frameSequence', 'scopeId', 'identityNotParity', 'thread', 'route', 'worldSize', 'clientWindow',
                  'tileRange', 'bufferTiles', 'callsiteCalls', 'splitCalls', 'returnedRects', 'splits', 'xOffset', 'stage',
                  'countersBefore', 'countersAfter', 'samples', 'worldForeground', 'worldBackground',
                  'renderedForeground', 'renderedBackground', 'painterSubmitted', 'configuration', 'backend', 'selector']:
        assert '"' + field + '"' in scene, field
    for contract in ['scene.preparedSequence == TileSectorArrayObserver::state.frameSequence',
                     'scene.queuedSequence == scene.preparedSequence', 'frameCaptured(scene.queuedName)',
                     'TileSectorArrayObserver::disarm();', 'scene.stage == 2',
                     'bool const wasDisarmed = !TileSectorArrayObserver::armed;',
                     'lruRequire(wasDisarmed && world',
                     'if (!complete)\n            writer.setForegroundMaterial',
                     'scene.painterSubmitted = false;', 'scene.painterSubmitted = true;',
                     '&& scene.painterSubmitted && !scene.proof.isNull()',
                     'scene.stage = int(stage);', 'int(stage) == scene.stage + 1',
                     'observed.callsiteCalls == 1', 'observed.splitCalls == 1', 'observed.returnedRects == 2',
                     'pmod(range[0], 128) + width > 128', 'width > 0 && width < 128',
                     'for (auto mode : {0u, 13u, 19u})', '(mode == 0 ? 1u : 2u)',
                     'observed.after[mode][1] == observed.before[mode][1]',
                     'strf("{:016x}", value)', 'data.geometry.pdiff(x, data.tileMinPosition[0])',
                     'data.tiles(index[0], index[1])', 'index[0] < int(data.tiles.size(0))',
                     'for (int x : {126, 2})', 'DungeonGeneratorWorld writer(authority, false)',
                     'authority->material(Vec2I(x, y), TileLayer::Foreground) == EmptyMaterialId',
                     'world->material(Vec2I(x, y), TileLayer::Foreground) == EmptyMaterialId',
                     '"static-vector-restoration.json"', '{"complete", true}']:
        assert contract in scene, contract
    assert scene.count('for (int x : {126, 2})') == 3
    assert not re.search(r'\b(StaticList|StaticVector)\s*<', scene), 'no proxy collection'
    assert 'if (!staticVectorFramePrepared' not in scene, 'must refresh every latest ready render'
    assert files[CLIENT].index('m_worldPainter->render(m_renderData') < files[CLIENT].index('BehaviorLab::staticVectorPainterSubmitted();')


class SourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = {p: (ROOT / p).read_text() for p in [CLIENT, WORLD, TILE, LAB, OBSERVER, SCENE]}
        cls.before = {}
        for path, digest in BEFORE_HASHES.items():
            raw = (BEFORE / (Path(path).name + '.data')).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == digest, 'before DATA identity'
            cls.before[path] = raw.decode()

    def test_source_contract(self):
        validate(self.files, self.before)

    def test_before_manifest_identity(self):
        self.assertEqual(hashlib.sha256((BEFORE.parent / 'before.json').read_bytes()).hexdigest(),
                         '31f3321d144eab0aa467b1accacac99173508378e89f5b1ec95cf9ac3b47f9ae')

    def test_protected_bytes(self):
        spec = importlib.util.spec_from_file_location('_scene26_bimap_cmake_projection',
            ROOT / 'source/lab/static-vector-production/test_source.py')
        production = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(production)
        for path, digest in PROTECTED.items():
            raw = (ROOT / path).read_bytes()
            if path == 'source/CMakeLists.txt':
                # Check the old scene's bytes after ONLY the exact separately
                # tested default-OFF UUID/BiMap integrations, not a renewed epoch.
                raw = production.normalize_current_cmake(raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest, path)

    def test_all_rust_inputs_unchanged(self):
        paths = sorted(p for p in (ROOT / 'source/rust').rglob('*') if p.is_file()
                       and (p.suffix == '.rs' or p.name in ('Cargo.toml', 'Cargo.lock'))
                       and 'target' not in p.parts)
        digest = hashlib.sha256()
        for module in ('bimap.rs', 'uuid.rs', 'ordered_set.rs', 'flat_hash_table.rs', 'map.rs', 'periodic.rs', 'worker_pool.rs', 'time.rs', 'net_signal.rs', 'net_field.rs', 'net_scalar.rs', 'net_group.rs'):
            self.assertIn(ROOT / 'source/rust/ffi/src' / module, paths)
            paths.remove(ROOT / 'source/rust/ffi/src' / module)
        for path in paths:
            raw = path.read_bytes()
            if path == ROOT / 'source/rust/ffi/src/lib.rs':
                # Only the additive BiMap/UUID registrations are outside
                # scene26's historical Rust input contract.
                for line in (b'mod net_group;\n', b'pub use net_group::{sb_net_group_run, sb_net_group_count};\n',
                             b'mod net_scalar;\n', b'pub use net_scalar::{sb_net_scalar_run, sb_net_scalar_count};\n',
                             b'mod net_field;\n', b'pub use net_field::{sb_net_field_run, sb_net_field_count};\n',
                             b'mod net_signal;\n', b'pub use net_signal::{sb_net_signal_run, sb_net_signal_count};\n',
                             b'mod time;\n', b'pub use time::{sb_time_convert, sb_time_count};\n',
                             b'mod worker_pool;\n', b'pub use worker_pool::{sb_worker_pool_count, sb_worker_pool_run};\n',
                             b'mod periodic;\n', b'pub use periodic::{sb_periodic_count, sb_periodic_run, SbPeriodicReply, SbPeriodicState};\n',
                             b'mod map;\n', b'pub use map::{sb_map_count, sb_map_global_count, sb_map_run, sb_map_select, sb_map_select_count};\n',
                             b'mod bimap;\n', b'pub use bimap::{sb_bimap_count, sb_bimap_run, SbBiMapHost, SbBiMapReply, SbBiMapRequest};\n',
                             b'mod flat_hash_table;\n', b'pub use flat_hash_table::{sb_flat_hash_count, sb_flat_hash_run, SbFlatHashReply};\n',
                             b'mod uuid;\n', b'pub use uuid::{sb_uuid_compare, sb_uuid_count, sb_uuid_from_bytes, sb_uuid_hash};\n',
                             b'mod ordered_set;\n', b'pub use ordered_set::{\n    sb_ordered_set_count, sb_ordered_set_run, sb_ordered_set_select, sb_ordered_set_select_count,\n    sb_set_count, sb_set_run, sb_set_select, sb_set_select_count, sb_set_global_count,\n};\n'):
                    self.assertEqual(raw.count(line), 1)
                    raw = raw.replace(line, b'', 1)
            digest.update(path.relative_to(ROOT).as_posix().encode() + b'\0' + hashlib.sha256(raw).digest())
        self.assertEqual(len(paths), 36)
        self.assertEqual(digest.hexdigest(), '22420f69b5e77de166075262c415b51a949d1021e244d61f3a0640c61c8d2dd3')

    def rejects(self, path, old, new):
        validate(self.files, self.before)
        mutated = dict(self.files)
        self.assertIn(old, mutated[path])
        mutated[path] = mutated[path].replace(old, new, 1)
        with self.assertRaises(AssertionError):
            validate(mutated, self.before)

    def test_bad_original_return(self):
        self.rejects(TILE, 'return {SplitRect{rect, xOffset}};', 'return {SplitRect{rect, 0}};')

    def test_bad_collection_field(self):
        self.rejects(TILE, 'class TileSectorArray {', 'class TileSectorArray {\n  int observerField;')

    def test_bad_world_statement(self):
        self.rejects(WORLD, 'renderTile.foreground = clientTile.foreground;', 'renderTile.foreground = 0;')

    def test_bad_old_camera(self):
        self.rejects(CLIENT, 'Vec2F(0, 48) : Vec2F(64, 48)', 'Vec2F(0, 48) : Vec2F(63, 48)')

    def test_bad_unguarded_count(self):
        self.rejects(OBSERVER, 'out[mode][stage] = 0;', 'out[mode][stage] = sb_static_vector_count(mode, stage);')

    def test_bad_wrong_array_scope(self):
        self.rejects(OBSERVER, 'armed->callsiteActive && armed->array == array', 'armed->callsiteActive')

    def test_bad_missing_owned_cleanup(self):
        self.rejects(CLIENT, '    if (staticVector) staticVectorSceneState().owned = true;\n', '')

    def test_bad_missing_authoritative_absence_check(self):
        self.rejects(SCENE, 'authority->material(Vec2I(x, y), TileLayer::Foreground) == EmptyMaterialId', 'true')

    def test_bad_missing_frame_disarm(self):
        self.rejects(OBSERVER, '~Frame() noexcept { if (observing) disarm(); }', '~Frame() noexcept {}')

    def test_bad_missing_shutdown_cleanup(self):
        self.rejects(CLIENT, 'void ClientApplication::shutdown() {\n  if (BehaviorLab::staticVectorScene())',
                     'void ClientApplication::shutdown() {\n  if (false)')

    def test_bad_missing_restoration_disarm(self):
        self.rejects(SCENE, '  TileSectorArrayObserver::disarm();', '')

    def test_bad_stale_frame(self):
        self.rejects(SCENE, 'scene.preparedSequence == TileSectorArrayObserver::state.frameSequence', 'true')

    def test_bad_fake_tiles(self):
        self.rejects(SCENE, 'data.tiles(index[0], index[1])', 'fakeTiles(index[0], index[1])')

    def test_bad_completion_repairs_instead_of_verifying(self):
        self.rejects(SCENE, 'if (!complete)\n            writer.setForegroundMaterial',
                     'if (true)\n            writer.setForegroundMaterial')

    def test_bad_missing_ack(self):
        self.rejects(SCENE, 'frameCaptured(scene.queuedName)', 'true')

    def test_bad_range_copy_threshold(self):
        self.rejects(SCENE, 'for (auto mode : {0u, 13u, 19u})', 'for (auto mode : {0u, 3u, 19u})')

    def test_bad_cleanup_can_mask_original_failure(self):
        self.rejects(CLIENT, '    // Diagnostic cleanup must not replace the original update failure.\n  }',
                     '    // Diagnostic cleanup must not replace the original update failure.\n    throw;\n  }')

    def test_bad_copyable_scope(self):
        self.rejects(OBSERVER, '  Split(Split const&) = delete;\n', '')

    def test_bad_missing_post_painter_association(self):
        self.rejects(CLIENT, '      if (BehaviorLab::staticVectorScene()) BehaviorLab::staticVectorPainterSubmitted();\n', '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
