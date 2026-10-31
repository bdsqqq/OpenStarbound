#include "StarDataStreamDevices.hpp"
#include "StarNetElementSignal.hpp"

#include "gtest/gtest.h"

#include <exception>
#include <functional>
#include <iostream>
#include <string>

#ifdef STAR_USE_RUST_NET_SIGNAL
#include "StarRustNetSignal.h"
#endif

using namespace Star;

namespace {
struct SignalMarker : std::exception {};
struct DerivedSignalMarker : SignalMarker {};

struct SignalTrace {
  std::string events;
  std::exception_ptr error = std::make_exception_ptr(DerivedSignalMarker{});
  int copyFailure = -999;
  int writeFailure = -999;
  int readFailure = -999;
  int live = 0;
  std::function<void(int)> copied;

  void log(std::string const& event) { events += event + ","; }
  [[noreturn]] void raise() { std::rethrow_exception(error); }
  void emit(char const* name) const {
    std::cout << "NET_SIGNAL_TRACE " << name << ' ' << events << '\n';
  }
};

struct TrackedSignal {
  static SignalTrace* trace;
  int value;

  explicit TrackedSignal(int value = 0) : value(value) {
    if (trace) { ++trace->live; trace->log("N" + std::to_string(value)); }
  }
  TrackedSignal(TrackedSignal const& other) : value(other.value) {
    if (trace) {
      trace->log("C" + std::to_string(value));
      if (trace->copyFailure == value) trace->raise();
      if (trace->copied) trace->copied(value);
      ++trace->live;
    }
  }
  TrackedSignal(TrackedSignal&& other) : value(other.value) {
    if (trace) { ++trace->live; trace->log("M" + std::to_string(value)); }
    other.value = -value;
  }
  TrackedSignal& operator=(TrackedSignal const&) = default;
  TrackedSignal& operator=(TrackedSignal&&) = default;
  ~TrackedSignal() {
    if (trace) { --trace->live; trace->log("D" + std::to_string(value)); }
  }
};
SignalTrace* TrackedSignal::trace = nullptr;

// These are real typed DataStream hooks, including a failure after a visible
// byte. The selector must not replace serialization or roll back that prefix.
DataStream& operator<<(DataStream& stream, TrackedSignal const& signal) {
  if (TrackedSignal::trace)
    TrackedSignal::trace->log("W" + std::to_string(signal.value));
  stream << static_cast<uint8_t>(signal.value);
  if (TrackedSignal::trace && TrackedSignal::trace->writeFailure == signal.value)
    TrackedSignal::trace->raise();
  return stream;
}

DataStream& operator>>(DataStream& stream, TrackedSignal& signal) {
  uint8_t value;
  stream >> value;
  signal.value = value;
  if (TrackedSignal::trace) {
    TrackedSignal::trace->log("R" + std::to_string(signal.value));
    if (TrackedSignal::trace->readFailure == signal.value)
      TrackedSignal::trace->raise();
  }
  return stream;
}

struct SignalTracing {
  SignalTrace* previous;
  explicit SignalTracing(SignalTrace& trace) : previous(TrackedSignal::trace) {
    TrackedSignal::trace = &trace;
  }
  ~SignalTracing() { TrackedSignal::trace = previous; }
};

template <typename Function>
void signalFailure(SignalTrace& trace, Function function) {
  try {
    function();
    FAIL() << "expected original derived marker";
  } catch (DerivedSignalMarker const&) {
    EXPECT_EQ(std::current_exception(), trace.error);
    trace.log("caught");
  }
}

List<int> signalValues(List<TrackedSignal> const& signals) {
  List<int> values;
  for (auto const& signal : signals)
    values.append(signal.value);
  return values;
}

void signalBytes(char const* name, DataStreamBuffer const& stream) {
  static char const hex[] = "0123456789abcdef";
  std::string bytes;
  for (size_t i = 0; i != stream.size(); ++i) {
    auto byte = static_cast<unsigned char>(stream.ptr()[i]);
    bytes += hex[byte >> 4];
    bytes += hex[byte & 15];
  }
  std::cout << "NET_SIGNAL_TRACE " << name << ' ' << bytes << '\n';
}

void expectIntWire(DataStreamBuffer& actual, List<int> const& values) {
  DataStreamBuffer expected;
  expected.writeVlqU(values.size());
  for (int value : values)
    expected.write(value);
  EXPECT_EQ(actual.data(), expected.data());
  actual.seek(0);
  EXPECT_EQ(actual.readVlqU(), values.size());
  for (int value : values)
    EXPECT_EQ(actual.read<int>(), value);
  EXPECT_TRUE(actual.atEnd());
}
}

