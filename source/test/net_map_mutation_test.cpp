#include "StarDataStreamDevices.hpp"
#include "StarNetElementContainers.hpp"

#include "gtest/gtest.h"

#include <algorithm>
#include <exception>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

using namespace Star;

namespace {
// Hooks observe actual native storage, comparisons and ADL codecs. They do not
// implement the wrapper's mutations or predict std::map's internal move counts.
struct MutationLog {
  static std::vector<std::string> events;
  static std::function<void(std::string const&)> hook;
  static void emit(std::string event) {
    events.push_back(event);
    if (hook) hook(event);
  }
  static void note(std::string event) { events.push_back(event); }
};
std::vector<std::string> MutationLog::events;
std::function<void(std::string const&)> MutationLog::hook;

struct MutationScope {
  MutationScope() { MutationLog::hook = {}; MutationLog::events.clear(); }
  ~MutationScope() { MutationLog::hook = {}; }
};

struct MutationKey {
  int32_t n = 0;
  MutationKey() { MutationLog::emit("key.default"); }
  explicit MutationKey(int32_t v) : n(v) {}
  MutationKey(MutationKey const& v) : n(v.n) { MutationLog::emit("key.copy:" + std::to_string(n)); }
  MutationKey(MutationKey&& v) : n(v.n) { v.n = -999; MutationLog::emit("key.move:" + std::to_string(n)); }
  MutationKey& operator=(MutationKey const&) = default;
  MutationKey& operator=(MutationKey&&) = default;
  ~MutationKey() { MutationLog::note("key.destroy:" + std::to_string(n)); }
  bool operator<(MutationKey const& v) const { return n < v.n; }
  bool operator==(MutationKey const& v) const { return n == v.n; }
};
std::ostream& operator<<(std::ostream& out, MutationKey const& key) { return out << key.n; }
DataStream& operator<<(DataStream& ds, MutationKey const& key) {
  MutationLog::emit("key.write:" + std::to_string(key.n));
  return ds << key.n;
}
DataStream& operator>>(DataStream& ds, MutationKey& key) {
  MutationLog::emit("key.read");
  return ds >> key.n;
}

struct MutationValue {
  int32_t n = 0;
  MutationValue() { MutationLog::emit("value.default"); }
  explicit MutationValue(int32_t v) : n(v) {}
  MutationValue(MutationValue const& v) : n(v.n) { MutationLog::emit("value.copy:" + std::to_string(n)); }
  MutationValue(MutationValue&& v) : n(v.n) { v.n = -999; MutationLog::emit("value.move:" + std::to_string(n)); }
  MutationValue& operator=(MutationValue const& v) {
    MutationLog::emit("value.copyassign:" + std::to_string(v.n)); n = v.n; return *this;
  }
  MutationValue& operator=(MutationValue&& v) {
    MutationLog::emit("value.moveassign:" + std::to_string(v.n)); n = v.n; v.n = -999; return *this;
  }
  ~MutationValue() { MutationLog::note("value.destroy:" + std::to_string(n)); }
  struct Equality {
    bool equal;
    operator bool() const = delete;
    bool operator!() const { MutationLog::emit("equal.not"); return !equal; }
    ~Equality() { MutationLog::note("equal.destroy"); }
  };
  Equality operator==(MutationValue const& v) const {
    MutationLog::emit("equal.compare"); return {n == v.n};
  }
};
DataStream& operator<<(DataStream& ds, MutationValue const& value) {
  MutationLog::emit("value.write:" + std::to_string(value.n));
  return ds << value.n;
}
DataStream& operator>>(DataStream& ds, MutationValue& value) {
  MutationLog::emit("value.read");
  return ds >> value.n;
}

struct MutationBase : Map<MutationKey, MutationValue> {
  using Plain = Map<MutationKey, MutationValue>;
  MutationBase() = default;
  MutationBase(MutationBase const&) = default;
  MutationBase(MutationBase&&) = default;
  MutationBase& operator=(MutationBase&& values) {
    MutationLog::emit("base.assign");
    Plain::operator=(std::move(values));
    return *this;
  }
  // A valid BaseMap result need not itself be std::pair. Keep its named local
  // and return conversion observable, without guessing iterator/RVO copy counts.
  struct InsertResult {
    iterator first;
    bool second;
    operator pair<const_iterator, bool>() const {
      MutationLog::emit("result.convert");
      return {first, second};
    }
    ~InsertResult() { MutationLog::note("result.destroy"); }
  };
  InsertResult insert(value_type const& value) {
    MutationLog::emit("base.insert.begin");
    auto result = Plain::insert(value);
    MutationLog::emit("base.insert.end");
    return {result.first, result.second};
  }
  InsertResult insert(value_type&& value) {
    MutationLog::emit("base.insert.begin");
    auto result = Plain::insert(std::move(value));
    MutationLog::emit("base.insert.end");
    return {result.first, result.second};
  }
  iterator erase(iterator i) {
    MutationLog::emit("base.erase.begin");
    auto result = Plain::erase(i);
    MutationLog::emit("base.erase.end");
    return result;
  }
  void clear() {
    MutationLog::emit("base.clear");
    Plain::clear();
  }
};
using MutationMap = NetElementMapWrapper<MutationBase>;

size_t eventIndex(std::string const& event) {
  auto const& events = MutationLog::events;
  return std::find(events.begin(), events.end(), event) - events.begin();
}
size_t eventCount(std::string const& event) {
  return std::count(MutationLog::events.begin(), MutationLog::events.end(), event);
}
void mutationTrace(char const* name, DataStreamBuffer const* wire = nullptr) {
  std::cout << "NET_MAP_MUTATION_TRACE " << name;
  for (auto const& event : MutationLog::events) std::cout << ' ' << event;
  if (wire) {
    static char const hex[] = "0123456789abcdef";
    std::cout << " wire=";
    for (size_t i = 0; i < wire->size(); ++i) {
      auto byte = static_cast<unsigned char>(wire->ptr()[i]);
      std::cout << hex[byte >> 4] << hex[byte & 15];
    }
  }
  std::cout << '\n';
}
void rawSet(DataStream& ds, int32_t key, int32_t value) {
  ds.write<uint8_t>(0); ds.write(key); ds.write(value);
}
void deltaSet(DataStream& ds, int32_t key, int32_t value) {
  ds.writeVlqU(2); rawSet(ds, key, value);
}
void deltaRemove(DataStream& ds, int32_t key) {
  ds.writeVlqU(2); ds.write<uint8_t>(1); ds.write(key);
}
void deltaClear(DataStream& ds) { ds.writeVlqU(2); ds.write<uint8_t>(2); }
void noMutationDelta(MutationMap const& map) {
  DataStreamBuffer ds;
  EXPECT_FALSE(map.writeNetDelta(ds, 1));
  EXPECT_TRUE(ds.data().empty());
}
template <typename F> void sameMutationException(std::exception_ptr expected, F&& f) {
  try { f(); FAIL() << "expected original exception"; }
  catch (...) { EXPECT_EQ(std::current_exception(), expected); }
}
struct MutationFailure : std::exception {};
struct MutationDerivedFailure : MutationFailure {};
}

