#include "StarWorkerPool.hpp"

#include "gtest/gtest.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <exception>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#if defined(STAR_USE_RUST_WORKER_POOL) && STAR_USE_RUST_WORKER_POOL
#include "StarRustWorkerPool.h"
#endif

using namespace Star;

TEST(WorkerPoolTest, All) {
  int counter = 0;
  Mutex counterMutex;

  auto incCounter = [&counter, &counterMutex]() {
    Thread::sleep(100);
    MutexLocker locker(counterMutex);
    counter += 1;
  };

  Deque<WorkerPoolHandle> handles;

  WorkerPool workerPool("WorkerPoolTest");
  for (size_t i = 0; i < 10; ++i)
    handles.append(workerPool.addWork(incCounter));

  workerPool.start(10);

  for (size_t i = 0; i < 90; ++i)
    handles.append(workerPool.addWork(incCounter));

  while (handles.size() > 20)
    handles.takeFirst().finish();

  workerPool.finish();

  EXPECT_EQ(counter, 100);
}

namespace {
// Test-only predicate waits tolerate spurious wakes. Production waits currently
// do not loop; these fixtures do not silently strengthen that native contract.
class WorkerGate {
public:
  void enter() {
    std::unique_lock<std::mutex> lock(m_mutex);
    ++m_entered;
    m_condition.notify_all();
    auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    if (!m_condition.wait_until(lock, deadline, [&] { return m_released; }))
      timedOut = true;
  }

  bool awaitEntered(unsigned count = 1) {
    std::unique_lock<std::mutex> lock(m_mutex);
    auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    return m_condition.wait_until(lock, deadline, [&] { return m_entered >= count; });
  }

  void release() {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_released = true;
    m_condition.notify_all();
  }

  std::atomic<bool> timedOut{false};

private:
  std::mutex m_mutex;
  std::condition_variable m_condition;
  unsigned m_entered = 0;
  bool m_released = false;
};

// Declare AFTER the pool: early returns must open the gate BEFORE its destructor
// joins workers. The gate itself must outlive both objects.
struct ReleaseWorkerGate {
  WorkerGate& gate;
  ~ReleaseWorkerGate() { gate.release(); }
};

struct WorkerPoolThrownObject {
  int value;
};

std::exception_ptr workerPoolOriginalException() {
  try {
    throw WorkerPoolThrownObject{731};
  } catch (...) {
    return std::current_exception();
  }
}

void expectWorkerPoolException(std::function<void()> const& action, std::exception_ptr original) {
  try {
    action();
    ADD_FAILURE() << "expected the original non-standard exception";
  } catch (...) {
    EXPECT_EQ(std::current_exception(), original);
    try {
      throw;
    } catch (WorkerPoolThrownObject const& object) {
      EXPECT_EQ(object.value, 731);
    } catch (...) {
      ADD_FAILURE() << "exception type changed";
    }
  }
}

struct WorkerCallableState {
  void record(char const* event, int liveDelta = 0) {
    std::lock_guard<std::mutex> lock(mutex);
    events.emplace_back(event);
    live += liveDelta;
    if (std::string(event) == "copy")
      ++copies;
  }

  std::mutex mutex;
  std::vector<std::string> events;
  int live = 0;
  int copies = 0;
};

struct WorkerTrackedCallable {
  explicit WorkerTrackedCallable(std::shared_ptr<WorkerCallableState> state,
      std::function<void()> body = {}) : state(std::move(state)), body(std::move(body)) {
    this->state->record("construct", 1);
  }
  WorkerTrackedCallable(WorkerTrackedCallable const& other) : state(other.state), body(other.body) {
    state->record("copy", 1);
  }
  WorkerTrackedCallable(WorkerTrackedCallable&& other) noexcept
    : state(std::move(other.state)), body(std::move(other.body)) {
    state->record("move");
  }
  ~WorkerTrackedCallable() {
    if (state)
      state->record("destroy", -1);
  }
  void operator()() const {
    state->record("call");
    if (body)
      body();
  }
  std::shared_ptr<WorkerCallableState> state;
  std::function<void()> body;
};
}

