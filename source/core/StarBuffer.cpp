#include "StarBuffer.hpp"
#include "StarMathCommon.hpp"
#include "StarIODevice.hpp"
#include "StarFormat.hpp"
#include "StarLogging.hpp"

#ifdef STAR_USE_RUST_BUFFER
#include "StarBufferHost.hpp"

// Capturingless member-scope thunks have legal private/protected access. No
// std::function allocation, field-layout mirror, or owner-wide busy lock.
#define BCONST NativeCtx c; c.constOwner=this;c.constPosition=&m_pos;c.constBytes=&m_bytes
#define BCTX BCONST; c.owner=this;c.position=&m_pos;c.bytes=&m_bytes; \
 c.setMode=+[](NativeCtx& x,IOMode m){x.owner->setMode(m);}; \
 c.baseCopy=+[](NativeCtx& x){x.owner->IODevice::operator=(*x.source);}; \
 c.child=+[](NativeCtx& x,uint64_t op,uint64_t v)->uint64_t{switch(op){ \
 case 0:x.owner->reset((size_t)v);break;case 1:if(!x.param)throw Stop{2};x.owner->reset(std::move(*x.param));break; \
 case 2:if(!x.source)throw Stop{2};*x.owner=*x.source;break;case 3:if(!x.moveSource)throw Stop{2};*x.owner=std::move(*x.moveSource);break; \
 case 4:x.ref=&x.owner->data();break;case 5:return x.owner->doRead(v,x.output,x.args[1]);case 6:return x.owner->doWrite(v,x.input,x.args[1]); \
 case 7:x.owner->resize((StreamOffset)v);break;case 8:x.owner->seek(0,IOSeek::End);break;default:throw Stop{2};}return 0;}
#define ECONST NativeCtx c;c.constExternal=this;c.constPosition=&m_pos;c.constBorrowed=&m_bytes;c.constExternalSize=&m_size
#define ECTX ECONST;c.external=this;c.position=&m_pos;c.borrowed=&m_bytes;c.externalSize=&m_size; \
 c.setMode=+[](NativeCtx& x,IOMode m){x.external->setMode(m);}; \
 c.child=+[](NativeCtx& x,uint64_t op,uint64_t v)->uint64_t{if(op==9){x.external->reset(x.input,x.args[0]);return 0;}if(op!=5)throw Stop{2};return x.external->doRead(v,x.output,x.args[1]);}
