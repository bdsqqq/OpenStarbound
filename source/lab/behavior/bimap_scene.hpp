// Included once inside namespace Star. Opt-in ordinary world/Lua consumer;
// no policy model, direct FFI invocation, or changes to non-lab worlds.
namespace {
bool biMapUniqueIdProbe() {
  return BehaviorLab::configuration().getBool("biMapUniqueIdProbe", false);
}
String biMapLampId(unsigned stage) {
  return stage == 1 ? "behavior-bimap-lamp-renamed" : "behavior-bimap-lamp-original";
}
void renameBiMapLamp(WorldServer* server, PlayerPtr const& player, EntityId id, unsigned stage) {
  if (!biMapUniqueIdProbe()) return;
  auto engine = LuaEngine::create();
  auto context = engine->createContext();
  context.setCallbacks("world", LuaBindings::makeWorldCallbacks(server, player.get()));
  context.load("function rename(id, name) world.setUniqueId(id, name) return world.entityUniqueId(id) end");
  auto expected = biMapLampId(stage);
  if (context.invokePath<String>("rename", id, expected) != expected)
    throw StarException("BehaviorLab: ordinary Lua unique-id setter did not update the lamp");
  // EntityMap updates its bidirectional index on the next normal server tick.
  // Never force an extra world update or query that index in the setter call.
}
Json observeBiMapLamp(WorldServer* server, PlayerPtr const& player, EntityId id, unsigned stage) {
  auto engine = LuaEngine::create();
  auto context = engine->createContext();
  context.setCallbacks("world", LuaBindings::makeWorldCallbacks(server, player.get()));
  context.load("function observe(id, expected, other) return {found=world.loadUniqueEntity(expected), missing=world.loadUniqueEntity(other), uniqueId=world.entityUniqueId(id), exists=world.entityExists(id)} end");
  auto expected = biMapLampId(stage), other = biMapLampId(stage == 1 ? 0 : 1);
  uint64_t before = 0, after = 0;
#ifdef STAR_USE_RUST_BIMAP
  before = sb_bimap_count(SB_BIMAP_MODE_PRESENT);
#endif
  auto state = context.invokePath<Json>("observe", id, expected, other);
#ifdef STAR_USE_RUST_BIMAP
  after = sb_bimap_count(SB_BIMAP_MODE_PRESENT);
  if (after - before < 2)
    throw StarException("BehaviorLab: real Lua unique-id lookups did not enter Rust BiMap");
#endif
  if (state.getInt("found") != id || state.getInt("missing") != NullEntityId
      || state.getString("uniqueId") != expected || !state.getBool("exists"))
    throw StarException("BehaviorLab: bidirectional unique-id mapping did not settle/restore");
  return JsonObject{{"schema", 1}, {"expectedUniqueId", expected}, {"otherAbsent", true},
      {"sameLamp", true}, {"lampExists", true}, {"restored", stage == 2},
#ifdef STAR_USE_RUST_BIMAP
      {"backend", "rust"},
#else
      {"backend", "cpp"},
#endif
      {"lookupDispatchDelta", after - before}};
}
}
