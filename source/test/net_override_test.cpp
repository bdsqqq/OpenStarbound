#include <functional>

#include "StarDataStreamDevices.hpp"
#include "StarNetElementExt.hpp"

#include "gtest/gtest.h"

#include <exception>
#include <iostream>
#include <memory>
#include <string>

using namespace Star;

namespace {
struct OverrideError : std::exception {};
struct DerivedOverrideError : OverrideError {};

ByteArray overrideBytes(std::initializer_list<uint8_t> bytes) {
  DataStreamBuffer ds;
  for (auto byte : bytes) ds.write(byte);
  return ds.takeData();
}

void overrideTrace(char const* name, std::string const& events, DataStreamBuffer const& ds) {
  static char const hex[] = "0123456789abcdef";
  std::cout << "NET_OVERRIDE_TRACE " << name << ' ' << events << '/';
  for (size_t i = 0; i < ds.data().size(); ++i) {
    auto byte = static_cast<unsigned char>(ds.data()[i]);
    std::cout << hex[byte >> 4] << hex[byte & 15];
  }
  std::cout << '\n';
}

// Unlike Top's bare-base mixin, Ext requires NetElement's virtual bool contract.
struct OverrideBase : NetElement {
  mutable std::string events;
  mutable DataStream* stream = nullptr;
  mutable uint64_t from = 0;
  mutable VersionNumber rulesVersion = AnyVersion;
  mutable bool admin = false;
  mutable unsigned streamVersion = 0;
  float time = 0;
  uint8_t value = 0;
  bool writes = true;
  std::exception_ptr error;

  void initNetVersion(NetElementVersion const*) override {}
  void observe(DataStream& ds, NetCompatibilityRules rules, char event) const {
    stream = &ds;
    rulesVersion = rules.version();
    admin = rules.isAdmin();
    streamVersion = ds.streamCompatibilityVersion();
    events += event;
  }
  void finish() const { if (error) std::rethrow_exception(error); }
  void netStore(DataStream& ds, NetCompatibilityRules rules) const override {
    observe(ds, rules, 'S');
    ds.write<uint8_t>(0xa1);
    finish();
  }
  void netLoad(DataStream& ds, NetCompatibilityRules rules) override {
    observe(ds, rules, 'L');
    value = ds.read<uint8_t>();
    finish();
  }
  bool writeNetDelta(DataStream& ds, uint64_t version, NetCompatibilityRules rules) const override {
    observe(ds, rules, 'W');
    from = version;
    ds.write<uint8_t>(0xb2);
    finish();
    return writes;
  }
  void readNetDelta(DataStream& ds, float interpolation, NetCompatibilityRules rules) override {
    observe(ds, rules, 'R');
    time = interpolation;
    value = ds.read<uint8_t>();
    finish();
  }
};
using Override = NetElementOverride<OverrideBase>;

struct MoreDerivedOverride : Override {
  mutable int unexpected = 0;
  void netStore(DataStream&, NetCompatibilityRules) const override { ++unexpected; }
  void netLoad(DataStream&, NetCompatibilityRules) override { ++unexpected; }
  bool writeNetDelta(DataStream&, uint64_t, NetCompatibilityRules) const override {
    ++unexpected;
    return false;
  }
  void readNetDelta(DataStream&, float, NetCompatibilityRules) override { ++unexpected; }
};

struct CopyState { int copies = 0; int deaths = 0; std::string events; };
struct CountedStore {
  CopyState* state;
  explicit CountedStore(CopyState& s) : state(&s) {}
  CountedStore(CountedStore const& other) : state(other.state) { ++state->copies; }
  ~CountedStore() { ++state->deaths; }
  void operator()(DataStream& ds, NetCompatibilityRules) const {
    state->events += 'C';
    ds.write<uint8_t>(0xc3);
  }
  bool operator()(DataStream& ds, uint64_t, NetCompatibilityRules rules) const {
    (*this)(ds, rules);
    return false;
  }
  void operator()(DataStream& ds, float, NetCompatibilityRules rules) const {
    (*this)(ds, rules);
  }
};

struct Release {
  std::string* events;
  char name;
  Release(std::string& e, char n) : events(&e), name(n) {}
  ~Release() { *events += name; }
};

void exceptionPaths(bool custom) {
  for (int kind = 0; kind != 2; ++kind) {
    auto error = kind == 0 ? std::make_exception_ptr(DerivedOverrideError{})
                           : std::make_exception_ptr(731);
    for (int op = 0; op != 4; ++op) {
      Override element;
      DataStreamBuffer ds(overrideBytes({0x19, 0x28}));
      if (custom) {
        element.setOverrides(
          [&](DataStream& out, NetCompatibilityRules) {
            element.events += 's'; out.write<uint8_t>(0xe1); std::rethrow_exception(error);
          },
          [&](DataStream& in, NetCompatibilityRules) {
            element.events += 'l'; element.value = in.read<uint8_t>(); std::rethrow_exception(error);
          },
          [&](DataStream& out, uint64_t, NetCompatibilityRules) -> bool {
            element.events += 'w'; out.write<uint8_t>(0xe2); std::rethrow_exception(error);
          },
          [&](DataStream& in, float, NetCompatibilityRules) {
            element.events += 'r'; element.value = in.read<uint8_t>(); std::rethrow_exception(error);
          });
      } else {
        element.error = error;
      }
      try {
        switch (op) {
          case 0: element.netStore(ds); break;
          case 1: element.netLoad(ds, {}); break;
          case 2: (void)element.writeNetDelta(ds, UINT64_MAX); break;
          case 3: element.readNetDelta(ds, -0.25f); break;
        }
        ADD_FAILURE() << "exception swallowed";
      } catch (...) {
        EXPECT_EQ(std::current_exception(), error);
        if (kind == 0) {
          try { throw; }
          catch (DerivedOverrideError const&) {}
          catch (...) { ADD_FAILURE() << "derived exception changed"; }
        } else {
          try { throw; }
          catch (int value) { EXPECT_EQ(value, 731); }
          catch (...) { ADD_FAILURE() << "nonstandard exception changed"; }
        }
      }
      EXPECT_EQ(ds.pos(), 1u);
      if (op == 1 || op == 3) {
        EXPECT_EQ(element.value, 0x19);
        EXPECT_EQ(ds.data(), overrideBytes({0x19, 0x28}));
      } else {
        uint8_t prefix = custom ? (op == 0 ? 0xe1 : 0xe2) : (op == 0 ? 0xa1 : 0xb2);
        EXPECT_EQ(ds.data(), overrideBytes({prefix, 0x28}));
      }
      overrideTrace(custom ? "custom-exception" : "base-exception", element.events, ds);
    }
  }
}
}

