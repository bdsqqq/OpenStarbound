#include "StarJsonRpc.hpp"
#include "StarAllocationProbe.hpp"
#include "StarDataStreamDevices.hpp"
#include "StarLogging.hpp"
#include "gtest/gtest.h"

#include <array>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef STAR_USE_RUST_JSON_RPC
#include "StarRustJsonRpc.h"
#endif

using namespace Star;

namespace {
ByteArray rpcWire(List<Json> const& messages) {
  DataStreamBuffer stream;
  stream.writeContainer(messages);
  return stream.takeData();
}

List<Json> rpcDecode(ByteArray const& bytes) {
  if (bytes.empty())
    return {};
  DataStreamBuffer stream(bytes);
  List<Json> messages;
  stream.readContainer(messages);
  return messages;
}

Json rpcRequest(uint64_t id, String handler, Json arguments = {}) {
  return JsonObject{{"command", "request"}, {"id", id}, {"handler", handler}, {"arguments", arguments}};
}
Json rpcResponse(uint64_t id, Json result) {
  return JsonObject{{"command", "response"}, {"id", id}, {"result", result}};
}
Json rpcFail(uint64_t id) {
  return JsonObject{{"command", "fail"}, {"id", id}};
}

// Traces contain decoded native wire values and explicit state/log markers,
// never exception stacks, timestamps, or backend-specific diagnostics.
struct RpcTrace {
  explicit RpcTrace(char const* name) : name(name) {}
  ~RpcTrace() { std::cout << "JSON_RPC_TRACE " << name << text << '\n'; }
  void wire(ByteArray const& bytes) {
    text += " wire=";
    text += Json(JsonArray(rpcDecode(bytes))).repr(0, true).utf8();
  }
  void state(uint64_t value) { text += " state=" + std::to_string(value); }
  void promise(RpcPromise<Json> const& p) {
    state(p.finished()); state(p.succeeded()); state(p.failed());
    if (p.result()) text += " result=" + p.result()->repr(0, true).utf8();
  }
  char const* name;
  std::string text;
};

class RpcLogSink : public LogSink {
public:
  RpcLogSink() { setLevel(LogLevel::Error); }
  void log(char const* message, LogLevel level) override {
    if (level == LogLevel::Error)
      messages.emplace_back(message);
  }
  size_t matching(char const* marker) const {
    size_t count = 0;
    for (auto const& message : messages)
      if (message.find(marker) != std::string::npos) ++count;
    return count;
  }
  std::vector<std::string> messages;
};
struct RpcLogs {
  RpcLogs() : sink(std::make_shared<RpcLogSink>()) { Logger::addSink(sink); }
  ~RpcLogs() { Logger::removeSink(sink); }
  std::shared_ptr<RpcLogSink> sink;
};

void expectUnfinished(RpcPromise<Json> const& promise) {
  EXPECT_FALSE(promise.finished());
  EXPECT_FALSE(promise.succeeded());
  EXPECT_FALSE(promise.failed());
  EXPECT_FALSE(promise.result());
  EXPECT_FALSE(promise.error());
}
void expectSuccess(RpcPromise<Json> const& promise, Json expected) {
  EXPECT_TRUE(promise.finished());
  EXPECT_TRUE(promise.succeeded());
  EXPECT_FALSE(promise.failed());
  ASSERT_TRUE(promise.result());
  EXPECT_EQ(*promise.result(), expected);
  EXPECT_FALSE(promise.error());
}

struct RpcFunctionCounts { unsigned copies = 0, moves = 0, live = 0, destroyed = 0, calls = 0; };
struct RpcCountedFunction {
  explicit RpcCountedFunction(std::shared_ptr<RpcFunctionCounts> counts) : counts(std::move(counts)) { ++this->counts->live; }
  RpcCountedFunction(RpcCountedFunction const& other) : counts(other.counts) { ++counts->copies; ++counts->live; }
  RpcCountedFunction(RpcCountedFunction&& other) noexcept : counts(other.counts) { ++counts->moves; ++counts->live; }
  ~RpcCountedFunction() { --counts->live; ++counts->destroyed; }
  Json operator()(Json const& argument) { ++counts->calls; return argument; }
  std::shared_ptr<RpcFunctionCounts> counts;
};
}

