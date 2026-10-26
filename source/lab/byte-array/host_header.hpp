#pragma once

#include "StarHash.hpp"
#include "StarException.hpp"
#include "StarFormat.hpp"

namespace Star {

STAR_CLASS(ByteArray);

// Class to hold an array of bytes.  Contains an internal buffer that may be
// larger than what is reported by size(), to avoid repeated allocations when a
// ByteArray grows.
class ByteArray {
public:
  typedef char value_type;
  typedef char* iterator;
  typedef char const* const_iterator;

  // Constructs a byte array from a given c string WITHOUT including the
  // trailing '\0'
  static ByteArray fromCString(char const* str);
  // Same, but includes the trailing '\0'
  static ByteArray fromCStringWithNull(char const* str);
  static ByteArray withReserve(size_t capacity);

  ByteArray();
  ByteArray(size_t dataSize, char c);
  ByteArray(char const* data, size_t dataSize);
  ByteArray(ByteArray const& b);
  ByteArray(ByteArray&& b) noexcept;
  ~ByteArray();

  ByteArray& operator=(ByteArray const& b);
  ByteArray& operator=(ByteArray&& b) noexcept;

  char const* ptr() const;
  char* ptr();

  size_t size() const;
  // Maximum size before realloc
  size_t capacity() const;
  // Is zero size
  bool empty() const;

  // Sets size to 0.
  void clear();
  // Clears and resets buffer to empty.
  void reset();

  void reserve(size_t capacity);

  void resize(size_t size);
  // resize, filling new space with given byte if it exists.
  void resize(size_t size, char f);

  // fill array with byte.
  void fill(char c);
  // fill array and resize to new size.
  void fill(size_t size, char c);

  void append(ByteArray const& b);
  void append(char const* data, size_t len);
  void appendByte(char b);

  void copyTo(char* data, size_t len) const;
  void copyTo(char* data) const;

  // Copy from ByteArray starting at pos, to data, with size len.
  void copyTo(char* data, size_t pos, size_t len) const;
  // Copy from data pointer to ByteArray at pos with size len.
  // Resizes if needed.
  void writeFrom(char const* data, size_t pos, size_t len);

  ByteArray sub(size_t b, size_t s) const;
  ByteArray left(size_t s) const;
  ByteArray right(size_t s) const;

  void trimLeft(size_t s);
  void trimRight(size_t s);

  // returns location of first character that is different than the given
  // ByteArray.
  size_t diffChar(ByteArray const& b) const;
  // returns -1 if this < b, 0 if this == b, 1 if this > b
  int compare(ByteArray const& b) const;

  template <typename Combiner>
  ByteArray combineWith(Combiner&& combine, ByteArray const& rhs, bool extend = false);

  ByteArray andWith(ByteArray const& rhs, bool extend = false);
  ByteArray orWith(ByteArray const& rhs, bool extend = false);
  ByteArray xorWith(ByteArray const& rhs, bool extend = false);

  iterator begin();
  iterator end();

  const_iterator begin() const;
  const_iterator end() const;

  void insert(size_t pos, char byte);
  iterator insert(const_iterator pos, char byte);
  void push_back(char byte);

  char& operator[](size_t i);
  char operator[](size_t i) const;
  char at(size_t i) const;

  bool operator<(ByteArray const& b) const;
  bool operator==(ByteArray const& b) const;
  bool operator!=(ByteArray const& b) const;

private:
  friend struct ByteArrayNativeAccess;
  char* m_data;
  size_t m_capacity;
  size_t m_size;
};

template <>
struct hash<ByteArray> {
  size_t operator()(ByteArray const& b) const;
};

std::ostream& operator<<(std::ostream& os, ByteArray const& b);

} // namespace Star
#include "host_native.hpp"
namespace Star {

inline void ByteArray::clear() {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(33,c);
}

inline void ByteArray::resize(size_t size) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=size; ByteArrayHost::execute(34,c);
}

inline void ByteArray::append(ByteArray const& b) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&b; ByteArrayHost::execute(35,c);
}

inline void ByteArray::append(const char* data, size_t len) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.input=data; c.inputCount=len; c.args[0]=len; ByteArrayHost::execute(36,c);
}

inline void ByteArray::appendByte(char b) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=static_cast<unsigned char>(b); ByteArrayHost::execute(37,c);
}

inline bool ByteArray::empty() const {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(38,c); return c.result;
}

inline char const* ByteArray::ptr() const {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(39,c); return c.pointer;
}

inline char* ByteArray::ptr() {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(40,c); return c.pointer;
}

inline size_t ByteArray::size() const {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(41,c); return c.result;
}

inline size_t ByteArray::capacity() const {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(42,c); return c.result;
}

inline void ByteArray::copyTo(char* data, size_t len) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.output=data; c.outputCount=len; c.args[0]=len; ByteArrayHost::execute(43,c);
}

inline void ByteArray::copyTo(char* data) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.output=data; c.outputCount=ByteArrayNativeAccess::size(*const_cast<ByteArray*>(this)); ByteArrayHost::execute(44,c);
}

inline void ByteArray::copyTo(char* data, size_t pos, size_t len) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.output=data; c.outputCount=len; c.args[0]=pos; c.args[1]=len; ByteArrayHost::execute(45,c);
}

inline void ByteArray::writeFrom(const char* data, size_t pos, size_t len) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.input=data; c.inputCount=len; c.args[0]=pos; c.args[1]=len; ByteArrayHost::execute(46,c);
}

template <typename Combiner>
ByteArray ByteArray::combineWith(Combiner&& combine, ByteArray const& rhs, bool extend) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&rhs; c.args[0]=extend; using F=typename std::remove_reference<Combiner>::type; ByteArrayHost::NativeGenericCtx<F> state{combine}; c.generic=&state; c.expression=&ByteArrayHost::NativeGenericCtx<F>::expression; ByteArrayHost::execute(47,c); return std::move(*c.value);
}

inline ByteArray::iterator ByteArray::begin() {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(48,c); return c.pointer;
}

inline ByteArray::iterator ByteArray::end() {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(49,c); return c.pointer;
}

inline ByteArray::const_iterator ByteArray::begin() const {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(50,c); return c.pointer;
}

inline ByteArray::const_iterator ByteArray::end() const {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(51,c); return c.pointer;
}

inline char& ByteArray::operator[](size_t i) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=i; ByteArrayHost::execute(52,c); return *c.pointer;
}

inline char ByteArray::operator[](size_t i) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=i; ByteArrayHost::execute(53,c); return static_cast<char>(c.result);
}

inline char ByteArray::at(size_t i) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=i; ByteArrayHost::execute(54,c); return static_cast<char>(c.result);
}

inline size_t hash<ByteArray>::operator()(ByteArray const& b) const {
  ByteArrayHost::NativeCtx c; c.owner=&b; ByteArrayHost::execute(55,c); return c.result;
}

}

template <> struct fmt::formatter<Star::ByteArray> : ostream_formatter {};
