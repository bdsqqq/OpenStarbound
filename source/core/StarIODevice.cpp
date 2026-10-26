#include "StarIODevice.hpp"
#include "StarMathCommon.hpp"
#include "StarFormat.hpp"

#ifdef STAR_USE_RUST_IO_DEVICE
#include "StarIODeviceHost.hpp"

namespace Star {
// Member scope binds the real private atomic; constructors expose its address
// without loading the uninitialized value. Every reentrant call gets a new ctx.
#define IO_CTX() IODeviceRust::NativeCtx c; c.owner=this;c.constOwner=this;c.modeField=&m_mode
#define IO_RUN(n) IODeviceRust::execute(n,c)
IODevice::IODevice(IOMode m){IO_CTX();c.modeReady=false;c.args[0]=(uint8_t)m;IO_RUN(STAR_IO_CTOR);}
IODevice::~IODevice(){IO_CTX();IO_RUN(STAR_IO_DTOR);}
void IODevice::resize(StreamOffset n){IO_CTX();c.args[0]=n;IO_RUN(STAR_IO_RESIZE);}
void IODevice::readFull(char* p,size_t n){IO_CTX();c.output=p;c.args[1]=n;IO_RUN(STAR_IO_READ_FULL);}
void IODevice::writeFull(char const* p,size_t n){IO_CTX();c.input=p;c.args[1]=n;IO_RUN(STAR_IO_WRITE_FULL);}
void IODevice::open(IOMode m){IO_CTX();c.args[0]=(uint8_t)m;IO_RUN(STAR_IO_OPEN);}
void IODevice::close(){IO_CTX();IO_RUN(STAR_IO_CLOSE);}
void IODevice::sync(){IO_CTX();IO_RUN(STAR_IO_SYNC);}
String IODevice::deviceName()const{IODeviceRust::NativeCtx c;c.constOwner=this;IO_RUN(STAR_IO_DEVICE_NAME);return c.name;}
bool IODevice::atEnd(){IO_CTX();IO_RUN(STAR_IO_AT_END);return c.result;}
StreamOffset IODevice::size(){IO_CTX();IO_RUN(STAR_IO_SIZE);return (StreamOffset)c.result;}
size_t IODevice::readAbsolute(StreamOffset p,char* b,size_t n){IO_CTX();c.args[0]=p;c.args[1]=n;c.output=b;IO_RUN(STAR_IO_READ_ABSOLUTE);return c.result;}
size_t IODevice::writeAbsolute(StreamOffset p,char const* b,size_t n){IO_CTX();c.args[0]=p;c.args[1]=n;c.input=b;IO_RUN(STAR_IO_WRITE_ABSOLUTE);return c.result;}
void IODevice::readFullAbsolute(StreamOffset p,char* b,size_t n){IO_CTX();c.args[0]=p;c.args[1]=n;c.output=b;IO_RUN(STAR_IO_READ_FULL_ABSOLUTE);}
void IODevice::writeFullAbsolute(StreamOffset p,char const* b,size_t n){IO_CTX();c.args[0]=p;c.args[1]=n;c.input=b;IO_RUN(STAR_IO_WRITE_FULL_ABSOLUTE);}
ByteArray IODevice::readBytes(size_t n){IO_CTX();c.args[0]=n;IO_RUN(STAR_IO_READ_BYTES);return std::move(c.value);}
void IODevice::writeBytes(ByteArray const& p){IO_CTX();IODeviceRust::bindParam(c,p);IO_RUN(STAR_IO_WRITE_BYTES);}
ByteArray IODevice::readBytesAbsolute(StreamOffset p,size_t n){IO_CTX();c.args[0]=p;c.args[1]=n;IO_RUN(STAR_IO_READ_BYTES_ABSOLUTE);return std::move(c.value);}
void IODevice::writeBytesAbsolute(StreamOffset p,ByteArray const& b){IO_CTX();c.args[0]=p;IODeviceRust::bindParam(c,b);IO_RUN(STAR_IO_WRITE_BYTES_ABSOLUTE);}
void IODevice::setMode(IOMode m){IO_CTX();c.args[0]=(uint8_t)m;IO_RUN(STAR_IO_SET_MODE);}
IODevice::IODevice(IODevice const& rhs){IO_CTX();c.modeReady=false;c.source=&rhs;IO_RUN(STAR_IO_COPY_CTOR);}
IODevice& IODevice::operator=(IODevice const& rhs){IO_CTX();c.source=&rhs;IO_RUN(STAR_IO_ASSIGN);return *this;}
#undef IO_RUN
#undef IO_CTX
}