TEST(NetSignalPolicy, DefaultVersionQueueBoundsAndReceiveOnce) {
  for (size_t capacity : {size_t(0), size_t(1), size_t(3)}) {
    NetElementSignal<int> signal(capacity);
    EXPECT_TRUE(signal.receive().empty());
    for (int value : {11, 22, 33, 44})
      signal.send(value);
    List<int> expected;
    if (capacity == 1) expected = {44};
    if (capacity == 3) expected = {22, 33, 44};
    EXPECT_EQ(signal.receive(), expected);
    EXPECT_TRUE(signal.receive().empty());
    DataStreamBuffer wire;
    EXPECT_EQ(signal.writeNetDelta(wire, 0), capacity != 0);
    if (capacity) expectIntWire(wire, expected);
    else EXPECT_TRUE(wire.empty());
    signalBytes(capacity == 0 ? "queue0" : capacity == 1 ? "queue1" : "queue3", wire);
    DataStreamBuffer later;
    EXPECT_FALSE(signal.writeNetDelta(later, 1));
    EXPECT_TRUE(later.empty());
    signal.send(55);
    EXPECT_EQ(signal.receive(), capacity ? List<int>({55}) : List<int>());
  }
}

TEST(NetSignalPolicy, InclusiveVersionWireAndUninterpolatedRoundTrip) {
  NetElementVersion version;
  NetElementSignal<int> sender(3);
  sender.initNetVersion(&version);
  EXPECT_EQ(version.increment(), 1u);
  sender.send(101);
  EXPECT_EQ(version.increment(), 2u);
  sender.send(202);
  sender.send(203);
  EXPECT_EQ(version.increment(), 3u);
  sender.send(303); // Evicts version 1, but keeps both version 2 entries.
  for (uint64_t threshold : {uint64_t(0), uint64_t(2), uint64_t(3)}) {
    List<int> expected = threshold == 3 ? List<int>({303}) : List<int>({202, 203, 303});
    DataStreamBuffer wire;
    ASSERT_TRUE(sender.writeNetDelta(wire, threshold));
    expectIntWire(wire, expected);
    signalBytes(threshold == 0 ? "version0" : threshold == 2 ? "version2" : "version3", wire);
    wire.seek(0);
    NetElementSignal<int> receiver(3);
    receiver.disableNetInterpolation();
    receiver.readNetDelta(wire);
    EXPECT_TRUE(wire.atEnd());
    EXPECT_EQ(receiver.receive(), expected);
    EXPECT_TRUE(receiver.receive().empty());
    DataStreamBuffer forwarded;
    ASSERT_TRUE(receiver.writeNetDelta(forwarded, 0));
    EXPECT_EQ(forwarded.data(), wire.data());
  }
  DataStreamBuffer future;
  EXPECT_FALSE(sender.writeNetDelta(future, 4));
  EXPECT_TRUE(future.empty());
  sender.initNetVersion();
  EXPECT_TRUE(sender.receive().empty());
  EXPECT_FALSE(sender.writeNetDelta(future, 0));
}

TEST(NetSignalPolicy, MultiByteVlqCountAndCompletePayload) {
  NetElementSignal<int> sender(130);
  List<int> values;
  for (int i = 0; i != 130; ++i) {
    values.append(i * 17);
    sender.send(i * 17);
  }
  DataStreamBuffer wire;
  ASSERT_TRUE(sender.writeNetDelta(wire, 0));
  wire.seek(0);
  EXPECT_EQ(wire.readVlqU(), 130u);
  EXPECT_EQ(wire.pos(), 2u);
  expectIntWire(wire, values);
  signalBytes("vlq130", wire);
}

