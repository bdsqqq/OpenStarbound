#include "StarRpcPromise.hpp"
#include "gtest/gtest.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <condition_variable>
#include <exception>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#ifdef STAR_USE_RUST_JSON_RPC
#include "StarRustRpcPromise.h"
#endif

// Compile-only contracts: a runtime done flag cannot make these native-invalid
// destructor/wrapper instantiations valid. Never enable in the ordinary suite.
#ifdef STAR_RPC_PROMISE_AUTO_ERROR_NEGATIVE
namespace {
struct PromiseNonStringError { explicit PromiseNonStringError(int) {} };
void promiseAutoErrorNegative() {
  auto pair = Star::RpcPromise<int, PromiseNonStringError>::createPair();
  Star::AutoFailRpcPromiseKeeper<int, PromiseNonStringError> guard(pair.second);
  guard.fulfill(1);
}
}
#endif
#ifdef STAR_RPC_PROMISE_MUTABLE_WRAP_NEGATIVE
namespace {
void promiseMutableWrapNegative() {
  auto promise = Star::RpcPromise<int>::createFulfilled(1);
  auto wrapped = promise.wrap([n = 0](int x) mutable { return x + ++n; });
  (void)wrapped;
}
}
#endif

using namespace Star;

namespace {
struct PromiseTrace {
  explicit PromiseTrace(char const* name) : name(name) {}
  ~PromiseTrace() { std::cout << "RPC_PROMISE_TRACE " << name << text << '\n'; }
  void add(std::string const& value) { text += " " + value; }
  template <typename T, typename E>
  void state(RpcPromise<T, E> const& p) {
    add(std::to_string(p.finished()) + std::to_string(p.succeeded()) + std::to_string(p.failed()));
  }
  char const* name;
  std::string text;
};
using Promise = RpcPromise<int>;
void pending(Promise const& p) {
  EXPECT_FALSE(p.finished()); EXPECT_FALSE(p.succeeded()); EXPECT_FALSE(p.failed());
  EXPECT_FALSE(p.result()); EXPECT_FALSE(p.error());
}
void success(Promise const& p, int value) {
  EXPECT_TRUE(p.finished()); EXPECT_TRUE(p.succeeded()); EXPECT_FALSE(p.failed());
  ASSERT_TRUE(p.result()); EXPECT_EQ(*p.result(), value); EXPECT_FALSE(p.error());
}
void failure(Promise const& p, String const& error) {
  EXPECT_TRUE(p.finished()); EXPECT_FALSE(p.succeeded()); EXPECT_TRUE(p.failed());
  EXPECT_FALSE(p.result()); ASSERT_TRUE(p.error()); EXPECT_EQ(*p.error(), error);
}
template <typename F>
void duplicate(F&& f, char const* message) {
  try { f(); FAIL() << "expected RpcPromiseException"; }
  catch (RpcPromiseException const& e) {
    // what() includes the native exception type and may include a stack trace.
    EXPECT_NE(std::string(e.what()).find(message), std::string::npos);
  }
}
struct CopyMarker {};
struct CopyProbe {
  std::vector<std::string> events;
  bool throwing = false;
  std::exception_ptr exception;
  CopyMarker const* identity = nullptr;
};
struct Tracked {
  Tracked(int value, std::shared_ptr<CopyProbe> probe) : value(value), probe(std::move(probe)) {}
  Tracked(Tracked const& other) : value(other.value), probe(other.probe) {
    probe->events.push_back("copy:" + std::to_string(value));
    if (probe->throwing) std::rethrow_exception(probe->exception);
  }
  Tracked(Tracked&& other) : value(other.value), probe(other.probe) {
    probe->events.push_back("move:" + std::to_string(value));
  }
  Tracked& operator=(Tracked const&) = default;
  Tracked& operator=(Tracked&&) = default;
  ~Tracked() { probe->events.push_back("drop:" + std::to_string(value)); }
  int value;
  std::shared_ptr<CopyProbe> probe;
};
std::shared_ptr<CopyProbe> copyProbe() {
  auto p = std::make_shared<CopyProbe>();
  try { throw CopyMarker{}; }
  catch (CopyMarker const& e) { p->identity = &e; p->exception = std::current_exception(); }
  return p;
}
struct Wrapper {
  Wrapper(std::shared_ptr<int> copies, std::shared_ptr<int> calls) : copies(copies), calls(calls) {}
  Wrapper(Wrapper const& other) : copies(other.copies), calls(other.calls) { ++*copies; }
  Wrapper(Wrapper&&) = default;
  int operator()(int value) const { ++*calls; return value + 1; }
  std::shared_ptr<int> copies, calls;
};
}