TEST(JsonRpc, RegistrationErrorsAndByValueFunctionLifetime) {
  RpcTrace trace("registration-byvalue-lifetime");
  auto counts = std::make_shared<RpcFunctionCounts>();
  {
    JsonRpc rpc;
    JsonRpcRemoteFunction function = RpcCountedFunction(counts);
    unsigned copies = counts->copies;
    rpc.registerHandler("echo", function);
    EXPECT_EQ(counts->copies, copies + 1);
    EXPECT_EQ(counts->live, 2u);
    copies = counts->copies;
    try {
      rpc.registerHandler("echo", function);
      FAIL() << "duplicate registration accepted";
    } catch (JsonRpcException const& e) {
      EXPECT_EQ(std::string(e.what()), "(JsonRpcException) Handler by that name already exists 'echo'");
    }
    EXPECT_EQ(counts->copies, copies + 1); // By-value parameter is copied even on rejection.
    EXPECT_EQ(counts->live, 2u);
    try {
      rpc.removeHandler("absent");
      FAIL() << "missing removal accepted";
    } catch (JsonRpcException const& e) {
      EXPECT_EQ(std::string(e.what()), "(JsonRpcException) No such handler by the name 'absent'");
    }
    copies = counts->copies;
    rpc.registerHandler("moved", std::move(function));
    EXPECT_EQ(counts->copies, copies);
    EXPECT_EQ(counts->live, 2u);
    rpc.removeHandler("echo");
    EXPECT_EQ(counts->live, 1u);
    rpc.clearHandlers();
    EXPECT_EQ(counts->live, 0u);
  }
  EXPECT_EQ(counts->live, 0u);
  trace.state(counts->copies); trace.state(counts->live);
}

TEST(JsonRpc, InvocationUsesStoredFunctionWithoutExtraCopies) {
  RpcTrace trace("stored-function-no-invocation-copy");
  JsonRpc client, server;
  auto counts = std::make_shared<RpcFunctionCounts>();
  server.registerHandler("echo", RpcCountedFunction(counts));
  auto copies = counts->copies;
  auto live = counts->live;
  auto promise = client.invokeRemote("echo", JsonObject{{"x", JsonArray{1, 2}}});
  auto outgoing = client.send(); trace.wire(outgoing);
  server.receive(outgoing);
  EXPECT_EQ(counts->copies, copies);
  EXPECT_EQ(counts->live, live);
  EXPECT_EQ(counts->calls, 1u);
  auto incoming = server.send(); trace.wire(incoming); client.receive(incoming);
  expectSuccess(promise, JsonObject{{"x", JsonArray{1, 2}}});
  trace.promise(promise); trace.state(counts->copies - copies);
}

TEST(JsonRpc, RegisterHandlersCopiesAndRetainsPrefixBeforeDuplicate) {
  RpcTrace trace("register-handlers-prefix");
  auto counts = std::make_shared<RpcFunctionCounts>();
  JsonRpcHandlers handlers;
  handlers.add("alpha", RpcCountedFunction(counts));
  handlers.add("beta", RpcCountedFunction(counts));
  handlers.add("gamma", RpcCountedFunction(counts));
  std::vector<String> order;
  for (auto const& entry : handlers) order.push_back(entry.first);
  ASSERT_EQ(order.size(), size_t(3));
  JsonRpc server;
  server.registerHandler(order[1], [](Json const&) { return Json("existing"); });
  auto copies = counts->copies;
  EXPECT_THROW(server.registerHandlers(handlers), JsonRpcException);
  EXPECT_EQ(counts->copies, copies + 2);
  server.receive(rpcWire({rpcRequest(0, order[0], "first"), rpcRequest(1, order[1]), rpcRequest(2, order[2])}));
  auto bytes = server.send(); trace.wire(bytes);
  EXPECT_EQ(rpcDecode(bytes), (List<Json>{rpcResponse(0, "first"), rpcResponse(1, "existing"), rpcFail(2)}));
  server.clearHandlers();
  EXPECT_EQ(counts->live, 3u); // The caller's registry still owns its callbacks.
  trace.state(counts->copies - copies); trace.state(counts->live);
}