TEST(NetSignalPolicy, EmptySubthresholdAndCompatibilityPerformNoStreamWrites) {
  size_t writes = 0;
  DataStreamFunctions stream({}, [&](char const*, size_t length) {
    ++writes;
    return length;
  });
  NetElementSignal<int> empty;
  EXPECT_FALSE(empty.writeNetDelta(stream, 0));
  NetElementSignal<int> signal;
  signal.send(17);
  EXPECT_FALSE(signal.writeNetDelta(stream, 1));
  signal.setCompatibilityVersion(static_cast<VersionNumber>(1));
  EXPECT_FALSE(signal.writeNetDelta(stream, 0, NetCompatibilityRules(LegacyVersion)));
  EXPECT_EQ(writes, 0u);
  EXPECT_TRUE(signal.writeNetDelta(stream, 0, NetCompatibilityRules(static_cast<VersionNumber>(1))));
  EXPECT_GT(writes, 0u);
  std::cout << "NET_SIGNAL_TRACE write-gates empty,subthreshold,rejected,accepted\n";
}

TEST(NetSignalPolicy, WholeExpressionLifetimesCopiesMovesEvictionAndReset) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal(1);
    TrackedSignal input(11);
    trace.events.clear();
    signal.send(input);
    trace.log("after-lvalue");
    signal.send(TrackedSignal(22));
    trace.log("after-temporary");
    {
      auto received = signal.receive();
      EXPECT_EQ(signalValues(received), List<int>({22}));
      EXPECT_TRUE(signal.receive().empty());
    }
    DataStreamBuffer wire;
    ASSERT_TRUE(signal.writeNetDelta(wire, 0));
    signalBytes("tracked-wire", wire);
    signal.initNetVersion();
    EXPECT_TRUE(signal.receive().empty());
    trace.log("after-reset");
  }
  EXPECT_EQ(trace.live, 0);
  // Do not guess Deque's intermediate moves; compare the complete OFF/ON trace.
  trace.emit("whole-expression");
}

TEST(NetSignalPolicy, SendAppendCopyThrowsOriginalErrorWithoutEviction) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal(1);
    signal.send(TrackedSignal(11));
    trace.events.clear();
    trace.copyFailure = 22;
    // A prvalue initializes the by-value parameter directly. The throwing copy
    // is the named parameter copied into SignalEntry, not a caller-side copy.
    signalFailure(trace, [&] { signal.send(TrackedSignal(22)); });
    EXPECT_NE(trace.events.find("C22,"), std::string::npos);
    EXPECT_EQ(trace.events.find("D11,"), std::string::npos);
    trace.copyFailure = -999;
    EXPECT_EQ(signalValues(signal.receive()), List<int>({11}));
    EXPECT_TRUE(signal.receive().empty());
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("send-copy-failure");
}

TEST(NetSignalPolicy, ReceiveCopyFailureMarksOnlyCompletedPrefix) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal(3);
    signal.send(TrackedSignal(11));
    signal.send(TrackedSignal(22));
    signal.send(TrackedSignal(33));
    trace.events.clear();
    trace.copyFailure = 22;
    signalFailure(trace, [&] { signal.receive(); });
    EXPECT_NE(trace.events.find("C11,"), std::string::npos);
    EXPECT_NE(trace.events.find("C22,"), std::string::npos);
    EXPECT_EQ(trace.events.find("C33,"), std::string::npos);
    EXPECT_EQ(trace.live, 3);
    trace.copyFailure = -999;
    EXPECT_EQ(signalValues(signal.receive()), List<int>({22, 33}));
    EXPECT_TRUE(signal.receive().empty());
    DataStreamBuffer wire;
    ASSERT_TRUE(signal.writeNetDelta(wire, 0));
    DataStreamBuffer expected;
    expected.writeVlqU(3);
    expected << uint8_t(11) << uint8_t(22) << uint8_t(33);
    EXPECT_EQ(wire.data(), expected.data());
    signalBytes("received-still-writes", wire);
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("receive-copy-failure");
}