TEST(WorkerPoolPolicy, StoppedPoolKeepsPendingWorkUntilCallerFinishes) {
  WorkerPool pool("stopped-policy");
  EXPECT_EQ(pool.getWorkerCount(), 0u);
  int calls = 0;
  auto handle = pool.addWork([&] { ++calls; });
  pool.stop();
  EXPECT_EQ(pool.getWorkerCount(), 0u);
  EXPECT_EQ(calls, 0);
  EXPECT_FALSE(handle.done());
  EXPECT_FALSE(handle.poll());
  EXPECT_FALSE(handle.wait(0));
#if defined(STAR_USE_RUST_WORKER_POOL) && STAR_USE_RUST_WORKER_POOL
  auto finishBefore = sb_worker_pool_count(0, SB_WORKER_POOL_FINISH);
  auto stopBefore = sb_worker_pool_count(0, SB_WORKER_POOL_STOP);
  auto markBefore = sb_worker_pool_count(0, SB_WORKER_POOL_MARK);
#endif
  pool.finish();
#if defined(STAR_USE_RUST_WORKER_POOL) && STAR_USE_RUST_WORKER_POOL
  EXPECT_GT(sb_worker_pool_count(0, SB_WORKER_POOL_FINISH), finishBefore);
  EXPECT_GT(sb_worker_pool_count(0, SB_WORKER_POOL_STOP), stopBefore);
  EXPECT_GT(sb_worker_pool_count(0, SB_WORKER_POOL_MARK), markBefore);
#endif
  EXPECT_EQ(calls, 1);
  EXPECT_TRUE(handle.done());
  EXPECT_TRUE(handle.poll());
}

TEST(WorkerPoolPolicy, CallerFinishIsFifoAndCallbacksCanEnqueue) {
  WorkerPool pool("fifo-policy");
  std::vector<int> order;
  auto first = pool.addWork([&] {
    order.push_back(1);
    // Reentry would deadlock if the callback still held the work mutex.
    pool.addWork([&] { order.push_back(3); });
  });
  auto second = pool.addWork([&] { order.push_back(2); });
  pool.finish();
  EXPECT_EQ(order, (std::vector<int>{1, 2, 3}));
  EXPECT_TRUE(first.done());
  EXPECT_TRUE(second.done());
  EXPECT_EQ(pool.getWorkerCount(), 0u);
  std::printf("WORKER_POOL_TRACE fifo");
  for (int value : order)
    std::printf(" %d", value);
  std::printf("\n");
}

TEST(WorkerPoolPolicy, PendingHandlePollAndTimedWaitThenRepeatCompletion) {
  WorkerGate gate;
  std::atomic<int> calls{0};
  WorkerPool pool("handle-policy", 1);
  ReleaseWorkerGate release{gate};
  auto handle = pool.addWork([&] { gate.enter(); ++calls; });
  if (!gate.awaitEntered()) {
    ADD_FAILURE() << "worker did not reach gate within 2 seconds";
    return;
  }
  EXPECT_FALSE(handle.done());
  EXPECT_FALSE(handle.poll());
  EXPECT_FALSE(handle.wait(0));
  EXPECT_FALSE(handle.wait(1));
  EXPECT_EQ(calls.load(), 0);
  gate.release();
  // Join first, rather than relying on the native single CV wait being immune
  // to spurious wakes. finish() is also exercised on the completed handle.
  pool.finish();
  EXPECT_FALSE(gate.timedOut.load());
  EXPECT_EQ(calls.load(), 1);
#if defined(STAR_USE_RUST_WORKER_POOL) && STAR_USE_RUST_WORKER_POOL
  auto waitBefore = sb_worker_pool_count(0, SB_WORKER_POOL_HANDLE_WAIT);
  auto finishBefore = sb_worker_pool_count(0, SB_WORKER_POOL_HANDLE_FINISH);
#endif
  handle.finish();
  handle.finish();
  EXPECT_TRUE(handle.done());
  EXPECT_TRUE(handle.poll());
  EXPECT_TRUE(handle.wait(0));
  EXPECT_TRUE(handle.wait(1));
#if defined(STAR_USE_RUST_WORKER_POOL) && STAR_USE_RUST_WORKER_POOL
  EXPECT_GT(sb_worker_pool_count(0, SB_WORKER_POOL_HANDLE_WAIT), waitBefore);
  EXPECT_GT(sb_worker_pool_count(0, SB_WORKER_POOL_HANDLE_FINISH), finishBefore);
#endif
  EXPECT_EQ(pool.getWorkerCount(), 0u);
}