TEST(RpcPromise, PendingAndFactories) {
  PromiseTrace trace("pending-factories");
  auto pair = Promise::createPair(); pending(pair.first); trace.state(pair.first);
  auto good = Promise::createFulfilled(17); success(good, 17); trace.state(good);
  auto bad = Promise::createFailed("bad"); failure(bad, "bad"); trace.state(bad);
}

TEST(RpcPromise, ExactlyOnceAndNativeMessages) {
  PromiseTrace trace("once");
  auto good = Promise::createPair(); good.second.fulfill(12);
  duplicate([&] { good.second.fulfill(13); }, "fulfill called on already finished RpcPromise");
  duplicate([&] { good.second.fail("late"); }, "fail called on already finished RpcPromise");
  success(good.first, 12); trace.state(good.first);
  auto bad = Promise::createPair(); bad.second.fail("first");
  duplicate([&] { bad.second.fulfill(3); }, "fulfill called on already finished RpcPromise");
  duplicate([&] { bad.second.fail("second"); }, "fail called on already finished RpcPromise");
  failure(bad.first, "first"); trace.state(bad.first);
}

TEST(RpcPromise, ChainPendingFollowsChildRatherThanStoredVariant) {
  PromiseTrace trace("chain-success");
  auto parent = Promise::createPair(); auto child = Promise::createPair();
  parent.second.chain(child.first); pending(parent.first); trace.state(parent.first);
  duplicate([&] { parent.second.fulfill(1); }, "fulfill called on already finished RpcPromise");
  child.second.fulfill(31); success(parent.first, 31); trace.state(parent.first);
}

TEST(RpcPromise, AcyclicMultilevelChainFailure) {
  PromiseTrace trace("chain-error");
  auto a = Promise::createPair(); auto b = Promise::createPair(); auto c = Promise::createPair();
  a.second.chain(b.first); b.second.chain(c.first);
  pending(a.first); trace.state(a.first); c.second.fail("leaf");
  failure(a.first, "leaf"); failure(b.first, "leaf"); trace.state(a.first);
}

TEST(RpcPromise, ResultCopiesThrowOriginalAndRetryAfterUnlock) {
  PromiseTrace trace("result-copies"); auto probe = copyProbe();
  auto promise = RpcPromise<Tracked>::createFulfilled(Tracked(41, probe));
  probe->events.clear();
  { auto result = promise.result(); ASSERT_TRUE(result); EXPECT_EQ(result->value, 41); }
  EXPECT_EQ(probe->events, (std::vector<std::string>{"copy:41", "drop:41"}));
  probe->events.clear(); probe->throwing = true;
  try { (void)promise.result(); FAIL(); }
  catch (CopyMarker const& e) { EXPECT_EQ(&e, probe->identity); trace.add("original"); }
  EXPECT_EQ(probe->events, (std::vector<std::string>{"copy:41"}));
  probe->throwing = false; probe->events.clear();
  { auto retry = promise.result(); ASSERT_TRUE(retry); EXPECT_EQ(retry->value, 41); }
  EXPECT_EQ(probe->events, (std::vector<std::string>{"copy:41", "drop:41"}));
  trace.add("copy-drop/throw/copy-drop");
}

TEST(RpcPromise, ErrorCopiesThrowOriginalAndRetryAfterUnlock) {
  PromiseTrace trace("error-copies"); auto probe = copyProbe();
  auto promise = RpcPromise<int, Tracked>::createFailed(Tracked(42, probe));
  probe->events.clear();
  { auto error = promise.error(); ASSERT_TRUE(error); EXPECT_EQ(error->value, 42); }
  EXPECT_EQ(probe->events, (std::vector<std::string>{"copy:42", "drop:42"}));
  probe->events.clear(); probe->throwing = true;
  try { (void)promise.error(); FAIL(); }
  catch (CopyMarker const& e) { EXPECT_EQ(&e, probe->identity); trace.add("original"); }
  EXPECT_EQ(probe->events, (std::vector<std::string>{"copy:42"}));
  probe->throwing = false; probe->events.clear();
  { auto retry = promise.error(); ASSERT_TRUE(retry); EXPECT_EQ(retry->value, 42); }
  EXPECT_EQ(probe->events, (std::vector<std::string>{"copy:42", "drop:42"}));
  trace.add("copy-drop/throw/copy-drop");
}