TEST(NetSignalPolicy, SerializerThrowsOriginalErrorAndKeepsWrittenPrefix) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal(3);
    signal.send(TrackedSignal(11));
    signal.send(TrackedSignal(22));
    signal.send(TrackedSignal(33));
    trace.events.clear();
    trace.writeFailure = 22;
    DataStreamBuffer wire;
    wire << uint8_t(0xaa);
    signalFailure(trace, [&] { signal.writeNetDelta(wire, 0); });
    EXPECT_EQ(trace.events, "W11,W22,caught,");
    DataStreamBuffer expected;
    expected << uint8_t(0xaa);
    expected.writeVlqU(3);
    expected << uint8_t(11) << uint8_t(22);
    EXPECT_EQ(wire.data(), expected.data());
    signalBytes("serializer-failure-prefix", wire);
    trace.writeFailure = -999;
    wire.clear();
    ASSERT_TRUE(signal.writeNetDelta(wire, 0));
    EXPECT_EQ(signalValues(signal.receive()), List<int>({11, 22, 33}));
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("serializer-failure");
}

TEST(NetSignalPolicy, VersionIsSampledBeforeEntryCopyHook) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementVersion version;
    NetElementSignal<TrackedSignal> signal;
    signal.initNetVersion(&version);
    version.increment();
    trace.copied = [&](int value) {
      if (value == 17) {
        trace.log("advance");
        version.increment();
      }
    };
    trace.events.clear();
    signal.send(TrackedSignal(17));
    trace.copied = {};
    EXPECT_EQ(version.current(), 2u);
    DataStreamBuffer future;
    EXPECT_FALSE(signal.writeNetDelta(future, 2));
    EXPECT_TRUE(future.empty());
    DataStreamBuffer current;
    ASSERT_TRUE(signal.writeNetDelta(current, 1));
    DataStreamBuffer expected;
    expected.writeVlqU(1);
    expected << uint8_t(17);
    EXPECT_EQ(current.data(), expected.data());
    signalBytes("version-before-copy", current);
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("version-copy-hook");
}