#else
namespace Star {

IODevice::IODevice(IOMode mode) {
  m_mode = mode;
}

IODevice::~IODevice() {
  close();
}

void IODevice::resize(StreamOffset) {
  throw IOException("resize not supported");
}

void IODevice::readFull(char* data, size_t len) {
  size_t r = read(data, len);
  if (r < len) {
    if (atEnd())
      throw EofException("Failed to read full buffer in readFull, eof reached.");
    else
      throw IOException("Failed to read full buffer in readFull");
  }
  data += r;
  len -= r;
}

void IODevice::writeFull(char const* data, size_t len) {
  size_t r = write(data, len);
  if (r < len) {
    if (atEnd())
      throw EofException("Failed to write full buffer in writeFull, eof reached.");
    else
      throw IOException("Failed to write full buffer in writeFull");
  }
  data += r;
  len -= r;
}

void IODevice::open(IOMode mode) {
  if (mode != m_mode)
    throw IOException::format("Cannot reopen device '{}", deviceName());
}

void IODevice::close() {
  m_mode = IOMode::Closed;
}

void IODevice::sync() {}

String IODevice::deviceName() const {
  return strf("IODevice <{}>", (void*)this);
}

bool IODevice::atEnd() {
  return pos() >= size();
}

StreamOffset IODevice::size() {
  try {
    StreamOffset storedPos = pos();
    seek(0, IOSeek::End);
    StreamOffset size = pos();
    seek(storedPos);
    return size;
  } catch (IOException const& e) {
    throw IOException("Cannot call size() on IODevice", e);
  }
}

size_t IODevice::readAbsolute(StreamOffset readPosition, char* data, size_t len) {
  StreamOffset storedPos = pos();
  seek(readPosition);
  size_t ret = read(data, len);
  seek(storedPos);
  return ret;
}

size_t IODevice::writeAbsolute(StreamOffset writePosition, char const* data, size_t len) {
  StreamOffset storedPos = pos();
  seek(writePosition);
  size_t ret = write(data, len);
  seek(storedPos);
  return ret;
}

void IODevice::readFullAbsolute(StreamOffset readPosition, char* data, size_t len) {
  while (len > 0) {
    size_t r = readAbsolute(readPosition, data, len);
    if (r == 0)
      throw IOException("Failed to read full buffer in readFullAbsolute");
    readPosition += r;
    data += r;
    len -= r;
  }
}

void IODevice::writeFullAbsolute(StreamOffset writePosition, char const* data, size_t len) {
  while (len > 0) {
    size_t r = writeAbsolute(writePosition, data, len);
    if (r == 0)
      throw IOException("Failed to write full buffer in writeFullAbsolute");
    writePosition += r;
    data += r;
    len -= r;
  }
}

ByteArray IODevice::readBytes(size_t size) {
  if (!size)
    return {};

  ByteArray p;
  p.resize(size);
  readFull(p.ptr(), size);
  return p;
}

void IODevice::writeBytes(ByteArray const& p) {
  writeFull(p.ptr(), p.size());
}

ByteArray IODevice::readBytesAbsolute(StreamOffset readPosition, size_t size) {
  if (!size)
    return {};

  ByteArray p;
  p.resize(size);
  readFullAbsolute(readPosition, p.ptr(), size);
  return p;
}

void IODevice::writeBytesAbsolute(StreamOffset writePosition, ByteArray const& p) {
  writeFullAbsolute(writePosition, p.ptr(), p.size());
}

void IODevice::setMode(IOMode m) {
  m_mode = m;
}

IODevice::IODevice(IODevice const& rhs) {
  m_mode = rhs.mode();
}

IODevice& IODevice::operator=(IODevice const& rhs) {
  m_mode = rhs.mode();
  return *this;
}

}
#endif