TEST(NetOverride, AllFallbacksQualifyBaseRatherThanRedispatchMoreDerived) {
  MoreDerivedOverride element;
  Override& wrapper = element;
  NetCompatibilityRules rules(LegacyVersion);
  rules.setIsAdmin(true);
  DataStreamBuffer ds;
  wrapper.Override::netStore(ds, rules);
  EXPECT_TRUE(wrapper.Override::writeNetDelta(ds, UINT64_MAX, rules));
  ds.seek(0);
  wrapper.Override::netLoad(ds, rules);
  wrapper.Override::readNetDelta(ds, -0.5f, rules);
  EXPECT_EQ(element.events, "SWLR");
  EXPECT_EQ(element.unexpected, 0);
  EXPECT_EQ(element.stream, &ds);
  EXPECT_EQ(element.from, UINT64_MAX);
  EXPECT_EQ(element.time, -0.5f);
  EXPECT_EQ(element.rulesVersion, LegacyVersion);
  EXPECT_TRUE(element.admin);
  EXPECT_EQ(element.value, 0xb2);
  EXPECT_EQ(ds.data(), overrideBytes({0xa1, 0xb2}));
  overrideTrace("qualified-fallback", element.events, ds);
}

TEST(NetOverride, CustomCallbacksReceiveOriginalParametersAndBothWriterResults) {
  Override element;
  NetCompatibilityRules rules(LegacyVersion);
  rules.setIsAdmin(true);
  DataStreamBuffer ds;
  auto originalStreamVersion = ds.streamCompatibilityVersion();
  bool writes = false;
  element.setOverrides(
    [&](DataStream& out, NetCompatibilityRules r) {
      element.observe(out, r, 's'); out.write<uint8_t>(0x31);
    },
    [&](DataStream& in, NetCompatibilityRules r) {
      element.observe(in, r, 'l'); element.value = in.read<uint8_t>();
    },
    [&](DataStream& out, uint64_t from, NetCompatibilityRules r) {
      element.observe(out, r, 'w'); element.from = from;
      out.write<uint8_t>(writes ? 0x42 : 0x40); return writes;
    },
    [&](DataStream& in, float time, NetCompatibilityRules r) {
      element.observe(in, r, 'r'); element.time = time; element.value = in.read<uint8_t>();
    });
  element.netStore(ds, rules);
  EXPECT_FALSE(element.writeNetDelta(ds, UINT64_MAX - 7, rules));
  EXPECT_EQ(element.from, UINT64_MAX - 7);
  writes = true;
  EXPECT_TRUE(element.writeNetDelta(ds, 0, rules));
  EXPECT_EQ(element.from, 0u);
  ds.seek(0);
  element.netLoad(ds, rules);
  EXPECT_EQ(element.value, 0x31);
  element.readNetDelta(ds, 0.125f, rules);
  EXPECT_EQ(element.value, 0x40);
  EXPECT_EQ(element.time, 0.125f);
  EXPECT_EQ(element.events, "swwlr");
  EXPECT_EQ(element.stream, &ds);
  EXPECT_EQ(element.rulesVersion, LegacyVersion);
  EXPECT_TRUE(element.admin);
  EXPECT_EQ(element.streamVersion, originalStreamVersion);
  EXPECT_EQ(ds.streamCompatibilityVersion(), originalStreamVersion);
  EXPECT_EQ(ds.data(), overrideBytes({0x31, 0x40, 0x42}));
  overrideTrace("custom-parameters", element.events, ds);
}