#define SRC c.source=&buffer;c.sourcePosition=&buffer.m_pos;c.sourceBytes=&buffer.m_bytes
#define MOVESRC SRC;c.moveSource=&buffer;c.moveSourcePosition=&buffer.m_pos;c.moveSourceBytes=&buffer.m_bytes
namespace Star {
using namespace BufferRust;
Buffer::Buffer(){BCTX;c.posReady=false;execute(c,SB_B_CTOR);}
Buffer::Buffer(size_t initialSize):Buffer(){BCTX;c.args[0]=initialSize;execute(c,SB_B_CTOR_SIZE);}
Buffer::Buffer(ByteArray b):Buffer(){BCTX;c.param=&b;execute(c,SB_B_CTOR_BYTES);}
Buffer::Buffer(Buffer const& buffer):Buffer(){BCTX;SRC;execute(c,SB_B_CTOR_COPY);}
Buffer::Buffer(Buffer&& buffer):Buffer(){BCTX;MOVESRC;execute(c,SB_B_CTOR_MOVE);}
StreamOffset Buffer::pos(){BCTX;execute(c,SB_B_POS);return c.result;}
void Buffer::seek(StreamOffset pos,IOSeek mode){BCTX;c.args[0]=pos;c.args[1]=(uint8_t)mode;execute(c,SB_B_SEEK);}
void Buffer::resize(StreamOffset size){BCTX;c.args[0]=size;execute(c,SB_B_RESIZE);}
bool Buffer::atEnd(){BCTX;execute(c,SB_B_END);return c.result;}
size_t Buffer::read(char* data,size_t len){BCTX;c.output=data;c.args[1]=len;execute(c,SB_B_READ);return c.result;}
size_t Buffer::write(char const* data,size_t len){BCTX;c.input=data;c.args[1]=len;execute(c,SB_B_WRITE);return c.result;}
size_t Buffer::readAbsolute(StreamOffset p,char* data,size_t len){BCTX;c.output=data;c.args[0]=p;c.args[1]=len;execute(c,SB_B_READ_ABS);return c.result;}
size_t Buffer::writeAbsolute(StreamOffset p,char const* data,size_t len){BCTX;c.input=data;c.args[0]=p;c.args[1]=len;execute(c,SB_B_WRITE_ABS);return c.result;}
void Buffer::open(IOMode mode){BCTX;c.args[0]=(uint8_t)mode;execute(c,SB_B_OPEN);}
String Buffer::deviceName()const{BCONST;execute(c,SB_B_NAME);return std::move(c.name);}
StreamOffset Buffer::size(){BCTX;execute(c,SB_B_SIZE);return c.result;}
ByteArray& Buffer::data(){BCTX;execute(c,SB_B_DATA);return *c.ref;}
ByteArray const& Buffer::data()const{BCONST;execute(c,SB_B_CONST_DATA);return *c.constRef;}
ByteArray Buffer::takeData(){BCTX;execute(c,SB_B_TAKE);return std::move(c.value);}
char* Buffer::ptr(){BCTX;execute(c,SB_B_PTR);return c.pointer;}
char const* Buffer::ptr()const{BCONST;execute(c,SB_B_CONST_PTR);return c.constPointer;}
size_t Buffer::dataSize()const{BCONST;execute(c,SB_B_DATA_SIZE);return c.result;}
void Buffer::reserve(size_t size){BCTX;c.args[0]=size;execute(c,SB_B_RESERVE);}
void Buffer::clear(){BCTX;execute(c,SB_B_CLEAR);}
bool Buffer::empty()const{BCONST;execute(c,SB_B_EMPTY);return c.result;}
void Buffer::reset(size_t size){BCTX;c.args[0]=size;execute(c,SB_B_RESET_SIZE);}
void Buffer::reset(ByteArray b){BCTX;c.param=&b;execute(c,SB_B_RESET_BYTES);}
Buffer& Buffer::operator=(Buffer const& buffer){BCTX;SRC;execute(c,SB_B_COPY);return *this;}
Buffer& Buffer::operator=(Buffer&& buffer){BCTX;MOVESRC;execute(c,SB_B_MOVE);return *this;}
size_t Buffer::doRead(size_t pos,char* data,size_t len){BCTX;c.args[0]=pos;c.args[1]=len;c.output=data;execute(c,SB_B_PRIVATE_READ);return c.result;}
size_t Buffer::doWrite(size_t pos,char const* data,size_t len){BCTX;c.args[0]=pos;c.args[1]=len;c.input=data;execute(c,SB_B_PRIVATE_WRITE);return c.result;}
ExternalBuffer::ExternalBuffer(){ECTX;c.posReady=false;c.extReady=false;execute(c,SB_E_CTOR);}
ExternalBuffer::ExternalBuffer(char const* data,size_t len):ExternalBuffer(){ECTX;c.input=data;c.args[0]=len;execute(c,SB_E_CTOR_BYTES);}
StreamOffset ExternalBuffer::pos(){ECTX;execute(c,SB_E_POS);return c.result;}
void ExternalBuffer::seek(StreamOffset pos,IOSeek mode){ECTX;c.args[0]=pos;c.args[1]=(uint8_t)mode;execute(c,SB_E_SEEK);}
bool ExternalBuffer::atEnd(){ECTX;execute(c,SB_E_END);return c.result;}
size_t ExternalBuffer::read(char* data,size_t len){ECTX;c.output=data;c.args[1]=len;execute(c,SB_E_READ);return c.result;}
size_t ExternalBuffer::write(char const*,size_t){ECTX;execute(c,SB_E_WRITE);return c.result;}
size_t ExternalBuffer::readAbsolute(StreamOffset pos,char* data,size_t len){ECTX;c.output=data;c.args[0]=pos;c.args[1]=len;execute(c,SB_E_READ_ABS);return c.result;}
size_t ExternalBuffer::writeAbsolute(StreamOffset,char const*,size_t){ECTX;execute(c,SB_E_WRITE_ABS);return c.result;}
String ExternalBuffer::deviceName()const{ECONST;execute(c,SB_E_NAME);return std::move(c.name);}
StreamOffset ExternalBuffer::size(){ECTX;execute(c,SB_E_SIZE);return c.result;}
char const* ExternalBuffer::ptr()const{ECONST;execute(c,SB_E_PTR);return c.constPointer;}
size_t ExternalBuffer::dataSize()const{ECONST;execute(c,SB_E_DATA_SIZE);return c.result;}
bool ExternalBuffer::empty()const{ECONST;execute(c,SB_E_EMPTY);return c.result;}
ExternalBuffer::operator bool()const{ECONST;execute(c,SB_E_BOOL);return c.result;}
void ExternalBuffer::reset(char const* data,size_t len){ECTX;c.input=data;c.args[0]=len;execute(c,SB_E_RESET);}
IODevicePtr Buffer::clone(){BCTX;execute(c,SB_B_CLONE);return std::move(c.clone);}
IODevicePtr ExternalBuffer::clone(){ECTX;execute(c,SB_E_CLONE);return std::move(c.clone);}
size_t ExternalBuffer::doRead(size_t pos,char* data,size_t len){ECTX;c.output=data;c.args[0]=pos;c.args[1]=len;execute(c,SB_E_PRIVATE_READ);return c.result;}
}
#undef BCTX
#undef BCONST
#undef ECTX
#undef ECONST
#undef SRC
#undef MOVESRC