TEST(JsonRpc, RemoveClearAndDestructionReleaseOnlyTheirCaptures) {
  RpcTrace trace("capture-release");
  auto capture = std::make_shared<int>(17);
  std::weak_ptr<int> weak = capture;
  {
    JsonRpc rpc;
    rpc.registerHandler("one", [capture](Json const&) { return Json(*capture); });
    rpc.registerHandler("two", [capture](Json const&) { return Json(*capture); });
    capture.reset();
    EXPECT_EQ(weak.use_count(), 2);
    rpc.removeHandler("one");
    EXPECT_EQ(weak.use_count(), 1);
    rpc.clearHandlers();
    EXPECT_TRUE(weak.expired());
    auto other = std::make_shared<int>(23);
    weak = other;
    rpc.registerHandler("last", [other](Json const&) { return Json(*other); });
  }
  EXPECT_TRUE(weak.expired()); trace.state(weak.expired());
}

TEST(JsonRpc, RequestIdsQueueAndRepeatedEmptySend) {
  RpcTrace trace("request-ids-queue-send");
  JsonRpc rpc;
  EXPECT_FALSE(rpc.sendPending());
  EXPECT_TRUE(rpc.send().empty());
  rpc.receive({});
  auto first = rpc.invokeRemote("first", JsonArray{1, "two", Json()});
  auto second = rpc.invokeRemote("second", JsonObject{{"ok", true}});
  expectUnfinished(first); expectUnfinished(second);
  EXPECT_TRUE(rpc.sendPending());
  auto bytes = rpc.send(); trace.wire(bytes);
  EXPECT_EQ(rpcDecode(bytes), (List<Json>{rpcRequest(0, "first", JsonArray{1, "two", Json()}),
      rpcRequest(1, "second", JsonObject{{"ok", true}})}));
  EXPECT_FALSE(rpc.sendPending());
  EXPECT_TRUE(rpc.send().empty()); EXPECT_TRUE(rpc.send().empty());
  expectUnfinished(first); expectUnfinished(second);
  trace.promise(first); trace.promise(second); trace.state(rpc.sendPending());
}

TEST(JsonRpc, TwoPeersOutOfOrderResponsesAndCopiedJsonArgument) {
  RpcTrace trace("two-peers-success-json-copy");
  JsonRpc client, server;
  Json observed;
  server.registerHandler("echo", [&observed](Json const& argument) { observed = argument; return argument; });
  Json argument = JsonObject{{"nested", JsonArray{1, false, "value"}}};
  auto first = client.invokeRemote("echo", argument);
  auto second = client.invokeRemote("echo", 99);
  argument = "caller-replaced";
  auto requests = client.send(); trace.wire(requests); server.receive(requests);
  auto responses = server.send(); trace.wire(responses);
  auto decoded = rpcDecode(responses);
  ASSERT_EQ(decoded.size(), size_t(2));
  client.receive(rpcWire({decoded[1], decoded[0]}));
  expectSuccess(first, JsonObject{{"nested", JsonArray{1, false, "value"}}});
  expectSuccess(second, 99); EXPECT_EQ(observed, Json(99));
  trace.promise(first); trace.promise(second);
}

TEST(JsonRpc, UnknownHandlerFailWireFulfillsNullRatherThanFailingPromise) {
  RpcTrace trace("unknown-handler-null-success");
  RpcLogs logs;
  JsonRpc client, server;
  auto promise = client.invokeRemote("missing", "argument");
  server.receive(client.send());
  auto bytes = server.send(); trace.wire(bytes);
  EXPECT_EQ(rpcDecode(bytes), (List<Json>{rpcFail(0)}));
  EXPECT_EQ(logs.sink->matching("Exception while handling variant rpc request handler call."), size_t(1));
  EXPECT_EQ(logs.sink->matching("Unknown handler 'missing'"), size_t(1));
  client.receive(bytes); expectSuccess(promise, Json());
  trace.promise(promise); trace.state(logs.sink->messages.size());
}

