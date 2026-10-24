#include "StarUtilityLuaBindings.hpp"
#include "StarJsonExtra.hpp"
#include "StarUuid.hpp"
#include "StarRandom.hpp"
#include "StarPerlin.hpp"
#include "StarXXHash.hpp"
#include "StarLogging.hpp"
#include "StarInterpolation.hpp"
#include "StarLuaConverters.hpp"
#include "StarText.hpp"
#include "StarTime.hpp"
#include "StarDataStreamDevices.hpp"
#include "StarBuffer.hpp"
#include "StarPathEmbed.hpp"
#include <array>
#ifdef STAR_USE_RUST_RANDOM_MWC
#include "StarRustRandomMwc.h"
#endif

namespace Star {

namespace {
struct RandomMwcRecorder {
  bool active = false;
  RandomSource* identity = nullptr;
  unsigned phase = 0;
  JsonArray events;
  Json resetDraw;
};
thread_local RandomMwcRecorder RandomMwcLab;
using MwcCounts = std::array<uint64_t, 3>;
MwcCounts mwcCounts() {
  MwcCounts counts{};
#ifdef STAR_USE_RUST_RANDOM_MWC
  for (unsigned op = 0; op != 3; ++op)
    counts[op] = star_random_mwc_call_count(op);
#endif
  return counts;
}
JsonArray mwcDelta(MwcCounts const& before) {
  auto after = mwcCounts();
  return JsonArray{after[0] - before[0], after[1] - before[1], after[2] - before[2]};
}
void mwcRequire(char const* op, RandomSource* source = nullptr, Maybe<uint64_t> seed = {}) {
  static char const* const operations[] = {"construct", "randu32", "randu64", "randu32",
      "addEntropy", "randu32", "randu64", "randb", "init", "randu32"};
  auto& r = RandomMwcLab;
  if (r.phase >= 10 || String(op) != operations[r.phase])
    throw LuaException("BehaviorLab: random MWC operation order mismatch");
  if (r.phase == 0 || r.phase == 4 || r.phase == 8) {
    uint64_t expected = r.phase == 4 ? 27182818 : 31415926;
    if (!seed || *seed != expected)
      throw LuaException("BehaviorLab: random MWC seed mismatch");
  }
  // The constructor's returned value can move/copy into Lua storage. Bind only
  // the first method's actual userdata, and never dereference this saved pointer.
  if (source) {
    if (r.phase == 1)
      r.identity = source;
    else if (source != r.identity)
      throw LuaException("BehaviorLab: random MWC userdata identity mismatch");
  }
}
void mwcRecord(Json row, JsonArray calls) {
  row = row.set("calls", std::move(calls));
  RandomMwcLab.events.append(std::move(row));
  ++RandomMwcLab.phase;
}
template <typename F>
auto mwcDraw(char const* op, RandomSource& source, F draw) -> decltype(draw()) {
  if (!RandomMwcLab.active)
    return draw();
  mwcRequire(op, &source);
  auto before = mwcCounts();
  auto value = draw();
  auto calls = mwcDelta(before);
  Json native;
  if constexpr (std::is_same_v<decltype(value), bool>)
    native = value;
  else
    native = strf("{}", value);
  // Capture receipts before any Json/String allocation can run incidental work.
  Json row = JsonObject{{"op", op}, {"native", native}, {"calls", calls}};
  auto& r = RandomMwcLab;
  if (r.phase == 9)
    r.resetDraw = JsonObject{{"native", native}, {"calls", calls}};
  else
    r.events.append(std::move(row));
  ++r.phase;
  return value;
}
}

void LuaBindings::beginRandomMwcLab() {
  if (RandomMwcLab.active)
    throw LuaException("BehaviorLab: random MWC recorder already armed");
  RandomMwcLab = RandomMwcRecorder{};
  RandomMwcLab.active = true;
}
void LuaBindings::abortRandomMwcLab() {
  RandomMwcLab = RandomMwcRecorder{};
}
Json LuaBindings::finishRandomMwcLab() {
  auto& r = RandomMwcLab;
  if (!r.active || r.phase != 10 || !r.identity)
    throw LuaException("BehaviorLab: incomplete random MWC native proof");
  String backend = "cpp";
#ifdef STAR_USE_RUST_RANDOM_MWC
  backend = "rust";
#endif
  Json proof = JsonObject{{"version", 1}, {"fixture", "random-mwc-v1"}, {"backend", backend},
      {"complete", true}, {"sameUserdata", true}, {"events", r.events}, {"resetDraw", r.resetDraw}};
  abortRandomMwcLab();
  return proof;
}

template <>
struct LuaConverter<RandomSource> : LuaUserDataConverter<RandomSource> {};

template <>
struct LuaUserDataMethods<RandomSource> {
  static LuaMethods<RandomSource> make() {
    LuaMethods<RandomSource> methods;

    methods.registerMethod("init", [](RandomSource& randomSource, Maybe<uint64_t> seed)
      {
        if (!RandomMwcLab.active) { seed ? randomSource.init(*seed) : randomSource.init(); return; }
        mwcRequire("init", &randomSource, seed);
        auto before = mwcCounts();
        randomSource.init(*seed);
        auto calls = mwcDelta(before);
        mwcRecord(JsonObject{{"op", "init"}, {"seed", strf("{}", *seed)}}, std::move(calls));
      });
    methods.registerMethod("addEntropy", [](RandomSource& randomSource, Maybe<uint64_t> seed)
      {
        if (!RandomMwcLab.active) { seed ? randomSource.addEntropy(*seed) : randomSource.addEntropy(); return; }
        mwcRequire("addEntropy", &randomSource, seed);
        auto before = mwcCounts();
        randomSource.addEntropy(*seed);
        auto calls = mwcDelta(before);
        mwcRecord(JsonObject{{"op", "addEntropy"}, {"seed", strf("{}", *seed)}}, std::move(calls));
      });

    methods.registerMethod("randu32", [](RandomSource& r) {
      return mwcDraw("randu32", r, [&]() { return r.randu32(); });
    });
    methods.registerMethod("randu64", [](RandomSource& r) {
      return mwcDraw("randu64", r, [&]() { return r.randu64(); });
    });
    methods.registerMethodWithSignature<int32_t, RandomSource&>("randi32", mem_fn(&RandomSource::randi32));
    methods.registerMethodWithSignature<int64_t, RandomSource&>("randi64", mem_fn(&RandomSource::randi64));

    methods.registerMethod("randf", [](RandomSource& randomSource, Maybe<float> arg1, Maybe<float> arg2)
      { return (arg1 && arg2) ? randomSource.randf(*arg1, *arg2) : randomSource.randf(); });
    methods.registerMethod("randd", [](RandomSource& randomSource, Maybe<double> arg1, Maybe<double> arg2)
      { return (arg1 && arg2) ? randomSource.randd(*arg1, *arg2) : randomSource.randd(); });

    methods.registerMethod("randb", [](RandomSource& r) {
      return mwcDraw("randb", r, [&]() { return r.randb(); });
    });

    methods.registerMethod("randInt", [](RandomSource& randomSource, int64_t arg1, Maybe<int64_t> arg2)
      { return arg2 ? randomSource.randInt(arg1, *arg2) : randomSource.randInt(arg1); });

    methods.registerMethod("randUInt", [](RandomSource& randomSource, uint64_t arg1, Maybe<uint64_t> arg2)
      { return arg2 ? randomSource.randUInt(arg1, *arg2) : randomSource.randUInt(arg1); });

    return methods;
  }
};

template <>
struct LuaConverter<PerlinF> : LuaUserDataConverter<PerlinF> {};

template <>
struct LuaUserDataMethods<PerlinF> {
  static LuaMethods<PerlinF> make() {
    LuaMethods<PerlinF> methods;

    methods.registerMethod("get",
        [](PerlinF& perlinF, float x, Maybe<float> y, Maybe<float> z) {
          if (y && z)
            return perlinF.get(x, *y, *z);
          else if (y)
            return perlinF.get(x, *y);
          else
            return perlinF.get(x);
        });

    return methods;
  }
};

String LuaBindings::formatLua(String const& string, List<LuaValue> const& args) {
  auto argsIt = args.begin();
  auto argsEnd = args.end();
  auto popArg = [&argsIt, &argsEnd]() -> LuaValue {
    if (argsIt == argsEnd)
      return LuaNil;
    return *argsIt++;
  };

  auto stringIt = string.begin();
  auto stringEnd = string.end();

  String result;

  while (stringIt != stringEnd) {
    if (*stringIt == '%') {
      auto next = stringIt;
      ++next;

      if (next == stringEnd)
        throw StarException("No specifier following '%'");
      else if (*next == '%')
        result += '%';
      else if (*next == 's')
        result += toString(popArg());
      else
        throw StarException::format("Improper lua log format specifier {}", (char)*next);
      ++next;
      stringIt = next;
    } else {
      result += *stringIt++;
    }
  }

  return result;
}

LuaCallbacks LuaBindings::makeUtilityCallbacks() {
  LuaCallbacks callbacks;

  callbacks.registerCallback("nrand", UtilityCallbacks::nrand);
  callbacks.registerCallback("makeUuid", UtilityCallbacks::makeUuid);
  callbacks.registerCallback("logInfo", UtilityCallbacks::logInfo);
  callbacks.registerCallback("logWarn", UtilityCallbacks::logWarn);
  callbacks.registerCallback("logError", UtilityCallbacks::logError);
  callbacks.registerCallback("setLogMap", UtilityCallbacks::setLogMap);
  callbacks.registerCallback("parseJson", UtilityCallbacks::parseJson);
  callbacks.registerCallback("printJson", UtilityCallbacks::printJson);
  callbacks.registerCallback("print", UtilityCallbacks::print);
  callbacks.registerCallback("interpolateSinEase", UtilityCallbacks::interpolateSinEase);
  callbacks.registerCallback("replaceTags", UtilityCallbacks::replaceTags);
  callbacks.registerCallback("stripEscapeCodes", [](String const& text) { return Text::stripEscapeCodes(text); });
  callbacks.registerCallback("parseJsonSequence", [](String const& json) { return Json::parseSequence(json); });
  callbacks.registerCallback("jsonMerge", [](Json const& a, Json const& b) { return jsonMerge(a, b); });
  callbacks.registerCallback("jsonEqual", [](Json const& a, Json const& b) { return a == b; });
  callbacks.registerCallback("jsonQuery", [](Json const& json, String const& path, Json const& def) { return json.query(path, def); });
  callbacks.registerCallback("makeRandomSource", [](Maybe<uint64_t> seed) {
    if (!RandomMwcLab.active)
      return seed ? RandomSource(*seed) : RandomSource();
    mwcRequire("construct", nullptr, seed);
    auto before = mwcCounts();
    RandomSource result(*seed);
    auto calls = mwcDelta(before);
    mwcRecord(JsonObject{{"op", "construct"}, {"seed", strf("{}", *seed)}}, std::move(calls));
    return result;
  });
  callbacks.registerCallback("makePerlinSource", [](Json const& config) { return PerlinF(config); });

  callbacks.copyCallback("parseJson", "jsonFromString"); // SE compat

  auto hash64LuaValues = [](LuaVariadic<LuaValue> const& values) -> uint64_t {
    XXHash64 hash;

    for (auto const& value : values) {
      if (auto b = value.ptr<LuaBoolean>())
        xxHash64Push(hash, *b);
      else if (auto i = value.ptr<LuaInt>())
        xxHash64Push(hash, *i);
      else if (auto f = value.ptr<LuaFloat>())
        xxHash64Push(hash, *f);
      else if (auto s = value.ptr<LuaString>())
        xxHash64Push(hash, s->ptr());
      else
        throw LuaException("Unhashable lua type passed to staticRandomXX binding");
    }

    return hash.digest();
  };

  callbacks.registerCallback("staticRandomI32",
      [hash64LuaValues](LuaVariadic<LuaValue> const& hashValues) { return (int32_t)hash64LuaValues(hashValues); });

  callbacks.registerCallback("staticRandomI32Range",
      [hash64LuaValues](int32_t min, int32_t max, LuaVariadic<LuaValue> const& hashValues) {
        if (max < min)
          throw LuaException("Maximum bound in staticRandomI32Range must be >= minimum bound!");
        uint64_t denom = (uint64_t)(-1) / ((uint64_t)(max - min) + 1);
        return (int32_t)(hash64LuaValues(hashValues) / denom + min);
      });

  callbacks.registerCallback("staticRandomDouble",
      [hash64LuaValues](LuaVariadic<LuaValue> const& hashValues) {
        return (hash64LuaValues(hashValues) & 0x7fffffffffffffff) / 9223372036854775808.0;
      });

  callbacks.registerCallback("staticRandomDoubleRange",
      [hash64LuaValues](double min, double max, LuaVariadic<LuaValue> const& hashValues) {
        if (max < min)
          throw LuaException("Maximum bound in staticRandomDoubleRange must be >= minimum bound!");
        return (hash64LuaValues(hashValues) & 0x7fffffffffffffff) / 9223372036854775808.0 * (max - min) + min;
      });
  
  callbacks.registerCallback("millisecondsSinceEpoch",
      []() -> int64_t {
        return Time::millisecondsSinceEpoch();
      });
  
  callbacks.registerCallback("makePromise",
      []() -> pair<RpcPromise<Json>,AutoFailRpcPromiseKeeperPtr<Json>> {
        auto pair = RpcPromise<Json>::createPair();
        return make_pair(pair.first,make_shared<AutoFailRpcPromiseKeeper<Json>>(pair.second));
      });
  
  callbacks.registerCallback("embedData", [](String const& data, String const& compression) -> String {
    auto compressionMethod = EmbeddedCompressionMethodNames.getLeft(compression);
    ByteArray ba = ByteArray(data.utf8Ptr(),data.utf8Size());
    return strf("/opensb_data;bin;{}",embedAndCompressData(ba,compressionMethod));
  });

  callbacks.registerCallback("embedJson", [](Json const& data, String const& compression) -> String {
    auto compressionMethod = EmbeddedCompressionMethodNames.getLeft(compression);
    DataStreamBuffer ds;
    ds.write(data);
    return strf("/opensb_data;json;{}",embedAndCompressData(ds.takeData(),compressionMethod));
  });

  callbacks.registerCallback("embedText", [](String const& data) -> String {
    return strf("/opensb_data;text;{}",embedEscapeText(data));
  });

  return callbacks;
}

double LuaBindings::UtilityCallbacks::nrand(Maybe<double> const& stdev, Maybe<double> const& mean) {
  return Random::nrandd(stdev.value(1.0), mean.value(0));
}

String LuaBindings::UtilityCallbacks::makeUuid() {
  return Uuid().hex();
}

void LuaBindings::UtilityCallbacks::logInfo(String const& str, LuaVariadic<LuaValue> const& args) {
  Logger::log(LogLevel::Info, formatLua(str, args).utf8Ptr());
}

void LuaBindings::UtilityCallbacks::logWarn(String const& str, LuaVariadic<LuaValue> const& args) {
  Logger::log(LogLevel::Warn, formatLua(str, args).utf8Ptr());
}

void LuaBindings::UtilityCallbacks::logError(String const& str, LuaVariadic<LuaValue> const& args) {
  Logger::log(LogLevel::Error, formatLua(str, args).utf8Ptr());
}

void LuaBindings::UtilityCallbacks::setLogMap(String const& key, String const& value, LuaVariadic<LuaValue> const& args) {
  LogMap::set(key, formatLua(value, args));
}

Json LuaBindings::UtilityCallbacks::parseJson(String const& str) {
  return Json::parse(str);
}

String LuaBindings::UtilityCallbacks::printJson(Json const& arg, Maybe<int> pretty) {
  return arg.repr(pretty.value());
}

String LuaBindings::UtilityCallbacks::print(LuaValue const& value) {
  return toString(value);
}

LuaValue LuaBindings::UtilityCallbacks::interpolateSinEase(LuaEngine& engine, double offset, LuaValue const& value1, LuaValue const& value2) {
  if (auto floatValue1 = engine.luaMaybeTo<double>(value1)) {
    auto floatValue2 = engine.luaMaybeTo<double>(value2);
    return sinEase(offset, *floatValue1, *floatValue2);
  } else {
    return engine.luaFrom<Vec2F>(sinEase(offset, engine.luaTo<Vec2F>(value1), engine.luaTo<Vec2F>(value2)));
  }
}

String LuaBindings::UtilityCallbacks::replaceTags(String const& str, StringMap<String> const& tags) {
  return str.replaceTags(tags);
}

}