TEST(WorkerPoolPolicy, HandleRetainsExactNonstandardException) {
  WorkerPool pool("handle-exception-policy");
  auto original = workerPoolOriginalException();
  auto handle = pool.addWork([original] { std::rethrow_exception(original); });
  pool.finish();
  EXPECT_NO_THROW(EXPECT_TRUE(handle.done()));
  expectWorkerPoolException([&] { handle.wait(0); }, original);
  expectWorkerPoolException([&] { handle.wait(1); }, original);
  expectWorkerPoolException([&] { handle.poll(); }, original);
  expectWorkerPoolException([&] { handle.finish(); }, original);
  expectWorkerPoolException([&] { handle.finish(); }, original);
  EXPECT_NO_THROW(EXPECT_TRUE(handle.done()));
  std::printf("WORKER_POOL_TRACE exception wait0 wait1 poll finish finish done\n");
}

TEST(WorkerPoolPolicy, ProducerZeroCompletesButEmptyMaybeRemainsPending) {
  WorkerPool pool("producer-values-policy");
  auto zero = pool.addProducer<int>([] { return 0; });
  auto empty = pool.addProducer<Maybe<int>>([] { return Maybe<int>(); });
  EXPECT_FALSE(zero.done());
  EXPECT_FALSE(empty.done());
  EXPECT_FALSE(zero.poll());
  EXPECT_FALSE(empty.wait(0));
  pool.finish();
  EXPECT_TRUE(zero.done());
  // Maybe<Maybe<int>>'s converting assignment resets the outer Maybe for an
  // empty inner value. Native completion remains false after the job ran;
  // get() would wait for a signal that has already happened, so do not call it.
  EXPECT_FALSE(empty.done());
#if defined(STAR_USE_RUST_WORKER_POOL) && STAR_USE_RUST_WORKER_POOL
  auto waitBefore = sb_worker_pool_count(0, SB_WORKER_POOL_HANDLE_WAIT);
  auto finishBefore = sb_worker_pool_count(0, SB_WORKER_POOL_HANDLE_FINISH);
#endif
  EXPECT_TRUE(zero.wait(0));
  EXPECT_FALSE(empty.poll());
  EXPECT_FALSE(empty.wait(1));
  EXPECT_EQ(zero.get(), 0);
  int* identity = &zero.get();
  zero.get() = 17;
  EXPECT_EQ(&zero.get(), identity);
  auto const& constZero = zero;
  EXPECT_EQ(&constZero.get(), identity);
  EXPECT_EQ(constZero.get(), 17);
  EXPECT_TRUE(zero.wait(1));
  std::printf("WORKER_POOL_TRACE producer zero-completed empty-maybe-native-pending\n");
#if defined(STAR_USE_RUST_WORKER_POOL) && STAR_USE_RUST_WORKER_POOL
  EXPECT_GT(sb_worker_pool_count(0, SB_WORKER_POOL_HANDLE_WAIT), waitBefore);
  EXPECT_GT(sb_worker_pool_count(0, SB_WORKER_POOL_HANDLE_FINISH), finishBefore);
#endif
}

