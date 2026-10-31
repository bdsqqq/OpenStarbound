#pragma once

#include <vector>

#include "StarConfig.hpp"

#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
#include "StarFlatHashTableHost.hpp"
#endif

namespace Star {

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
struct FlatHashTable {
private:
  static size_t const EmptyHashValue = 0;
  static size_t const EndHashValue = 1;
  static size_t const FilledHashBit = (size_t)1 << (sizeof(size_t) * 8 - 1);

  struct Bucket {
    Bucket();
    ~Bucket();

    Bucket(Bucket const& rhs);
    Bucket(Bucket&& rhs);

    Bucket& operator=(Bucket const& rhs);
    Bucket& operator=(Bucket&& rhs);

    void setFilled(size_t hash, Value value);
    void setEmpty();
    void setEnd();

    Value const* valuePtr() const;
    Value* valuePtr();
    bool isEmpty() const;
    bool isEnd() const;

    union {
      Value value;
    };
    size_t hash;
  };

  typedef std::vector<Bucket, typename std::allocator_traits<Allocator>::template rebind_alloc<Bucket>> Buckets;

public:
  struct const_iterator {
    bool operator==(const_iterator const& rhs) const;
    bool operator!=(const_iterator const& rhs) const;

    const_iterator& operator++();
    const_iterator operator++(int);

    Value const& operator*() const;
    Value const* operator->() const;

    Bucket const* current;
  };

  struct iterator {
    bool operator==(iterator const& rhs) const;
    bool operator!=(iterator const& rhs) const;

    iterator& operator++();
    iterator operator++(int);

    Value& operator*() const;
    Value* operator->() const;

    operator const_iterator() const;

    Bucket* current;
  };

  FlatHashTable(size_t bucketCount, GetKey const& getKey, Hash const& hash, Equals const& equal, Allocator const& alloc);

  iterator begin();
  iterator end();

  const_iterator begin() const;
  const_iterator end() const;

  size_t empty() const;
  size_t size() const;
  void clear();

  pair<iterator, bool> insert(Value value);

  iterator erase(const_iterator pos);
  iterator erase(const_iterator first, const_iterator last);

  const_iterator find(Key const& key) const;
  iterator find(Key const& key);

  void reserve(size_t capacity);
  Allocator getAllocator() const;

  bool operator==(FlatHashTable const& rhs) const;
  bool operator!=(FlatHashTable const& rhs) const;

private:
  static constexpr size_t MinCapacity = 8;
  static constexpr double MaxFillLevel = 0.7;

  // Scans for the next bucket value that is non-empty
  static Bucket* scan(Bucket* p);
  static Bucket const* scan(Bucket const* p);

#ifndef STAR_USE_RUST_FLAT_HASH_TABLE
  size_t hashBucket(size_t hash) const;
  size_t bucketError(size_t current, size_t target) const;
#endif
  void checkCapacity(size_t additionalCapacity);

  Buckets m_buckets;
  size_t m_filledCount;