TEST(NetOverride, CallbackPresenceDoesNotIntroduceCompatibilityGuard) {
  Override element;
  element.setCompatibilityVersion(LegacyVersion + 1);
  NetCompatibilityRules rules(LegacyVersion);
  ASSERT_FALSE(element.checkWithRules(rules));
  DataStreamBuffer ds;
  element.setOverrides(
    [&](DataStream& out, NetCompatibilityRules) { element.events += 's'; out.write<uint8_t>(1); },
    [&](DataStream& in, NetCompatibilityRules) { element.events += 'l'; element.value = in.read<uint8_t>(); },
    [&](DataStream& out, uint64_t, NetCompatibilityRules) { element.events += 'w'; out.write<uint8_t>(2); return true; },
    [&](DataStream& in, float, NetCompatibilityRules) { element.events += 'r'; element.value = in.read<uint8_t>(); });
  element.netStore(ds, rules);
  EXPECT_TRUE(element.writeNetDelta(ds, 1, rules));
  ds.seek(0);
  element.netLoad(ds, rules);
  element.readNetDelta(ds, 0, rules);
  EXPECT_EQ(element.events, "swlr");
  EXPECT_EQ(element.value, 2);
  overrideTrace("no-rule-guard", element.events, ds);
}

TEST(NetOverride, InvocationDoesNotCopyOrDestroyStoredCallable) {
  CopyState state;
  {
    Override element;
    element.setOverrides(CountedStore{state}, CountedStore{state},
      CountedStore{state}, CountedStore{state});
    auto copies = state.copies;
    auto deaths = state.deaths;
    DataStreamBuffer ds;
    element.netStore(ds);
    element.netStore(ds);
    element.netLoad(ds, {});
    EXPECT_FALSE(element.writeNetDelta(ds, 1));
    element.readNetDelta(ds);
    EXPECT_EQ(state.copies, copies);
    EXPECT_EQ(state.deaths, deaths);
    EXPECT_EQ(state.events, "CCCCC");
    EXPECT_EQ(ds.data(), overrideBytes({0xc3, 0xc3, 0xc3, 0xc3, 0xc3}));
    overrideTrace("no-callable-copy", state.events, ds);
    element.setOverrides({}, {}, {}, {});
    EXPECT_EQ(state.deaths, deaths + 4);
  }
}

TEST(NetOverride, CustomExceptionsPreserveIdentityAndPartialStreamAndState) {
  exceptionPaths(true);
}

