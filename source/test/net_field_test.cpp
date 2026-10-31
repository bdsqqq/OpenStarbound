#include "StarDataStreamDevices.hpp"
#include "StarNetElementBasicFields.hpp"

#include "gtest/gtest.h"

#include <exception>
#include <functional>
#include <iostream>
#include <string>

#ifdef STAR_USE_RUST_NET_FIELD
#include "StarRustNetField.h"
#endif

using namespace Star;

namespace {
struct FieldMarker : std::exception {};
struct DerivedFieldMarker : FieldMarker {};

struct FieldTrace {
  std::string events;
  std::exception_ptr error = std::make_exception_ptr(DerivedFieldMarker{});
  int live = 0;
  int copyFailure = -999;
  int assignFailure = -999;
  int readFailure = -999;
  int writeFailure = -999;
  int updatedFailure = -999;

  void log(std::string const& event) { events += event + ","; }
  [[noreturn]] void raise() { std::rethrow_exception(error); }
  void emit(char const* name) const {
    std::cout << "NET_FIELD_TRACE " << name << ' ' << events << '\n';
  }
};

struct TrackedFieldValue {
  static FieldTrace* trace;
  int value;
  explicit TrackedFieldValue(int v = 0) : value(v) {
    if (trace) { ++trace->live; trace->log("N" + std::to_string(value)); }
  }
  TrackedFieldValue(TrackedFieldValue const& other) : value(other.value) {
    if (trace) {
      trace->log("C" + std::to_string(value));
      if (trace->copyFailure == value) trace->raise();
      ++trace->live;
    }
  }
  TrackedFieldValue(TrackedFieldValue&& other) : value(other.value) {
    if (trace) { ++trace->live; trace->log("M" + std::to_string(value)); }
    other.value = -value;
  }
  TrackedFieldValue& operator=(TrackedFieldValue const& other) {
    value = other.value;
    if (trace) {
      trace->log("A" + std::to_string(value));
      if (trace->assignFailure == value) { value += 100; trace->raise(); }
    }
    return *this;
  }
  TrackedFieldValue& operator=(TrackedFieldValue&& other) {
    value = other.value;
    if (trace) {
      trace->log("a" + std::to_string(value));
      if (trace->assignFailure == value) { value += 100; trace->raise(); }
    }
    other.value = -value;
    return *this;
  }
  ~TrackedFieldValue() {
    if (trace) { --trace->live; trace->log("D" + std::to_string(value)); }
  }
  bool operator==(TrackedFieldValue const& other) const { return value == other.value; }
};
FieldTrace* TrackedFieldValue::trace = nullptr;

struct FieldTracing {
  FieldTrace* previous;
  explicit FieldTracing(FieldTrace& trace) : previous(TrackedFieldValue::trace) {
    TrackedFieldValue::trace = &trace;
  }
  ~FieldTracing() { TrackedFieldValue::trace = previous; }
};

int fieldValue(int value) { return value; }
int fieldValue(TrackedFieldValue const& value) { return value.value; }
void fieldAssign(int& target, int value) { target = value; }
void fieldAssign(TrackedFieldValue& target, int value) { target.value = value; }

// Deliberately no equality operator: only set(), not the field's other
// operations or its virtual table, is allowed to require equality.
struct NonComparablePayload { int value = 0; };
int fieldValue(NonComparablePayload const& value) { return value.value; }
void fieldAssign(NonComparablePayload& target, int value) { target.value = value; }

struct ProxyPayload;
int fieldValue(ProxyPayload const& value);
void fieldAssign(ProxyPayload& target, int value);

template <typename T>
struct DerivedField : NetElementBasicField<T> {
  FieldTrace* trace = nullptr;
  NetElementVersion const* observedVersion = nullptr;
  bool probing = false;
  std::string observedWrites;
  int updates = 0;