TEST(RpcPromise, WrapDeferredAndCachedAfterSuccess) {
  PromiseTrace trace("wrap-cache"); auto pair = Promise::createPair(); int calls = 0;
  auto wrapped = pair.first.wrap([&](int x) { ++calls; return x * 2; });
  EXPECT_EQ(calls, 0); pending(wrapped); EXPECT_EQ(calls, 0);
  pair.second.fulfill(7); EXPECT_EQ(calls, 0);
  success(wrapped, 14); success(wrapped, 14); EXPECT_EQ(calls, 1);
  trace.state(wrapped); trace.add(std::to_string(calls));
}

TEST(RpcPromise, WrapPropagatesErrorWithoutCallingWrapper) {
  PromiseTrace trace("wrap-error"); auto pair = Promise::createPair(); int calls = 0;
  auto wrapped = pair.first.wrap([&](int x) { ++calls; return x; });
  pair.second.fail("source"); failure(wrapped, "source"); failure(wrapped, "source");
  EXPECT_EQ(calls, 0); trace.state(wrapped); trace.add(std::to_string(calls));
}

TEST(RpcPromise, ThrowingWrapperRetriedWithoutCachingException) {
  PromiseTrace trace("wrap-retry"); auto probe = copyProbe(); int calls = 0;
  auto wrapped = Promise::createFulfilled(9).wrap([&](int x) {
    if (++calls == 1) std::rethrow_exception(probe->exception);
    return x + 3;
  });
  try { (void)wrapped.finished(); FAIL(); }
  catch (CopyMarker const& e) { EXPECT_EQ(&e, probe->identity); trace.add("original"); }
  success(wrapped, 12); success(wrapped, 12); EXPECT_EQ(calls, 2);
  trace.state(wrapped); trace.add(std::to_string(calls));
}

TEST(RpcPromise, WrapperCaptureCopiesAndTwoLayers) {
  PromiseTrace trace("wrap-captures");
  auto copies = std::make_shared<int>(0), calls = std::make_shared<int>(0);
  Wrapper wrapper(copies, calls);
  auto first = Promise::createFulfilled(5).wrap(wrapper);
  // Native by-value parameter copies once; init-capture moves it. Evaluation
  // invokes the const capture directly, not a copied callable sent to Rust.
  EXPECT_EQ(*copies, 1); EXPECT_EQ(*calls, 0);
  auto second = first.wrap([](int x) { return x * 3; });
  // The second native `other = *this` copies first's stored callable/capture.
  // Evaluation itself must not add another copy.
  EXPECT_EQ(*copies, 2);
  success(second, 18); success(first, 6); success(second, 18);
  EXPECT_EQ(*copies, 2); EXPECT_EQ(*calls, 1);
  trace.add(std::to_string(*copies)); trace.add(std::to_string(*calls));
}

TEST(RpcPromise, AutoKeeperPendingDestructionUsesDefaultString) {
  PromiseTrace trace("auto-drop"); auto pair = Promise::createPair();
  { AutoFailRpcPromiseKeeper<int> guard(pair.second); pending(pair.first); }
  failure(pair.first, "Keeper destroyed"); trace.state(pair.first);
}

TEST(RpcPromise, AutoKeeperSuccessfulFailedAndChainedForwarding) {
  PromiseTrace trace("auto-forward");
  auto a = Promise::createPair(); { AutoFailRpcPromiseKeeper<int> guard(a.second); guard.fulfill(4); }
  success(a.first, 4); trace.state(a.first);
  auto b = Promise::createPair(); { AutoFailRpcPromiseKeeper<int> guard(b.second); guard.fail("explicit"); }
  failure(b.first, "explicit"); trace.state(b.first);
  auto c = Promise::createPair(); auto child = Promise::createPair();
  { AutoFailRpcPromiseKeeper<int> guard(c.second); guard.chain(child.first); }
  pending(c.first); child.second.fulfill(6); success(c.first, 6); trace.state(c.first);
}

