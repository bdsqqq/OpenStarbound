#ifdef STAR_USE_RUST_BYTE_ARRAY
#include "StarByteArray.hpp"
#include "StarEncode.hpp"

namespace Star {

ByteArray ByteArray::fromCString(char const* str) {
  ByteArrayRust::NativeCtx c; c.input=str; ByteArrayRust::execute(0,c); return std::move(*c.value);
}

ByteArray ByteArray::fromCStringWithNull(char const* str) {
  ByteArrayRust::NativeCtx c; c.input=str; ByteArrayRust::execute(1,c); return std::move(*c.value);
}

ByteArray ByteArray::withReserve(size_t capacity) {
  ByteArrayRust::NativeCtx c; c.args[0]=capacity; ByteArrayRust::execute(2,c); return std::move(*c.value);
}

ByteArray::ByteArray() {
  ByteArrayRust::NativeCtx c; c.owner=this; c.ready=false; ByteArrayRust::execute(3,c);
}

ByteArray::ByteArray(size_t dataSize, char c)
  : ByteArray() {
  ByteArrayRust::NativeCtx ctx; ctx.owner=this; ctx.args[0]=dataSize; ctx.args[1]=static_cast<unsigned char>(c); ByteArrayRust::execute(4,ctx);
}

ByteArray::ByteArray(const char* data, size_t dataSize)
  : ByteArray() {
  ByteArrayRust::NativeCtx c; c.owner=this; c.input=data; c.inputCount=dataSize; c.args[0]=dataSize; ByteArrayRust::execute(5,c);
}

ByteArray::ByteArray(ByteArray const& b)
  : ByteArray() {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&b; ByteArrayRust::execute(6,c);
}

ByteArray::ByteArray(ByteArray&& b) noexcept
  : ByteArray() {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&b; ByteArrayRust::execute(7,c);
}

ByteArray::~ByteArray() {
  ByteArrayRust::NativeCtx c; c.owner=this; ByteArrayRust::execute(8,c);
}

ByteArray& ByteArray::operator=(ByteArray const& b) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&b; ByteArrayRust::execute(9,c); return *this;
}

ByteArray& ByteArray::operator=(ByteArray&& b) noexcept {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&b; ByteArrayRust::execute(10,c); return *this;
}

void ByteArray::reset() {
  ByteArrayRust::NativeCtx c; c.owner=this; ByteArrayRust::execute(11,c);
}

void ByteArray::reserve(size_t newCapacity) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.args[0]=newCapacity; ByteArrayRust::execute(12,c);
}

void ByteArray::resize(size_t size, char f) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.args[0]=size; c.args[1]=static_cast<unsigned char>(f); ByteArrayRust::execute(13,c);
}

void ByteArray::fill(size_t s, char c) {
  ByteArrayRust::NativeCtx ctx; ctx.owner=this; ctx.args[0]=s; ctx.args[1]=static_cast<unsigned char>(c); ByteArrayRust::execute(14,ctx);
}

void ByteArray::fill(char c) {
  ByteArrayRust::NativeCtx ctx; ctx.owner=this; ctx.args[0]=static_cast<unsigned char>(c); ByteArrayRust::execute(15,ctx);
}

ByteArray ByteArray::sub(size_t b, size_t s) const {
  ByteArrayRust::NativeCtx c; c.owner=this; c.args[0]=b; c.args[1]=s; ByteArrayRust::execute(16,c); return std::move(*c.value);
}

ByteArray ByteArray::left(size_t s) const {
  ByteArrayRust::NativeCtx c; c.owner=this; c.args[0]=s; ByteArrayRust::execute(17,c); return std::move(*c.value);
}

ByteArray ByteArray::right(size_t s) const {
  ByteArrayRust::NativeCtx c; c.owner=this; c.args[0]=s; ByteArrayRust::execute(18,c); return std::move(*c.value);
}

void ByteArray::trimLeft(size_t s) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.args[0]=s; ByteArrayRust::execute(19,c);
}

void ByteArray::trimRight(size_t s) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.args[0]=s; ByteArrayRust::execute(20,c);
}

size_t ByteArray::diffChar(const ByteArray& b) const {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&b; ByteArrayRust::execute(21,c); return c.result;
}

