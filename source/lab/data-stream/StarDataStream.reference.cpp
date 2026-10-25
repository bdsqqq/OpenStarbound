#include "StarDataStream.reference.hpp"
#include "StarBytes.hpp"
#include "StarVlqEncoding.hpp"

#include <string.h>

namespace Star {

unsigned const ReferenceCurrentStreamVersion = 21;// update OpenProtocolVersion too!

DataStreamReference::DataStreamReference()
  : m_byteOrder(ByteOrder::BigEndian),
    m_nullTerminatedStrings(false),
    m_streamCompatibilityVersion(ReferenceCurrentStreamVersion) {}

ByteOrder DataStreamReference::byteOrder() const {
  return m_byteOrder;
}

void DataStreamReference::setByteOrder(ByteOrder byteOrder) {
  m_byteOrder = byteOrder;
}

bool DataStreamReference::nullTerminatedStrings() const {
  return m_nullTerminatedStrings;
}

void DataStreamReference::setNullTerminatedStrings(bool nullTerminatedStrings) {
  m_nullTerminatedStrings = nullTerminatedStrings;
}

unsigned DataStreamReference::streamCompatibilityVersion() const {
  return m_streamCompatibilityVersion;
}

void DataStreamReference::setStreamCompatibilityVersion(unsigned streamCompatibilityVersion) {
  m_streamCompatibilityVersion = streamCompatibilityVersion;
}

void DataStreamReference::setStreamCompatibilityVersion(NetCompatibilityRules const& rules) {
  m_streamCompatibilityVersion = rules.version();
}

ByteArray DataStreamReference::readBytes(size_t len) {
  ByteArray ba;
  ba.resize(len);
  readData(ba.ptr(), len);
  return ba;
}

void DataStreamReference::writeBytes(ByteArray const& ba) {
  writeData(ba.ptr(), ba.size());
}

DataStreamReference& DataStreamReference::operator<<(bool d) {
  operator<<((uint8_t)d);
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(char c) {
  writeData(&c, 1);
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(int8_t d) {
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(uint8_t d) {
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(int16_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(uint16_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(int32_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(uint32_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(int64_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(uint64_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(float d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(double d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(bool& d) {
  uint8_t bu;
  readData((char*)&bu, sizeof(bu));
  d = (bool)bu;
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(char& c) {
  readData(&c, 1);
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(int8_t& d) {
  readData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(uint8_t& d) {
  readData((char*)&d, sizeof(d));
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(int16_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(uint16_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(int32_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(uint32_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(int64_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(uint64_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(float& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(double& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

size_t DataStreamReference::writeVlqU(uint64_t i) {
  return Star::writeVlqU(i, makeFunctionOutputIterator([this](uint8_t b) { *this << b; }));
}

size_t DataStreamReference::writeVlqI(int64_t i) {
  return Star::writeVlqI(i, makeFunctionOutputIterator([this](uint8_t b) { *this << b; }));
}

size_t DataStreamReference::writeVlqS(size_t i) {
  uint64_t i64;
  if (i == NPos)
    i64 = 0;
  else
    i64 = i + 1;
  return writeVlqU(i64);
}

size_t DataStreamReference::readVlqU(uint64_t& i) {
  size_t bytesRead = Star::readVlqU(i, makeFunctionInputIterator([this]() { return this->read<uint8_t>(); }));

  if (bytesRead == NPos)
    throw DataStreamException("Error reading VLQ encoded integer!");

  return bytesRead;
}

size_t DataStreamReference::readVlqI(int64_t& i) {
  size_t bytesRead = Star::readVlqI(i, makeFunctionInputIterator([this]() { return this->read<uint8_t>(); }));

  if (bytesRead == NPos)
    throw DataStreamException("Error reading VLQ encoded integer!");

  return bytesRead;
}

size_t DataStreamReference::readVlqS(size_t& i) {
  uint64_t i64;
  size_t res = readVlqU(i64);
  if (i64 == 0)
    i = NPos;
  else
    i = (size_t)(i64 - 1);
  return res;
}

uint64_t DataStreamReference::readVlqU() {
  uint64_t i;
  readVlqU(i);
  return i;
}

int64_t DataStreamReference::readVlqI() {
  int64_t i;
  readVlqI(i);
  return i;
}

size_t DataStreamReference::readVlqS() {
  size_t i;
  readVlqS(i);
  return i;
}

DataStreamReference& DataStreamReference::operator<<(char const* s) {
  /*if (m_streamCompatibilityVersion < 21 && !isValidUtf8(s, strlen(s))) {
    auto sanitized = String(s).sanitize();
    writeStringData(sanitized.utf8Ptr(), sanitized.utf8Size());
    return *this;
  }*/
  writeStringData(s, strlen(s));
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(std::string const& d) {
  /*if (m_streamCompatibilityVersion < 21) {
    String u8s = String(d);
    if (!u8s.isValid()) {
      auto sanitized = u8s.sanitize();
      writeStringData(sanitized.utf8Ptr(), sanitized.utf8Size());
      return *this;
    }
  }*/
  writeStringData(d.c_str(), d.size());
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(const ByteArray& d) {
  writeVlqU(d.size());
  writeData(d.ptr(), d.size());
  return *this;
}

DataStreamReference& DataStreamReference::operator<<(const String& s) {
  /*if (m_streamCompatibilityVersion < 21 && !s.isValid()) {
    auto sanitized = s.sanitize();
    writeStringData(sanitized.utf8Ptr(), sanitized.utf8Size());
  } else {*/
    writeStringData(s.utf8Ptr(), s.utf8Size());
  //}
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(std::string& d) {
  if (m_nullTerminatedStrings) {
    d.clear();
    char c;
    while (true) {
      readData((char*)&c, sizeof(c));
      if (c == '\0')
        break;
      d.push_back(c);
    }
  } else {
    d.resize((size_t)readVlqU());
    readData(&d[0], d.size());
  }
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(ByteArray& d) {
  d.resize((size_t)readVlqU());
  readData(d.ptr(), d.size());
  return *this;
}

DataStreamReference& DataStreamReference::operator>>(String& s) {
  std::string string;
  operator>>(string);
  s = std::move(string);
  return *this;
}

void DataStreamReference::writeStringData(char const* data, size_t len) {
  if (m_nullTerminatedStrings) {
    writeData(data, len);
    operator<<((uint8_t)0x00);
  } else {
    writeVlqU(len);
    writeData(data, len);
  }
}

}