  void readData(DataStream& ds, T& value) const override {
    auto byte = ds.read<uint8_t>();
    fieldAssign(value, byte);
    if (trace) {
      trace->log("R" + std::to_string(byte));
      if (trace->readFailure == byte) trace->raise();
    }
  }
  void writeData(DataStream& ds, T const& value) const override {
    int v = fieldValue(value);
    if (trace) trace->log("W" + std::to_string(v));
    ds.write(static_cast<uint8_t>(v));
    if (trace && trace->writeFailure == v) trace->raise();
  }
  void updated() override {
    NetElementBasicField<T>::updated();
    ++updates;
    if (trace) trace->log("U" + std::to_string(fieldValue(this->get())));
    if (observedVersion && !probing) {
      probing = true;
      DataStreamBuffer wire;
      bool written = this->writeNetDelta(wire, observedVersion->current());
      observedWrites += written ? "1" : "0";
      if (trace) trace->log(written ? "visible1" : "visible0");
      probing = false;
    }
    if (trace && trace->updatedFailure == fieldValue(this->get())) trace->raise();
  }
};

template <typename Function>
void fieldFailure(FieldTrace& trace, Function function) {
  try {
    function();
    FAIL() << "expected original derived marker";
  } catch (DerivedFieldMarker const&) {
    EXPECT_EQ(std::current_exception(), trace.error);
    trace.log("caught");
  }
}

void fieldBytes(char const* name, DataStreamBuffer const& wire) {
  static char const hex[] = "0123456789abcdef";
  std::string bytes;
  for (size_t i = 0; i != wire.size(); ++i) {
    auto byte = static_cast<unsigned char>(wire.ptr()[i]);
    bytes += hex[byte >> 4];
    bytes += hex[byte & 15];
  }
  std::cout << "NET_FIELD_TRACE " << name << ' ' << bytes << '\n';
}

template <typename T>
void fieldRead(DerivedField<T>& field, int value, float delay = 0.0f) {
  DataStreamBuffer wire;
  wire.write(static_cast<uint8_t>(value));
  wire.seek(0);
  field.readNetDelta(wire, delay);
  EXPECT_TRUE(wire.atEnd());
}

template <typename T>
void expectFieldWire(DerivedField<T> const& field, int value, char const* name) {
  DataStreamBuffer stored;
  field.netStore(stored);
  DataStreamBuffer expected;
  expected.write(static_cast<uint8_t>(value));
  EXPECT_EQ(stored.data(), expected.data());
  DataStreamBuffer delta;
  EXPECT_TRUE(field.writeNetDelta(delta, 0));
  EXPECT_EQ(delta.data(), expected.data());
  fieldBytes(name, stored);
  fieldBytes("delta", delta);
}

struct LvalueMutator {
  FieldTrace& trace;
  bool result;
  LvalueMutator(FieldTrace& trace, bool result) : trace(trace), result(result) {}
  LvalueMutator(LvalueMutator const&) = delete;
  LvalueMutator(LvalueMutator&&) = delete;
  bool operator()(TrackedFieldValue& value) & {
    trace.log("call-lvalue");
    value.value += 1;
    return result;
  }
  bool operator()(TrackedFieldValue&) && = delete;
};

// Equality's overloaded ! deliberately disagrees with bool conversion.
// Keeping state in the C++ scope also exposes full-expression destruction.
struct EqualityProxy {
  FieldTrace* trace;
  bool equal;
  explicit operator bool() const { trace->log("eq-bool"); return equal; }
  bool operator!() const { trace->log("eq-not"); return true; }
  ~EqualityProxy() { trace->log("eq-dtor"); }
};
struct ProxyPayload {
  int value = 0;
  FieldTrace* trace = nullptr;
  ProxyPayload() = default;
  ProxyPayload(int value, FieldTrace& trace) : value(value), trace(&trace) {}
  ProxyPayload(ProxyPayload const& other) : value(other.value), trace(other.trace) {
    if (trace) trace->log("proxy-copy");
  }
  ProxyPayload(ProxyPayload&&) = default;
  ProxyPayload& operator=(ProxyPayload const&) = default;
  ProxyPayload& operator=(ProxyPayload&&) = default;
  EqualityProxy operator==(ProxyPayload const& other) const {
    return {other.trace, value == other.value};
  }
};
int fieldValue(ProxyPayload const& value) { return value.value; }
void fieldAssign(ProxyPayload& target, int value) { target.value = value; }

struct ConditionalProxy {
  FieldTrace& trace;
  explicit operator bool() const { trace.log("condition-bool"); return true; }
  ~ConditionalProxy() { trace.log("condition-dtor"); }
};
}

