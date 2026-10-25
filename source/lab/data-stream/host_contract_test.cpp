// One translation unit exposes the native-only context guards to this fixture.
// No production header is rewritten, and these are the actual member symbols.
#include "host_contract.cpp"
#define main data_stream_frozen_oracle_main
#include "lab.cpp"
#undef main
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <vector>
using namespace Star::DataStreamLab;
namespace {
struct Opaque {std::vector<uint32_t> ops;uint32_t status=0;unsigned chars=0;uint64_t order=0;bool boolMode=false;};
Opaque* nullState=nullptr;
uint32_t opaqueHost(void* ctx,uint32_t op,uint64_t a,uint64_t b,uint64_t*out){
 auto&s=ctx?*static_cast<Opaque*>(ctx):*nullState;s.ops.push_back(op);*out=0;
 if(s.status)return s.status;
 if(op==DS_ARGUMENT&&s.boolMode)*out=1;
 if(op==DS_CHILD&&s.boolMode)assert(a==4&&b==1);
 if(op==DS_CONFIG_GET){*out=a==5?1:a==1?1:s.order;}
 if(op==DS_CHAR_READ)*out=s.chars++==0?'A':0;
 if(op==DS_APPEND)assert(a==0&&b=='A');
 if(op==DS_CONVERT)assert(a==s.order&&b==0);
 if(op==DS_VLQ)*out=UINT64_MAX;
 return 0;
}
uint32_t foreignThrow(void*,uint32_t,uint64_t,uint64_t,uint64_t*){throw std::runtime_error("cpp-only callback throw");}
void protocol(){
 Opaque o;nullState=&o;
 assert(data_stream_lab_run(DS_READ_U32,nullptr,opaqueHost)==0);
 assert((o.ops==std::vector<uint32_t>{DS_SCALAR_IO,DS_CONFIG_GET,DS_CONVERT,DS_FINISH}));
 for(uint64_t order:{uint64_t(1),uint64_t(2)}){o={};o.order=order;assert(data_stream_lab_run(DS_READ_U32,&o,opaqueHost)==0);assert((o.ops==std::vector<uint32_t>{DS_SCALAR_IO,DS_CONFIG_GET,DS_CONVERT,DS_FINISH}));o.ops.clear();assert(data_stream_lab_run(DS_WRITE_U32,&o,opaqueHost)==0);assert((o.ops==std::vector<uint32_t>{DS_CONFIG_GET,DS_CONVERT,DS_SCALAR_IO,DS_FINISH}));}
 o={};assert(data_stream_lab_run(DS_READ_STDSTRING,&o,opaqueHost)==0);
 assert((o.ops==std::vector<uint32_t>{DS_CONFIG_GET,DS_CLEAR,DS_CHAR_READ,DS_APPEND,DS_CHAR_READ,DS_FINISH}));
 o={};o.boolMode=true;assert(data_stream_lab_run(DS_WRITE_BOOL,&o,opaqueHost)==0);assert((o.ops==std::vector<uint32_t>{DS_ARGUMENT,DS_CHILD,DS_FINISH}));
 o={};assert(data_stream_lab_run(99,&o,opaqueHost)==2&&o.ops.empty());
 assert(data_stream_lab_run(0,&o,nullptr)==2&&o.ops.empty());
 o.status=99;assert(data_stream_lab_run(DS_READ_U32,&o,opaqueHost)==2&&o.ops.size()==1);
 o={};o.status=1;assert(data_stream_lab_run(DS_READ_U32,&o,opaqueHost)==1&&o.ops.size()==1);
 o={};assert(data_stream_lab_run(DS_READ_VLQU,&o,opaqueHost)==2);
 assert((o.ops==std::vector<uint32_t>{DS_VLQ,DS_RAISE_VLQ}));
 // This catch exists only in the C++ controller; never future Rust unwind proof.
 assert(data_stream_lab_run(0,nullptr,foreignThrow)==3);
}
void guards(){
 Stream s;Context c(&s);c.mut=&s;uint64_t out=0;uint32_t value=0;c.bind(value);
 assert(host(nullptr,DS_FINISH,0,0,&out)==2);
 assert(host(&c,DS_FINISH,0,0,nullptr)==2);
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(uintptr_t(1)))==2);
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(UINTPTR_MAX-7))==2);
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(&c))==2);
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(&s))==2);
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(&value))==2);
 assert(host(&c,DS_FINISH,0,1,&out)==2&&!c.finished);
 assert(host(&c,DS_CONFIG_GET,99,0,&out)==2);
 ByteOrder order=ByteOrder::BigEndian;c.order=&order;c.orderMut=&order;assert(host(&c,DS_CONFIG_SET,0,uint64_t(UINT32_MAX)+1,&out)==2&&order==ByteOrder::BigEndian);
 assert(host(&c,DS_CHAR_READ,0,1,&out)==2);
 assert(host(&c,DS_SCALAR_IO,2,0,&out)==2);
 assert(host(&c,DS_CONVERT,UINT64_MAX,0,&out)==2);
 uint64_t uninitialized;c.uout=&uninitialized;assert(host(&c,DS_VLQ_VALUE,0,0,&out)==2);c.uout=nullptr;
 assert(host(&c,DS_VLQ_VALUE,3,0,&out)==2);
 assert(host(&c,DS_CHILD,8,0,&out)==2);
 c.busy=true;assert(host(&c,DS_FINISH,0,0,&out)==2);c.busy=false;
 ByteArray a(32,'Q');c.array=&a;c.arrayMut=&a;c.kind=Kind::Array;
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(&a))==2);
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(a.ptr()))==2);
 assert(host(&c,DS_CAPTURE,0,0,&out)==0&&out==32);
 assert(host(&c,DS_APPEND,0,256,&out)==2);
 std::string text(64,'x');c.stdstr=&text;
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(&text))==2);
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(&text[0]))==2);
 String st(std::string(64,'y'));c.str=&st;
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(reinterpret_cast<uintptr_t>(st.utf8Ptr())))==2);
 // A C-string may be backed by live uint64 objects: output aliasing is
 // defined memory access, but must not overwrite current or captured input.
 uint64_t backing[4]{};std::memcpy(backing,"abcdefghijklmnopqrstuvwx",24);
 Context cs(&s);cs.mut=&s;cs.kind=Kind::Cstr;cs.cstr=reinterpret_cast<char const*>(backing);
 assert(host(&cs,DS_FINISH,0,0,backing+1)==2&&!cs.finished);
 assert(host(&cs,DS_CAPTURE,0,0,&out)==0&&out==24);
 reinterpret_cast<char*>(backing)[0]='\0';auto saved=backing[1];
 assert(host(&cs,DS_FINISH,0,0,backing+1)==2&&!cs.finished&&backing[1]==saved);
 std::memset(backing,'Z',sizeof(backing)); // no live terminator after capture
 assert(host(&cs,DS_FINISH,0,0,&out)==0&&cs.finished);
 c.kind=Kind::Raw;c.view=text.data();c.length=text.size();c.captured=true;
 assert(host(&c,DS_FINISH,0,0,reinterpret_cast<uint64_t*>(&text[0]))==2);
 assert(host(&c,DS_FINISH,0,0,&out)==0&&c.finished);
 assert(host(&c,DS_ARGUMENT,0,0,&out)==2);
}
void nativeFailures(){
 Stream s;uint32_t x=0xaabbccdd;s.input="x";s.fail=0;s.partial=1;
 Context c(&s);c.mut=&s;c.bind(x);uint64_t out=0;
 s.hook=[&](bool,char*,size_t){assert(host(&c,DS_FINISH,0,0,&out)==2);s.setByteOrder(ByteOrder::LittleEndian);assert(s.byteOrder()==ByteOrder::LittleEndian);assert(!s.nullTerminatedStrings());};
 assert(host(&c,DS_SCALAR_IO,0,0,&out)==1);
 assert(c.pending==s.injected&&reinterpret_cast<unsigned char*>(&x)[0]=='x');
 auto calls=s.calls;assert(host(&c,DS_FINISH,0,0,&out)==1&&s.calls==calls);
 bool caught=false;try{execute(DS_READ_U32,c);}catch(Fault const&){caught=true;assert(std::current_exception()==s.injected);}assert(caught);
 // Actual member wrappers: fresh order, direct partial mutation, native bool
 // assignment, array pointer reacquisition and failed String temp assignment
 // also have independent literals in the unchanged 683-record oracle.
 Stream r;r.input=std::string("\x12\x34\x56\x78",4);r.flip=true;x=0;r>>x;assert(x==0x78563412);
 Stream f;f.input="x";f.fail=0;f.partial=1;x=0xaabbccdd;auto err=attempt(f,[&]{f>>x;});assert(!err.empty()&&reinterpret_cast<unsigned char*>(&x)[0]=='x');
 Stream b;b.input="\xff";bool flag=false;b>>flag;assert(flag);
 Stream array;ByteArray bytes("a",1);array.hook=[&](bool read,char*,size_t){if(!read&&array.calls==1)bytes=ByteArray("expanded",8);};array<<bytes;assert(array.output==std::string("\x01" "expanded",9));
 Stream str;str.fail=0;str.input="\x03";str.partial=1;String original("old");str.hook=[&](bool,char*,size_t){original=String("callback");};err=attempt(str,[&]{str>>original;});assert(!err.empty()&&original==String("callback"));
}
}
int main(){protocol();guards();nativeFailures();std::cout<<"selected native guards, opaque NULL ctx, controller sequencing, pending identity: PASS\ncpp-only foreign callback containment: PASS (not Rust proof)\n";return 0;}