TEST(JsonRpc, StandardHandlerExceptionLogsFailsAndContinuesBatch) {
  RpcTrace trace("std-exception-continue");
  RpcLogs logs;
  JsonRpc client, server;
  unsigned calls = 0;
  server.registerHandler("throw", [](Json const&) -> Json { throw std::runtime_error("rpc-test-standard"); });
  server.registerHandler("good", [&calls](Json const& argument) { ++calls; return argument; });
  auto bad = client.invokeRemote("throw", {});
  auto good = client.invokeRemote("good", 41);
  server.receive(client.send());
  auto bytes = server.send(); trace.wire(bytes);
  EXPECT_EQ(rpcDecode(bytes), (List<Json>{rpcFail(0), rpcResponse(1, 41)}));
  EXPECT_EQ(calls, 1u);
  EXPECT_EQ(logs.sink->matching("rpc-test-standard"), size_t(1));
  client.receive(bytes); expectSuccess(bad, Json()); expectSuccess(good, 41);
  trace.promise(bad); trace.promise(good); trace.state(logs.sink->messages.size());
}

TEST(JsonRpc, NonstandardExceptionEscapesWithIdentityAndPreservesPendingPrefix) {
  RpcTrace trace("nonstd-identity-prefix");
  RpcLogs logs;
  struct Tag { int identity; };
  JsonRpc server;
  unsigned calls = 0;
  Tag const* thrownAddress = nullptr;
  server.registerHandler("good", [&calls](Json const& argument) { ++calls; return argument; });
  server.registerHandler("throw", [&thrownAddress](Json const&) -> Json {
    try { throw Tag{73}; } catch (Tag const& tag) { thrownAddress = &tag; throw; }
  });
  auto pending = server.invokeRemote("outbound", "prefix");
  try {
    server.receive(rpcWire({rpcRequest(4, "good", 11), rpcRequest(5, "throw"), rpcRequest(6, "good", 13)}));
    FAIL() << "nonstandard exception swallowed";
  } catch (Tag const& tag) {
    EXPECT_EQ(&tag, thrownAddress); EXPECT_EQ(tag.identity, 73);
  }
  EXPECT_EQ(calls, 1u); EXPECT_TRUE(logs.sink->messages.empty());
  auto bytes = server.send(); trace.wire(bytes);
  EXPECT_EQ(rpcDecode(bytes), (List<Json>{rpcRequest(0, "outbound", "prefix"), rpcResponse(4, 11)}));
  expectUnfinished(pending); trace.promise(pending); trace.state(calls); trace.state(logs.sink->messages.size());
}

TEST(JsonRpc, NativeCommandComparisonIgnoresNumbersAndUnknownStrings) {
  RpcTrace trace("native-command-comparison");
  RpcLogs logs;
  JsonRpc rpc;
  rpc.receive(rpcWire({JsonObject{{"command", 1}}, JsonObject{{"command", "REQUEST"}},
      JsonObject{{"command", Json()}}, JsonObject{{"command", true}}, JsonObject{{"command", "other"}}}));
  EXPECT_FALSE(rpc.sendPending()); EXPECT_TRUE(logs.sink->messages.empty());
  trace.wire(rpc.send()); trace.state(logs.sink->messages.size());
}

TEST(JsonRpc, MissingCommandThrowsOutsideCatchAfterEarlierEffects) {
  RpcTrace trace("missing-command-outside-catch");
  RpcLogs logs;
  JsonRpc rpc;
  unsigned calls = 0;
  rpc.registerHandler("good", [&calls](Json const& value) { ++calls; return value; });
  EXPECT_THROW(rpc.receive(rpcWire({rpcRequest(0, "good", 7), JsonObject{{"id", 9}},
      rpcRequest(2, "good", 8)})), JsonException);
  EXPECT_EQ(calls, 1u); EXPECT_TRUE(logs.sink->messages.empty());
  auto bytes = rpc.send(); trace.wire(bytes);
  EXPECT_EQ(rpcDecode(bytes), (List<Json>{rpcResponse(0, 7)}));
  trace.state(calls); trace.state(logs.sink->messages.size());
}

