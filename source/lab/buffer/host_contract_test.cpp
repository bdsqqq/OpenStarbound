// Compiles alone: actual prototype implementation plus the immutable native
// corpus, renamed only at its entry point. Assertions stay active under -DNDEBUG.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include "host_contract.cpp"
#define main original_native_oracle_main
#include "lab.cpp"
#undef main

namespace {
unsigned nullCalls=0;
uint32_t nullHost(void* p,uint32_t op,uint64_t a,uint64_t b,uint64_t* out){
  assert(!p);assert(!b);++nullCalls;
  if(op==SB_OP_SIZE){assert(!a);*out=0;}
  else if(op==SB_OP_RESULT){assert(a==1);*out=0;}
  else {assert(op==SB_OP_FINISH);assert(!a);*out=0;}
  return 0;
}
uint32_t unknownStatus(void*,uint32_t,uint64_t,uint64_t,uint64_t*){return 99;}
uint32_t contradictoryError(void*,uint32_t op,uint64_t a,uint64_t b,uint64_t*out){assert(op==SB_OP_ERROR&&a==2&&!b);*out=0;return 0;}
uint32_t foreignThrow(void*,uint32_t,uint64_t,uint64_t,uint64_t*){throw std::runtime_error("prototype foreign callback ONLY");}
struct DirectSpy:Buffer {
  std::exception_ptr failure;unsigned resizes=0,seeks=0;
  NativeCtx* active=nullptr;bool sameCtxRejected=false,changeMode=false;
  void modeLeaf(IOMode m){setMode(m);}
  void resize(StreamOffset n)override{
    ++resizes;assert(mode()==(IOMode)14);
    if(active){uint64_t out=0;sameCtxRejected=nativeHost(active,SB_OP_MODE,0,0,&out)==2;}
    if(changeMode)open(IOMode::Read);
    Buffer::resize(n);
    if(failure)std::rethrow_exception(failure);
  }
  void seek(StreamOffset p,IOSeek m=IOSeek::Absolute)override{
    ++seeks;assert(resizes==1);Buffer::seek(p,m);
  }
};
NativeCtx directContext(DirectSpy& owner){
  NativeCtx c;c.owner=&owner;c.constOwner=&owner;c.bytes=&owner.data();c.constBytes=c.bytes;
  c.setMode=+[](NativeCtx& x,IOMode m){static_cast<DirectSpy*>(x.owner)->modeLeaf(m);};
  c.child=+[](NativeCtx& x,uint64_t op,uint64_t v)->uint64_t{
    if(op==7)x.owner->resize(v);
    else if(op==8)x.owner->seek(0,IOSeek::End);
    else throw Stop{2};return 0;
  };return c;
}
void protocolTests(){
  assert(sb_buffer_run(SB_B_EMPTY,nullptr,nullHost)==0&&nullCalls==3);
  assert(sb_buffer_run(50,nullptr,nullHost)==2);
  assert(sb_buffer_run(SB_B_EMPTY,nullptr,nullptr)==2);
  assert(sb_buffer_run(SB_B_EMPTY,nullptr,nativeHost)==2);
  assert(sb_buffer_run(SB_B_EMPTY,nullptr,unknownStatus)==2);
  assert(sb_buffer_run(SB_E_WRITE,nullptr,contradictoryError)==2);
  assert(sb_buffer_run(SB_B_EMPTY,nullptr,foreignThrow)==3); // C++ only, no Rust unwind claim.
  NativeCtx c;uint64_t out=777;
  assert(nativeHost(nullptr,SB_OP_RESULT,0,0,&out)==2);
  assert(nativeHost(&c,SB_OP_RESULT,1,1,&out)==2&&out==777);
  assert(nativeHost(&c,999,0,0,&out)==2);
  assert(nativeHost(&c,SB_OP_ARG,3,0,&out)==2);
  assert(nativeHost(&c,SB_OP_POS,0,0,&out)==2);
  assert(nativeHost(&c,SB_OP_STORAGE,0,0,&out)==2);
  assert(nativeHost(&c,SB_OP_RESULT,0,0,nullptr)==2);
  alignas(uint64_t) unsigned char span[16]={};
  assert(nativeHost(&c,SB_OP_RESULT,0,0,reinterpret_cast<uint64_t*>(span+1))==2);
  assert(nativeHost(&c,SB_OP_RESULT,0,0,reinterpret_cast<uint64_t*>(UINTPTR_MAX-7))==2);
  assert(nativeHost(&c,SB_OP_RESULT,0,0,&c.result)==2);
  c.busy=true;assert(nativeHost(&c,SB_OP_RESULT,0,0,&out)==2);c.busy=false;
  assert(nativeHost(&c,SB_OP_FINISH,0,0,&out)==0);
  assert(nativeHost(&c,SB_OP_RESULT,0,0,&out)==2);
  // Poisoned placement storage exercises actual constructors without assuming
  // zero-filled stack memory. Guards may inspect addresses, never old fields.
  alignas(Buffer) unsigned char bufferStorage[sizeof(Buffer)];
  memset(bufferStorage,0xa5,sizeof bufferStorage);
  auto constructed=new(bufferStorage) Buffer;
  assert(constructed->pos()==0&&constructed->mode()==IOMode::ReadWrite&&constructed->empty());
  constructed->~Buffer();
  alignas(ExternalBuffer) unsigned char externalStorage[sizeof(ExternalBuffer)];
  memset(externalStorage,0xa5,sizeof externalStorage);
  auto extConstructed=new(externalStorage) ExternalBuffer;
  assert(extConstructed->pos()==0&&extConstructed->ptr()==nullptr&&extConstructed->size()==0);
  extConstructed->~ExternalBuffer();
  ExternalBuffer nullBorrow(nullptr,7);assert(nullBorrow.size()==7&&nullBorrow.ptr()==nullptr);
  nullBorrow.reset(nullptr,9);assert(nullBorrow.size()==9&&nullBorrow.read(nullptr,0)==0);
  DirectSpy spy;auto n=directContext(spy);
  assert(nativeHost(&n,SB_OP_SET_MODE,256,0,&out)==2);
  assert(nativeHost(&n,SB_OP_SET_MODE,255,0,&out)==0&&spy.mode()==(IOMode)255);
  assert(nativeHost(&n,SB_OP_RESULT,0,0,reinterpret_cast<uint64_t*>(&spy))==2);
  spy.reset(ByteArray(16,'Q'));
  assert(nativeHost(&n,SB_OP_RESULT,0,0,reinterpret_cast<uint64_t*>(spy.ptr()))==2);
  n.param=n.bytes;
  assert(nativeHost(&n,SB_OP_RESULT,0,0,reinterpret_cast<uint64_t*>(n.param))==2);
  n.param=nullptr;
  n.args[0]=256;assert(sb_buffer_run(SB_B_OPEN,&n,nativeHost)==2);
  n.args[0]=0;n.args[1]=256;size_t pos=0;n.position=&pos;n.constPosition=&pos;
  assert(sb_buffer_run(SB_B_SEEK,&n,nativeHost)==2);
  // Constructor guard receives only addresses until first initialization.
  size_t uninitializedPos,uninitializedSize;char const* uninitializedBorrow;
  NativeCtx ctor;ctor.posReady=false;ctor.extReady=false;
  ctor.position=&uninitializedPos;ctor.constPosition=&uninitializedPos;
  ctor.borrowed=&uninitializedBorrow;ctor.constBorrowed=&uninitializedBorrow;
  ctor.externalSize=&uninitializedSize;ctor.constExternalSize=&uninitializedSize;
  assert(nativeHost(&ctor,SB_OP_SET_POS,0,0,reinterpret_cast<uint64_t*>(&uninitializedPos))==2);
  assert(nativeHost(&ctor,SB_OP_EXTERNAL_INIT,0,0,reinterpret_cast<uint64_t*>(&uninitializedSize))==2);
  assert(nativeHost(&ctor,SB_OP_POS,0,0,&out)==2);
  assert(nativeHost(&ctor,SB_OP_SIZE,0,0,&out)==2);
  assert(nativeHost(&ctor,SB_OP_SET_POS,0,0,&out)==0);
  assert(nativeHost(&ctor,SB_OP_EXTERNAL_INIT,0,0,&out)==0);
  assert(uninitializedPos==0&&uninitializedSize==0&&uninitializedBorrow==nullptr);
  // Native pending captures the same exception object, retains partial mutation,
  // rejects retries, and permits a new context on the same owner.
  DirectSpy failing;failing.reset(ByteArray("abcd",4));
  failing.failure=std::make_exception_ptr(IOException("direct-native-sentinel"));
  void const* expected=nullptr;try{std::rethrow_exception(failing.failure);}catch(IOException const& e){expected=&e;}
  auto failed=directContext(failing);failed.args[0]=14;failing.active=&failed;
  assert(sb_buffer_run(SB_B_OPEN,&failed,nativeHost)==1);
  assert(failed.pending&&!failed.finished&&failing.sameCtxRejected&&failing.resizes==1&&failing.seeks==0);
  assert(failing.mode()==(IOMode)14&&failing.size()==0);
  bool same=false;try{std::rethrow_exception(failed.pending);}catch(IOException const& e){same=&e==expected;}assert(same);
  assert(nativeHost(&failed,SB_OP_SET_MODE,1,0,&out)==1&&failing.mode()==(IOMode)14);
  auto fresh=directContext(failing);assert(nativeHost(&fresh,SB_OP_SET_MODE,1,0,&out)==0);
  DirectSpy reentry;reentry.reset(ByteArray("abcd",4));reentry.changeMode=true;
  auto live=directContext(reentry);live.args[0]=14;reentry.active=&live;
  assert(sb_buffer_run(SB_B_OPEN,&live,nativeHost)==0);
  assert(reentry.sameCtxRejected&&reentry.mode()==IOMode::Read&&reentry.resizes==1&&reentry.seeks==1);
}
void wideReadTests(){
  const auto max=std::numeric_limits<size_t>::max();
  Buffer b(ByteArray("abcdefgh",8));char output[8]{};
  assert(b.read(output,max)==8&&std::memcmp(output,"abcdefgh",8)==0&&b.pos()==8);
  assert(b.read(nullptr,max)==0&&b.readAbsolute(-1,output,max)==0);
  ExternalBuffer e("abcdefgh",8);std::memset(output,0,8);
  assert(e.read(output,max)==8&&std::memcmp(output,"abcdefgh",8)==0);
  assert(e.read(nullptr,max)==0&&e.readAbsolute(-1,output,max)==0);
  char const* input="abcdefgh";ExternalBuffer logical(input,max);
  assert(logical.dataSize()==max&&logical.ptr()==input);
  logical.reset(input,max);assert(logical.read(output,8)==8);
  logical.seek(-1);assert(logical.read(nullptr,max)==0);
}
void copyGuardTests(){
  Buffer b(ByteArray(16,'Q'));b.resize(4);char output[8];std::memset(output,'Z',8);
  NativeCtx c;c.constBytes=&b.data();c.bytes=&b.data();c.output=output;c.args[1]=1;
  uint64_t out=777;
  assert(nativeHost(&c,SB_OP_RESULT,0,0,reinterpret_cast<uint64_t*>(c.bytes))==2);
  assert(nativeHost(&c,SB_OP_COPY_OUT,4,1,&out)==2&&output[0]=='Z'&&out==777);
  assert(nativeHost(&c,SB_OP_COPY_OUT,0,2,&out)==2&&output[0]=='Z');
  assert(nativeHost(&c,SB_OP_COPY_OUT,UINT64_MAX,1,&out)==2);
  char input='X';c.input=&input;auto tail=b.ptr()[4];
  assert(nativeHost(&c,SB_OP_COPY_IN,4,1,&out)==2&&b.ptr()[4]==tail&&b.size()==4);
  assert(nativeHost(&c,SB_OP_COPY_IN,0,2,&out)==2&&b.ptr()[0]=='Q');
  assert(nativeHost(&c,SB_OP_COPY_OUT,0,1,&out)==0&&output[0]=='Q');
  alignas(uint64_t) uint64_t aliased[2]{};c.output=reinterpret_cast<char*>(aliased);c.args[1]=8;
  assert(nativeHost(&c,SB_OP_COPY_OUT,0,4,aliased)==2&&aliased[0]==0);
  alignas(uint64_t) uint64_t borrowed[2]{};char const* view=reinterpret_cast<char const*>(borrowed);size_t size=8;
  NativeCtx external;external.constBorrowed=&view;external.constExternalSize=&size;
  external.output=output;external.args[1]=8;
  assert(nativeHost(&external,SB_OP_COPY_OUT,0,8,borrowed)==2&&borrowed[0]==0);
}
}
int main(){protocolTests();wideReadTests();copyGuardTests();int result=original_native_oracle_main();assert(result==0);std::cerr<<"buffer native protocol assertions passed; immutable 583-record corpus follows on stdout\n";return result;}
