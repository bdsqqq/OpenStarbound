#pragma once

#include "StarException.hpp"
#include "StarFormat.hpp"
#include "frame.hpp"
#include "StarRustStaticVector.h"

namespace Star {

STAR_EXCEPTION(StaticVectorSizeException, StarException);

// Stack allocated vector of elements with a dynamic size which must be less
// than a given maximum.  Acts like a vector with a built-in allocator of a
// maximum size, throws bad_alloc on attempting to resize beyond the maximum
// size.
template <typename Element, size_t MaxSize>
class StaticVector {
public:
  typedef Element* iterator;
  typedef Element const* const_iterator;

  typedef std::reverse_iterator<iterator> reverse_iterator;
  typedef std::reverse_iterator<const_iterator> const_reverse_iterator;

  typedef Element value_type;

  typedef Element& reference;
  typedef Element const& const_reference;

  static constexpr size_t MaximumSize = MaxSize;

  StaticVector();
  StaticVector(StaticVector const& other);
  StaticVector(StaticVector&& other);
  template <typename OtherElement, size_t OtherMaxSize>
  StaticVector(StaticVector<OtherElement, OtherMaxSize> const& other);
  template <class Iterator>
  StaticVector(Iterator first, Iterator last);
  StaticVector(size_t size, Element const& value = Element());
  StaticVector(initializer_list<Element> list);
  ~StaticVector();

  StaticVector& operator=(StaticVector const& other);
  StaticVector& operator=(StaticVector&& other);
  StaticVector& operator=(std::initializer_list<Element> list);

  size_t size() const;
  bool empty() const;
  void resize(size_t size, Element const& e = Element());

  reference at(size_t i);
  const_reference at(size_t i) const;

  reference operator[](size_t i);
  const_reference operator[](size_t i) const;

  const_iterator begin() const;
  const_iterator end() const;

  iterator begin();
  iterator end();

  const_reverse_iterator rbegin() const;
  const_reverse_iterator rend() const;

  reverse_iterator rbegin();
  reverse_iterator rend();

  // Pointer to internal data, always valid even if empty.
  Element const* ptr() const;
  Element* ptr();

  void push_back(Element e);
  void pop_back();

  iterator insert(iterator pos, Element e);
  template <typename Iterator>
  iterator insert(iterator pos, Iterator begin, Iterator end);
  iterator insert(iterator pos, initializer_list<Element> list);

  template <typename... Args>
  void emplace(iterator pos, Args&&... args);

  template <typename... Args>
  void emplace_back(Args&&... args);

  void clear();

  iterator erase(iterator pos);
  iterator erase(iterator begin, iterator end);

  bool operator==(StaticVector const& other) const;
  bool operator!=(StaticVector const& other) const;
  bool operator<(StaticVector const& other) const;

private:
  size_t m_size;
  typename std::aligned_storage<MaxSize * sizeof(Element), alignof(Element)>::type m_elements;
};

template <typename Element, size_t MaxSize>
StaticVector<Element, MaxSize>::StaticVector()
  : m_size(0) {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    (void)request;
    return invalidReply();
  });
  frame.run(SB_STATIC_VECTOR_DEFAULT_CTOR);
}

template <typename Element, size_t MaxSize>
StaticVector<Element, MaxSize>::~StaticVector() {
  clear();
}

template <typename Element, size_t MaxSize>
StaticVector<Element, MaxSize>::StaticVector(StaticVector const& other)
  : StaticVector() {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_CALL_FORWARD: {
        insert(begin(), other.begin(), other.end());
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_CTOR_INSERT);
}

template <typename Element, size_t MaxSize>
StaticVector<Element, MaxSize>::StaticVector(StaticVector&& other)
  : StaticVector() {
  auto cursor = other.begin();
  auto last = other.end();
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_ITERATOR_PRESENT: {
        return boolReply(static_cast<bool>(cursor != last));
      }
      case SB_STATIC_VECTOR_CALL_EMPLACE_CURRENT: {
        auto& e = *cursor;
        emplace_back(std::move(e));
        return voidReply();
      }
      case SB_STATIC_VECTOR_ADVANCE_ITERATOR: {
        ++cursor;
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_RANGE_MOVE);
}

template <typename Element, size_t MaxSize>
template <typename OtherElement, size_t OtherMaxSize>
StaticVector<Element, MaxSize>::StaticVector(StaticVector<OtherElement, OtherMaxSize> const& other)
  : StaticVector() {
  auto cursor = other.begin();
  auto last = other.end();
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_ITERATOR_PRESENT: {
        return boolReply(static_cast<bool>(cursor != last));
      }
      case SB_STATIC_VECTOR_CALL_EMPLACE_CURRENT: {
        auto const& e = *cursor;
        emplace_back(e);
        return voidReply();
      }
      case SB_STATIC_VECTOR_ADVANCE_ITERATOR: {
        ++cursor;
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_RANGE_COPY);
}