TEST(JsonRpc, MissingRequestIdEscapesFailureConstructionAndStopsRemainingItems) {
  RpcTrace trace("malformed-id-failure-construction");
  RpcLogs logs;
  JsonRpc rpc;
  unsigned calls = 0;
  rpc.registerHandler("good", [&calls](Json const& value) { ++calls; return value; });
  Json malformed = JsonObject{{"command", "request"}, {"handler", "missing"}, {"arguments", 3}};
  EXPECT_THROW(rpc.receive(rpcWire({rpcRequest(4, "good", 17), malformed, rpcRequest(6, "good", 19)})), JsonException);
  EXPECT_EQ(calls, 1u);
  EXPECT_EQ(logs.sink->matching("Exception while handling variant rpc request handler call."), size_t(1));
  auto bytes = rpc.send(); trace.wire(bytes);
  EXPECT_EQ(rpcDecode(bytes), (List<Json>{rpcResponse(4, 17)}));
  trace.state(calls); trace.state(logs.sink->messages.size());
}

TEST(JsonRpc, MissingResultTakesKeeperBeforeLookupLeavingPromiseUnfinished) {
  RpcTrace trace("missing-result-consumes-keeper");
  RpcLogs logs;
  JsonRpc rpc;
  auto lost = rpc.invokeRemote("lost", {});
  auto good = rpc.invokeRemote("good", {});
  trace.wire(rpc.send());
  rpc.receive(rpcWire({JsonObject{{"command", "response"}, {"id", 0}}, rpcResponse(0, 17), rpcResponse(1, 19)}));
  expectUnfinished(lost); expectSuccess(good, 19);
  EXPECT_EQ(logs.sink->matching("Exception while handling variant rpc response handler call."), size_t(2));
  EXPECT_FALSE(rpc.sendPending());
  trace.promise(lost); trace.promise(good); trace.state(logs.sink->messages.size());
}

TEST(JsonRpc, DuplicateUnknownResponsesAndFailCommandsLogAndContinue) {
  RpcTrace trace("response-fail-duplicates-continue");
  RpcLogs logs;
  JsonRpc rpc;
  auto success = rpc.invokeRemote("first", {});
  auto nullSuccess = rpc.invokeRemote("second", {});
  trace.wire(rpc.send());
  rpc.receive(rpcWire({rpcResponse(999, 1), rpcResponse(0, 23), rpcResponse(0, 29),
      rpcFail(1), rpcFail(1), rpcFail(999)}));
  expectSuccess(success, 23); expectSuccess(nullSuccess, Json());
  EXPECT_EQ(logs.sink->matching("Exception while handling variant rpc response handler call."), size_t(2));
  EXPECT_EQ(logs.sink->matching("Exception while handling variant rpc failure handler call."), size_t(2));
  EXPECT_FALSE(rpc.sendPending());
  trace.promise(success); trace.promise(nullSuccess); trace.state(logs.sink->messages.size());
}

TEST(JsonRpc, SafeHandlerReentryInvokesRemoteAndRemovesDifferentCallback) {
  RpcTrace trace("safe-reentry-native-message-order");
  JsonRpc rpc, peer;
  auto capture = std::make_shared<int>(31);
  std::weak_ptr<int> weak = capture;
  rpc.registerHandler("other", [capture](Json const&) { return Json(*capture); });
  capture.reset();
  RpcPromise<Json> nested;
  unsigned calls = 0;
  rpc.registerHandler("active", [&rpc, &nested, &calls](Json const& argument) {
    ++calls;
    rpc.removeHandler("other"); // Never destroys the executing callable.
    nested = rpc.invokeRemote("echo", argument);
    return Json("outer-result");
  });
  peer.registerHandler("echo", [](Json const& value) { return value; });
  auto outer = peer.invokeRemote("active", JsonArray{37, 41});
  rpc.receive(peer.send());
  EXPECT_TRUE(weak.expired()); EXPECT_EQ(calls, 1u); expectUnfinished(nested);
  auto bytes = rpc.send(); trace.wire(bytes);
  EXPECT_EQ(rpcDecode(bytes), (List<Json>{rpcRequest(0, "echo", JsonArray{37, 41}), rpcResponse(0, "outer-result")}));
  peer.receive(bytes); expectSuccess(outer, "outer-result");
  auto replies = peer.send(); trace.wire(replies); rpc.receive(replies);
  expectSuccess(nested, JsonArray{37, 41});
  trace.promise(outer); trace.promise(nested); trace.state(weak.expired()); trace.state(calls);
}

