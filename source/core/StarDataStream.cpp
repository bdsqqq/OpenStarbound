#include "StarDataStream.hpp"
#include "StarBytes.hpp"
#include "StarVlqEncoding.hpp"

#include <string.h>

#if defined(STAR_USE_RUST_DATA_STREAM)
#include "StarDataStreamHost.hpp"
namespace Star {
unsigned const CurrentStreamVersion = 21;// update OpenProtocolVersion too!
using namespace DataStreamRust;
// These factories occur in real member lexical scope: no class-layout mirror,
// private/public preprocessor rewrite or const_cast is involved.
#define DS_CONTEXT Context c(this);c.mut=this;c.order=&m_byteOrder;c.orderMut=&m_byteOrder;c.term=&m_nullTerminatedStrings;c.termMut=&m_nullTerminatedStrings;c.version=&m_streamCompatibilityVersion;c.versionMut=&m_streamCompatibilityVersion
#define DS_CONST Context c(this);c.order=&m_byteOrder;c.term=&m_nullTerminatedStrings;c.version=&m_streamCompatibilityVersion
#define DS_PRIVATE c.privateWrite=[](Context&x){x.mut->writeStringData(x.view,x.length);}
DataStream::DataStream(){DS_CONTEXT;execute(DS_CTOR,c);}
ByteOrder DataStream::byteOrder()const{DS_CONST;execute(DS_GET_ORDER,c);return ByteOrder(uint32_t(c.result));}
void DataStream::setByteOrder(ByteOrder x){DS_CONTEXT;c.argument=uint32_t(x);execute(DS_SET_ORDER,c);}
bool DataStream::nullTerminatedStrings()const{DS_CONST;execute(DS_GET_NULL,c);return bool(c.result);}
void DataStream::setNullTerminatedStrings(bool x){DS_CONTEXT;c.argument=x;execute(DS_SET_NULL,c);}
unsigned DataStream::streamCompatibilityVersion()const{DS_CONST;execute(DS_GET_VERSION,c);return unsigned(c.result);}
void DataStream::setStreamCompatibilityVersion(unsigned x){DS_CONTEXT;c.argument=x;execute(DS_SET_VERSION,c);}
void DataStream::setStreamCompatibilityVersion(NetCompatibilityRules const&x){DS_CONTEXT;c.rules=&x;execute(DS_SET_RULES,c);}
ByteArray DataStream::readBytes(size_t n){ByteArray ba;DS_CONTEXT;c.kind=Kind::Array;c.array=&ba;c.arrayMut=&ba;c.argument=n;execute(DS_READ_BYTES,c);return ba;}
void DataStream::writeBytes(ByteArray const&ba){DS_CONTEXT;c.kind=Kind::Array;c.array=&ba;execute(DS_WRITE_BYTES,c);}
DataStream& DataStream::operator<<(bool x){DS_CONTEXT;c.argument=uint8_t(x);execute(DS_WRITE_BOOL,c);return *this;}
DataStream& DataStream::operator<<(char x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_CHAR,c);return *this;}
 DataStream& DataStream::operator<<(int8_t x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_I8,c);return *this;}
 DataStream& DataStream::operator<<(uint8_t x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_U8,c);return *this;}

DataStream& DataStream::operator<<(int16_t x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_I16,c);return *this;}
 DataStream& DataStream::operator<<(uint16_t x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_U16,c);return *this;}
 DataStream& DataStream::operator<<(int32_t x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_I32,c);return *this;}
 DataStream& DataStream::operator<<(uint32_t x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_U32,c);return *this;}

DataStream& DataStream::operator<<(int64_t x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_I64,c);return *this;}
 DataStream& DataStream::operator<<(uint64_t x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_U64,c);return *this;}
 DataStream& DataStream::operator<<(float x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_F32,c);return *this;}
 DataStream& DataStream::operator<<(double x){DS_CONTEXT;c.bind(x);execute(DS_WRITE_F64,c);return *this;}

DataStream& DataStream::operator>>(bool&x){DS_CONTEXT;c.boolOut=&x;c.bind(c.byte);execute(DS_READ_BOOL,c);return *this;}
DataStream& DataStream::operator>>(char&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_CHAR,c);return *this;}
 DataStream& DataStream::operator>>(int8_t&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_I8,c);return *this;}
 DataStream& DataStream::operator>>(uint8_t&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_U8,c);return *this;}

DataStream& DataStream::operator>>(int16_t&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_I16,c);return *this;}
 DataStream& DataStream::operator>>(uint16_t&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_U16,c);return *this;}
 DataStream& DataStream::operator>>(int32_t&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_I32,c);return *this;}
 DataStream& DataStream::operator>>(uint32_t&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_U32,c);return *this;}

DataStream& DataStream::operator>>(int64_t&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_I64,c);return *this;}
 DataStream& DataStream::operator>>(uint64_t&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_U64,c);return *this;}
 DataStream& DataStream::operator>>(float&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_F32,c);return *this;}
 DataStream& DataStream::operator>>(double&x){DS_CONTEXT;c.bindRead(x);execute(DS_READ_F64,c);return *this;}