template <typename Element, size_t MaxSize>
template <class Iterator>
StaticVector<Element, MaxSize>::StaticVector(Iterator first, Iterator last)
  : StaticVector() {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_CALL_FORWARD: {
        insert(begin(), first, last);
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_CTOR_INSERT);
}

template <typename Element, size_t MaxSize>
StaticVector<Element, MaxSize>::StaticVector(size_t size, Element const& value)
  : StaticVector() {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_CALL_FORWARD: {
        resize(size, value);
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_CTOR_RESIZE);
}

template <typename Element, size_t MaxSize>
StaticVector<Element, MaxSize>::StaticVector(initializer_list<Element> list)
  : StaticVector() {
  auto cursor = list.begin();
  auto last = list.end();
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_ITERATOR_PRESENT: {
        return boolReply(static_cast<bool>(cursor != last));
      }
      case SB_STATIC_VECTOR_CALL_EMPLACE_CURRENT: {
        auto const& e = *cursor;
        emplace_back(e);
        return voidReply();
      }
      case SB_STATIC_VECTOR_ADVANCE_ITERATOR: {
        ++cursor;
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_RANGE_COPY);
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::operator=(StaticVector const& other) -> StaticVector& {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_SELF: {
        return boolReply(static_cast<bool>(this == &other));
      }
      case SB_STATIC_VECTOR_CALL_RESIZE_OTHER: {
        resize(other.size());
        return voidReply();
      }
      case SB_STATIC_VECTOR_CALL_ASSIGN: {
        operator[](static_cast<size_t>(request.arg0)) = other[static_cast<size_t>(request.arg0)];
        return voidReply();
      }
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_COPY_ASSIGN);
  return *this;
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::operator=(StaticVector&& other) -> StaticVector& {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_CALL_RESIZE_OTHER: {
        resize(other.size());
        return voidReply();
      }
      case SB_STATIC_VECTOR_CALL_ASSIGN: {
        operator[](static_cast<size_t>(request.arg0)) = std::move(other[static_cast<size_t>(request.arg0)]);
        return voidReply();
      }
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_MOVE_ASSIGN);
  return *this;
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::operator=(std::initializer_list<Element> list) -> StaticVector& {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_CALL_RESIZE_OTHER: {
        resize(list.size());
        return voidReply();
      }
      case SB_STATIC_VECTOR_CALL_ASSIGN: {
        operator[](static_cast<size_t>(request.arg0)) = std::move(list[static_cast<size_t>(request.arg0)]);
        return voidReply();
      }
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_LIST_ASSIGN);
  return *this;
}

template <typename Element, size_t MaxSize>
size_t StaticVector<Element, MaxSize>::size() const {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      default:
        return invalidReply();
    }
  });
  return frame.run(SB_STATIC_VECTOR_SIZE).value;
}

template <typename Element, size_t MaxSize>
bool StaticVector<Element, MaxSize>::empty() const {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      default:
        return invalidReply();
    }
  });
  return frame.run(SB_STATIC_VECTOR_EMPTY).value;
}