TEST(NetMapMutation, NamedLvalueInsertCopiesStorageBeforeRecordingAndPreservesArgument) {
  MutationScope scope;
  MutationMap map;
  MutationBase::value_type value{MutationKey(1), MutationValue(10)};
  MutationLog::events.clear();
  auto result = map.insert(value);
  ASSERT_TRUE(result.second);
  EXPECT_EQ(result.first->second.n, 10);
  EXPECT_EQ(value.first.n, 1); EXPECT_EQ(value.second.n, 10);
  auto begin = eventIndex("base.insert.begin");
  auto end = eventIndex("base.insert.end");
  ASSERT_LT(begin, end); ASSERT_LT(end, MutationLog::events.size());
  EXPECT_NE(std::find(MutationLog::events.begin() + begin, MutationLog::events.begin() + end,
      "value.copy:10"), MutationLog::events.begin() + end);
  EXPECT_LT(eventIndex("result.convert"), eventIndex("result.destroy"));
  auto destroyed = eventIndex("result.destroy");
  ASSERT_LT(destroyed, MutationLog::events.size());
  EXPECT_NE(std::find(MutationLog::events.begin() + destroyed, MutationLog::events.end(),
      "value.destroy:-999"), MutationLog::events.end());
  EXPECT_NE(std::find(MutationLog::events.begin() + end, MutationLog::events.end(), "key.copy:1"), MutationLog::events.end());
  EXPECT_TRUE(map.pullUpdated()); EXPECT_FALSE(map.pullUpdated());
  mutationTrace("insert_named_lvalue");
  DataStreamBuffer actual, expected;
  ASSERT_TRUE(map.writeNetDelta(actual, 0));
  deltaSet(expected, 1, 10); expected.writeVlqU(0);
  EXPECT_EQ(actual.data(), expected.data());
}