TEST(WorkerPoolPolicy, ProducerMoveOnlyResultHasStableConstAndMutableReferences) {
  WorkerPool pool("producer-move-only-policy");
  auto promise = pool.addProducer<std::unique_ptr<int>>([] {
    return std::unique_ptr<int>(new int(42));
  });
  pool.finish();
  EXPECT_TRUE(promise.done());
  EXPECT_TRUE(promise.poll());
  auto* resultIdentity = &promise.get();
  int* pointee = promise.get().get();
  ASSERT_NE(pointee, nullptr);
  EXPECT_EQ(*pointee, 42);
  EXPECT_EQ(&promise.get(), resultIdentity);
  auto const& constPromise = promise;
  EXPECT_EQ(&constPromise.get(), resultIdentity);
  EXPECT_EQ(constPromise.get().get(), pointee);
  EXPECT_TRUE(promise.wait(1));
}

TEST(WorkerPoolPolicy, ProducerRetainsExactNonstandardException) {
  WorkerPool pool("producer-exception-policy");
  auto original = workerPoolOriginalException();
  auto promise = pool.addProducer<int>([original]() -> int { std::rethrow_exception(original); });
  EXPECT_FALSE(promise.done());
  pool.finish();
  EXPECT_NO_THROW(EXPECT_TRUE(promise.done()));
  expectWorkerPoolException([&] { promise.wait(0); }, original);
  expectWorkerPoolException([&] { promise.wait(1); }, original);
  expectWorkerPoolException([&] { promise.poll(); }, original);
  expectWorkerPoolException([&] { promise.get(); }, original);
  auto const& constPromise = promise;
  expectWorkerPoolException([&] { constPromise.get(); }, original);
  EXPECT_NO_THROW(EXPECT_TRUE(promise.done()));
}

TEST(WorkerPoolPolicy, PendingProducerPollAndTimedWaitThenGet) {
  WorkerGate gate;
  WorkerPool pool("producer-gate-policy", 1);
  ReleaseWorkerGate release{gate};
  auto promise = pool.addProducer<int>([&] { gate.enter(); return 23; });
  if (!gate.awaitEntered()) {
    ADD_FAILURE() << "producer did not reach gate within 2 seconds";
    return;
  }
  EXPECT_FALSE(promise.done());
  EXPECT_FALSE(promise.poll());
  EXPECT_FALSE(promise.wait(0));
  EXPECT_FALSE(promise.wait(1));
  gate.release();
  pool.finish();
  EXPECT_FALSE(gate.timedOut.load());
  EXPECT_TRUE(promise.done());
  EXPECT_TRUE(promise.poll());
  EXPECT_TRUE(promise.wait(1));
  EXPECT_EQ(promise.get(), 23);
  EXPECT_EQ(&promise.get(), &promise.get());
  auto const& constPromise = promise;
  EXPECT_EQ(&constPromise.get(), &promise.get());
}

TEST(WorkerPoolPolicy, CallerCallableCopiesAndDestructsBeforeFinishReturns) {
  auto state = std::make_shared<WorkerCallableState>();
  {
    WorkerPool pool("caller-lifetime-policy");
    WorkerTrackedCallable root(state);
    std::function<void()> work(root);
    int copiesBefore = state->copies;
    auto handle = pool.addWork(std::move(work));
    work = {}; // Do not rely on a moved-from std::function retaining no target.
    // addWork's named by-value function is captured BY COPY, not moved into
    // the wrapper. Do not impose a library-specific total copy count.
    EXPECT_GT(state->copies, copiesBefore);
    EXPECT_GE(state->live, 2);
    EXPECT_FALSE(handle.done());
    state->record("before-finish");
    pool.finish();
    state->record("after-finish");
    EXPECT_EQ(state->live, 1);
    EXPECT_TRUE(handle.done());
  }
  EXPECT_EQ(state->live, 0);
  std::printf("WORKER_POOL_TRACE callable");
  for (auto const& event : state->events)
    std::printf(" %s", event.c_str());
  std::printf("\n");
}

