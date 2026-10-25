#include "host_contract.hpp"
#include "StarDataStream.hpp"
#include "StarBytes.hpp"
#include "StarVlqEncoding.hpp"
#include <cstring>
#include <exception>
#include <limits>
#include <stdexcept>

// Scalar-only sequencing prototype. Native leaves below catch exceptions before
// returning; Stop never crosses this C ABI and is not a Rust unwind mechanism.
namespace {
struct Stop { uint32_t status; };
struct Controller {
 void* ctx; data_stream_lab_host host;
 uint64_t call(uint32_t op,uint64_t a=0,uint64_t b=0) {
  uint64_t out=0;auto s=host(ctx,op,a,b,&out);
  if(s)throw Stop{s==1?1u:2u};return out;
 }
 uint64_t readU(){return call(DS_CHILD,1);}
 void writeU(uint64_t x){call(DS_CHILD,0,x);}
 void run(uint32_t m) {
  if(m==DS_CTOR){call(DS_CONFIG_SET,0,0);call(DS_CONFIG_SET,1,0);call(DS_CONFIG_SET,2,call(DS_CONFIG_GET,4));}
  else if(m==DS_GET_ORDER||m==DS_GET_NULL||m==DS_GET_VERSION){call(DS_RESULT,0,call(DS_CONFIG_GET,(m-1)/2));}
  else if(m==DS_SET_ORDER||m==DS_SET_NULL||m==DS_SET_VERSION){call(DS_CONFIG_SET,(m-2)/2,call(DS_ARGUMENT));}
  else if(m==DS_SET_RULES){call(DS_CONFIG_SET,2,call(DS_CONFIG_GET,3));}
  else if(m==DS_READ_BYTES){call(DS_RESIZE,0,call(DS_ARGUMENT));call(DS_CAPTURE);call(DS_VIEW_IO);}
  else if(m==DS_WRITE_BYTES){call(DS_CAPTURE);call(DS_VIEW_IO,1);}
  else if(m==DS_WRITE_BOOL){call(DS_CHILD,4,call(DS_ARGUMENT));}
  else if(m>=DS_WRITE_CHAR&&m<=DS_WRITE_F64){
   if(m>=DS_WRITE_I16){auto order=call(DS_CONFIG_GET,0);call(DS_CONVERT,order);}
   call(DS_SCALAR_IO,1);
  } else if(m>=DS_READ_BOOL&&m<=DS_READ_F64){
   call(DS_SCALAR_IO);
   if(m==DS_READ_BOOL)call(DS_BOOL_ASSIGN);
   else if(m>=DS_READ_I16){auto order=call(DS_CONFIG_GET,0);call(DS_CONVERT,order);}
  } else if(m==DS_WRITE_VLQU||m==DS_WRITE_VLQI){call(DS_RESULT,0,call(DS_VLQ,m-DS_WRITE_VLQU,call(DS_ARGUMENT)));}
  else if(m==DS_WRITE_VLQS){auto n=call(DS_ARGUMENT);call(DS_RESULT,0,call(DS_CHILD,0,n==UINT64_MAX?0:n+1));}
  else if(m==DS_READ_VLQU||m==DS_READ_VLQI){auto n=call(DS_VLQ,2+m-DS_READ_VLQU);if(n==UINT64_MAX){call(DS_RAISE_VLQ);throw Stop{2};}call(DS_RESULT,0,n);}
  else if(m==DS_READ_VLQS){auto count=call(DS_CHILD,5);auto n=call(DS_VLQ_VALUE);call(DS_ASSIGN_SIZE,0,n==0?UINT64_MAX:n-1);call(DS_RESULT,0,count);}
  else if(m>=DS_VALUE_VLQU&&m<=DS_VALUE_VLQS){call(DS_CHILD,5+m-DS_VALUE_VLQU);call(DS_RESULT,0,call(DS_VLQ_VALUE,m-DS_VALUE_VLQU));}
  else if(m==DS_WRITE_CSTRING||m==DS_WRITE_STDSTRING||m==DS_WRITE_STRING){call(DS_CAPTURE);call(DS_CHILD,2);}
  else if(m==DS_WRITE_ARRAY){auto n=call(DS_SIZE);writeU(n);call(DS_CAPTURE);call(DS_VIEW_IO,1);}
  else if(m==DS_READ_STDSTRING){
   auto term=call(DS_CONFIG_GET,1);
   if(term){call(DS_CLEAR);for(;;){auto c=call(DS_CHAR_READ);if(!c)break;call(DS_APPEND,0,c);}}
   else {auto n=readU();call(DS_RESIZE,0,n);call(DS_CAPTURE);call(DS_VIEW_IO);}
  } else if(m==DS_READ_ARRAY){auto n=readU();call(DS_RESIZE,0,n);call(DS_CAPTURE);call(DS_VIEW_IO);}
  else if(m==DS_READ_STRING){call(DS_CHILD,3);call(DS_ASSIGN_STRING);}
  else if(m==DS_WRITE_STRING_DATA){auto term=call(DS_CONFIG_GET,1);auto n=call(DS_SIZE);if(!term)writeU(n);call(DS_VIEW_IO,1);if(term)call(DS_CHILD,4);}
  call(DS_FINISH);
 }
};
}
extern "C" uint32_t data_stream_lab_run(uint32_t mode,void* ctx,data_stream_lab_host host){
 if(!host||mode>DS_WRITE_STRING_DATA)return 2;
 try{Controller{ctx,host}.run(mode);return 0;}catch(Stop const&e){return e.status;}catch(...){return 3;}
}