#ifdef STAR_USE_RUST_NET_SIGNAL
TEST(NetSignalPolicy, RustCountersObserveNaturalRootsAndAttemptedLeaves) {
  auto send = sb_net_signal_count(0, SB_NET_SIGNAL_SEND);
  auto receive = sb_net_signal_count(0, SB_NET_SIGNAL_RECEIVE);
  auto write = sb_net_signal_count(0, SB_NET_SIGNAL_WRITE);
  auto append = sb_net_signal_count(2, SB_NET_SIGNAL_APPEND_SIGNAL);
  auto header = sb_net_signal_count(2, SB_NET_SIGNAL_WRITE_HEADER);
  NetElementSignal<int> signal(1);
  signal.send(17);
  EXPECT_EQ(signal.receive(), List<int>({17}));
  EXPECT_TRUE(signal.receive().empty());
  DataStreamBuffer wire;
  EXPECT_TRUE(signal.writeNetDelta(wire, 0));
  signal.setCompatibilityVersion(static_cast<VersionNumber>(1));
  EXPECT_FALSE(signal.writeNetDelta(wire, 0, NetCompatibilityRules(LegacyVersion)));
  EXPECT_EQ(sb_net_signal_count(0, SB_NET_SIGNAL_SEND) - send, 1u);
  EXPECT_EQ(sb_net_signal_count(0, SB_NET_SIGNAL_RECEIVE) - receive, 2u);
  EXPECT_EQ(sb_net_signal_count(0, SB_NET_SIGNAL_WRITE) - write, 1u);
  // Kind 2 is all-thread ATTEMPTED leaves, not completed jobs or TLS roots.
  EXPECT_GT(sb_net_signal_count(2, SB_NET_SIGNAL_APPEND_SIGNAL), append);
  EXPECT_GT(sb_net_signal_count(2, SB_NET_SIGNAL_WRITE_HEADER), header);
  EXPECT_EQ(sb_net_signal_count(0, SB_NET_SIGNAL_COUNT), 0u);
  EXPECT_EQ(sb_net_signal_count(2, SB_NET_SIGNAL_OP_COUNT), 0u);
}
TEST(NetSignalPolicy, RustCountersObserveReadFlushAndTickWithoutRustFloatingPoint) {
  uint64_t before[4];
  for (unsigned i = 0; i != 4; ++i)
    before[i] = sb_net_signal_count(0, SB_NET_SIGNAL_READ + i);
  auto decrement = sb_net_signal_count(2, SB_NET_SIGNAL_DECREMENT_TIME);
  DataStreamBuffer wire;
  wire.writeVlqU(1);
  wire.write(17);
  wire.seek(0);
  NetElementSignal<int> signal;
  signal.enableNetInterpolation();
  signal.readNetDelta(wire, 0.5f);
  signal.tickNetInterpolation(0.25f);
  signal.disableNetInterpolation();
  EXPECT_EQ(signal.receive(), List<int>({17}));
  for (unsigned i = 0; i != 4; ++i)
    EXPECT_EQ(sb_net_signal_count(0, SB_NET_SIGNAL_READ + i) - before[i], 1u);
  EXPECT_EQ(sb_net_signal_count(2, SB_NET_SIGNAL_DECREMENT_TIME) - decrement, 1u);
}
#endif

namespace {
// Keep fixture serialization (and its temporary lifetimes) out of the receive
// trace. Failure injection belongs to the read/queue operation, not setup.
void enqueueSignalWire(DataStreamBuffer& wire, List<int> const& values) {
  SignalTrace setup;
  {
    SignalTracing writing(setup);
    wire.clear();
    wire.writeVlqU(values.size());
    for (int value : values)
      wire.write(TrackedSignal(value));
    wire.seek(0);
  }
  EXPECT_EQ(setup.live, 0);
}
}

TEST(NetSignalPolicy, ReadDelayRequiresEnabledInterpolationAndPositiveTime) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal;
    DataStreamBuffer wire;
    enqueueSignalWire(wire, {11});
    signal.readNetDelta(wire, 1.0f); // Disabled: immediate despite positive time.
    EXPECT_TRUE(wire.atEnd());
    EXPECT_EQ(signalValues(signal.receive()), List<int>({11}));
    signal.enableNetInterpolation(-7.0f); // The finite hint does not gate reads.
    for (float delay : {0.0f, -0.25f}) {
      enqueueSignalWire(wire, {22});
      signal.readNetDelta(wire, delay);
      EXPECT_EQ(signalValues(signal.receive()), List<int>({22}));
    }
    enqueueSignalWire(wire, {33, 44});
    signal.readNetDelta(wire, 0.5f);
    trace.log("delayed-read-return");
    EXPECT_TRUE(wire.atEnd());
    EXPECT_TRUE(signal.receive().empty());
    signal.tickNetInterpolation(0.25f);
    EXPECT_TRUE(signal.receive().empty());
    signal.tickNetInterpolation(0.25f);
    EXPECT_EQ(signalValues(signal.receive()), List<int>({33, 44}));
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("read-delay-branches");
}