TEST(NetMapMutation, DuplicateInsertReturnsExistingIteratorWithoutHistoryOrUpdate) {
  MutationScope scope;
  MutationMap map; map.set(MutationKey(1), MutationValue(10)); map.pullUpdated();
  MutationLog::events.clear();
  auto result = map.insert(MutationKey(1), MutationValue(20));
  EXPECT_FALSE(result.second); EXPECT_EQ(result.first->second.n, 10);
  EXPECT_FALSE(map.pullUpdated()); noMutationDelta(map);
  EXPECT_EQ(eventCount("value.moveassign:20"), 0u);
  mutationTrace("duplicate_insert");
  auto error = std::make_exception_ptr(307);
  MutationLog::events.clear();
  MutationLog::hook = [&](std::string const& event) {
    if (event == "result.convert") std::rethrow_exception(error);
  };
  sameMutationException(error, [&] { map.insert(MutationKey(1), MutationValue(30)); });
  MutationLog::hook = {};
  EXPECT_LT(eventIndex("result.convert"), eventIndex("result.destroy"));
  EXPECT_EQ(map.get(MutationKey(1)).n, 10); EXPECT_FALSE(map.pullUpdated());
  noMutationDelta(map); mutationTrace("duplicate_insert_return_failure");
}

TEST(NetMapMutation, DuplicateAddFormatsTheAlreadyMovedParameterKey) {
  MutationScope scope;
  MutationMap map; map.set(MutationKey(1), MutationValue(10)); map.pullUpdated();
  // The fixture's move constructor deterministically leaves -999 in its source.
  // Derive the exception type prefix through the native exception formatter.
  auto expected = MapException::format("Entry with key '{}' already present.", outputAny(MutationKey(-999)));
  try { map.add(MutationKey(1), MutationValue(20)); FAIL(); }
  catch (MapException const& e) { EXPECT_STREQ(e.what(), expected.what()); }
  EXPECT_EQ(map.get(MutationKey(1)).n, 10);
  EXPECT_FALSE(map.pullUpdated()); noMutationDelta(map);
  mutationTrace("duplicate_add_moved_key");
}

TEST(NetMapMutation, EqualSetUsesNegationProxyAndEndsItsLifetimeWithoutDelta) {
  MutationScope scope;
  MutationMap map; map.set(MutationKey(1), MutationValue(10)); map.pullUpdated();
  MutationLog::events.clear(); map.set(MutationKey(1), MutationValue(10));
  EXPECT_EQ(eventCount("equal.compare"), 1u);
  EXPECT_LT(eventIndex("equal.compare"), eventIndex("equal.not"));
  EXPECT_LT(eventIndex("equal.not"), eventIndex("equal.destroy"));
  EXPECT_EQ(eventCount("value.copy:10"), 0u);
  EXPECT_EQ(eventCount("value.moveassign:10"), 0u);
  EXPECT_FALSE(map.pullUpdated()); noMutationDelta(map);
  mutationTrace("equal_set_proxy");
}

TEST(NetMapMutation, ChangedSetDestroysProxyThenCopiesHistoryBeforeMoveAssignment) {
  MutationScope scope;
  MutationMap map; map.set(MutationKey(1), MutationValue(10)); map.pullUpdated();
  MutationLog::events.clear(); map.set(MutationKey(1), MutationValue(20));
  EXPECT_LT(eventIndex("equal.destroy"), eventIndex("value.copy:20"));
  EXPECT_LT(eventIndex("value.copy:20"), eventIndex("value.moveassign:20"));
  EXPECT_EQ(map.get(MutationKey(1)).n, 20); EXPECT_TRUE(map.pullUpdated());
  mutationTrace("changed_set_copy_before_assign");
}

TEST(NetMapMutation, ExistingSetCopyFailureLeavesStorageAndUpdatedUntouched) {
  MutationScope scope;
  MutationMap map; map.set(MutationKey(1), MutationValue(10)); map.pullUpdated();
  auto error = std::make_exception_ptr(MutationDerivedFailure{});
  MutationLog::events.clear();
  MutationLog::hook = [&](std::string const& event) {
    if (event == "value.copy:20") std::rethrow_exception(error);
  };
  sameMutationException(error, [&] { map.set(MutationKey(1), MutationValue(20)); });
  MutationLog::hook = {};
  EXPECT_LT(eventIndex("equal.destroy"), eventIndex("value.copy:20"));
  EXPECT_EQ(eventCount("value.moveassign:20"), 0u);
  EXPECT_EQ(map.get(MutationKey(1)).n, 10); EXPECT_FALSE(map.pullUpdated());
  noMutationDelta(map); mutationTrace("existing_set_copy_failure");
}