TEST(WorkerPoolPolicy, WorkerCallableLifetimeEndsBeforeStopReturns) {
  auto state = std::make_shared<WorkerCallableState>();
  WorkerGate gate;
  WorkerPool pool("worker-lifetime-policy", 1);
  ReleaseWorkerGate release{gate};
  {
    WorkerTrackedCallable root(state, [&] { gate.enter(); });
    std::function<void()> work(root);
    auto handle = pool.addWork(std::move(work));
    work = {};
    if (!gate.awaitEntered()) {
      ADD_FAILURE() << "tracked callable did not reach gate within 2 seconds";
      return;
    }
    {
      std::lock_guard<std::mutex> lock(state->mutex);
      EXPECT_GE(state->live, 2);
      EXPECT_GE(state->copies, 2);
    }
    EXPECT_FALSE(handle.done());
    gate.release();
    pool.stop();
    EXPECT_FALSE(gate.timedOut.load());
    EXPECT_TRUE(handle.done());
    EXPECT_EQ(pool.getWorkerCount(), 0u);
    EXPECT_EQ(state->live, 1);
  }
  EXPECT_EQ(state->live, 0);
  // Deliberately no worker-order trace: scheduling is not deterministic.
}

TEST(WorkerPoolPolicy, TwoWorkersRunConcurrentlyBeforeEitherGateIsReleased) {
#if defined(STAR_USE_RUST_WORKER_POOL) && STAR_USE_RUST_WORKER_POOL
  auto startBefore = sb_worker_pool_count(1, SB_WORKER_POOL_START);
  auto spawnBefore = sb_worker_pool_count(1, SB_WORKER_POOL_SPAWN);
  auto runBefore = sb_worker_pool_count(1, SB_WORKER_POOL_RUN);
  auto runWorkBefore = sb_worker_pool_count(2, SB_WORKER_POOL_RUN_WORK);
#endif
  WorkerGate gate;
  std::atomic<unsigned> mask{0};
  WorkerPool pool("concurrent-policy", 2);
  ReleaseWorkerGate release{gate};
  auto first = pool.addWork([&] { gate.enter(); mask.fetch_or(1u); });
  auto second = pool.addWork([&] { gate.enter(); mask.fetch_or(2u); });
  EXPECT_EQ(pool.getWorkerCount(), 2u);
  if (!gate.awaitEntered(2)) {
    ADD_FAILURE() << "both workers must enter before release within 2 seconds";
    return;
  }
  EXPECT_EQ(mask.load(), 0u);
  EXPECT_FALSE(first.done());
  EXPECT_FALSE(second.done());
  gate.release();
  pool.finish();
  EXPECT_FALSE(gate.timedOut.load());
  EXPECT_EQ(mask.load(), 3u);
  EXPECT_TRUE(first.done());
  EXPECT_TRUE(second.done());
  EXPECT_EQ(pool.getWorkerCount(), 0u);
#if defined(STAR_USE_RUST_WORKER_POOL) && STAR_USE_RUST_WORKER_POOL
  // RUN enters on native worker threads: current-thread counters cannot prove
  // their execution. Both gates were reached before caller finish could help.
  EXPECT_GT(sb_worker_pool_count(1, SB_WORKER_POOL_START), startBefore);
  EXPECT_GT(sb_worker_pool_count(1, SB_WORKER_POOL_SPAWN), spawnBefore);
  EXPECT_GT(sb_worker_pool_count(1, SB_WORKER_POOL_RUN), runBefore);
  EXPECT_GT(sb_worker_pool_count(2, SB_WORKER_POOL_RUN_WORK), runWorkBefore);
#endif
}

TEST(WorkerPoolPolicy, StopJoinsOneControlledActiveJob) {
  WorkerGate gate;
  std::atomic<unsigned> completed{0};
  WorkerPool pool("stop-active-policy", 1);
  ReleaseWorkerGate release{gate};
  auto handle = pool.addWork([&] { gate.enter(); ++completed; });
  if (!gate.awaitEntered()) {
    ADD_FAILURE() << "active worker did not reach gate within 2 seconds";
    return;
  }
  EXPECT_EQ(completed.load(), 0u);
  EXPECT_FALSE(handle.done());
  // No new tasks, no idle-worker start/reconfigure broadcast assumption.
  gate.release();
  pool.stop();
  EXPECT_FALSE(gate.timedOut.load());
  EXPECT_EQ(completed.load(), 1u);
  EXPECT_TRUE(handle.done());
  EXPECT_EQ(pool.getWorkerCount(), 0u);
}