TEST(NetSignalPolicy, TickNegativeEqualAndGreaterStepsKeepFrontFifoOrder) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal;
    signal.enableNetInterpolation();
    DataStreamBuffer wire;
    enqueueSignalWire(wire, {33, 11});
    signal.readNetDelta(wire, 0.5f);
    enqueueSignalWire(wire, {22});
    signal.readNetDelta(wire, 1.0f);
    trace.log("before-negative");
    signal.tickNetInterpolation(-0.25f);
    signal.tickNetInterpolation(0.5f);
    EXPECT_TRUE(signal.receive().empty());
    trace.log("before-equal");
    signal.tickNetInterpolation(0.25f);
    EXPECT_EQ(signalValues(signal.receive()), List<int>({33, 11}));
    trace.log("before-greater");
    signal.tickNetInterpolation(1.0f);
    EXPECT_EQ(signalValues(signal.receive()), List<int>({22}));
    signal.tickNetInterpolation(0.0f);
    EXPECT_TRUE(signal.receive().empty());

    // A native Signal copy hook can enqueue during an owned flush: the
    // original incoming signal is appended AFTER that hook's pending entry.
    // This makes genuinely out-of-time-order pending entries through public
    // operations, so a due tail cannot be mistaken for a sorted timer queue.
    signal.initNetVersion();
    enqueueSignalWire(wire, {55});
    signal.readNetDelta(wire, 1.0f);
    bool injected = false;
    trace.copied = [&](int value) {
      if (value == 55 && !injected) {
        injected = true;
        trace.log("enqueue-from-copy");
        DataStreamBuffer nested;
        enqueueSignalWire(nested, {44});
        signal.readNetDelta(nested, 1.0f);
      }
    };
    enqueueSignalWire(wire, {33});
    signal.readNetDelta(wire, 0.5f);
    trace.copied = {};
    EXPECT_TRUE(injected);
    EXPECT_EQ(signalValues(signal.receive()), List<int>({55}));
    signal.tickNetInterpolation(0.5f);
    EXPECT_TRUE(signal.receive().empty()); // 33 is due, but 44 at the front isn't.
    signal.tickNetInterpolation(0.5f);
    EXPECT_EQ(signalValues(signal.receive()), List<int>({44, 33}));
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("tick-finite-front-fifo");
}

TEST(NetSignalPolicy, SmallerDelayFlushesOldPendingBeforeAppendingNewSignal) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal;
    signal.enableNetInterpolation();
    DataStreamBuffer wire;
    enqueueSignalWire(wire, {11, 22});
    signal.readNetDelta(wire, 1.0f);
    trace.events.clear(); // Both pending objects stay alive across this boundary.
    enqueueSignalWire(wire, {33});
    signal.readNetDelta(wire, 0.5f);
    trace.log("smaller-read-return");
    EXPECT_EQ(signalValues(signal.receive()), List<int>({11, 22}));
    EXPECT_LT(trace.events.find("R33,"), trace.events.find("C11,"));
    EXPECT_LT(trace.events.find("C22,"), trace.events.find("M33,"));
    signal.tickNetInterpolation(0.25f);
    EXPECT_TRUE(signal.receive().empty());
    signal.tickNetInterpolation(0.25f);
    EXPECT_EQ(signalValues(signal.receive()), List<int>({33}));
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("read-smaller-flush-before-append");
}

TEST(NetSignalPolicy, EqualDelayDoesNotFlushPendingOrExposeSignalsEarly) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal;
    signal.enableNetInterpolation();
    DataStreamBuffer wire;
    enqueueSignalWire(wire, {22});
    signal.readNetDelta(wire, 0.5f);
    enqueueSignalWire(wire, {11});
    signal.readNetDelta(wire, 0.5f);
    trace.log("equal-read-return");
    EXPECT_TRUE(signal.receive().empty());
    signal.tickNetInterpolation(0.5f);
    EXPECT_EQ(signalValues(signal.receive()), List<int>({22, 11}));
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("read-equal-no-flush");
}