#if defined(__APPLE__) && defined(_LIBCPP_VERSION) && _LIBCPP_VERSION == 220106 && !defined(STAR_USE_RPMALLOC)
TEST(JsonRpc, AllocationFailureStillConsumesRequestIdBeforeEnqueue) {
  RpcTrace trace("allocation-failure-consumes-id");
  JsonRpc rpc;
  String handler("prepared");
  Json arguments = JsonObject{{"prepared", 7}};
  struct Context { JsonRpc* rpc; String const* handler; Json const* arguments; } context{&rpc, &handler, &arguments};
  auto result = StarTest::failNextAllocation(&context, [](void* raw) {
    auto& c = *static_cast<Context*>(raw);
    c.rpc->invokeRemote(*c.handler, *c.arguments);
  });
  EXPECT_TRUE(result.caught);
  EXPECT_TRUE(result.originalIdentity);
  EXPECT_EQ(result.failures, 1u);
  EXPECT_FALSE(rpc.sendPending());
  auto next = rpc.invokeRemote(handler, arguments);
  auto bytes = rpc.send();
  EXPECT_EQ(rpcDecode(bytes), (List<Json>{rpcRequest(1, handler, arguments)}));
  expectUnfinished(next);
  trace.wire(bytes); trace.promise(next);
  trace.state(result.caught); trace.state(result.originalIdentity); trace.state(result.failures);
}
#endif

#ifdef STAR_USE_RUST_JSON_RPC
namespace {
static_assert(SB_JSON_RPC_REGISTER == 0 && SB_JSON_RPC_REQUEST == 12 && SB_JSON_RPC_ENQUEUE == 13 && SB_JSON_RPC_COUNT == 14,
    "JsonRpc accepted-root diagnostic ABI");
static_assert(SB_JSON_RPC_HAS_HANDLER == 0 && SB_JSON_RPC_APPEND_RESPONSE == 25 && SB_JSON_RPC_OP_COUNT == 26,
    "JsonRpc attempted-leaf diagnostic ABI");
static_assert(sizeof(SbNetGroupReply) == 16 && alignof(SbNetGroupReply) == 8,
    "JsonRpc shares existing group reply ABI");
std::array<uint64_t, SB_JSON_RPC_COUNT> rpcRootCounts(uint32_t kind) {
  std::array<uint64_t, SB_JSON_RPC_COUNT> counts{};
  for (uint32_t i = 0; i < counts.size(); ++i) counts[i] = sb_json_rpc_count(kind, i);
  return counts;
}
std::array<uint64_t, SB_JSON_RPC_OP_COUNT> rpcLeafCounts(uint32_t kind) {
  std::array<uint64_t, SB_JSON_RPC_OP_COUNT> counts{};
  for (uint32_t i = 0; i < counts.size(); ++i) counts[i] = sb_json_rpc_count(kind, i);
  return counts;
}
uint32_t rpcNeverCalled(void* context, uint32_t, uint64_t, SbNetGroupReply*) {
  ++*static_cast<unsigned*>(context);
  return 0;
}
}