int ByteArray::compare(const ByteArray& b) const {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&b; ByteArrayRust::execute(22,c); return c.result==UINT64_MAX?-1:static_cast<int>(c.result);
}

ByteArray ByteArray::andWith(ByteArray const& rhs, bool extend) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&rhs; c.args[0]=extend; ByteArrayRust::execute(23,c); return std::move(*c.value);
}

ByteArray ByteArray::orWith(ByteArray const& rhs, bool extend) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&rhs; c.args[0]=extend; ByteArrayRust::execute(24,c); return std::move(*c.value);
}

ByteArray ByteArray::xorWith(ByteArray const& rhs, bool extend) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&rhs; c.args[0]=extend; ByteArrayRust::execute(25,c); return std::move(*c.value);
}

void ByteArray::insert(size_t pos, char byte) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.args[0]=pos; c.args[1]=static_cast<unsigned char>(byte); ByteArrayRust::execute(26,c);
}

ByteArray::iterator ByteArray::insert(const_iterator pos, char byte) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.position=pos; c.args[0]=static_cast<unsigned char>(byte); ByteArrayRust::execute(27,c); return c.pointer;
}

void ByteArray::push_back(char byte) {
  ByteArrayRust::NativeCtx c; c.owner=this; c.args[0]=static_cast<unsigned char>(byte); ByteArrayRust::execute(28,c);
}

bool ByteArray::operator<(const ByteArray& b) const {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&b; ByteArrayRust::execute(29,c); return c.result;
}

bool ByteArray::operator==(const ByteArray& b) const {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&b; ByteArrayRust::execute(30,c); return c.result;
}

bool ByteArray::operator!=(const ByteArray& b) const {
  ByteArrayRust::NativeCtx c; c.owner=this; c.other=&b; ByteArrayRust::execute(31,c); return c.result;
}

std::ostream& operator<<(std::ostream& os, const ByteArray& b) {
  ByteArrayRust::NativeCtx c; c.owner=&b; c.stream=&os; ByteArrayRust::execute(32,c); return os;
}

}

namespace Star::ByteArrayRust { void streamHex(NativeCtx& c){ *c.stream << hexEncode(*c.owner); } }
#else
#include "StarByteArray.hpp"
#include "StarEncode.hpp"