template <typename Element, size_t MaxSize>
void StaticVector<Element, MaxSize>::resize(size_t size, Element const& e) {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_TARGET: {
        return sizeReply(size);
      }
      case SB_STATIC_VECTOR_READ_CAPACITY: {
        return sizeReply(MaxSize);
      }
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_THROW_RESIZE: {
        throw StaticVectorSizeException::format("StaticVector::resize({}) out of range {}", m_size + size, MaxSize);
      }
      case SB_STATIC_VECTOR_CALL_POP: {
        pop_back();
        return voidReply();
      }
      case SB_STATIC_VECTOR_CALL_EMPLACE_VALUE: {
        emplace_back(e);
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_RESIZE);
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::at(size_t i) -> reference {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_INDEX: {
        return sizeReply(i);
      }
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_THROW_AT: {
        throw OutOfRangeException::format("out of range in StaticVector::at({})", i);
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_AT);
  return ptr()[i];
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::at(size_t i) const -> const_reference {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_INDEX: {
        return sizeReply(i);
      }
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_THROW_AT: {
        throw OutOfRangeException::format("out of range in StaticVector::at({})", i);
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_AT);
  return ptr()[i];
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::operator[](size_t i) -> reference {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_ASSERT_INDEX: {
        starAssert(i < m_size);
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_INDEX);
  return ptr()[i];
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::operator[](size_t i) const -> const_reference {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_ASSERT_INDEX: {
        starAssert(i < m_size);
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_INDEX);
  return ptr()[i];
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::begin() const -> const_iterator {
  return ptr();
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::end() const -> const_iterator {
  return ptr() + m_size;
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::begin() -> iterator {
  return ptr();
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::end() -> iterator {
  return ptr() + m_size;
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::rbegin() const -> const_reverse_iterator {
  return const_reverse_iterator(end());
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::rend() const -> const_reverse_iterator {
  return const_reverse_iterator(begin());
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::rbegin() -> reverse_iterator {
  return reverse_iterator(end());
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::rend() -> reverse_iterator {
  return reverse_iterator(begin());
}

template <typename Element, size_t MaxSize>
Element const* StaticVector<Element, MaxSize>::ptr() const {
  return (Element const*)&m_elements;
}

template <typename Element, size_t MaxSize>
Element* StaticVector<Element, MaxSize>::ptr() {
  return (Element*)&m_elements;
}

template <typename Element, size_t MaxSize>
void StaticVector<Element, MaxSize>::push_back(Element e) {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_CALL_FORWARD: {
        emplace_back(std::move(e));
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_PUSH_BACK);
}

template <typename Element, size_t MaxSize>
void StaticVector<Element, MaxSize>::pop_back() {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_THROW_POP: {
        throw OutOfRangeException("StaticVector::pop_back called on empty StaticVector");
      }
      case SB_STATIC_VECTOR_DECREMENT_SIZE: {
        --m_size;
        return voidReply();
      }
      case SB_STATIC_VECTOR_DESTROY_LAST: {
        (ptr() + m_size)->~Element();
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_POP_BACK);
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::insert(iterator pos, Element e) -> iterator {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_CALL_FORWARD: {
        emplace(pos, std::move(e));
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_INSERT_ONE);
  return pos;
}

template <typename Element, size_t MaxSize>
template <typename Iterator>
auto StaticVector<Element, MaxSize>::insert(iterator pos, Iterator begin, Iterator end) -> iterator {
  size_t toAdd = std::distance(begin, end);
  size_t startIndex = pos - ptr();
  size_t endIndex = startIndex + toAdd;
  size_t toShift = m_size - startIndex;

  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_TO_ADD: {
        return sizeReply(toAdd);
      }
      case SB_STATIC_VECTOR_READ_START: {
        return sizeReply(startIndex);
      }
      case SB_STATIC_VECTOR_READ_END: {
        return sizeReply(endIndex);
      }
      case SB_STATIC_VECTOR_READ_SHIFT: {
        return sizeReply(toShift);
      }
      case SB_STATIC_VECTOR_CALL_RESIZE_ADD: {
        resize(m_size + toAdd);
        return voidReply();
      }
      case SB_STATIC_VECTOR_MOVE_ASSIGN_SLOTS: {
        operator[](static_cast<size_t>(request.arg0)) = std::move(operator[](static_cast<size_t>(request.arg1)));
        return voidReply();
      }
      case SB_STATIC_VECTOR_ASSIGN_FROM_ITERATOR: {
        operator[](static_cast<size_t>(request.arg0)) = *begin++;
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_INSERT_RANGE);
  return pos;
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::insert(iterator pos, initializer_list<Element> list) -> iterator {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_CALL_FORWARD: {
        insert(pos, list.begin(), list.end());
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_INSERT_LIST);
  return pos;
}

template <typename Element, size_t MaxSize>
template <typename... Args>
void StaticVector<Element, MaxSize>::emplace(iterator pos, Args&&... args) {
  size_t index = pos - ptr();
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_INDEX: {
        return sizeReply(index);
      }
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_CALL_RESIZE_PLUS_ONE: {
        resize(m_size + 1);
        return voidReply();
      }
      case SB_STATIC_VECTOR_MOVE_ASSIGN_SLOTS: {
        operator[](static_cast<size_t>(request.arg0)) = std::move(operator[](static_cast<size_t>(request.arg1)));
        return voidReply();
      }
      case SB_STATIC_VECTOR_ASSIGN_FROM_ARGS: {
        operator[](static_cast<size_t>(request.arg0)) = Element(std::forward<Args>(args)...);
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_EMPLACE);
}

template <typename Element, size_t MaxSize>
template <typename... Args>
void StaticVector<Element, MaxSize>::emplace_back(Args&&... args) {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_READ_CAPACITY: {
        return sizeReply(MaxSize);
      }
      case SB_STATIC_VECTOR_THROW_EMPLACE_BACK: {
        throw StaticVectorSizeException::format("StaticVector::emplace_back would extend StaticVector beyond size {}", MaxSize);
      }
      case SB_STATIC_VECTOR_INCREMENT_SIZE: {
        m_size += 1;
        return voidReply();
      }
      case SB_STATIC_VECTOR_CONSTRUCT_LAST: {
        new (ptr() + m_size - 1) Element(std::forward<Args>(args)...);
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_EMPLACE_BACK);
}

template <typename Element, size_t MaxSize>
void StaticVector<Element, MaxSize>::clear() {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_CALL_POP: {
        pop_back();
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_CLEAR);
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::erase(iterator pos) -> iterator {
  size_t index = pos - ptr();
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_INDEX: {
        return sizeReply(index);
      }
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_MOVE_ASSIGN_SLOTS: {
        operator[](static_cast<size_t>(request.arg0)) = std::move(operator[](static_cast<size_t>(request.arg1)));
        return voidReply();
      }
      case SB_STATIC_VECTOR_CALL_RESIZE_MINUS_ONE: {
        resize(m_size - 1);
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_ERASE_ONE);
  return pos;
}

template <typename Element, size_t MaxSize>
auto StaticVector<Element, MaxSize>::erase(iterator begin, iterator end) -> iterator {
  size_t startIndex = begin - ptr();
  size_t endIndex = end - ptr();
  size_t toRemove = endIndex - startIndex;
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_START: {
        return sizeReply(startIndex);
      }
      case SB_STATIC_VECTOR_READ_END: {
        return sizeReply(endIndex);
      }
      case SB_STATIC_VECTOR_READ_REMOVE: {
        return sizeReply(toRemove);
      }
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_MOVE_ASSIGN_SLOTS: {
        operator[](static_cast<size_t>(request.arg0)) = std::move(operator[](static_cast<size_t>(request.arg1)));
        return voidReply();
      }
      case SB_STATIC_VECTOR_CALL_RESIZE_MINUS_REMOVE: {
        resize(m_size - toRemove);
        return voidReply();
      }
      default:
        return invalidReply();
    }
  });
  frame.run(SB_STATIC_VECTOR_ERASE_RANGE);
  return begin;
}

template <typename Element, size_t MaxSize>
bool StaticVector<Element, MaxSize>::operator==(StaticVector const& other) const {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_SELF: {
        return boolReply(static_cast<bool>(this == &other));
      }
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_OTHER_SIZE: {
        return sizeReply(other.m_size);
      }
      case SB_STATIC_VECTOR_ELEMENT_NOT_EQUAL: {
        return boolReply(static_cast<bool>(operator[](static_cast<size_t>(request.arg0)) != other[static_cast<size_t>(request.arg0)]));
      }
      default:
        return invalidReply();
    }
  });
  return frame.run(SB_STATIC_VECTOR_EQUAL).value;
}

template <typename Element, size_t MaxSize>
bool StaticVector<Element, MaxSize>::operator!=(StaticVector const& other) const {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_CALL_EQUAL: {
        return boolReply(static_cast<bool>(operator==(other)));
      }
      default:
        return invalidReply();
    }
  });
  return frame.run(SB_STATIC_VECTOR_NOT_EQUAL).value;
}

template <typename Element, size_t MaxSize>
bool StaticVector<Element, MaxSize>::operator<(StaticVector const& other) const {
  auto frame = StaticVectorFrames::makeFrame([&](SbStaticVectorRequest const& request) -> SbStaticVectorReply {
    using namespace StaticVectorFrames;
    switch (request.op) {
      case SB_STATIC_VECTOR_READ_SIZE: {
        return sizeReply(m_size);
      }
      case SB_STATIC_VECTOR_OTHER_SIZE: {
        return sizeReply(other.size());
      }
      case SB_STATIC_VECTOR_COMPARE_PAIR: {
        Element const& a = operator[](static_cast<size_t>(request.arg0));
        Element const& b = other[static_cast<size_t>(request.arg0)];
        auto pair = makeFrame([&](SbStaticVectorRequest const& pairRequest) -> SbStaticVectorReply {
          switch (pairRequest.op) {
            case SB_STATIC_VECTOR_PAIR_LESS:
              return boolReply(static_cast<bool>(a < b));
            case SB_STATIC_VECTOR_PAIR_GREATER:
              return boolReply(static_cast<bool>(b < a));
            default:
              return invalidReply();
          }
        });
        return pair.run(SB_STATIC_VECTOR_LESS, SB_STATIC_VECTOR_CONTINUE);
      }
      default:
        return invalidReply();
    }
  });
  return frame.run(SB_STATIC_VECTOR_LESS).value;
}

}