TEST(NetMapMutation, MissingSetCopiesKeyThenValueBeforeNativeInsert) {
  MutationScope scope;
  MutationMap map;
  auto error = std::make_exception_ptr(411);
  MutationLog::hook = [&](std::string const& event) {
    if (event == "value.copy:20") std::rethrow_exception(error);
  };
  sameMutationException(error, [&] { map.set(MutationKey(2), MutationValue(20)); });
  MutationLog::hook = {};
  EXPECT_LT(eventIndex("key.copy:2"), eventIndex("value.copy:20"));
  EXPECT_EQ(eventCount("base.insert.begin"), 0u);
  EXPECT_TRUE(map.empty()); EXPECT_FALSE(map.pullUpdated()); noMutationDelta(map);
  mutationTrace("missing_set_history_failure");
}

TEST(NetMapMutation, RemoveErasesBeforeHistoryKeyCopyFailureAndMissingRemoveIsNoop) {
  MutationScope scope;
  MutationMap map; map.set(MutationKey(1), MutationValue(10)); map.pullUpdated();
  MutationKey key(1);
  auto error = std::make_exception_ptr(MutationDerivedFailure{});
  MutationLog::events.clear();
  MutationLog::hook = [&](std::string const& event) {
    if (event == "key.copy:1") std::rethrow_exception(error);
  };
  sameMutationException(error, [&] { map.remove(key); });
  MutationLog::hook = {};
  EXPECT_LT(eventIndex("base.erase.end"), eventIndex("key.copy:1"));
  EXPECT_FALSE(map.contains(key)); EXPECT_FALSE(map.pullUpdated()); noMutationDelta(map);
  EXPECT_FALSE(map.remove(key)); EXPECT_FALSE(map.pullUpdated());
  mutationTrace("remove_erased_before_copy_failure");
}

TEST(NetMapMutation, ClearRecordsHistoryAndUpdatedBeforeThrowingNativeClear) {
  MutationScope scope;
  MutationMap map; NetElementVersion version; map.initNetVersion(&version);
  version.increment(); map.set(MutationKey(1), MutationValue(10)); map.pullUpdated();
  version.increment();
  auto error = std::make_exception_ptr(512);
  MutationLog::events.clear();
  MutationLog::hook = [&](std::string const& event) {
    if (event == "base.clear") {
      EXPECT_TRUE(map.contains(MutationKey(1)));
      EXPECT_TRUE(map.pullUpdated());
      DataStreamBuffer actual, expected;
      EXPECT_TRUE(map.writeNetDelta(actual, 2));
      deltaClear(expected); expected.writeVlqU(0);
      EXPECT_EQ(actual.data(), expected.data());
      std::rethrow_exception(error);
    }
  };
  sameMutationException(error, [&] { map.clear(); }); MutationLog::hook = {};
  EXPECT_EQ(map.get(MutationKey(1)).n, 10); EXPECT_FALSE(map.pullUpdated());
  mutationTrace("clear_history_before_base_failure");
  map.clear(); EXPECT_TRUE(map.empty()); EXPECT_TRUE(map.pullUpdated());
  map.clear(); EXPECT_FALSE(map.pullUpdated());
}

TEST(NetMapMutation, UnchangedResetStillAssignsNativeStorageButDoesNotMarkUpdated) {
  MutationScope scope;
  MutationMap map; map.set(MutationKey(1), MutationValue(10)); map.pullUpdated();
  MutationBase values; values.set(MutationKey(1), MutationValue(10));
  MutationLog::events.clear(); map.reset(std::move(values));
  EXPECT_LT(eventIndex("equal.destroy"), eventIndex("base.assign"));
  EXPECT_EQ(eventCount("value.copy:10"), 0u);
  EXPECT_FALSE(map.pullUpdated()); noMutationDelta(map);
  EXPECT_EQ(map.get(MutationKey(1)).n, 10);
  mutationTrace("unchanged_reset_assigns");
}