TEST(NetFieldPolicy, DefaultSetPushAndNonComparableVirtualWire) {
  DerivedField<int> field;
  EXPECT_EQ(field.get(), 0);
  EXPECT_FALSE(field.pullUpdated());
  field.set(0);
  EXPECT_FALSE(field.pullUpdated());
  field.set(17);
  EXPECT_EQ(field.get(), 17);
  EXPECT_TRUE(field.pullUpdated());
  EXPECT_FALSE(field.pullUpdated());
  field.set(17);
  EXPECT_FALSE(field.pullUpdated());
  field.push(17);
  EXPECT_TRUE(field.pullUpdated());
  EXPECT_EQ(field.updates, 2);
  expectFieldWire(field, 17, "default-set-push");

  DerivedField<NonComparablePayload> noEquality;
  NonComparablePayload payload;
  payload.value = 29;
  noEquality.push(payload);
  EXPECT_EQ(noEquality.get().value, 29);
  expectFieldWire(noEquality, 29, "no-equality");
  fieldRead(noEquality, 31);
  EXPECT_EQ(noEquality.get().value, 31);
}

#ifdef STAR_NET_FIELD_NO_EQUAL_NEGATIVE
// Parent compiles this negative control under BOTH selectors. A policy thunk
// must not eagerly instantiate set's equality requirement for ordinary push.
void netFieldNoEqualNegative() {
  DerivedField<NonComparablePayload> field;
  NonComparablePayload payload;
  field.set(payload);
}
#endif

TEST(NetFieldPolicy, SetOverloadedNotAndMutatorConditionDestroyBeforeUpdated) {
  FieldTrace trace;
  {
    DerivedField<ProxyPayload> field;
    field.trace = &trace;
    ProxyPayload value(0, trace);
    field.set(value); // Equal values still push because native operator! says so.
    EXPECT_EQ(field.updates, 1);
    EXPECT_EQ(trace.events.find("eq-bool"), std::string::npos);
    EXPECT_LT(trace.events.find("eq-not,"), trace.events.find("eq-dtor,"));
    EXPECT_LT(trace.events.find("eq-dtor,"), trace.events.find("proxy-copy,"));
    EXPECT_LT(trace.events.find("proxy-copy,"), trace.events.find("U0,"));
    trace.log("set-return");
    field.update([&](ProxyPayload&) { return ConditionalProxy{trace}; });
    EXPECT_LT(trace.events.find("condition-bool,"), trace.events.find("condition-dtor,"));
    EXPECT_LT(trace.events.find("condition-dtor,"), trace.events.rfind("U0,"));
  }
  trace.emit("cpp-condition-scope");
}

