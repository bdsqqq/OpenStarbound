#include "StarBuffer.reference.hpp"
#include "StarMathCommon.hpp"
#include "StarIODevice.hpp"
#include "StarFormat.hpp"
#include "StarLogging.hpp"

namespace Star {

BufferReference::BufferReference()
  : m_pos(0) {
  setMode(IOMode::ReadWrite);
}

BufferReference::BufferReference(size_t initialSize)
  : BufferReference() {
  reset(initialSize);
}

BufferReference::BufferReference(ByteArray b)
  : BufferReference() {
  reset(std::move(b));
}

BufferReference::BufferReference(BufferReference const& buffer)
  : BufferReference() {
  operator=(buffer);
}

BufferReference::BufferReference(BufferReference&& buffer)
  : BufferReference() {
  operator=(std::move(buffer));
}

StreamOffset BufferReference::pos() {
  return m_pos;
}

void BufferReference::seek(StreamOffset pos, IOSeek mode) {
  StreamOffset newPos = m_pos;
  if (mode == IOSeek::Absolute)
    newPos = pos;
  else if (mode == IOSeek::Relative)
    newPos += pos;
  else if (mode == IOSeek::End)
    newPos = m_bytes.size() - pos;
  m_pos = newPos;
}

void BufferReference::resize(StreamOffset size) {
  data().resize((size_t)size);
}

bool BufferReference::atEnd() {
  return m_pos >= m_bytes.size();
}

size_t BufferReference::read(char* data, size_t len) {
  size_t l = doRead(m_pos, data, len);
  m_pos += l;
  return l;
}

size_t BufferReference::write(char const* data, size_t len) {
  size_t l = doWrite(m_pos, data, len);
  m_pos += l;
  return l;
}

size_t BufferReference::readAbsolute(StreamOffset readPosition, char* data, size_t len) {
  size_t rpos = readPosition;
  if ((StreamOffset)rpos != readPosition)
    throw IOException("Error, readPosition out of range");

  return doRead(rpos, data, len);
}

size_t BufferReference::writeAbsolute(StreamOffset writePosition, char const* data, size_t len) {
  size_t wpos = writePosition;
  if ((StreamOffset)wpos != writePosition)
    throw IOException("Error, writePosition out of range");

  return doWrite(wpos, data, len);
}

void BufferReference::open(IOMode mode) {
  setMode(mode);
  if (mode & IOMode::Write && mode & IOMode::Truncate)
    resize(0);
  if (mode & IOMode::Append)
    seek(0, IOSeek::End);
}

String BufferReference::deviceName() const {
  return strf("Buffer <{}>", (void*)this);
}

StreamOffset BufferReference::size() {
  return m_bytes.size();
}

ByteArray& BufferReference::data() {
  return m_bytes;
}

ByteArray const& BufferReference::data() const {
  return m_bytes;
}

ByteArray BufferReference::takeData() {
  ByteArray ret = std::move(m_bytes);
  reset(0);
  return ret;
}

char* BufferReference::ptr() {
  return data().ptr();
}

char const* BufferReference::ptr() const {
  return m_bytes.ptr();
}

size_t BufferReference::dataSize() const {
  return m_bytes.size();
}

void BufferReference::reserve(size_t size) {
  data().reserve(size);
}

void BufferReference::clear() {
  m_pos = 0;
  m_bytes.clear();
}

bool BufferReference::empty() const {
  return m_bytes.empty();
}

void BufferReference::reset(size_t newSize) {
  m_pos = 0;
  m_bytes.fill(newSize, 0);
}

void BufferReference::reset(ByteArray b) {
  m_pos = 0;
  m_bytes = std::move(b);
}

BufferReference& BufferReference::operator=(BufferReference const& buffer) {
  IODevice::operator=(buffer);
  m_pos = buffer.m_pos;
  m_bytes = buffer.m_bytes;
  return *this;
}

BufferReference& BufferReference::operator=(BufferReference&& buffer) {
  IODevice::operator=(buffer);
  m_pos = buffer.m_pos;
  m_bytes = std::move(buffer.m_bytes);

  buffer.m_pos = 0;
  buffer.m_bytes = ByteArray();

  return *this;
}

size_t BufferReference::doRead(size_t pos, char* data, size_t len) {
  if (len == 0)
    return 0;

  if (!isReadable())
    throw IOException("Error, read called on non-readable Buffer");

  if (pos >= m_bytes.size())
    return 0;

  size_t l = min(m_bytes.size() - pos, len);
  memcpy(data, m_bytes.ptr() + pos, l);
  return l;
}

size_t BufferReference::doWrite(size_t pos, char const* data, size_t len) {
  if (len == 0)
    return 0;

  if (!isWritable())
    throw EofException("Error, write called on non-writable Buffer");

  if (pos + len > m_bytes.size())
    m_bytes.resize(pos + len);

  memcpy(m_bytes.ptr() + pos, data, len);
  return len;
}

ExternalBufferReference::ExternalBufferReference()
  : m_pos(0), m_bytes(nullptr), m_size(0) {
  setMode(IOMode::Read);
}

ExternalBufferReference::ExternalBufferReference(char const* externalData, size_t len) : ExternalBufferReference() {
  reset(externalData, len);
}

StreamOffset ExternalBufferReference::pos() {
  return m_pos;
}

void ExternalBufferReference::seek(StreamOffset pos, IOSeek mode) {
  StreamOffset newPos = m_pos;
  if (mode == IOSeek::Absolute)
    newPos = pos;
  else if (mode == IOSeek::Relative)
    newPos += pos;
  else if (mode == IOSeek::End)
    newPos = m_size - pos;
  m_pos = newPos;
}

bool ExternalBufferReference::atEnd() {
  return m_pos >= m_size;
}

size_t ExternalBufferReference::read(char* data, size_t len) {
  size_t l = doRead(m_pos, data, len);
  m_pos += l;
  return l;
}

size_t ExternalBufferReference::write(char const*, size_t) {
  throw IOException("Error, ExternalBuffer is not writable");
}

size_t ExternalBufferReference::readAbsolute(StreamOffset readPosition, char* data, size_t len) {
  size_t rpos = readPosition;
  if ((StreamOffset)rpos != readPosition)
    throw IOException("Error, readPosition out of range");

  return doRead(rpos, data, len);
}

size_t ExternalBufferReference::writeAbsolute(StreamOffset, char const*, size_t) {
  throw IOException("Error, ExternalBuffer is not writable");
}

String ExternalBufferReference::deviceName() const {
  return strf("ExternalBuffer <{}>", (void*)this);
}

StreamOffset ExternalBufferReference::size() {
  return m_size;
}

char const* ExternalBufferReference::ptr() const {
  return m_bytes;
}

size_t ExternalBufferReference::dataSize() const {
  return m_size;
}

bool ExternalBufferReference::empty() const {
  return m_size == 0;
}

ExternalBufferReference::operator bool() const {
  return m_size == 0;
}

void ExternalBufferReference::reset(char const* externalData, size_t len) {
  m_pos = 0;
  m_bytes = externalData;
  m_size = len;
}

IODevicePtr BufferReference::clone() {
  auto cloned = make_shared<BufferReference>(*this);
  // Reset position to 0 while preserving mode and data
  cloned->seek(0);
  return cloned;
}

IODevicePtr ExternalBufferReference::clone() {
  Logger::info("Cloning ExternalBuffer from position {}");
  return make_shared<ExternalBufferReference>(*this);
}

size_t ExternalBufferReference::doRead(size_t pos, char* data, size_t len) {
  if (len == 0)
    return 0;

  if (!isReadable())
    throw IOException("Error, read called on non-readable Buffer");

  if (pos >= m_size)
    return 0;

  size_t l = min(m_size - pos, len);
  memcpy(data, m_bytes + pos, l);
  return l;
}

}