size_t DataStream::writeVlqU(uint64_t x){DS_CONTEXT;c.argument=x;execute(DS_WRITE_VLQU,c);return size_t(c.result);}
size_t DataStream::writeVlqI(int64_t x){DS_CONTEXT;std::memcpy(&c.argument,&x,8);execute(DS_WRITE_VLQI,c);return size_t(c.result);}
size_t DataStream::writeVlqS(size_t x){DS_CONTEXT;c.argument=x;execute(DS_WRITE_VLQS,c);return size_t(c.result);}
size_t DataStream::readVlqU(uint64_t&x){DS_CONTEXT;c.uout=&x;execute(DS_READ_VLQU,c);return size_t(c.result);}
size_t DataStream::readVlqI(int64_t&x){DS_CONTEXT;c.iout=&x;execute(DS_READ_VLQI,c);return size_t(c.result);}
size_t DataStream::readVlqS(size_t&x){uint64_t temporary;DS_CONTEXT;c.uout=&temporary;c.sout=&x;execute(DS_READ_VLQS,c);return size_t(c.result);}
uint64_t DataStream::readVlqU(){uint64_t temporary;DS_CONTEXT;c.uout=&temporary;execute(DS_VALUE_VLQU,c);return c.result;}
int64_t DataStream::readVlqI(){int64_t temporary;DS_CONTEXT;c.iout=&temporary;execute(DS_VALUE_VLQI,c);int64_t x;std::memcpy(&x,&c.result,8);return x;}
size_t DataStream::readVlqS(){size_t temporary;DS_CONTEXT;c.sout=&temporary;execute(DS_VALUE_VLQS,c);return size_t(c.result);}
DataStream& DataStream::operator<<(char const*x){DS_CONTEXT;DS_PRIVATE;c.kind=Kind::Cstr;c.cstr=x;execute(DS_WRITE_CSTRING,c);return *this;}
DataStream& DataStream::operator<<(std::string const&x){DS_CONTEXT;DS_PRIVATE;c.kind=Kind::Std;c.stdstr=&x;execute(DS_WRITE_STDSTRING,c);return *this;}
DataStream& DataStream::operator<<(ByteArray const&x){DS_CONTEXT;c.kind=Kind::Array;c.array=&x;execute(DS_WRITE_ARRAY,c);return *this;}
DataStream& DataStream::operator<<(String const&x){DS_CONTEXT;DS_PRIVATE;c.kind=Kind::String;c.str=&x;execute(DS_WRITE_STRING,c);return *this;}
DataStream& DataStream::operator>>(std::string&x){DS_CONTEXT;c.kind=Kind::Std;c.stdstr=&x;c.stdMut=&x;execute(DS_READ_STDSTRING,c);return *this;}
DataStream& DataStream::operator>>(ByteArray&x){DS_CONTEXT;c.kind=Kind::Array;c.array=&x;c.arrayMut=&x;execute(DS_READ_ARRAY,c);return *this;}
DataStream& DataStream::operator>>(String&x){std::string temporary;DS_CONTEXT;c.str=&x;c.strMut=&x;c.temp=&temporary;execute(DS_READ_STRING,c);return *this;}
void DataStream::writeStringData(char const*data,size_t len){DS_CONTEXT;c.kind=Kind::Raw;c.view=data;c.length=len;c.captured=true;execute(DS_WRITE_STRING_DATA,c);}
#undef DS_CONTEXT
#undef DS_CONST
#undef DS_PRIVATE
#undef DS_WRITE
#undef DS_READ
}