TEST(NetOverride, BaseExceptionsPreserveIdentityAndPartialStreamAndState) {
  exceptionPaths(false);
}

TEST(NetOverride, ReentryAndReplacingOtherCallbackUseFreshStoredFunction) {
  Override element;
  int depth = 0;
  DataStreamBuffer input(overrideBytes({0x11, 0x22, 0x33}));
  DataStreamBuffer output;
  element.setNetStorer([&](DataStream& out, NetCompatibilityRules rules) {
    int id = depth + 1;
    element.events += 's';
    element.setNetLoader([&, id](DataStream& in, NetCompatibilityRules) {
      element.events += char('0' + id);
      element.value = in.read<uint8_t>();
    });
    element.netLoad(input, rules);
    if (depth == 0) {
      ++depth;
      element.netStore(out, rules);
      --depth;
      element.netLoad(input, rules);
    }
    out.write<uint8_t>(uint8_t(id));
  });
  element.netStore(output);
  EXPECT_EQ(element.events, "s1s22");
  EXPECT_EQ(element.value, 0x33);
  EXPECT_EQ(input.pos(), 3u);
  EXPECT_EQ(output.data(), overrideBytes({2, 1}));
  overrideTrace("reentry-fresh-other", element.events, output);
}

TEST(NetOverride, SetOverridesReleasesOldTargetsInNativeMemberOrder) {
  std::string released;
  Override element;
  auto s = std::make_shared<Release>(released, 'S');
  auto l = std::make_shared<Release>(released, 'L');
  auto w = std::make_shared<Release>(released, 'W');
  auto r = std::make_shared<Release>(released, 'R');
  element.setOverrides(
    [s](DataStream&, NetCompatibilityRules) {},
    [l](DataStream&, NetCompatibilityRules) {},
    [w](DataStream&, uint64_t, NetCompatibilityRules) { return false; },
    [r](DataStream&, float, NetCompatibilityRules) {});
  s.reset(); l.reset(); w.reset(); r.reset();
  ASSERT_TRUE(released.empty());
  element.setOverrides({}, {}, {}, {});
  EXPECT_EQ(released, "SLWR");
  DataStreamBuffer ds;
  element.netStore(ds);
  EXPECT_TRUE(element.writeNetDelta(ds, 1));
  ds.seek(0);
  element.netLoad(ds, {});
  element.readNetDelta(ds);
  EXPECT_EQ(element.events, "SWLR");
  overrideTrace("ordered-release", released + element.events, ds);
}

TEST(NetOverride, IndividualSettersReleaseOldTargetsBeforeReturning) {
  std::string released;
  Override element;
  auto install = [&](char name) { return std::make_shared<Release>(released, name); };
  element.setNetStorer([p = install('S')](DataStream&, NetCompatibilityRules) {});
  element.setNetLoader([p = install('L')](DataStream&, NetCompatibilityRules) {});
  element.setNetDeltaWriter([p = install('W')](DataStream&, uint64_t, NetCompatibilityRules) { return false; });
  element.setNetDeltaReader([p = install('R')](DataStream&, float, NetCompatibilityRules) {});
  element.setNetDeltaReader({}); EXPECT_EQ(released, "R");
  element.setNetStorer({}); EXPECT_EQ(released, "RS");
  element.setNetDeltaWriter({}); EXPECT_EQ(released, "RSW");
  element.setNetLoader({}); EXPECT_EQ(released, "RSWL");
  DataStreamBuffer ds;
  overrideTrace("individual-release", released, ds);
}

TEST(NetOverride, ReferenceCapturesObserveLiveNoncopyableStateAndBaseWriteFalse) {
  Override element;
  auto value = std::make_unique<uint8_t>(5);
  DataStreamBuffer ds;
  element.setNetStorer([&](DataStream& out, NetCompatibilityRules) { out.write(*value); });
  element.netStore(ds);
  *value = 9;
  element.netStore(ds);
  element.writes = false;
  EXPECT_FALSE(element.writeNetDelta(ds, UINT64_MAX));
  EXPECT_EQ(element.from, UINT64_MAX);
  EXPECT_EQ(ds.data(), overrideBytes({5, 9, 0xb2}));
  EXPECT_EQ(element.events, "W");
  overrideTrace("live-reference-base-false", element.events, ds);
}