namespace Star {

ByteArray ByteArray::fromCString(char const* str) {
  return ByteArray(str, strlen(str));
}

ByteArray ByteArray::fromCStringWithNull(char const* str) {
  size_t len = strlen(str);
  ByteArray ba(str, len + 1);
  ba[len] = 0;
  return ba;
}

ByteArray ByteArray::withReserve(size_t capacity) {
  ByteArray bytes;
  bytes.reserve(capacity);
  return bytes;
}

ByteArray::ByteArray() {
  m_data = nullptr;
  m_capacity = 0;
  m_size = 0;
}

ByteArray::ByteArray(size_t dataSize, char c)
  : ByteArray() {
  fill(dataSize, c);
}

ByteArray::ByteArray(const char* data, size_t dataSize)
  : ByteArray() {
  append(data, dataSize);
}

ByteArray::ByteArray(ByteArray const& b)
  : ByteArray() {
  operator=(b);
}

ByteArray::ByteArray(ByteArray&& b) noexcept
  : ByteArray() {
  operator=(std::move(b));
}

ByteArray::~ByteArray() {
  reset();
}

ByteArray& ByteArray::operator=(ByteArray const& b) {
  if (&b != this) {
    clear();
    append(b);
  }

  return *this;
}

ByteArray& ByteArray::operator=(ByteArray&& b) noexcept {
  if (&b != this) {
    reset();

    m_data = take(b.m_data);
    m_capacity = take(b.m_capacity);
    m_size = take(b.m_size);
  }

  return *this;
}

void ByteArray::reset() {
  if (m_data) {
    Star::free(m_data, m_capacity);
    m_data = nullptr;
    m_capacity = 0;
    m_size = 0;
  }
}

void ByteArray::reserve(size_t newCapacity) {
  if (newCapacity > m_capacity) {
    if (!m_data) {
      auto newMem = (char*)Star::malloc(newCapacity);
      if (!newMem)
        throw MemoryException::format("Could not set new ByteArray capacity {}\n", newCapacity);
      m_data = newMem;
      m_capacity = newCapacity;
    } else {
      newCapacity = max({m_capacity * 2, newCapacity, (size_t)8});
      auto newMem = (char*)Star::realloc(m_data, newCapacity);
      if (!newMem)
        throw MemoryException::format("Could not set new ByteArray capacity {}\n", newCapacity);
      m_data = newMem;
      m_capacity = newCapacity;
    }
  }
}

void ByteArray::resize(size_t size, char f) {
  if (m_size == size)
    return;

  size_t oldSize = m_size;
  resize(size);
  for (size_t i = oldSize; i < m_size; ++i)
    (*this)[i] = f;
}

void ByteArray::fill(size_t s, char c) {
  if (s != NPos)
    resize(s);

  memset(m_data, c, m_size);
}

void ByteArray::fill(char c) {
  fill(NPos, c);
}

ByteArray ByteArray::sub(size_t b, size_t s) const {
  if (b == 0 && s >= m_size) {
    return ByteArray(*this);
  } else {
    return ByteArray(m_data + b, min(m_size, b + s));
  }
}

ByteArray ByteArray::left(size_t s) const {
  return sub(0, s);
}

ByteArray ByteArray::right(size_t s) const {
  if (s > m_size)
    s = 0;
  else
    s = m_size - s;

  return sub(s, m_size);
}

void ByteArray::trimLeft(size_t s) {
  if (s >= m_size) {
    clear();
  } else {
    std::memmove(m_data, m_data + s, m_size - s);
    resize(m_size - s);
  }
}

void ByteArray::trimRight(size_t s) {
  if (s >= m_size)
    clear();
  else
    resize(m_size - s);
}

size_t ByteArray::diffChar(const ByteArray& b) const {
  size_t s = min(m_size, b.size());
  char* ac = m_data;
  char* bc = b.m_data;
  size_t i;
  for (i = 0; i < s; ++i) {
    if (ac[i] != bc[i])
      break;
  }

  return i;
}

int ByteArray::compare(const ByteArray& b) const {
  if (m_size == 0 && b.m_size == 0)
    return 0;

  if (m_size == 0)
    return -1;

  if (b.m_size == 0)
    return 1;

  size_t d = diffChar(b);
  if (d == m_size) {
    if (d != b.m_size)
      return -1;
    else
      return 0;
  }

  if (d == b.m_size) {
    if (d != m_size)
      return 1;
    else
      return 0;
  }

  unsigned char c1 = (*this)[d];
  unsigned char c2 = b[d];

  if (c1 < c2) {
    return -1;
  } else if (c1 > c2) {
    return 1;
  } else {
    return 0;
  }
}

ByteArray ByteArray::andWith(ByteArray const& rhs, bool extend) {
  return combineWith([](char a, char b) { return a & b; }, rhs, extend);
}

ByteArray ByteArray::orWith(ByteArray const& rhs, bool extend) {
  return combineWith([](char a, char b) { return a | b; }, rhs, extend);
}

ByteArray ByteArray::xorWith(ByteArray const& rhs, bool extend) {
  return combineWith([](char a, char b) { return a ^ b; }, rhs, extend);
}

void ByteArray::insert(size_t pos, char byte) {
  starAssert(pos <= m_size);
  resize(m_size + 1);
  for (size_t i = m_size - 1; i > pos; --i)
    m_data[i] = m_data[i - 1];
  m_data[pos] = byte;
}

ByteArray::iterator ByteArray::insert(const_iterator pos, char byte) {
  size_t d = pos - begin();
  insert(d, byte);
  return begin() + d + 1;
}

void ByteArray::push_back(char byte) {
  resize(m_size + 1);
  m_data[m_size - 1] = byte;
}

bool ByteArray::operator<(const ByteArray& b) const {
  return compare(b) < 0;
}

bool ByteArray::operator==(const ByteArray& b) const {
  return compare(b) == 0;
}

bool ByteArray::operator!=(const ByteArray& b) const {
  return compare(b) != 0;
}

std::ostream& operator<<(std::ostream& os, const ByteArray& b) {
  os << "0x" << hexEncode(b);
  return os;
}

}
#endif
