#pragma once
#include "StarRustDataStream.h"
#include "StarDataStream.hpp"
#include "StarBytes.hpp"
#include "StarVlqEncoding.hpp"
#include <cstring>
#include <exception>
#include <limits>
#include <stdexcept>

// Native ownership and exception containment; only scalar sequencing crosses Rust.
namespace Star { namespace DataStreamRust {
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
inline uint32_t host(void* opaque,uint32_t op,uint64_t a,uint64_t b,uint64_t* out) noexcept{
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
inline void execute(uint32_t mode,Context&c){auto s=star_data_stream_run(mode,&c,host);if(c.pending)std::rethrow_exception(c.pending);if(s||!c.finished)throw std::runtime_error("DataStream Rust protocol failure");}
}}