TEST(JsonRpc, RustPublicRoutesReachAllAcceptedRootsWithoutCounterReset) {
  auto tls = rpcRootCounts(0);
  auto global = rpcRootCounts(1);
  auto leaves = rpcLeafCounts(2);
  auto globalLeaves = rpcLeafCounts(3);
  JsonRpc client, server;
  JsonRpcHandlers handlers;
  handlers.add("echo", [](Json const& value) { return value; });
  server.registerHandlers(handlers);
  server.registerHandler("removed", [](Json const&) { return Json(); });
  server.removeHandler("removed");
  EXPECT_FALSE(client.sendPending());
  auto promise = client.invokeRemote("echo", 47);
  EXPECT_TRUE(client.sendPending());
  server.receive(client.send());
  client.receive(server.send());
  expectSuccess(promise, 47);
  server.clearHandlers();
  auto after = rpcRootCounts(0);
  auto globalAfter = rpcRootCounts(1);
  for (size_t i = 0; i < after.size(); ++i) {
    EXPECT_GE(after[i] - tls[i], uint64_t(1)) << "root " << i;
    EXPECT_GE(globalAfter[i] - global[i], after[i] - tls[i]) << "global root " << i;
  }
  auto leafAfter = rpcLeafCounts(2);
  auto globalLeafAfter = rpcLeafCounts(3);
  for (size_t i = 0; i < leafAfter.size(); ++i) {
    EXPECT_GE(leafAfter[i], leaves[i]);
    EXPECT_GE(globalLeafAfter[i] - globalLeaves[i], leafAfter[i] - leaves[i]);
  }
  EXPECT_GT(leafAfter[SB_JSON_RPC_SET_ID], leaves[SB_JSON_RPC_SET_ID]);
  EXPECT_GT(leafAfter[SB_JSON_RPC_APPEND_REQUEST], leaves[SB_JSON_RPC_APPEND_REQUEST]);
  EXPECT_GT(leafAfter[SB_JSON_RPC_ADD_PROMISE], leaves[SB_JSON_RPC_ADD_PROMISE]);
  EXPECT_GT(leafAfter[SB_JSON_RPC_HANDLE_RESPONSE], leaves[SB_JSON_RPC_HANDLE_RESPONSE]);
  EXPECT_EQ(rpcRootCounts(0), after); // Reads do not reset or increment accepted roots.
  EXPECT_EQ(rpcLeafCounts(2), leafAfter);
  std::cout << "JSON_RPC_DIAGNOSTIC public-routes all-13-roots leaves-monotonic counter-read-no-reset\n";
}

TEST(JsonRpc, RustRejectedRootsDoNotCallHostCountOrOverwriteOutput) {
  auto roots = rpcRootCounts(0);
  auto leaves = rpcLeafCounts(2);
  unsigned calls = 0;
  SbNetGroupReply reply{53, 59};
  for (uint32_t mode = 0; mode < SB_JSON_RPC_COUNT; ++mode) {
    if (mode != SB_JSON_RPC_ENQUEUE) EXPECT_EQ(sb_json_rpc_run(mode, &calls, rpcNeverCalled, 1, &reply), uint32_t(SB_JSON_RPC_INVALID));
    EXPECT_EQ(sb_json_rpc_run(mode, nullptr, rpcNeverCalled, 0, &reply), uint32_t(SB_JSON_RPC_INVALID));
    EXPECT_EQ(sb_json_rpc_run(mode, &calls, nullptr, 0, &reply), uint32_t(SB_JSON_RPC_INVALID));
    EXPECT_EQ(sb_json_rpc_run(mode, &calls, rpcNeverCalled, 0, nullptr), uint32_t(SB_JSON_RPC_INVALID));
  }
  EXPECT_EQ(sb_json_rpc_run(SB_JSON_RPC_COUNT, &calls, rpcNeverCalled, 0, &reply), uint32_t(SB_JSON_RPC_INVALID));
  EXPECT_EQ(calls, 0u);
  EXPECT_EQ(reply.a, uint64_t(53)); EXPECT_EQ(reply.b, uint64_t(59));
  EXPECT_EQ(rpcRootCounts(0), roots); EXPECT_EQ(rpcLeafCounts(2), leaves);
  for (uint32_t kind : {uint32_t(0), uint32_t(1)})
    EXPECT_EQ(sb_json_rpc_count(kind, SB_JSON_RPC_COUNT), uint64_t(0));
  for (uint32_t kind : {uint32_t(2), uint32_t(3)})
    EXPECT_EQ(sb_json_rpc_count(kind, SB_JSON_RPC_OP_COUNT), uint64_t(0));
  EXPECT_EQ(sb_json_rpc_count(4, 0), uint64_t(0));
  std::cout << "JSON_RPC_DIAGNOSTIC invalid-root no-host no-counter no-output-write\n";
}
#endif