TEST(RpcPromise, AutoKeeperMarksDoneBeforeEveryThrowingForward) {
  PromiseTrace trace("auto-before-throw");
  // The original keeper completes first. If forwarding marks done too late,
  // the guard's implicit-noexcept destructor would terminate. No death fixture
  // or deliberately throwing destructor is executed here.
  for (int mode = 0; mode != 3; ++mode) {
    auto pair = Promise::createPair(); pair.second.fulfill(11);
    {
      AutoFailRpcPromiseKeeper<int> guard(pair.second);
      duplicate([&] {
        if (mode == 0) guard.fulfill(2);
        else if (mode == 1) guard.fail("late");
        else guard.chain(Promise::createFulfilled(3));
      }, mode == 1 ? "fail called on already finished RpcPromise" : "fulfill called on already finished RpcPromise");
    }
    success(pair.first, 11); trace.state(pair.first);
  }
}

TEST(RpcPromise, TwoWritersBarrierOneWinnerAndConsistentFinalState) {
  PromiseTrace trace("two-writers"); auto pair = Promise::createPair();
  std::mutex mutex; std::condition_variable cv; int ready = 0; bool go = false;
  std::atomic<int> wins{0}, rejected{0}, unexpected{0};
  auto writer = [&](bool fulfill) {
    { std::unique_lock<std::mutex> lock(mutex); ++ready; cv.notify_all(); cv.wait(lock, [&] { return go; }); }
    try { if (fulfill) pair.second.fulfill(77); else pair.second.fail("race"); ++wins; }
    catch (RpcPromiseException const&) { ++rejected; }
    catch (...) { ++unexpected; }
  };
  std::thread a(writer, true), b(writer, false);
  { std::unique_lock<std::mutex> lock(mutex); cv.wait(lock, [&] { return ready == 2; }); go = true; }
  cv.notify_all(); a.join(); b.join();
  EXPECT_EQ(wins.load(), 1); EXPECT_EQ(rejected.load(), 1); EXPECT_EQ(unexpected.load(), 0);
  EXPECT_TRUE(pair.first.finished()); EXPECT_NE(pair.first.succeeded(), pair.first.failed());
  if (pair.first.succeeded()) success(pair.first, 77); else failure(pair.first, "race");
  // Winner is intentionally nondeterministic; trace only the invariant.
  trace.add("one-winner/one-rejected/consistent");
}

TEST(RpcPromise, SharedReferencesByValueAndCallbackOwnershipRelease) {
  PromiseTrace trace("reference-ownership");
  auto token = std::make_shared<int>(8); std::weak_ptr<int> weak = token;
  {
    auto pair = Promise::createPair(); auto keeper = pair.second;
    auto wrapped = pair.first.wrap([token](int x) { return x + *token; });
    auto copied = wrapped; token.reset(); EXPECT_FALSE(weak.expired());
    auto byValue = [](Promise p) { return p; };
    auto returned = byValue(copied); keeper.fulfill(2); success(returned, 10);
    // Cache completion does not retire the stored callable or its capture.
    EXPECT_FALSE(weak.expired()); trace.add("capture-live");
  }
  EXPECT_TRUE(weak.expired()); trace.add("capture-released");
}

#ifdef STAR_USE_RUST_JSON_RPC
namespace {
std::array<uint64_t, SB_RPC_PROMISE_COUNT> promiseRoots() {
  std::array<uint64_t, SB_RPC_PROMISE_COUNT> counts{};
  for (uint32_t i = 0; i < counts.size(); ++i) counts[i] = sb_rpc_promise_count(0, i);
  return counts;
}
uint32_t promiseUnexpectedHost(void* ctx, uint32_t, uint64_t, SbNetGroupReply*) {
  ++*static_cast<unsigned*>(ctx);
  return SB_RPC_PROMISE_HOST_ERROR;
}
}