TEST(NetMapMutation, ResetRecordsAbsentThenChangedAndAddedBeforeNativeAssignmentFailure) {
  MutationScope scope;
  MutationMap map; NetElementVersion version; map.initNetVersion(&version);
  map.set(MutationKey(1), MutationValue(10)); map.set(MutationKey(2), MutationValue(20));
  map.pullUpdated(); version.increment();
  MutationBase values; values.set(MutationKey(2), MutationValue(21)); values.set(MutationKey(3), MutationValue(30));
  auto error = std::make_exception_ptr(MutationDerivedFailure{});
  MutationLog::events.clear();
  MutationLog::hook = [&](std::string const& event) {
    if (event == "base.assign") std::rethrow_exception(error);
  };
  sameMutationException(error, [&] { map.reset(std::move(values)); }); MutationLog::hook = {};
  EXPECT_LT(eventIndex("key.copy:1"), eventIndex("value.copy:21"));
  EXPECT_LT(eventIndex("value.copy:21"), eventIndex("value.copy:30"));
  EXPECT_LT(eventIndex("value.copy:30"), eventIndex("base.assign"));
  EXPECT_EQ(map.get(MutationKey(1)).n, 10); EXPECT_EQ(map.get(MutationKey(2)).n, 20);
  EXPECT_FALSE(map.contains(MutationKey(3))); EXPECT_TRUE(map.pullUpdated());
  DataStreamBuffer actual, expected; ASSERT_TRUE(map.writeNetDelta(actual, 1));
  deltaRemove(expected, 1); deltaSet(expected, 2, 21); deltaSet(expected, 3, 30); expected.writeVlqU(0);
  EXPECT_EQ(actual.data(), expected.data()); mutationTrace("reset_assignment_failure", &actual);
}

TEST(NetMapMutation, TypedLoadDefaultsKeyThenValueAndReadsInOrderBeforeFailure) {
  MutationScope scope;
  MutationMap map;
  DataStreamBuffer ds; ds.writeVlqU(1); rawSet(ds, 7, 70); ds.seek(0);
  auto error = std::make_exception_ptr(613);
  MutationLog::events.clear();
  MutationLog::hook = [&](std::string const& event) {
    if (event == "value.read") std::rethrow_exception(error);
  };
  sameMutationException(error, [&] { map.netLoad(ds, {}); }); MutationLog::hook = {};
  EXPECT_LT(eventIndex("key.default"), eventIndex("value.default"));
  EXPECT_LT(eventIndex("value.default"), eventIndex("key.read"));
  EXPECT_LT(eventIndex("key.read"), eventIndex("value.read"));
  EXPECT_TRUE(map.empty()); EXPECT_FALSE(map.pullUpdated());
  EXPECT_EQ(ds.pos(), 6u); // count + tag + int32 key; value read has not consumed bytes.
  mutationTrace("typed_load_read_failure");
}

TEST(NetMapMutation, TypedStoreWritesTagBeforeKeyAndPreservesOriginalException) {
  MutationScope scope;
  MutationMap map; map.set(MutationKey(7), MutationValue(70)); map.pullUpdated();
  DataStreamBuffer actual, expected;
  expected.writeVlqU(1); expected.write<uint8_t>(0);
  auto error = std::make_exception_ptr(MutationDerivedFailure{});
  MutationLog::events.clear();
  MutationLog::hook = [&](std::string const& event) {
    if (event == "key.write:7") std::rethrow_exception(error);
  };
  sameMutationException(error, [&] { map.netStore(actual); }); MutationLog::hook = {};
  EXPECT_EQ(actual.data(), expected.data()); EXPECT_EQ(eventCount("value.write:70"), 0u);
  EXPECT_EQ(map.get(MutationKey(7)).n, 70); EXPECT_FALSE(map.pullUpdated());
  mutationTrace("typed_store_key_failure", &actual);
}

TEST(NetMapMutation, TypedCodecSetRemoveClearAndInvalidTagUseOrdinaryDeltaEntry) {
  MutationScope scope;
  MutationMap map;
  DataStreamBuffer wire;
  deltaSet(wire, 1, 10); deltaRemove(wire, 1); deltaClear(wire);
  deltaSet(wire, 2, 20); wire.writeVlqU(0); wire.seek(0);
  map.readNetDelta(wire);
  EXPECT_TRUE(wire.atEnd()); ASSERT_EQ(map.size(), 1u);
  EXPECT_EQ(map.get(MutationKey(2)).n, 20); EXPECT_TRUE(map.pullUpdated());
  mutationTrace("typed_set_remove_clear", &wire);
  DataStreamBuffer invalid;
  invalid.writeVlqU(2); invalid.write<uint8_t>(3); invalid.write<uint8_t>(0x5a); invalid.seek(0);
  IOException expected("Improper type code received in NetElementMapWrapper::readChange");
  try { map.readNetDelta(invalid); FAIL(); }
  catch (IOException const& e) { EXPECT_STREQ(e.what(), expected.what()); }
  EXPECT_EQ(invalid.read<uint8_t>(), 0x5a);
  EXPECT_EQ(map.get(MutationKey(2)).n, 20); EXPECT_FALSE(map.pullUpdated());
}