TEST(NetSignalPolicy, DisableFailureDestroysOwnedRemainderAndLeavesInterpolationDisabled) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal;
    signal.enableNetInterpolation();
    DataStreamBuffer wire;
    enqueueSignalWire(wire, {11, 22, 33});
    signal.readNetDelta(wire, 1.0f);
    trace.events.clear();
    trace.copyFailure = 22;
    signalFailure(trace, [&] { signal.disableNetInterpolation(); });
    // The successful prefix remains in m_signals. The whole taken deque,
    // including 33, has died; it is not an incrementally popped source queue.
    EXPECT_EQ(trace.live, 1);
    EXPECT_NE(trace.events.find("D33,"), std::string::npos);
    EXPECT_EQ(trace.events.find("C33,"), std::string::npos);
    trace.copyFailure = -999;
    EXPECT_EQ(signalValues(signal.receive()), List<int>({11}));
    enqueueSignalWire(wire, {44});
    signal.readNetDelta(wire, 1.0f);
    EXPECT_EQ(signalValues(signal.receive()), List<int>({44}));
    signal.enableNetInterpolation();
    signal.tickNetInterpolation(1.0f);
    signal.disableNetInterpolation();
    EXPECT_TRUE(signal.receive().empty());
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("disable-owned-flush-failure");
}

TEST(NetSignalPolicy, SmallerDelayFlushFailureConsumesIncomingButDoesNotAppendIt) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal;
    signal.enableNetInterpolation();
    DataStreamBuffer wire;
    enqueueSignalWire(wire, {11, 22, 33});
    signal.readNetDelta(wire, 1.0f);
    enqueueSignalWire(wire, {44});
    trace.events.clear();
    trace.copyFailure = 22;
    signalFailure(trace, [&] { signal.readNetDelta(wire, 0.5f); });
    EXPECT_TRUE(wire.atEnd());
    EXPECT_EQ(trace.live, 1);
    EXPECT_NE(trace.events.find("R44,"), std::string::npos);
    EXPECT_NE(trace.events.find("D44,"), std::string::npos);
    EXPECT_NE(trace.events.find("D33,"), std::string::npos);
    EXPECT_EQ(trace.events.find("M44,"), std::string::npos);
    trace.copyFailure = -999;
    EXPECT_EQ(signalValues(signal.receive()), List<int>({11}));
    signal.tickNetInterpolation(1.0f);
    EXPECT_TRUE(signal.receive().empty());
    // A flush during read does not disable interpolation, even when it throws.
    enqueueSignalWire(wire, {55});
    signal.readNetDelta(wire, 0.25f);
    EXPECT_TRUE(signal.receive().empty());
    signal.tickNetInterpolation(0.25f);
    EXPECT_EQ(signalValues(signal.receive()), List<int>({55}));
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("read-owned-flush-failure");
}

TEST(NetSignalPolicy, TickFailureLosesPoppedSignalButKeepsLaterAlreadyDecrementedTimers) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal;
    signal.enableNetInterpolation();
    DataStreamBuffer wire;
    enqueueSignalWire(wire, {11});
    signal.readNetDelta(wire, 0.25f);
    enqueueSignalWire(wire, {22});
    signal.readNetDelta(wire, 0.5f);
    enqueueSignalWire(wire, {33});
    signal.readNetDelta(wire, 1.0f);
    trace.events.clear();
    trace.copyFailure = 22;
    signalFailure(trace, [&] { signal.tickNetInterpolation(0.5f); });
    EXPECT_EQ(trace.live, 2); // Sent 11 and pending 33; popped 22 is gone.
    EXPECT_NE(trace.events.find("C22,"), std::string::npos);
    EXPECT_EQ(trace.events.find("C33,"), std::string::npos);
    trace.copyFailure = -999;
    EXPECT_EQ(signalValues(signal.receive()), List<int>({11}));
    signal.tickNetInterpolation(0.0f);
    EXPECT_TRUE(signal.receive().empty());
    signal.tickNetInterpolation(0.5f);
    // 33's timer was decremented before the earlier send threw, not lazily
    // when 33 reached the front. Equal-to-zero is due, not strictly negative.
    EXPECT_EQ(signalValues(signal.receive()), List<int>({33}));
    signal.disableNetInterpolation();
    EXPECT_TRUE(signal.receive().empty());
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("tick-pop-prvalue-copy-failure");
}