#else
namespace Star {

unsigned const CurrentStreamVersion = 21;// update OpenProtocolVersion too!

DataStream::DataStream()
  : m_byteOrder(ByteOrder::BigEndian),
    m_nullTerminatedStrings(false),
    m_streamCompatibilityVersion(CurrentStreamVersion) {}

ByteOrder DataStream::byteOrder() const {
  return m_byteOrder;
}

void DataStream::setByteOrder(ByteOrder byteOrder) {
  m_byteOrder = byteOrder;
}

bool DataStream::nullTerminatedStrings() const {
  return m_nullTerminatedStrings;
}

void DataStream::setNullTerminatedStrings(bool nullTerminatedStrings) {
  m_nullTerminatedStrings = nullTerminatedStrings;
}

unsigned DataStream::streamCompatibilityVersion() const {
  return m_streamCompatibilityVersion;
}

void DataStream::setStreamCompatibilityVersion(unsigned streamCompatibilityVersion) {
  m_streamCompatibilityVersion = streamCompatibilityVersion;
}

void DataStream::setStreamCompatibilityVersion(NetCompatibilityRules const& rules) {
  m_streamCompatibilityVersion = rules.version();
}

ByteArray DataStream::readBytes(size_t len) {
  ByteArray ba;
  ba.resize(len);
  readData(ba.ptr(), len);
  return ba;
}

void DataStream::writeBytes(ByteArray const& ba) {
  writeData(ba.ptr(), ba.size());
}

DataStream& DataStream::operator<<(bool d) {
  operator<<((uint8_t)d);
  return *this;
}

DataStream& DataStream::operator<<(char c) {
  writeData(&c, 1);
  return *this;
}

DataStream& DataStream::operator<<(int8_t d) {
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator<<(uint8_t d) {
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator<<(int16_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator<<(uint16_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator<<(int32_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator<<(uint32_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator<<(int64_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator<<(uint64_t d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator<<(float d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator<<(double d) {
  d = toByteOrder(m_byteOrder, d);
  writeData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator>>(bool& d) {
  uint8_t bu;
  readData((char*)&bu, sizeof(bu));
  d = (bool)bu;
  return *this;
}

DataStream& DataStream::operator>>(char& c) {
  readData(&c, 1);
  return *this;
}

DataStream& DataStream::operator>>(int8_t& d) {
  readData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator>>(uint8_t& d) {
  readData((char*)&d, sizeof(d));
  return *this;
}

DataStream& DataStream::operator>>(int16_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStream& DataStream::operator>>(uint16_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStream& DataStream::operator>>(int32_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStream& DataStream::operator>>(uint32_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStream& DataStream::operator>>(int64_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStream& DataStream::operator>>(uint64_t& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStream& DataStream::operator>>(float& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

DataStream& DataStream::operator>>(double& d) {
  readData((char*)&d, sizeof(d));
  d = fromByteOrder(m_byteOrder, d);
  return *this;
}

size_t DataStream::writeVlqU(uint64_t i) {
  return Star::writeVlqU(i, makeFunctionOutputIterator([this](uint8_t b) { *this << b; }));
}

size_t DataStream::writeVlqI(int64_t i) {
  return Star::writeVlqI(i, makeFunctionOutputIterator([this](uint8_t b) { *this << b; }));
}

size_t DataStream::writeVlqS(size_t i) {
  uint64_t i64;
  if (i == NPos)
    i64 = 0;
  else
    i64 = i + 1;
  return writeVlqU(i64);
}

size_t DataStream::readVlqU(uint64_t& i) {
  size_t bytesRead = Star::readVlqU(i, makeFunctionInputIterator([this]() { return this->read<uint8_t>(); }));

  if (bytesRead == NPos)
    throw DataStreamException("Error reading VLQ encoded integer!");

  return bytesRead;
}

size_t DataStream::readVlqI(int64_t& i) {
  size_t bytesRead = Star::readVlqI(i, makeFunctionInputIterator([this]() { return this->read<uint8_t>(); }));

  if (bytesRead == NPos)
    throw DataStreamException("Error reading VLQ encoded integer!");

  return bytesRead;
}

size_t DataStream::readVlqS(size_t& i) {
  uint64_t i64;
  size_t res = readVlqU(i64);
  if (i64 == 0)
    i = NPos;
  else
    i = (size_t)(i64 - 1);
  return res;
}

uint64_t DataStream::readVlqU() {
  uint64_t i;
  readVlqU(i);
  return i;
}

int64_t DataStream::readVlqI() {
  int64_t i;
  readVlqI(i);
  return i;
}

size_t DataStream::readVlqS() {
  size_t i;
  readVlqS(i);
  return i;
}

DataStream& DataStream::operator<<(char const* s) {
  /*if (m_streamCompatibilityVersion < 21 && !isValidUtf8(s, strlen(s))) {
    auto sanitized = String(s).sanitize();
    writeStringData(sanitized.utf8Ptr(), sanitized.utf8Size());
    return *this;
  }*/
  writeStringData(s, strlen(s));
  return *this;
}

DataStream& DataStream::operator<<(std::string const& d) {
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

DataStream& DataStream::operator<<(const ByteArray& d) {
  writeVlqU(d.size());
  writeData(d.ptr(), d.size());
  return *this;
}

DataStream& DataStream::operator<<(const String& s) {
  /*if (m_streamCompatibilityVersion < 21 && !s.isValid()) {
    auto sanitized = s.sanitize();
    writeStringData(sanitized.utf8Ptr(), sanitized.utf8Size());
  } else {*/
    writeStringData(s.utf8Ptr(), s.utf8Size());
  //}
  return *this;
}

DataStream& DataStream::operator>>(std::string& d) {
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

DataStream& DataStream::operator>>(ByteArray& d) {
  d.resize((size_t)readVlqU());
  readData(d.ptr(), d.size());
  return *this;
}

DataStream& DataStream::operator>>(String& s) {
  std::string string;
  operator>>(string);
  s = std::move(string);
  return *this;
}

void DataStream::writeStringData(char const* data, size_t len) {
  if (m_nullTerminatedStrings) {
    writeData(data, len);
    operator<<((uint8_t)0x00);
  } else {
    writeVlqU(len);
    writeData(data, len);
  }
}

}

#endif
