#include "StarByteArray.hpp"
#include "StarEncode.hpp"

namespace Star {

ByteArray ByteArray::fromCString(char const* str) {
  ByteArrayHost::NativeCtx c; c.input=str; ByteArrayHost::execute(0,c); return std::move(*c.value);
}

ByteArray ByteArray::fromCStringWithNull(char const* str) {
  ByteArrayHost::NativeCtx c; c.input=str; ByteArrayHost::execute(1,c); return std::move(*c.value);
}

ByteArray ByteArray::withReserve(size_t capacity) {
  ByteArrayHost::NativeCtx c; c.args[0]=capacity; ByteArrayHost::execute(2,c); return std::move(*c.value);
}

ByteArray::ByteArray() {
  ByteArrayHost::NativeCtx c; c.owner=this; c.ready=false; ByteArrayHost::execute(3,c);
}

ByteArray::ByteArray(size_t dataSize, char c)
  : ByteArray() {
  ByteArrayHost::NativeCtx ctx; ctx.owner=this; ctx.args[0]=dataSize; ctx.args[1]=static_cast<unsigned char>(c); ByteArrayHost::execute(4,ctx);
}

ByteArray::ByteArray(const char* data, size_t dataSize)
  : ByteArray() {
  ByteArrayHost::NativeCtx c; c.owner=this; c.input=data; c.inputCount=dataSize; c.args[0]=dataSize; ByteArrayHost::execute(5,c);
}

ByteArray::ByteArray(ByteArray const& b)
  : ByteArray() {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&b; ByteArrayHost::execute(6,c);
}

ByteArray::ByteArray(ByteArray&& b) noexcept
  : ByteArray() {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&b; ByteArrayHost::execute(7,c);
}

ByteArray::~ByteArray() {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(8,c);
}

ByteArray& ByteArray::operator=(ByteArray const& b) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&b; ByteArrayHost::execute(9,c); return *this;
}

ByteArray& ByteArray::operator=(ByteArray&& b) noexcept {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&b; ByteArrayHost::execute(10,c); return *this;
}

void ByteArray::reset() {
  ByteArrayHost::NativeCtx c; c.owner=this; ByteArrayHost::execute(11,c);
}

void ByteArray::reserve(size_t newCapacity) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=newCapacity; ByteArrayHost::execute(12,c);
}

void ByteArray::resize(size_t size, char f) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=size; c.args[1]=static_cast<unsigned char>(f); ByteArrayHost::execute(13,c);
}

void ByteArray::fill(size_t s, char c) {
  ByteArrayHost::NativeCtx ctx; ctx.owner=this; ctx.args[0]=s; ctx.args[1]=static_cast<unsigned char>(c); ByteArrayHost::execute(14,ctx);
}

void ByteArray::fill(char c) {
  ByteArrayHost::NativeCtx ctx; ctx.owner=this; ctx.args[0]=static_cast<unsigned char>(c); ByteArrayHost::execute(15,ctx);
}

ByteArray ByteArray::sub(size_t b, size_t s) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=b; c.args[1]=s; ByteArrayHost::execute(16,c); return std::move(*c.value);
}

ByteArray ByteArray::left(size_t s) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=s; ByteArrayHost::execute(17,c); return std::move(*c.value);
}

ByteArray ByteArray::right(size_t s) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=s; ByteArrayHost::execute(18,c); return std::move(*c.value);
}

void ByteArray::trimLeft(size_t s) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=s; ByteArrayHost::execute(19,c);
}

void ByteArray::trimRight(size_t s) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=s; ByteArrayHost::execute(20,c);
}

size_t ByteArray::diffChar(const ByteArray& b) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&b; ByteArrayHost::execute(21,c); return c.result;
}

int ByteArray::compare(const ByteArray& b) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&b; ByteArrayHost::execute(22,c); return c.result==UINT64_MAX?-1:static_cast<int>(c.result);
}

ByteArray ByteArray::andWith(ByteArray const& rhs, bool extend) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&rhs; c.args[0]=extend; ByteArrayHost::execute(23,c); return std::move(*c.value);
}

ByteArray ByteArray::orWith(ByteArray const& rhs, bool extend) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&rhs; c.args[0]=extend; ByteArrayHost::execute(24,c); return std::move(*c.value);
}

ByteArray ByteArray::xorWith(ByteArray const& rhs, bool extend) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&rhs; c.args[0]=extend; ByteArrayHost::execute(25,c); return std::move(*c.value);
}

void ByteArray::insert(size_t pos, char byte) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=pos; c.args[1]=static_cast<unsigned char>(byte); ByteArrayHost::execute(26,c);
}

ByteArray::iterator ByteArray::insert(const_iterator pos, char byte) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.position=pos; c.args[0]=static_cast<unsigned char>(byte); ByteArrayHost::execute(27,c); return c.pointer;
}

void ByteArray::push_back(char byte) {
  ByteArrayHost::NativeCtx c; c.owner=this; c.args[0]=static_cast<unsigned char>(byte); ByteArrayHost::execute(28,c);
}

bool ByteArray::operator<(const ByteArray& b) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&b; ByteArrayHost::execute(29,c); return c.result;
}

bool ByteArray::operator==(const ByteArray& b) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&b; ByteArrayHost::execute(30,c); return c.result;
}

bool ByteArray::operator!=(const ByteArray& b) const {
  ByteArrayHost::NativeCtx c; c.owner=this; c.other=&b; ByteArrayHost::execute(31,c); return c.result;
}

std::ostream& operator<<(std::ostream& os, const ByteArray& b) {
  ByteArrayHost::NativeCtx c; c.owner=&b; c.stream=&os; ByteArrayHost::execute(32,c); return os;
}

}

namespace Star::ByteArrayHost { void streamHex(NativeCtx& c){ *c.stream << hexEncode(*c.owner); } }