TEST(NetSignalPolicy, DeserializationFailureKeepsConsumedPrefixAndDestroysLocalSignal) {
  SignalTrace trace;
  SignalTracing tracing(trace);
  {
    NetElementSignal<TrackedSignal> signal;
    DataStreamBuffer wire;
    enqueueSignalWire(wire, {11, 22, 33});
    trace.readFailure = 22;
    signalFailure(trace, [&] { signal.readNetDelta(wire, 0.5f); });
    EXPECT_EQ(wire.pos(), 3u); // One count byte, successful 11, failing 22.
    EXPECT_EQ(wire.size(), 4u);
    EXPECT_EQ(trace.live, 1);
    EXPECT_NE(trace.events.find("N0,R22,D22,caught,"), std::string::npos);
    EXPECT_EQ(signalValues(signal.receive()), List<int>({11}));
    trace.readFailure = -999;
    // The old count is not restartable. Explicitly frame the remaining byte
    // with count 1, consuming it from the original stream without rewinding.
    DataStreamBuffer remaining;
    remaining.writeVlqU(1);
    remaining << wire.read<uint8_t>();
    EXPECT_TRUE(wire.atEnd());
    remaining.seek(0);
    signal.readNetDelta(remaining, 0.5f);
    EXPECT_TRUE(remaining.atEnd());
    EXPECT_EQ(signalValues(signal.receive()), List<int>({33}));
    signalBytes("read-failure-consumed-wire", wire);

    // A separate failure in send's named-parameter copy happens AFTER read
    // and the move into send, not during deserialization or caller setup.
    signal.initNetVersion();
    enqueueSignalWire(wire, {44, 55});
    trace.copyFailure = 44;
    trace.log("before-immediate-send-failure");
    signalFailure(trace, [&] { signal.readNetDelta(wire, 0.5f); });
    EXPECT_EQ(wire.pos(), 2u);
    EXPECT_EQ(wire.size(), 3u);
    EXPECT_EQ(trace.live, 0);
    trace.copyFailure = -999;
    remaining.clear();
    remaining.writeVlqU(1);
    remaining << wire.read<uint8_t>();
    remaining.seek(0);
    signal.readNetDelta(remaining, 0.5f);
    EXPECT_TRUE(wire.atEnd());
    EXPECT_TRUE(remaining.atEnd());
    EXPECT_EQ(signalValues(signal.receive()), List<int>({55}));
  }
  EXPECT_EQ(trace.live, 0);
  trace.emit("deserialize-byte-failure-resume");
}

TEST(NetSignalPolicy, VersionResetPreservesPendingAndStoreLoadAreNoopsIncludingZeroCapacity) {
  for (size_t capacity : {size_t(0), size_t(3)}) {
    SignalTrace trace;
    SignalTracing tracing(trace);
    {
      NetElementSignal<TrackedSignal> signal(capacity);
      signal.send(TrackedSignal(11));
      signal.enableNetInterpolation(7.0f);
      DataStreamBuffer wire;
      enqueueSignalWire(wire, {22, 33});
      signal.readNetDelta(wire, 0.5f);
      signal.initNetVersion(); // Clears the sent queue ONLY.
      EXPECT_TRUE(signal.receive().empty());
      EXPECT_EQ(trace.live, 2);
      DataStreamBuffer unused;
      unused << uint8_t(77);
      unused.seek(0);
      signal.netStore(unused);
      signal.netLoad(unused, {});
      EXPECT_EQ(unused.pos(), 0u);
      EXPECT_EQ(unused.size(), 1u);
      EXPECT_EQ(static_cast<unsigned char>(unused.ptr()[0]), 77u);
      EXPECT_EQ(trace.live, 2);
      signal.tickNetInterpolation(0.5f);
      EXPECT_EQ(signalValues(signal.receive()), capacity ? List<int>({22, 33}) : List<int>());
      EXPECT_EQ(trace.live, capacity ? 2 : 0);
      signal.disableNetInterpolation();
      EXPECT_TRUE(signal.receive().empty());
    }
    EXPECT_EQ(trace.live, 0);
    trace.emit(capacity ? "reset-pending-noop-store-load" : "pending-zero-capacity");
  }
}