namespace Star {
unsigned const CurrentStreamVersion=21; // Production constant, not archive bypass.
namespace DataStreamLab {
enum class Kind { None, Array, Std, String, Cstr, Raw };
struct Context {
 DataStream const* owner;DataStream* mut=nullptr;
 ByteOrder const* order=nullptr;ByteOrder* orderMut=nullptr;
 bool const* term=nullptr;bool* termMut=nullptr;
 unsigned const* version=nullptr;unsigned* versionMut=nullptr;
 NetCompatibilityRules const* rules=nullptr;
 void* scalar=nullptr;size_t width=0;void(*convert)(void*,ByteOrder)=nullptr;
 bool* boolOut=nullptr;uint8_t byte=0;
 uint64_t argument=0,result=0;
 uint64_t* uout=nullptr;int64_t* iout=nullptr;size_t* sout=nullptr;
 bool uReady=false,iReady=false,sReady=false;
 Kind kind=Kind::None;ByteArray const* array=nullptr;ByteArray* arrayMut=nullptr;
 std::string const* stdstr=nullptr;std::string* stdMut=nullptr;
 String const* str=nullptr;String* strMut=nullptr;
 char const* cstr=nullptr;char const* view=nullptr;char* writeView=nullptr;size_t length=0;bool captured=false;
 std::string* temp=nullptr;
 void(*privateWrite)(Context&)=nullptr;
 bool busy=false,finished=false;std::exception_ptr pending;
 explicit Context(DataStream const* p):owner(p){}
 template<class T>void bind(T& v){scalar=&v;width=sizeof(T);convert=[](void*p,ByteOrder o){auto&x=*static_cast<T*>(p);x=toByteOrder(o,x);};}
 template<class T>void bindRead(T& v){bind(v);convert=[](void*p,ByteOrder o){auto&x=*static_cast<T*>(p);x=fromByteOrder(o,x);};}
 bool overlaps(void const* out,void const* p,size_t n)const{
  if(!p||!n)return false;auto x=reinterpret_cast<uintptr_t>(out),y=reinterpret_cast<uintptr_t>(p);
  return y>UINTPTR_MAX-n || (x<y+n&&y<x+8);
 }
 bool outputOK(uint64_t* out)const{
  auto x=reinterpret_cast<uintptr_t>(out);
  if(!out||x%alignof(uint64_t)||x>UINTPTR_MAX-8)return false;
  if(overlaps(out,this,sizeof(*this))||overlaps(out,owner,sizeof(DataStream))||overlaps(out,scalar,width)||overlaps(out,boolOut,sizeof(bool))||overlaps(out,uout,8)||overlaps(out,iout,8)||overlaps(out,sout,sizeof(size_t)))return false;
  if(overlaps(out,order,sizeof(ByteOrder))||overlaps(out,term,sizeof(bool))||overlaps(out,version,sizeof(unsigned)))return false;
  if(captured&&overlaps(out,view,length))return false;
  // Prefix callbacks may remove the terminator after source-time capture.
  // Re-reading strlen then would inspect bytes the original never reads.
  if(cstr){auto n=captured?length:std::strlen(cstr);if(n==SIZE_MAX||overlaps(out,cstr,n+1))return false;}
  if(overlaps(out,array,sizeof(ByteArray))||overlaps(out,stdstr,sizeof(std::string))||overlaps(out,str,sizeof(String))||overlaps(out,temp,sizeof(std::string))||overlaps(out,rules,sizeof(NetCompatibilityRules)))return false;
  // Only active, currently valid native views are inspected. Captured input
  // pointers can be invalidated by source-undefined callbacks; not dereferenced.
  if(array&&overlaps(out,array->ptr(),array->size()))return false;
  if(stdstr&&overlaps(out,stdstr->data(),stdstr->size()+1))return false;
  if(str&&overlaps(out,str->utf8Ptr(),str->utf8Size()+1))return false;
  if(temp&&overlaps(out,temp->data(),temp->size()+1))return false;
  return true;
 }
};
uint32_t host(void* opaque,uint32_t op,uint64_t a,uint64_t b,uint64_t* out) noexcept{
 if(!opaque)return 2;auto&c=*static_cast<Context*>(opaque);
 if(c.busy||c.finished)return 2;
 if(c.pending)return 1;
 c.busy=true;
 struct Busy {Context&c;~Busy(){c.busy=false;}} guard{c};
 try {
  if(!c.outputOK(out))return 2;
  uint64_t r=0;
  switch(op){
   case DS_CONFIG_GET:if(b)return 2;switch(a){case 0:if(!c.order)return 2;r=uint32_t(*c.order);break;case 1:if(!c.term)return 2;r=*c.term;break;case 2:if(!c.version)return 2;r=*c.version;break;case 3:if(!c.rules)return 2;r=c.rules->version();break;case 4:r=CurrentStreamVersion;break;case 5:r=uint32_t(platformByteOrder());break;default:return 2;}break;
   case DS_CONFIG_SET:if(a==0&&c.orderMut&&b<=UINT32_MAX)*c.orderMut=ByteOrder(uint32_t(b));else if(a==1&&c.termMut&&b<=1)*c.termMut=bool(b);else if(a==2&&c.versionMut&&b<=UINT32_MAX)*c.versionMut=unsigned(b);else return 2;break;
   case DS_ARGUMENT:if(a||b)return 2;r=c.argument;break;
   case DS_RESULT:if(a)return 2;c.result=b;break;
   case DS_SCALAR_IO:if(a>1||b||!c.mut||!c.scalar||!c.width)return 2;if(a)c.mut->writeData(static_cast<char*>(c.scalar),c.width);else c.mut->readData(static_cast<char*>(c.scalar),c.width);break;
   case DS_CONVERT:if(b||a>UINT32_MAX||!c.convert||!c.scalar)return 2;c.convert(c.scalar,ByteOrder(uint32_t(a)));break;
   case DS_BOOL_ASSIGN:if(a||b||!c.boolOut)return 2;*c.boolOut=bool(c.byte);break;
   case DS_SIZE:if(a||b)return 2;if(c.kind==Kind::Array&&c.array)r=c.array->size();else if(c.kind==Kind::Raw)r=c.length;else return 2;break;
   case DS_CAPTURE:if(a||b)return 2;
    if(c.kind==Kind::Array&&c.array){c.view=c.array->ptr();c.length=c.array->size();c.writeView=c.arrayMut?c.arrayMut->ptr():nullptr;}
    else if(c.kind==Kind::Std&&c.stdstr){c.view=c.stdstr->c_str();c.length=c.stdstr->size();c.writeView=c.stdMut?&(*c.stdMut)[0]:nullptr;}
    else if(c.kind==Kind::String&&c.str){c.view=c.str->utf8Ptr();c.length=c.str->utf8Size();}
    else if(c.kind==Kind::Cstr&&c.cstr){c.view=c.cstr;c.length=std::strlen(c.cstr);}
    else return 2;
    c.captured=true;r=c.length;break;
   case DS_VIEW_IO:if(a>1||b||!c.captured||!c.mut)return 2;if(a)c.mut->writeData(c.view,c.length);else {if(c.length&&!c.writeView)return 2;c.mut->readData(c.writeView,c.length);}break;
   case DS_RESIZE:if(a||b>SIZE_MAX)return 2;if(c.arrayMut)c.arrayMut->resize(size_t(b));else if(c.stdMut)c.stdMut->resize(size_t(b));else return 2;c.captured=false;break;
   case DS_CLEAR:if(a||b||!c.stdMut)return 2;c.stdMut->clear();c.captured=false;break;
   case DS_APPEND:if(a||b>255||!c.stdMut)return 2;c.stdMut->push_back(char(b));c.captured=false;break;
   case DS_CHAR_READ:if(a||b||!c.mut)return 2;c.mut->readData(reinterpret_cast<char*>(&c.byte),1);r=c.byte;break;
   case DS_CHILD:if(!c.mut)return 2;switch(a){
    case 0:r=c.mut->writeVlqU(b);break;
    case 1:if(b)return 2;r=c.mut->readVlqU();break;
    case 2:if(b||!c.privateWrite||!c.captured)return 2;c.privateWrite(c);break;
    case 3:if(b||!c.temp)return 2;*c.mut>>*c.temp;break;
    case 4:if(b>255)return 2;*c.mut<<uint8_t(b);break;
    case 5:if(b||!c.uout)return 2;r=c.mut->readVlqU(*c.uout);c.uReady=true;break;
    case 6:if(b||!c.iout)return 2;r=c.mut->readVlqI(*c.iout);c.iReady=true;break;
    case 7:if(b||!c.sout)return 2;r=c.mut->readVlqS(*c.sout);c.sReady=true;break;
    default:return 2;}break;
   case DS_VLQ:if(a>3||(a>=2&&b)||!c.mut)return 2;
    if(a==0)r=Star::writeVlqU(b,makeFunctionOutputIterator([&](uint8_t x){*c.mut<<x;}));
    else if(a==1){int64_t x;std::memcpy(&x,&b,8);r=Star::writeVlqI(x,makeFunctionOutputIterator([&](uint8_t x){*c.mut<<x;}));}
    else if(a==2&&c.uout)r=Star::readVlqU(*c.uout,makeFunctionInputIterator([&](){return c.mut->read<uint8_t>();}));
    else if(a==3&&c.iout)r=Star::readVlqI(*c.iout,makeFunctionInputIterator([&](){return c.mut->read<uint8_t>();}));
    else return 2;break;
   case DS_VLQ_VALUE:if(b)return 2;if(a==0&&c.uout&&c.uReady)r=*c.uout;else if(a==1&&c.iout&&c.iReady)std::memcpy(&r,c.iout,8);else if(a==2&&c.sout&&c.sReady)r=*c.sout;else return 2;break;
   case DS_ASSIGN_SIZE:if(a||!c.sout)return 2;*c.sout=size_t(b);break;
   case DS_ASSIGN_STRING:if(a||b||!c.strMut||!c.temp)return 2;*c.strMut=std::move(*c.temp);break;
   case DS_RAISE_VLQ:if(a||b)return 2;throw DataStreamException("Error reading VLQ encoded integer!");
   case DS_FINISH:if(a||b)return 2;c.finished=true;break;
   default:return 2;
  }
  *out=r;return 0;
 }catch(...){c.pending=std::current_exception();return 1;}
}
void execute(uint32_t mode,Context&c){auto s=data_stream_lab_run(mode,&c,host);if(c.pending)std::rethrow_exception(c.pending);if(s||!c.finished)throw std::runtime_error("DataStream lab protocol failure");}
}
using namespace DataStreamLab;
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
#define DS_WRITE(T,M) DataStream& DataStream::operator<<(T x){DS_CONTEXT;c.bind(x);execute(M,c);return *this;}
DS_WRITE(char,DS_WRITE_CHAR) DS_WRITE(int8_t,DS_WRITE_I8) DS_WRITE(uint8_t,DS_WRITE_U8)
DS_WRITE(int16_t,DS_WRITE_I16) DS_WRITE(uint16_t,DS_WRITE_U16) DS_WRITE(int32_t,DS_WRITE_I32) DS_WRITE(uint32_t,DS_WRITE_U32)
DS_WRITE(int64_t,DS_WRITE_I64) DS_WRITE(uint64_t,DS_WRITE_U64) DS_WRITE(float,DS_WRITE_F32) DS_WRITE(double,DS_WRITE_F64)
DataStream& DataStream::operator>>(bool&x){DS_CONTEXT;c.boolOut=&x;c.bind(c.byte);execute(DS_READ_BOOL,c);return *this;}
#define DS_READ(T,M) DataStream& DataStream::operator>>(T&x){DS_CONTEXT;c.bindRead(x);execute(M,c);return *this;}
DS_READ(char,DS_READ_CHAR) DS_READ(int8_t,DS_READ_I8) DS_READ(uint8_t,DS_READ_U8)
DS_READ(int16_t,DS_READ_I16) DS_READ(uint16_t,DS_READ_U16) DS_READ(int32_t,DS_READ_I32) DS_READ(uint32_t,DS_READ_U32)
DS_READ(int64_t,DS_READ_I64) DS_READ(uint64_t,DS_READ_U64) DS_READ(float,DS_READ_F32) DS_READ(double,DS_READ_F64)
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
