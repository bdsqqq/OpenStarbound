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
  if (TrackedSignal::trace)
    TrackedSignal::trace->log("R" + std::to_string(signal.value));
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
  EXPECT_EQ(sb_net_signal_count(0, 3), 0u);
  EXPECT_EQ(sb_net_signal_count(2, SB_NET_SIGNAL_OP_COUNT), 0u);
}
#endif