TEST(NetFieldPolicy, NamedMutatorIsLvalueAndFalseStillMutatesWithoutVersionOrClear) {
  FieldTrace trace;
  FieldTracing tracing(trace);
  {
    DerivedField<TrackedFieldValue> field;
    field.trace = &trace;
    NetElementVersion version;
    field.initNetVersion(&version);
    version.increment();
    field.push(TrackedFieldValue(10));
    field.pullUpdated();
    field.enableNetInterpolation();
    fieldRead(field, 22, 0.5f);
    int updates = field.updates;
    version.increment();
    field.update(LvalueMutator(trace, false));
    EXPECT_EQ(field.get().value, 11);
    EXPECT_EQ(field.updates, updates);
    EXPECT_FALSE(field.pullUpdated());
    expectFieldWire(field, 22, "false-mutator-keeps-pending");
    DataStreamBuffer future;
    EXPECT_FALSE(field.writeNetDelta(future, uint64_t(2)));
    field.update(LvalueMutator(trace, true));
    EXPECT_EQ(field.get().value, 12);
    EXPECT_TRUE(field.pullUpdated());
    field.tickNetInterpolation(1.0f);
    EXPECT_EQ(field.get().value, 12);
    expectFieldWire(field, 12, "true-mutator-clears");
    EXPECT_TRUE(field.writeNetDelta(future, uint64_t(2)));
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("named-lvalue-mutator");
}

TEST(NetFieldPolicy, UpdatedSeesOldPushUpdateVersionAndNewLoadReadVersion) {
  FieldTrace trace;
  DerivedField<int> field;
  field.trace = &trace;
  NetElementVersion version;
  field.initNetVersion(&version);
  field.observedVersion = &version;
  for (int i = 0; i != 3; ++i) version.increment();
  EXPECT_EQ(version.current(), uint64_t(3));
  field.push(11);
  version.increment();
  field.update([](int& value) { value = 22; return true; });
  version.increment();
  DataStreamBuffer loaded;
  loaded.write(uint8_t(33));
  loaded.seek(0);
  field.netLoad(loaded, {});
  EXPECT_TRUE(loaded.atEnd());
  version.increment();
  fieldRead(field, 44);
  EXPECT_EQ(field.observedWrites, "0011");
  DataStreamBuffer current;
  EXPECT_TRUE(field.writeNetDelta(current, uint64_t(6)));
  EXPECT_EQ(current.size(), 1u);
  fieldBytes("inclusive-version6", current);
  DataStreamBuffer future;
  EXPECT_FALSE(field.writeNetDelta(future, uint64_t(7)));
  EXPECT_TRUE(future.empty());
  // init only resets latest version: current value, update flag and pending stay.
  field.enableNetInterpolation();
  fieldRead(field, 55, 0.5f);
  field.initNetVersion();
  EXPECT_TRUE(field.pullUpdated());
  EXPECT_FALSE(field.writeNetDelta(future, uint64_t(1)));
  expectFieldWire(field, 55, "init-preserves-pending");
  field.observedVersion = nullptr;
  field.tickNetInterpolation(0.5f);
  EXPECT_EQ(field.get(), 55);
  trace.emit("virtual-updated-version-order");
}

TEST(NetFieldPolicy, FiniteDelayAppendEqualSmallerNegativeAndDisabledBranches) {
  DerivedField<int> field;
  fieldRead(field, 11, 1.0f); // No pending storage: positive delay is immediate.
  EXPECT_EQ(field.get(), 11);
  EXPECT_TRUE(field.pullUpdated());
  field.enableNetInterpolation(-0.25f);
  fieldRead(field, 22, 0.5f);
  field.enableNetInterpolation(4.0f); // Idempotent: does not drop 22.
  fieldRead(field, 33, 0.5f); // Equal is append, not immediate/reset.
  EXPECT_EQ(field.get(), 11);
  EXPECT_FALSE(field.pullUpdated());
  expectFieldWire(field, 33, "equal-delay-latest");
  field.tickNetInterpolation(-0.25f);
  field.tickNetInterpolation(0.5f);
  EXPECT_EQ(field.get(), 11);
  field.tickNetInterpolation(0.25f);
  EXPECT_EQ(field.get(), 33);
  EXPECT_EQ(field.updates, 3);
  EXPECT_TRUE(field.pullUpdated());
  fieldRead(field, 44, 1.0f);
  fieldRead(field, 55, 0.5f); // Smaller than tail: immediate, clear first.
  EXPECT_EQ(field.get(), 55);
  EXPECT_TRUE(field.pullUpdated());
  field.tickNetInterpolation(2.0f);
  EXPECT_EQ(field.get(), 55);
  for (float delay : {0.0f, -0.25f}) {
    fieldRead(field, 66, 0.5f);
    fieldRead(field, 77, delay);
    EXPECT_EQ(field.get(), 77);
    expectFieldWire(field, 77, "nonpositive-clears");
  }
}

TEST(NetFieldPolicy, DisableTakesLastWithoutUpdatedAndTickDoesNotResampleVersion) {
  FieldTrace trace;
  FieldTracing tracing(trace);
  {
    DerivedField<TrackedFieldValue> field;
    field.trace = &trace;
    NetElementVersion version;
    field.initNetVersion(&version);
    version.increment();
    field.enableNetInterpolation();
    fieldRead(field, 11, 0.25f);
    fieldRead(field, 22, 0.5f);
    version.increment();
    field.disableNetInterpolation();
    EXPECT_EQ(field.get().value, 22);
    EXPECT_FALSE(field.pullUpdated());
    EXPECT_EQ(field.updates, 0);
    DataStreamBuffer future;
    EXPECT_FALSE(field.writeNetDelta(future, uint64_t(2)));
    fieldRead(field, 33, 1.0f);
    EXPECT_EQ(field.get().value, 33); // Disabled really means immediate.
    EXPECT_TRUE(field.pullUpdated());
    field.enableNetInterpolation();
    fieldRead(field, 44, 0.25f);
    version.increment();
    field.tickNetInterpolation(0.25f);
    EXPECT_EQ(field.get().value, 44);
    EXPECT_TRUE(field.pullUpdated());
    EXPECT_FALSE(field.writeNetDelta(future, uint64_t(3)));
    expectFieldWire(field, 44, "tick-keeps-read-version");
    field.disableNetInterpolation();
    field.disableNetInterpolation();
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("disable-tick-lifetimes");
}

TEST(NetFieldPolicy, ThrowingCopyAndAssignmentPreserveNativePartialPushState) {
  FieldTrace trace;
  FieldTracing tracing(trace);
  {
    DerivedField<TrackedFieldValue> field;
    field.trace = &trace;
    field.push(TrackedFieldValue(11));
    field.pullUpdated();
    field.enableNetInterpolation();
    fieldRead(field, 33, 0.5f);
    TrackedFieldValue input(22);
    trace.copyFailure = 22;
    fieldFailure(trace, [&] { field.set(input); });
    EXPECT_EQ(field.get().value, 11);
    EXPECT_FALSE(field.pullUpdated());
    expectFieldWire(field, 33, "copy-failure-keeps-pending");
    trace.copyFailure = -999;
    trace.assignFailure = 22;
    fieldFailure(trace, [&] { field.push(TrackedFieldValue(22)); });
    EXPECT_EQ(field.get().value, 122); // Assignment mutated its target before throw.
    EXPECT_FALSE(field.pullUpdated());
    expectFieldWire(field, 33, "push-partial-assignment");
    trace.assignFailure = -999;
    field.tickNetInterpolation(0.5f);
    EXPECT_EQ(field.get().value, 33);
    field.pullUpdated();

    // A throwing virtual updated runs after assignment but before PUSH's
    // version capture and clear. LOAD captures version before that same hook.
    NetElementVersion version;
    field.initNetVersion(&version);
    version.increment();
    fieldRead(field, 44, 1.0f);
    version.increment();
    trace.updatedFailure = 55;
    fieldFailure(trace, [&] { field.push(TrackedFieldValue(55)); });
    EXPECT_EQ(field.get().value, 55);
    EXPECT_TRUE(field.pullUpdated()); // Base updated already ran.
    DataStreamBuffer future;
    EXPECT_FALSE(field.writeNetDelta(future, uint64_t(2)));
    expectFieldWire(field, 44, "throwing-push-updated-keeps-pending");
    DataStreamBuffer load;
    load.write(uint8_t(55));
    load.seek(0);
    fieldFailure(trace, [&] { field.netLoad(load, {}); });
    EXPECT_TRUE(load.atEnd());
    EXPECT_TRUE(field.writeNetDelta(future, uint64_t(2)));
    expectFieldWire(field, 44, "throwing-load-updated-keeps-pending");
    trace.updatedFailure = -999;
    trace.log("before-mutator-throw");
    fieldFailure(trace, [&] {
      field.update([&](TrackedFieldValue& value) -> bool {
        value.value = 66;
        trace.raise();
      });
    });
    EXPECT_EQ(field.get().value, 66);
    expectFieldWire(field, 44, "throwing-mutator-keeps-pending");
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("copy-and-push-assignment-failure");
}

TEST(NetFieldPolicy, DisableAssignmentFailureAlreadyPoppedLastButKeepsPendingEngaged) {
  FieldTrace trace;
  FieldTracing tracing(trace);
  {
    DerivedField<TrackedFieldValue> field;
    field.trace = &trace;
    field.enableNetInterpolation();
    fieldRead(field, 11, 0.25f);
    fieldRead(field, 22, 0.5f);
    trace.assignFailure = 22;
    fieldFailure(trace, [&] { field.disableNetInterpolation(); });
    EXPECT_EQ(field.get().value, 122);
    EXPECT_FALSE(field.pullUpdated());
    expectFieldWire(field, 11, "disable-popped-last");
    trace.assignFailure = -999;
    fieldRead(field, 33, 0.5f); // Still enabled, appends after surviving 11.
    EXPECT_EQ(field.get().value, 122);
    field.tickNetInterpolation(0.25f);
    EXPECT_EQ(field.get().value, 11);
    field.tickNetInterpolation(0.25f);
    EXPECT_EQ(field.get().value, 33);
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("disable-partial-assignment");
}

TEST(NetFieldPolicy, TickFailureLosesPoppedValueAfterAllTimersWereDecremented) {
  FieldTrace trace;
  FieldTracing tracing(trace);
  {
    DerivedField<TrackedFieldValue> field;
    field.trace = &trace;
    field.enableNetInterpolation();
    fieldRead(field, 11, 0.25f);
    fieldRead(field, 22, 0.5f);
    fieldRead(field, 33, 1.0f);
    trace.events.clear();
    trace.assignFailure = 22;
    fieldFailure(trace, [&] { field.tickNetInterpolation(0.5f); });
    EXPECT_EQ(field.get().value, 122);
    EXPECT_EQ(field.updates, 1);
    EXPECT_TRUE(field.pullUpdated());
    EXPECT_NE(trace.events.find("U11,"), std::string::npos);
    EXPECT_EQ(trace.events.find("U122,"), std::string::npos);
    trace.assignFailure = -999;
    field.tickNetInterpolation(0.0f);
    EXPECT_EQ(field.get().value, 122); // Failed 22 was popped, not retried.
    EXPECT_FALSE(field.pullUpdated());
    field.tickNetInterpolation(0.5f);
    EXPECT_EQ(field.get().value, 33); // Tail's time was decremented before throw.
    EXPECT_TRUE(field.pullUpdated());
    expectFieldWire(field, 33, "tick-failure-surviving-tail");
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("tick-pop-assignment-failure");
}

TEST(NetFieldPolicy, LoadReadsDirectlyButReadFailureDiscardsTemporaryAndKeepsVersion) {
  FieldTrace trace;
  FieldTracing tracing(trace);
  {
    NetElementVersion version;
    DerivedField<TrackedFieldValue> field;
    field.trace = &trace;
    field.initNetVersion(&version);
    version.increment();
    field.push(TrackedFieldValue(11));
    field.pullUpdated();
    field.enableNetInterpolation();
    fieldRead(field, 33, 1.0f);
    version.increment();
    trace.readFailure = 22;
    DataStreamBuffer load;
    load.write(uint8_t(22));
    load.write(uint8_t(99));
    load.seek(0);
    fieldFailure(trace, [&] { field.netLoad(load, {}); });
    EXPECT_EQ(load.pos(), 1u);
    EXPECT_EQ(field.get().value, 22); // Direct read's mutation persists.
    EXPECT_FALSE(field.pullUpdated());
    expectFieldWire(field, 33, "failed-load-still-stores-pending");
    DataStreamBuffer delta;
    delta.write(uint8_t(22));
    delta.write(uint8_t(88));
    delta.seek(0);
    trace.emit("load-failure-before-read");
    trace.events.clear();
    fieldFailure(trace, [&] { field.readNetDelta(delta, 0.5f); });
    EXPECT_EQ(delta.pos(), 1u);
    EXPECT_EQ(field.get().value, 22); // Local failed t was discarded.
    EXPECT_EQ(trace.events, "N0,R22,D22,caught,");
    DataStreamBuffer future;
    EXPECT_FALSE(field.writeNetDelta(future, uint64_t(2)));
    trace.readFailure = -999;
    trace.assignFailure = 44;
    fieldFailure(trace, [&] { fieldRead(field, 44, 0.0f); });
    EXPECT_EQ(field.get().value, 144);
    EXPECT_FALSE(field.pullUpdated());
    // READ sampled the new version before assignment failed, but didn't clear.
    EXPECT_TRUE(field.writeNetDelta(future, uint64_t(2)));
    expectFieldWire(field, 33, "read-assignment-failure-keeps-pending");
    trace.assignFailure = -999;
    fieldRead(field, 44, 0.0f);
    EXPECT_EQ(field.get().value, 44);
    EXPECT_TRUE(field.pullUpdated());
    expectFieldWire(field, 44, "successful-read-clears-pending");
    fieldRead(field, 55, 0.5f);
    trace.updatedFailure = 66;
    fieldFailure(trace, [&] { fieldRead(field, 66); });
    EXPECT_EQ(field.get().value, 66);
    EXPECT_TRUE(field.pullUpdated());
    expectFieldWire(field, 66, "throwing-read-updated-already-cleared");
    trace.updatedFailure = -999;
    field.tickNetInterpolation(1.0f);
    EXPECT_EQ(field.get().value, 66);
    EXPECT_FALSE(field.pullUpdated());
    fieldRead(field, 77, 0.5f);
    DataStreamBuffer goodLoad;
    goodLoad.write(uint8_t(88));
    goodLoad.seek(0);
    field.netLoad(goodLoad, {});
    EXPECT_TRUE(goodLoad.atEnd());
    EXPECT_EQ(field.get().value, 88);
    EXPECT_TRUE(field.pullUpdated());
    field.tickNetInterpolation(1.0f);
    EXPECT_EQ(field.get().value, 88);
    EXPECT_FALSE(field.pullUpdated());
    expectFieldWire(field, 88, "successful-load-clears-pending");
    fieldBytes("load-consumed-prefix", load);
    fieldBytes("read-consumed-prefix", delta);
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("load-versus-read-failure");
}

TEST(NetFieldPolicy, CompatibilityAndVersionGuardsPrecedeVirtualWireAndKeepPrefixes) {
  FieldTrace trace;
  DerivedField<int> field;
  field.trace = &trace;
  NetElementVersion version;
  field.initNetVersion(&version);
  version.increment();
  field.push(17);
  field.pullUpdated();
  field.setCompatibilityVersion(static_cast<VersionNumber>(1));
  auto rejected = NetCompatibilityRules(LegacyVersion);
  DataStreamBuffer wire;
  wire.write(uint8_t(0xaa));
  wire.seek(0);
  trace.events.clear();
  field.netLoad(wire, rejected);
  field.readNetDelta(wire, 0.5f, rejected);
  field.netStore(wire, rejected);
  EXPECT_FALSE(field.writeNetDelta(wire, 0, rejected));
  EXPECT_EQ(wire.pos(), 0u);
  EXPECT_EQ(wire.size(), 1u);
  EXPECT_EQ(field.get(), 17);
  EXPECT_FALSE(field.pullUpdated());
  EXPECT_TRUE(trace.events.empty());
  auto accepted = NetCompatibilityRules(static_cast<VersionNumber>(1));
  EXPECT_FALSE(field.writeNetDelta(wire, uint64_t(2), accepted));
  EXPECT_TRUE(trace.events.empty());
  wire.seek(1);
  trace.writeFailure = 17;
  fieldFailure(trace, [&] { field.writeNetDelta(wire, uint64_t(1), accepted); });
  EXPECT_EQ(wire.size(), 2u);
  EXPECT_EQ(static_cast<unsigned char>(wire.ptr()[0]), 0xaau);
  EXPECT_EQ(static_cast<unsigned char>(wire.ptr()[1]), 17u);
  fieldBytes("writer-failure-full-prefix", wire);
  trace.emit("guards-and-serializer-failure");
}

#ifdef STAR_USE_RUST_NET_FIELD
TEST(NetFieldPolicy, RustCountersExposeNestedSetPushAndGuardedWireRoots) {
  auto set = sb_net_field_count(0, SB_NET_FIELD_SET);
  auto push = sb_net_field_count(0, SB_NET_FIELD_PUSH);
  auto write = sb_net_field_count(0, SB_NET_FIELD_WRITE);
  auto changed = sb_net_field_count(2, SB_NET_FIELD_CHANGED);
  auto copy = sb_net_field_count(2, SB_NET_FIELD_PUSH_COPY);
  DerivedField<int> field;
  field.set(0);
  field.set(17); // Natural nested PUSH, not an artificial selector call.
  field.set(17);
  field.push(18);
  EXPECT_EQ(sb_net_field_count(0, SB_NET_FIELD_SET) - set, uint64_t(3));
  EXPECT_EQ(sb_net_field_count(0, SB_NET_FIELD_PUSH) - push, uint64_t(2));
  EXPECT_EQ(sb_net_field_count(2, SB_NET_FIELD_CHANGED) - changed, uint64_t(3));
  EXPECT_EQ(sb_net_field_count(2, SB_NET_FIELD_PUSH_COPY) - copy, uint64_t(1));
  DataStreamBuffer wire;
  EXPECT_FALSE(field.writeNetDelta(wire, uint64_t(1)));
  EXPECT_TRUE(wire.empty());
  EXPECT_TRUE(field.writeNetDelta(wire, uint64_t(0)));
  field.setCompatibilityVersion(static_cast<VersionNumber>(1));
  EXPECT_FALSE(field.writeNetDelta(wire, 0, NetCompatibilityRules(LegacyVersion)));
  EXPECT_EQ(sb_net_field_count(0, SB_NET_FIELD_WRITE) - write, uint64_t(2));
  EXPECT_EQ(sb_net_field_count(0, SB_NET_FIELD_COUNT), uint64_t(0));
  EXPECT_EQ(sb_net_field_count(2, SB_NET_FIELD_OP_COUNT), uint64_t(0));
  std::cout << "NET_FIELD_DIAGNOSTIC counter-natural-roots bytes=" << wire.size() << '\n';
}
#endif