TEST(RpcPromise, RustNaturalPublicRoutesReachEveryRoot) {
  auto before = promiseRoots();
  auto a = Promise::createPair(); pending(a.first);
  auto wrapped = a.first.wrap([](int x) { return x + 1; }); pending(wrapped);
  { AutoFailRpcPromiseKeeper<int> guard(a.second); guard.fulfill(4); }
  success(wrapped, 5);
  auto b = Promise::createPair();
  { AutoFailRpcPromiseKeeper<int> guard(b.second); }
  failure(b.first, "Keeper destroyed");
  auto after = promiseRoots();
  for (uint32_t i = 0; i < before.size(); ++i) {
    EXPECT_GT(after[i], before[i]) << "root " << i;
    std::cout << "RPC_PROMISE_DIAGNOSTIC root " << i << " positive\n";
  }
  // No claim that these public paths exercise every leaf or every failure.
  for (uint32_t kind : {0u, 1u}) EXPECT_EQ(sb_rpc_promise_count(kind, SB_RPC_PROMISE_COUNT), uint64_t(0));
  for (uint32_t kind : {2u, 3u}) EXPECT_EQ(sb_rpc_promise_count(kind, SB_RPC_PROMISE_OP_COUNT), uint64_t(0));
  EXPECT_EQ(sb_rpc_promise_count(4, 0), uint64_t(0));
}

TEST(RpcPromise, RustInvalidRootsPreserveOutputAndNeverCallHost) {
  auto before = promiseRoots(); unsigned calls = 0;
  SbNetGroupReply out{123, 456};
  auto rejected = [&](uint32_t mode, void* ctx, SbNetGroupHost host, uint64_t argument, SbNetGroupReply* reply) {
    EXPECT_EQ(sb_rpc_promise_run(mode, ctx, host, argument, reply), uint32_t(SB_RPC_PROMISE_INVALID));
    EXPECT_EQ(out.a, uint64_t(123)); EXPECT_EQ(out.b, uint64_t(456));
  };
  rejected(SB_RPC_PROMISE_COUNT, &calls, promiseUnexpectedHost, 0, &out);
  rejected(SB_RPC_PROMISE_FINISHED, &calls, promiseUnexpectedHost, 1, &out);
  rejected(SB_RPC_PROMISE_FINISHED, nullptr, promiseUnexpectedHost, 0, &out);
  rejected(SB_RPC_PROMISE_FINISHED, &calls, nullptr, 0, &out);
  rejected(SB_RPC_PROMISE_FINISHED, &calls, promiseUnexpectedHost, 0, nullptr);
  EXPECT_EQ(calls, 0u); EXPECT_EQ(promiseRoots(), before);
  std::cout << "RPC_PROMISE_DIAGNOSTIC invalid/no-host/no-count/output-preserved\n";
}
#endif

// ADL can overload the exact native logical expression. The proxy's implicit
// conversion and full-expression destruction are observable before assignment.
namespace PromiseAdl {
thread_local std::vector<std::string>* events = nullptr;
struct Result {
  Result() = default;
  Result(Result const&) = default;
  Result(Result&&) { if (events) events->push_back("move"); }
  Result& operator=(Result const&) = default;
  Result& operator=(Result&&) { if (events) events->push_back("assign"); return *this; }
};
struct Proxy {
  bool value;
#ifdef STAR_RPC_PROMISE_BOOL_RETURN_NEGATIVE
  explicit operator bool() const { return value; }
#else
  operator bool() const { if (events) events->push_back("bool"); return value; }
#endif
  ~Proxy() { if (events) events->push_back("proxy-drop"); }
};
Proxy operator||(MVariant<Result, RpcPromise<Result, String>> const& result, Maybe<String> const& error) {
  if (events) events->push_back("logical");
  return { !result.empty() || error.isValid() };
}
}

TEST(RpcPromise, AdlLogicalConversionAndTemporaryLifetime) {
  PromiseTrace trace("adl-logical"); std::vector<std::string> events;
  struct Reset { ~Reset() { PromiseAdl::events = nullptr; } } reset;
  PromiseAdl::events = &events;
  auto pair = RpcPromise<PromiseAdl::Result>::createPair();
  EXPECT_FALSE(pair.first.finished());
  EXPECT_EQ(events, (std::vector<std::string>{"logical", "bool", "proxy-drop"}));
  events.clear(); pair.second.fulfill(PromiseAdl::Result{});
  auto logical = std::find(events.begin(), events.end(), "logical");
  ASSERT_NE(logical, events.end());
  ASSERT_GE(std::distance(logical, events.end()), 4);
  EXPECT_EQ(logical[1], "bool"); EXPECT_EQ(logical[2], "proxy-drop");
  EXPECT_EQ(logical[3], "move");
  for (auto const& event : events) trace.add(event);
  events.clear(); EXPECT_TRUE(pair.first.finished());
  EXPECT_EQ(events, (std::vector<std::string>{"logical", "bool", "proxy-drop"}));
}