#else
namespace Star {

Buffer::Buffer()
  : m_pos(0) {
  setMode(IOMode::ReadWrite);
}

Buffer::Buffer(size_t initialSize)
  : Buffer() {
  reset(initialSize);
}

Buffer::Buffer(ByteArray b)
  : Buffer() {
  reset(std::move(b));
}

Buffer::Buffer(Buffer const& buffer)
  : Buffer() {
  operator=(buffer);
}

Buffer::Buffer(Buffer&& buffer)
  : Buffer() {
  operator=(std::move(buffer));
}

StreamOffset Buffer::pos() {
  return m_pos;
}

void Buffer::seek(StreamOffset pos, IOSeek mode) {
  StreamOffset newPos = m_pos;
  if (mode == IOSeek::Absolute)
    newPos = pos;
  else if (mode == IOSeek::Relative)
    newPos += pos;
  else if (mode == IOSeek::End)
    newPos = m_bytes.size() - pos;
  m_pos = newPos;
}

void Buffer::resize(StreamOffset size) {
  data().resize((size_t)size);
}

bool Buffer::atEnd() {
  return m_pos >= m_bytes.size();
}

size_t Buffer::read(char* data, size_t len) {
  size_t l = doRead(m_pos, data, len);
  m_pos += l;
  return l;
}

size_t Buffer::write(char const* data, size_t len) {
  size_t l = doWrite(m_pos, data, len);
  m_pos += l;
  return l;
}

size_t Buffer::readAbsolute(StreamOffset readPosition, char* data, size_t len) {
  size_t rpos = readPosition;
  if ((StreamOffset)rpos != readPosition)
    throw IOException("Error, readPosition out of range");

  return doRead(rpos, data, len);
}

size_t Buffer::writeAbsolute(StreamOffset writePosition, char const* data, size_t len) {
  size_t wpos = writePosition;
  if ((StreamOffset)wpos != writePosition)
    throw IOException("Error, writePosition out of range");

  return doWrite(wpos, data, len);
}

void Buffer::open(IOMode mode) {
  setMode(mode);
  if (mode & IOMode::Write && mode & IOMode::Truncate)
    resize(0);
  if (mode & IOMode::Append)
    seek(0, IOSeek::End);
}

String Buffer::deviceName() const {
  return strf("Buffer <{}>", (void*)this);
}

StreamOffset Buffer::size() {
  return m_bytes.size();
}

ByteArray& Buffer::data() {
  return m_bytes;
}

ByteArray const& Buffer::data() const {
  return m_bytes;
}

ByteArray Buffer::takeData() {
  ByteArray ret = std::move(m_bytes);
  reset(0);
  return ret;
}

char* Buffer::ptr() {
  return data().ptr();
}

char const* Buffer::ptr() const {
  return m_bytes.ptr();
}

size_t Buffer::dataSize() const {
  return m_bytes.size();
}

void Buffer::reserve(size_t size) {
  data().reserve(size);
}

void Buffer::clear() {
  m_pos = 0;
  m_bytes.clear();
}

bool Buffer::empty() const {
  return m_bytes.empty();
}

void Buffer::reset(size_t newSize) {
  m_pos = 0;
  m_bytes.fill(newSize, 0);
}

void Buffer::reset(ByteArray b) {
  m_pos = 0;
  m_bytes = std::move(b);
}

Buffer& Buffer::operator=(Buffer const& buffer) {
  IODevice::operator=(buffer);
  m_pos = buffer.m_pos;
  m_bytes = buffer.m_bytes;
  return *this;
}

Buffer& Buffer::operator=(Buffer&& buffer) {
  IODevice::operator=(buffer);
  m_pos = buffer.m_pos;
  m_bytes = std::move(buffer.m_bytes);

  buffer.m_pos = 0;
  buffer.m_bytes = ByteArray();

  return *this;
}

size_t Buffer::doRead(size_t pos, char* data, size_t len) {
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

size_t Buffer::doWrite(size_t pos, char const* data, size_t len) {
  if (len == 0)
    return 0;

  if (!isWritable())
    throw EofException("Error, write called on non-writable Buffer");

  if (pos + len > m_bytes.size())
    m_bytes.resize(pos + len);

  memcpy(m_bytes.ptr() + pos, data, len);
  return len;
}

ExternalBuffer::ExternalBuffer()
  : m_pos(0), m_bytes(nullptr), m_size(0) {
  setMode(IOMode::Read);
}

ExternalBuffer::ExternalBuffer(char const* externalData, size_t len) : ExternalBuffer() {
  reset(externalData, len);
}

StreamOffset ExternalBuffer::pos() {
  return m_pos;
}

void ExternalBuffer::seek(StreamOffset pos, IOSeek mode) {
  StreamOffset newPos = m_pos;
  if (mode == IOSeek::Absolute)
    newPos = pos;
  else if (mode == IOSeek::Relative)
    newPos += pos;
  else if (mode == IOSeek::End)
    newPos = m_size - pos;
  m_pos = newPos;
}

bool ExternalBuffer::atEnd() {
  return m_pos >= m_size;
}

size_t ExternalBuffer::read(char* data, size_t len) {
  size_t l = doRead(m_pos, data, len);
  m_pos += l;
  return l;
}

size_t ExternalBuffer::write(char const*, size_t) {
  throw IOException("Error, ExternalBuffer is not writable");
}

size_t ExternalBuffer::readAbsolute(StreamOffset readPosition, char* data, size_t len) {
  size_t rpos = readPosition;
  if ((StreamOffset)rpos != readPosition)
    throw IOException("Error, readPosition out of range");

  return doRead(rpos, data, len);
}

size_t ExternalBuffer::writeAbsolute(StreamOffset, char const*, size_t) {
  throw IOException("Error, ExternalBuffer is not writable");
}

String ExternalBuffer::deviceName() const {
  return strf("ExternalBuffer <{}>", (void*)this);
}

StreamOffset ExternalBuffer::size() {
  return m_size;
}

char const* ExternalBuffer::ptr() const {
  return m_bytes;
}

size_t ExternalBuffer::dataSize() const {
  return m_size;
}

bool ExternalBuffer::empty() const {
  return m_size == 0;
}

ExternalBuffer::operator bool() const {
  return m_size == 0;
}

void ExternalBuffer::reset(char const* externalData, size_t len) {
  m_pos = 0;
  m_bytes = externalData;
  m_size = len;
}

IODevicePtr Buffer::clone() {
  auto cloned = make_shared<Buffer>(*this);
  // Reset position to 0 while preserving mode and data
  cloned->seek(0);
  return cloned;
}

IODevicePtr ExternalBuffer::clone() {
  Logger::info("Cloning ExternalBuffer from position {}");
  return make_shared<ExternalBuffer>(*this);
}

size_t ExternalBuffer::doRead(size_t pos, char* data, size_t len) {
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

#endif