  GetKey m_getKey;
  Hash m_hash;
  Equals m_equals;
};

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::Bucket() {
  this->hash = EmptyHashValue;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::~Bucket() {
  if (auto s = valuePtr())
    s->~Value();
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::Bucket(Bucket const& rhs) {
  this->hash = rhs.hash;
  if (auto o = rhs.valuePtr())
    new (&this->value) Value(*o);
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::Bucket(Bucket&& rhs) {
  this->hash = rhs.hash;
  if (auto o = rhs.valuePtr())
    new (&this->value) Value(std::move(*o));
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::operator=(Bucket const& rhs) -> Bucket& {
  if (auto o = rhs.valuePtr()) {
    if (auto s = valuePtr())
      *s = *o;
    else
      new (&this->value) Value(*o);
  } else {
    if (auto s = valuePtr())
      s->~Value();
  }
  this->hash = rhs.hash;
  return *this;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::operator=(Bucket&& rhs) -> Bucket& {
  if (auto o = rhs.valuePtr()) {
    if (auto s = valuePtr())
      *s = std::move(*o);
    else
      new (&this->value) Value(std::move(*o));
  } else {
    if (auto s = valuePtr())
      s->~Value();
  }
  this->hash = rhs.hash;
  return *this;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
void FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::setFilled(size_t hash, Value value) {
  if (auto s = valuePtr())
    *s = std::move(value);
  else
    new (&this->value) Value(std::move(value));
  this->hash = hash | FilledHashBit;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
void FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::setEmpty() {
  if (auto s = valuePtr())
    s->~Value();
  this->hash = EmptyHashValue;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
void FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::setEnd() {
  if (auto s = valuePtr())
    s->~Value();
  this->hash = EndHashValue;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
Value const* FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::valuePtr() const {
  if (hash & FilledHashBit)
    return &this->value;
  return nullptr;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
Value* FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::valuePtr() {
  if (hash & FilledHashBit)
    return &this->value;
  return nullptr;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
bool FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::isEmpty() const {
  return this->hash == EmptyHashValue;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
bool FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::Bucket::isEnd() const {
  return this->hash == EndHashValue;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
bool FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::const_iterator::operator==(const_iterator const& rhs) const {
  return current == rhs.current;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
bool FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::const_iterator::operator!=(const_iterator const& rhs) const {
  return current != rhs.current;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::const_iterator::operator++() -> const_iterator& {
  current = scan(++current);
  return *this;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::const_iterator::operator++(int) -> const_iterator {
  const_iterator copy(*this);
  operator++();
  return copy;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::const_iterator::operator*() const -> Value const& {
  return *operator->();
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::const_iterator::operator->() const -> Value const* {
  return current->valuePtr();
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
bool FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::iterator::operator==(iterator const& rhs) const {
  return current == rhs.current;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
bool FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::iterator::operator!=(iterator const& rhs) const {
  return current != rhs.current;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::iterator::operator++() -> iterator& {
  current = scan(++current);
  return *this;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::iterator::operator++(int) -> iterator {
  iterator copy(*this);
  operator++();
  return copy;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::iterator::operator*() const -> Value& {
  return *operator->();
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::iterator::operator->() const -> Value* {
  return current->valuePtr();
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::iterator::operator typename FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::const_iterator() const {
  return const_iterator{current};
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::FlatHashTable(size_t bucketCount,
    GetKey const& getKey, Hash const& hash, Equals const& equal, Allocator const& alloc)
  : m_buckets(alloc), m_filledCount(0), m_getKey(getKey),
    m_hash(hash), m_equals(equal) {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  checkCapacity(bucketCount);
#else
  if (bucketCount != 0)
    checkCapacity(bucketCount);
#endif
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::begin() -> iterator {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  auto reply = FlatHashTableDetail::run(SB_FLAT_HASH_BEGIN, [&](uint32_t operation, size_t) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_SIZE: return m_buckets.size();
      default: FlatHashTableDetail::invalidOperation();
    }
  });
  if (reply.found > 1)
    FlatHashTableDetail::invalidOperation();
  if (!reply.found)
    return end();
  return iterator{scan(m_buckets.data())};
#else
  if (m_buckets.empty())
    return end();
  return iterator{scan(m_buckets.data())};
#endif
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::end() -> iterator {
  return iterator{m_buckets.data() + m_buckets.size() - 1};
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::begin() const -> const_iterator {
  return const_cast<FlatHashTable*>(this)->begin();
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::end() const -> const_iterator {
  return const_cast<FlatHashTable*>(this)->end();
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
size_t FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::empty() const {
  return m_filledCount == 0;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
size_t FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::size() const {
  return m_filledCount;
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
void FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::clear() {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  FlatHashTableDetail::run(SB_FLAT_HASH_CLEAR, [&](uint32_t operation, size_t argument) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_SIZE: return m_buckets.size();
      case SB_FLAT_HASH_CLEAR_BUCKET: m_buckets[argument].setEmpty(); return 0;
      case SB_FLAT_HASH_RESET_FILLED: m_filledCount = 0; return 0;
      default: FlatHashTableDetail::invalidOperation();
    }
  });
#else
  if (m_buckets.empty())
    return;

  for (size_t i = 0; i < m_buckets.size() - 1; ++i)
    m_buckets[i].setEmpty();
  m_filledCount = 0;
#endif
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::insert(Value value) -> pair<iterator, bool> {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  Bucket* active = nullptr;
  Value* activeValue = nullptr;
  auto reply = FlatHashTableDetail::run(SB_FLAT_HASH_INSERT, [&](uint32_t operation, size_t argument) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_SIZE: return m_buckets.size();
      case SB_FLAT_HASH_HASH: return m_hash(m_getKey(value));
      case SB_FLAT_HASH_LOAD:
        active = &m_buckets[argument];
        activeValue = active->valuePtr();
        return activeValue ? 1 : 0;
      case SB_FLAT_HASH_EQUALS:
        return m_equals(m_getKey(*activeValue), m_getKey(value)) ? 1 : 0;
      // Retain the selected bucket across equality and Value swap reentry.
      case SB_FLAT_HASH_ACTIVE_HASH: return active->hash;
      // Keep the original expression native: Release fast-math may evaluate
      // its load-factor comparison differently from Rust floating arithmetic.
      case SB_FLAT_HASH_CAPACITY_NEEDED:
        return (m_buckets.empty() || m_filledCount + 1 > (m_buckets.size() - 1) * MaxFillLevel) ? 1 : 0;
      case SB_FLAT_HASH_ENSURE_CAPACITY: checkCapacity(1); return 0;
      case SB_FLAT_HASH_SWAP_VALUE: swap(value, *activeValue); return 0;
      case SB_FLAT_HASH_EXCHANGE_HASH: {
        size_t previous = active->hash;
        active->hash = argument;
        return previous;
      }
      case SB_FLAT_HASH_SET_FILLED: active->setFilled(argument, std::move(value)); return 0;
      case SB_FLAT_HASH_INCREMENT_FILLED: ++m_filledCount; return 0;
      default: FlatHashTableDetail::invalidOperation();
    }
  });
  if (reply.found > 1)
    FlatHashTableDetail::invalidOperation();
  return make_pair(iterator{m_buckets.data() + reply.index}, reply.found == 0);
#else
  if (m_buckets.empty() || m_filledCount + 1 > (m_buckets.size() - 1) * MaxFillLevel)
    checkCapacity(1);

  size_t hash = m_hash(m_getKey(value)) | FilledHashBit;
  size_t targetBucket = hashBucket(hash);
  size_t currentBucket = targetBucket;
  size_t insertedBucket = NPos;

  while (true) {
    auto& target = m_buckets[currentBucket];
    if (auto entryValue = target.valuePtr()) {
      if (target.hash == hash && m_equals(m_getKey(*entryValue), m_getKey(value)))
        return make_pair(iterator{m_buckets.data() + currentBucket}, false);

      size_t entryTargetBucket = hashBucket(target.hash);
      size_t entryError = bucketError(currentBucket, entryTargetBucket);
      size_t addError = bucketError(currentBucket, targetBucket);
      if (addError > entryError) {
        if (insertedBucket == NPos)
          insertedBucket = currentBucket;

        swap(value, *entryValue);
        swap(hash, target.hash);
        targetBucket = entryTargetBucket;
      }
      currentBucket = hashBucket(currentBucket + 1);

    } else {
      target.setFilled(hash, std::move(value));
      ++m_filledCount;
      if (insertedBucket == NPos)
        insertedBucket = currentBucket;

      return make_pair(iterator{m_buckets.data() + insertedBucket}, true);
    }
  }
#endif
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::erase(const_iterator pos) -> iterator {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  size_t bucketIndex = pos.current - m_buckets.data();
  auto currentBucket = &m_buckets[bucketIndex];
  Bucket* nextBucket = nullptr;
  Value* nextPtr = nullptr;
  auto reply = FlatHashTableDetail::run(SB_FLAT_HASH_ERASE, [&](uint32_t operation, size_t argument) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_REQUEST: return bucketIndex;
      case SB_FLAT_HASH_SIZE: return m_buckets.size();
      case SB_FLAT_HASH_LOAD:
        nextBucket = &m_buckets[argument];
        nextPtr = nextBucket->valuePtr();
        return nextPtr ? 1 : 0;
      case SB_FLAT_HASH_ACTIVE_HASH: return nextBucket->hash;
      case SB_FLAT_HASH_SHIFT:
        // Preserve the native partial mutation if Value move-assignment throws.
        currentBucket->hash = nextBucket->hash;
        *currentBucket->valuePtr() = std::move(*nextPtr);
        currentBucket = nextBucket;
        return 0;
      case SB_FLAT_HASH_CLEAR_BUCKET: m_buckets[argument].setEmpty(); return 0;
      case SB_FLAT_HASH_DECREMENT_FILLED: --m_filledCount; return 0;
      default: FlatHashTableDetail::invalidOperation();
    }
  });
  return iterator{scan(m_buckets.data() + reply.index)};
#else
  size_t bucketIndex = pos.current - m_buckets.data();
  size_t currentBucketIndex = bucketIndex;
  auto currentBucket = &m_buckets[currentBucketIndex];

  while (true) {
    size_t nextBucketIndex = hashBucket(currentBucketIndex + 1);
    auto nextBucket = &m_buckets[nextBucketIndex];
    if (auto nextPtr = nextBucket->valuePtr()) {
      if (bucketError(nextBucketIndex, nextBucket->hash) > 0) {
        currentBucket->hash = nextBucket->hash;
        *currentBucket->valuePtr() = std::move(*nextPtr);
        currentBucketIndex = nextBucketIndex;
        currentBucket = nextBucket;
      } else {
        break;
      }
    } else {
      break;
    }
  }

  m_buckets[currentBucketIndex].setEmpty();
  --m_filledCount;

  return iterator{scan(m_buckets.data() + bucketIndex)};
#endif
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::erase(const_iterator first, const_iterator last) -> iterator {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  FlatHashTableDetail::run(SB_FLAT_HASH_ERASE_RANGE, [&](uint32_t operation, size_t) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_ITER_MORE: return first != last ? 1 : 0;
      case SB_FLAT_HASH_ERASE_ITER: first = erase(first); return 0;
      default: FlatHashTableDetail::invalidOperation();
    }
  });
#else
  while (first != last)
    first = erase(first);
#endif
  return iterator{(Bucket*)first.current};
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::find(Key const& key) const -> const_iterator {
  return const_cast<FlatHashTable*>(this)->find(key);
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::find(Key const& key) -> iterator {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  Bucket* active = nullptr;
  Value* activeValue = nullptr;
  auto reply = FlatHashTableDetail::run(SB_FLAT_HASH_FIND, [&](uint32_t operation, size_t argument) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_SIZE: return m_buckets.size();
      case SB_FLAT_HASH_HASH: return m_hash(key);
      case SB_FLAT_HASH_LOAD:
        active = &m_buckets[argument];
        activeValue = active->valuePtr();
        return activeValue ? 1 : 0;
      case SB_FLAT_HASH_EQUALS:
        return m_equals(m_getKey(*activeValue), key) ? 1 : 0;
      // Keep the selected native bucket across equality callbacks, including
      // reentry; do not reconstruct it from a potentially changed vector.
      case SB_FLAT_HASH_ACTIVE_HASH: return active->hash;
      default: FlatHashTableDetail::invalidOperation();
    }
  });
  if (reply.found > 1)
    FlatHashTableDetail::invalidOperation();
  if (reply.found)
    return iterator{m_buckets.data() + reply.index};
  return end();
#else
  if (m_buckets.empty())
    return end();

  size_t hash = m_hash(key) | FilledHashBit;
  size_t targetBucket = hashBucket(hash);
  size_t currentBucket = targetBucket;
  while (true) {
    auto& bucket = m_buckets[currentBucket];
    if (auto value = bucket.valuePtr()) {
      if (bucket.hash == hash && m_equals(m_getKey(*value), key))
        return iterator{m_buckets.data() + currentBucket};

      size_t entryError = bucketError(currentBucket, bucket.hash);
      size_t findError = bucketError(currentBucket, targetBucket);

      if (findError > entryError)
        return end();

      currentBucket = hashBucket(currentBucket + 1);

    } else {
      return end();
    }
  }
#endif
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
void FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::reserve(size_t capacity) {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  FlatHashTableDetail::run(SB_FLAT_HASH_RESERVE, [&](uint32_t operation, size_t argument) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_REQUEST: return capacity;
      case SB_FLAT_HASH_FILLED: return m_filledCount;
      case SB_FLAT_HASH_CALL_GROW: checkCapacity(argument); return 0;
      default: FlatHashTableDetail::invalidOperation();
    }
  });
#else
  if (capacity > m_filledCount)
    checkCapacity(capacity - m_filledCount);
#endif
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
Allocator FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::getAllocator() const {
  return m_buckets.get_allocator();
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
bool FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::operator==(FlatHashTable const& rhs) const {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  auto reply = FlatHashTableDetail::run(SB_FLAT_HASH_EQUAL, [&](uint32_t operation, size_t) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_SIZES_EQUAL: return size() == rhs.size() ? 1 : 0;
      case SB_FLAT_HASH_ENTER_COMPARE: {
        auto i = begin();
        auto j = rhs.begin();
        auto e = end();
        auto comparison = FlatHashTableDetail::run(SB_FLAT_HASH_COMPARE, [&](uint32_t operation, size_t) -> size_t {
          switch (operation) {
            case SB_FLAT_HASH_ITER_MORE: return i != e ? 1 : 0;
            case SB_FLAT_HASH_NOT_EQUAL: return *i != *j ? 1 : 0;
            case SB_FLAT_HASH_ADVANCE_BOTH: ++i; ++j; return 0;
            default: FlatHashTableDetail::invalidOperation();
          }
        });
        if (comparison.found > 1)
          FlatHashTableDetail::invalidOperation();
        return comparison.found != 0;
      }
      default: FlatHashTableDetail::invalidOperation();
    }
  });
  if (reply.found > 1)
    FlatHashTableDetail::invalidOperation();
  return reply.found != 0;
#else
  if (size() != rhs.size())
    return false;

  auto i = begin();
  auto j = rhs.begin();
  auto e = end();

  while (i != e) {
    if (*i != *j)
      return false;
    ++i;
    ++j;
  }

  return true;
#endif
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
bool FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::operator!=(FlatHashTable const& rhs) const {
  return !operator==(rhs);
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
constexpr size_t FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::MinCapacity;

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
constexpr double FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::MaxFillLevel;

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::scan(Bucket* p) -> Bucket* {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  return FlatHashTableDetail::scan(p);
#else
  while (p->isEmpty())
    ++p;
  return p;
#endif
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
auto FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::scan(Bucket const* p) -> Bucket const* {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  return FlatHashTableDetail::scan(p);
#else
  while (p->isEmpty())
    ++p;
  return p;
#endif
}

#ifndef STAR_USE_RUST_FLAT_HASH_TABLE
template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
size_t FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::hashBucket(size_t hash) const {
  return hash & (m_buckets.size() - 2);
}

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
size_t FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::bucketError(size_t current, size_t target) const {
  return hashBucket(current - target);
}
#endif

template <typename Value, typename Key, typename GetKey, typename Hash, typename Equals, typename Allocator>
void FlatHashTable<Value, Key, GetKey, Hash, Equals, Allocator>::checkCapacity(size_t additionalCapacity) {
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  auto plan = FlatHashTableDetail::run(SB_FLAT_HASH_GROW_PLAN, [&](uint32_t operation, size_t argument) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_REQUEST: return additionalCapacity;
      case SB_FLAT_HASH_SIZE: return m_buckets.size();
      case SB_FLAT_HASH_MIN_CAPACITY: return MinCapacity;
      // Preserve native Release fast-math evaluation, not an equivalent ratio.
      case SB_FLAT_HASH_TOO_FULL:
        return (double)(m_filledCount + additionalCapacity) / (double)argument > MaxFillLevel ? 1 : 0;
      default: FlatHashTableDetail::invalidOperation();
    }
  });
  if (plan.found > 1)
    FlatHashTableDetail::invalidOperation();
  if (!plan.found)
    return;

  // Keep storage ownership in this scope through every nested call and error.
  // In particular, a failed resize after swap must still destroy oldBuckets.
  Buckets oldBuckets;
  FlatHashTableDetail::run(SB_FLAT_HASH_GROW_WORK, [&](uint32_t operation, size_t argument) -> size_t {
    switch (operation) {
      case SB_FLAT_HASH_REQUEST: return plan.index;
      case SB_FLAT_HASH_SWAP_STORAGE: swap(m_buckets, oldBuckets); return 0;
      case SB_FLAT_HASH_RESIZE_BUCKETS: m_buckets.resize(argument); return 0;
      case SB_FLAT_HASH_VECTOR_CAPACITY: return m_buckets.capacity();
      case SB_FLAT_HASH_SET_END: m_buckets[argument].setEnd(); return 0;
      case SB_FLAT_HASH_RESET_FILLED: m_filledCount = 0; return 0;
      case SB_FLAT_HASH_ENTER_REINSERT: {
        // Initialize iterators only after resize, sentinel and count reset.
        auto oldIter = oldBuckets.begin(), oldEnd = oldBuckets.end();
        Value* oldValue = nullptr;
        FlatHashTableDetail::run(SB_FLAT_HASH_REINSERT, [&](uint32_t operation, size_t) -> size_t {
          switch (operation) {
            case SB_FLAT_HASH_ITER_MORE: return oldIter != oldEnd ? 1 : 0;
            case SB_FLAT_HASH_OLD_VALUE:
              oldValue = oldIter->valuePtr();
              return oldValue ? 1 : 0;
            case SB_FLAT_HASH_INSERT_VALUE: insert(std::move(*oldValue)); return 0;
            case SB_FLAT_HASH_ADVANCE_OLD: ++oldIter; return 0;
            default: FlatHashTableDetail::invalidOperation();
          }
        });
        return 0;
      }
      default: FlatHashTableDetail::invalidOperation();
    }
  });
#else
  if (additionalCapacity == 0)
    return;

  size_t newSize;
  if (!m_buckets.empty())
    newSize = m_buckets.size() - 1;
  else
    newSize = MinCapacity;

  while ((double)(m_filledCount + additionalCapacity) / (double)newSize > MaxFillLevel)
    newSize *= 2;

  if (newSize == m_buckets.size() - 1)
    return;

  Buckets oldBuckets;
  swap(m_buckets, oldBuckets);

  // Leave an extra end entry when allocating buckets, so that iterators are
  // simpler and can simply iterate until they find something that is not an
  // empty entry.
  m_buckets.resize(newSize + 1);
  while (m_buckets.capacity() > newSize * 2 + 1) {
    newSize *= 2;
    m_buckets.resize(newSize + 1);
  }
  m_buckets[newSize].setEnd();

  m_filledCount = 0;

  for (auto& entry : oldBuckets) {
    if (auto ptr = entry.valuePtr())
      insert(std::move(*ptr));
  }
#endif
}

}
