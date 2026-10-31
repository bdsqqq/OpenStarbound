#include "StarWorkerPool.hpp"
#include "StarIterator.hpp"
#include "StarMathCommon.hpp"
#ifdef STAR_USE_RUST_WORKER_POOL
#include "StarWorkerPoolHost.hpp"
#endif

namespace Star {

bool WorkerPoolHandle::done() const {
  MutexLocker locker(m_impl->mutex);
  return m_impl->done;
}

bool WorkerPoolHandle::wait(unsigned millis) const {
#ifdef STAR_USE_RUST_WORKER_POOL
  MutexLocker locker(m_impl->mutex);
  return WorkerPoolDetail::run(SB_WORKER_POOL_HANDLE_WAIT, [&](uint32_t operation) -> uint32_t {
    switch (operation) {
    case SB_WORKER_POOL_DONE:
      return m_impl->done ? 1u : 0u;
    case SB_WORKER_POOL_NONZERO_TIMEOUT:
      return millis != 0 ? 1u : 0u;
    case SB_WORKER_POOL_TIMED_WAIT:
      m_impl->condition.wait(m_impl->mutex, millis);
      return 0;
    case SB_WORKER_POOL_RETHROW:
      if (m_impl->exception)
        std::rethrow_exception(m_impl->exception);
      return 0;
    default:
      WorkerPoolDetail::invalidOperation();
    }
  });
#else
  MutexLocker locker(m_impl->mutex);

  if (!m_impl->done && millis != 0)
    m_impl->condition.wait(m_impl->mutex, millis);

  if (m_impl->exception)
    std::rethrow_exception(m_impl->exception);

  return m_impl->done;
#endif
}

bool WorkerPoolHandle::poll() const {
  return wait(0);
}

void WorkerPoolHandle::finish() const {
#ifdef STAR_USE_RUST_WORKER_POOL
  MutexLocker locker(m_impl->mutex);
  WorkerPoolDetail::run(SB_WORKER_POOL_HANDLE_FINISH, [&](uint32_t operation) -> uint32_t {
    switch (operation) {
    case SB_WORKER_POOL_DONE:
      return m_impl->done ? 1u : 0u;
    case SB_WORKER_POOL_WAIT:
      m_impl->condition.wait(m_impl->mutex);
      return 0;
    case SB_WORKER_POOL_RETHROW:
      if (m_impl->exception)
        std::rethrow_exception(m_impl->exception);
      return 0;
    default:
      WorkerPoolDetail::invalidOperation();
    }
  });
#else
  MutexLocker locker(m_impl->mutex);

  if (!m_impl->done)
    m_impl->condition.wait(m_impl->mutex);

  if (m_impl->exception)
    std::rethrow_exception(m_impl->exception);

  return;
#endif
}

WorkerPoolHandle::Impl::Impl() : done(false) {}

WorkerPoolHandle::WorkerPoolHandle(shared_ptr<Impl> impl) : m_impl(std::move(impl)) {}

WorkerPool::WorkerPool(String name) : m_name(std::move(name)) {}

WorkerPool::WorkerPool(String name, unsigned threadCount) : WorkerPool(std::move(name)) {
  start(threadCount);
}

WorkerPool::~WorkerPool() {
  stop();
}

WorkerPool::WorkerPool(WorkerPool&&) = default;
WorkerPool& WorkerPool::operator=(WorkerPool&&) = default;

void WorkerPool::start(unsigned threadCount) {
#ifdef STAR_USE_RUST_WORKER_POOL
  MutexLocker threadLock(m_threadMutex);
  WorkerPoolDetail::run(SB_WORKER_POOL_START, [&](uint32_t operation) -> uint32_t {
    switch (operation) {
    case SB_WORKER_POOL_MARK_THREADS: {
      auto iterator = m_workerThreads.begin();
      auto end = m_workerThreads.end();
      WorkerPoolDetail::run(SB_WORKER_POOL_MARK, [&](uint32_t leaf) -> uint32_t {
        switch (leaf) {
        case SB_WORKER_POOL_MORE:
          return iterator != end ? 1u : 0u;
        case SB_WORKER_POOL_SET_STOP: {
          auto const& workerThread = *iterator;
          workerThread->shouldStop = true;
          return 0;
        }
        case SB_WORKER_POOL_ADVANCE:
          ++iterator;
          return 0;
        default:
          WorkerPoolDetail::invalidOperation();
        }
      });
      return 0;
    }
    case SB_WORKER_POOL_BROADCAST:
      m_workCondition.broadcast();
      return 0;
    case SB_WORKER_POOL_CLEAR_THREADS:
      m_workerThreads.clear();
      return 0;
    case SB_WORKER_POOL_ENTER_SPAWN: {
      size_t i = m_workerThreads.size();
      WorkerPoolDetail::run(SB_WORKER_POOL_SPAWN, [&](uint32_t leaf) -> uint32_t {
        switch (leaf) {
        case SB_WORKER_POOL_MORE:
          return i < threadCount ? 1u : 0u;
        case SB_WORKER_POOL_APPEND_THREAD:
          m_workerThreads.append(make_unique<WorkerThread>(this));
          return 0;
        case SB_WORKER_POOL_ADVANCE:
          ++i;
          return 0;
        default:
          WorkerPoolDetail::invalidOperation();
        }
      });
      return 0;
    }
    default:
      WorkerPoolDetail::invalidOperation();
    }
  });
#else
  MutexLocker threadLock(m_threadMutex);

  for (auto const& workerThread : m_workerThreads)
    workerThread->shouldStop = true;

  m_workCondition.broadcast();
  m_workerThreads.clear();

  for (size_t i = m_workerThreads.size(); i < threadCount; ++i)
    m_workerThreads.append(make_unique<WorkerThread>(this));
#endif
}

void WorkerPool::stop() {
#ifdef STAR_USE_RUST_WORKER_POOL
  MutexLocker threadLock(m_threadMutex);
  WorkerPoolDetail::run(SB_WORKER_POOL_STOP, [&](uint32_t operation) -> uint32_t {
    switch (operation) {
    case SB_WORKER_POOL_MARK_THREADS: {
      auto iterator = m_workerThreads.begin();
      auto end = m_workerThreads.end();
      WorkerPoolDetail::run(SB_WORKER_POOL_MARK, [&](uint32_t leaf) -> uint32_t {
        switch (leaf) {
        case SB_WORKER_POOL_MORE:
          return iterator != end ? 1u : 0u;
        case SB_WORKER_POOL_SET_STOP: {
          auto const& workerThread = *iterator;
          workerThread->shouldStop = true;
          return 0;
        }
        case SB_WORKER_POOL_ADVANCE:
          ++iterator;
          return 0;
        default:
          WorkerPoolDetail::invalidOperation();
        }
      });
      return 0;
    }
    case SB_WORKER_POOL_BROADCAST_LOCKED: {
      // Release the work lock before clearing (and joining) native threads.
      MutexLocker workLock(m_workMutex);
      m_workCondition.broadcast();
      return 0;
    }
    case SB_WORKER_POOL_CLEAR_THREADS:
      m_workerThreads.clear();
      return 0;
    default:
      WorkerPoolDetail::invalidOperation();
    }
  });
#else
  MutexLocker threadLock(m_threadMutex);
  for (auto const& workerThread : m_workerThreads)
    workerThread->shouldStop = true;

  {
    // Must hold the work lock while broadcasting to ensure that any worker
    // threads that might wait without stopping actually get the signal.
    MutexLocker workLock(m_workMutex);
    m_workCondition.broadcast();
  }

  m_workerThreads.clear();
#endif
}

void WorkerPool::finish() {
#ifdef STAR_USE_RUST_WORKER_POOL
  MutexLocker workMutex(m_workMutex);
  WorkerPoolDetail::run(SB_WORKER_POOL_FINISH, [&](uint32_t operation) -> uint32_t {
    switch (operation) {
    case SB_WORKER_POOL_EMPTY:
      return m_pendingWork.empty() ? 1u : 0u;
    case SB_WORKER_POOL_FINISH_WORK: {
      auto firstWork = m_pendingWork.takeFirst();
      workMutex.unlock();
      firstWork();
      Thread::yield();
      workMutex.lock();
      return 0;
    }
    case SB_WORKER_POOL_FINAL_UNLOCK:
      workMutex.unlock();
      return 0;
    case SB_WORKER_POOL_STOP_POOL:
      stop();
      return 0;
    default:
      WorkerPoolDetail::invalidOperation();
    }
  });
#else
  // This is kind of a weird way to "wait" until all the pending work is
  // finished.  In order for the currently active worker threads to
  // cooperatively complete the remaining work, the work lock must not be held
  // the entire time (then just this thread would be the one finishing the
  // work).  Instead, the calling thread joins in on the action and tries to
  // finish work while yielding to the other threads after each completed job.
  MutexLocker workMutex(m_workMutex);
  while (!m_pendingWork.empty()) {
    auto firstWork = m_pendingWork.takeFirst();
    workMutex.unlock();
    firstWork();
    Thread::yield();
    workMutex.lock();
  }
  workMutex.unlock();

  stop();
#endif
}

WorkerPoolHandle WorkerPool::addWork(function<void()> work) {
  // Construct a worker pool handle and wrap the work to signal the handle when
  // finished.  Set the result to empty string if successful and to the content
  // of the exception if an exception is thrown.
  auto workerPoolHandleImpl = make_shared<WorkerPoolHandle::Impl>();
  queueWork([workerPoolHandleImpl, work]() {
    try {
      work();
      MutexLocker handleLocker(workerPoolHandleImpl->mutex);
      workerPoolHandleImpl->done = true;
      workerPoolHandleImpl->condition.broadcast();
    } catch (...) {
      MutexLocker handleLocker(workerPoolHandleImpl->mutex);
      workerPoolHandleImpl->done = true;
      workerPoolHandleImpl->exception = std::current_exception();
      workerPoolHandleImpl->condition.broadcast();
    }
  });

  return workerPoolHandleImpl;
}

size_t WorkerPool::getWorkerCount() const {
  return m_workerThreads.size();
}

WorkerPool::WorkerThread::WorkerThread(WorkerPool* parent)
  : Thread(strf("WorkerThread for WorkerPool '{}'", parent->m_name)),
    parent(parent),
    shouldStop(false),
    waiting(false) {
  start();
}

WorkerPool::WorkerThread::~WorkerThread() {
  join();
}

void WorkerPool::WorkerThread::run() {
#ifdef STAR_USE_RUST_WORKER_POOL
  MutexLocker workLock(parent->m_workMutex);
  WorkerPoolDetail::run(SB_WORKER_POOL_RUN, [&](uint32_t operation) -> uint32_t {
    switch (operation) {
    case SB_WORKER_POOL_SHOULD_STOP:
      return shouldStop ? 1u : 0u;
    case SB_WORKER_POOL_EMPTY:
      return parent->m_pendingWork.empty() ? 1u : 0u;
    case SB_WORKER_POOL_WAIT_WORK:
      waiting = true;
      parent->m_workCondition.wait(parent->m_workMutex);
      waiting = false;
      return 0;
    case SB_WORKER_POOL_RUN_WORK: {
      auto work = parent->m_pendingWork.takeFirst();
      workLock.unlock();
      work();
      workLock.lock();
      return 0;
    }
    default:
      WorkerPoolDetail::invalidOperation();
    }
  });
#else
  MutexLocker workLock(parent->m_workMutex);
  while (true) {
    if (shouldStop)
      break;

    if (parent->m_pendingWork.empty()) {
      waiting = true;
      parent->m_workCondition.wait(parent->m_workMutex);
      waiting = false;
    }

    if (!parent->m_pendingWork.empty()) {
      auto work = parent->m_pendingWork.takeFirst();
      workLock.unlock();
      work();
      workLock.lock();
    }
  }
#endif
}

void WorkerPool::queueWork(function<void()> work) {
  MutexLocker workLock(m_workMutex);
  m_pendingWork.append(std::move(work));
  m_workCondition.signal();
}

}
