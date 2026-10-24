#include "host_contract.cpp"
#include "StarZSTDCompression.reference.hpp"
#include <array>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
using namespace ZstdLab;
using Star::ByteArray;
static size_t checks=0;
#define CHECK(x) do {++checks; if(!(x)) {std::cerr<<"failure line "<<__LINE__<<": " #x "\n"; std::exit(1);}} while(0)
static std::array<size_t,18> coverage{};
static uint32_t observing(void* p,uint32_t op,uint64_t a,uint64_t b,uint64_t* out) {
  auto s=host(p,op,a,b,out); if(s!=ZC_HOST_INVALID) ++coverage[op]; return s;
}
static void execute(Context& c) {
  invoke(c,observing); CHECK(!c.traceOverflow);
  if(c.mode<2) {
    size_t chunks=0,inputs=0,steps=0;
    for(size_t i=0;i<c.traceSize;++i) {chunks+=c.trace[i]==ZC_STREAM_CHUNK;inputs+=c.trace[i]==ZC_INIT_INPUT;steps+=c.trace[i]==ZC_STEP_COMPRESS || c.trace[i]==ZC_STEP_DECOMPRESS;}
    CHECK(chunks==1);CHECK(inputs==1);CHECK(steps==c.steps);CHECK(steps>=1);
  }
}
static ByteArray one(uint32_t mode,ByteArray const& input) {Context c(mode,input.ptr(),input.size()); execute(c); return std::move(c.result);}
static ByteArray initialized() {ByteArray out(8*1024*1024,char(0x6d)); out.resize(2); out[0]=char(0xaa);out[1]=char(0x55);return out;}
static void safe(Context const& c,ByteArray const& output,char const* old) {CHECK(output.ptr()==old); CHECK(output.size()<=8*1024*1024); CHECK(!c.traceOverflow);}
struct Script {
  uint32_t mode=0; size_t n=0, steps=0, size=2, pos=0, cap=0, consumed=0;
  bool full=false, partial=false, retZeroNotConsumed=false, highError=false, nested=false;
  uint64_t seen=0;
};
static uint32_t scripted(void* p,uint32_t op,uint64_t a,uint64_t b,uint64_t* out) {
  auto& s=*static_cast<Script*>(p); uint64_t v=0; ++s.n;
  if(op==ZC_BEGIN) {CHECK(a==s.mode); if(s.nested) {Script inner;inner.mode=1; CHECK(run(1,scripted,&inner)==0);CHECK(inner.steps==1);}}
  else if(op==ZC_GET) {
    if(a==ZC_OUTPUT_SIZE)v=s.size;
    else if(a==ZC_OUTPUT_POS)v=s.pos;
    else if(a==ZC_OUTPUT_CAPACITY)v=s.cap;
    else if(a==ZC_INPUT_POS)v=s.consumed;
    else if(a==ZC_INPUT_SIZE)v=3;
  } else if(op==ZC_STREAM_CHUNK)v=4;
  else if(op==ZC_RESIZE_STREAM)s.size=a;
  else if(op==ZC_PREPARE_OUT)s.cap=b;
  else if(op==ZC_STEP_COMPRESS || op==ZC_STEP_DECOMPRESS) {
    ++s.steps; s.pos=s.full && s.steps==1?s.cap:1;
    s.consumed=s.retZeroNotConsumed && s.steps==1?1:3;
    v=s.highError?UINT64_C(0xffffffff00000001):(s.partial && s.steps==1?7:0);
  } else if(op==ZC_IS_ERROR) {s.seen=a; v=s.highError;}
  else if(op==ZC_RAISE_CODEC) {CHECK(a==s.seen);return ZC_EXCEPTION;}
  *out=v;return ZC_OK;
}
static uint32_t nestedHost(void* p,uint32_t op,uint64_t a,uint64_t b,uint64_t* out) {
  auto status=observing(p,op,a,b,out);
  if(op==ZC_BEGIN && status==0) {
    // Reentry uses real callback execution, not controller context inspection.
    CHECK(run(static_cast<Context*>(p)->mode,host,p)==ZC_INVALID);
    ByteArray literal("abc",3); auto wire=one(2,literal); CHECK(one(3,wire)==literal);
    CompressionHandle handle; ByteArray output; Context inner(0,"abc",3,&output);inner.compression=handle.value; execute(inner);CHECK(inner.steps>0);
  }
  return status;
}
static uint32_t invalidHost(void*,uint32_t,uint64_t,uint64_t,uint64_t*) {return 99;}
static uint32_t throwingHost(void*,uint32_t,uint64_t,uint64_t,uint64_t*) {throw std::runtime_error("custom callback throw");}
int main() {
  CHECK(run(99,scripted,nullptr)==ZC_INVALID); CHECK(run(0,nullptr,nullptr)==ZC_INVALID);
  CHECK(run(0,invalidHost,nullptr)==ZC_INVALID);CHECK(run(0,throwingHost,nullptr)==ZC_PANIC);
  for(unsigned mode=0;mode<2;++mode) for(unsigned variant=0;variant<4;++variant) {
    Script s;s.mode=mode;s.full=variant==0;s.partial=variant==1;s.retZeroNotConsumed=variant==2;s.nested=variant==3;
    CHECK(run(mode,scripted,&s)==0);
    CHECK(s.steps==((s.full || s.retZeroNotConsumed || (s.partial && mode==0))?2:1));
  }
  {Script wrapping;wrapping.size=SIZE_MAX-2;CHECK(run(0,scripted,&wrapping)==0);CHECK(wrapping.size==SIZE_MAX-1);}
  Script error;error.highError=true;CHECK(run(0,scripted,&error)==ZC_NATIVE_PENDING);CHECK(error.seen==UINT64_C(0xffffffff00000001));CHECK(error.steps==1);
  ByteArray empty; CHECK(one(2,empty).empty());
  ByteArray literal("\x28\xb5\x2f\xfd\x20\x03\x19\x00\x00\x61\x62\x63",12);
  CHECK(one(3,literal)==ByteArray("abc",3));
  for(size_t length: {size_t(1),size_t(3),size_t(131071),size_t(131072),size_t(131073),size_t(500000)}) {
    ByteArray input(length,0); uint64_t seed=123;
    for(size_t i=0;i<length;++i){seed=seed*6364136223846793005ULL+1;input[i]=char(seed>>32);}
    if(length==3) input=ByteArray("A\0B",3);
    auto compressed=one(2,input);
    CHECK(compressed==ZstdReference::ZstdCompression::compress(input,2)); CHECK(one(3,compressed)==input);
    CompressionHandle ch; DecompressionHandle dh;
    ZstdReference::CompressionStream referenceC; ZstdReference::DecompressionStream referenceD;
    size_t offset=0;
    for(size_t split: {size_t(0),length/2,length-length/2}) {
      auto output=initialized(), expected=initialized();auto old=output.ptr();
      Context c(0,input.ptr()+offset,split,&output); c.compression=ch.value; execute(c);safe(c,output,old);
      referenceC.compress(input.ptr()+offset,split,expected); CHECK(output==expected);
      ByteArray decoded=initialized(), refDecoded=initialized(); auto dOld=decoded.ptr();
      Context d(1,output.ptr()+2,output.size()-2,&decoded);d.decompression=dh.value;execute(d);safe(d,decoded,dOld);
      referenceD.decompress(expected.ptr()+2,expected.size()-2,refDecoded);CHECK(decoded==refDecoded);
      offset+=split;
    }
  }
  for(auto pattern: {std::array<size_t,3>{0,1,2},std::array<size_t,3>{1,0,2}}) {
    CompressionHandle ch;ZstdReference::CompressionStream cr;DecompressionHandle dh;ZstdReference::DecompressionStream dr;
    ByteArray input("A\0B",3);size_t offset=0;
    for(size_t n:pattern) {
      auto actual=initialized(),expected=initialized();auto old=actual.ptr();
      Context c(0,input.ptr()+offset,n,&actual);c.compression=ch.value;execute(c);safe(c,actual,old);cr.compress(input.ptr()+offset,n,expected);CHECK(actual==expected);offset+=n;
    }
    offset=0;
    for(size_t n: {pattern[0],pattern[1],pattern[2],size_t(9)}) {
      auto actual=initialized(),expected=initialized();auto old=actual.ptr();
      Context c(1,literal.ptr()+offset,n,&actual);c.decompression=dh.value;execute(c);safe(c,actual,old);dr.decompress(literal.ptr()+offset,n,expected);CHECK(actual==expected);offset+=n;
    }
  }
  // Capacity-stable alias: captured input remains in a genuine live allocation.
  {auto out=initialized();out.resize(3);out[0]='A';out[1]=0;out[2]='B';auto old=out.ptr();CompressionHandle h;
   Context c(0,out.ptr(),3,&out);c.compression=h.value;execute(c);safe(c,out,old);}
  {auto out=initialized();CompressionHandle h;Context c(0,"",0,&out);c.compression=h.value; CHECK(run(0,nestedHost,&c)==0);CHECK(c.steps>=1);}
  // Metadata checks must precede even BEGIN mutation and preserve canaries.
  {Context c(2,"A",1); alignas(8) uint64_t scalar=0x123456789abcdef0ULL;
   CHECK(host(&c,ZC_BEGIN,3,0,&scalar)==2);CHECK(c.phase==Context::Fresh);CHECK(scalar==0x123456789abcdef0ULL);
   CHECK(host(&c,ZC_BEGIN,2,1,&scalar)==2);CHECK(host(&c,18,0,0,&scalar)==2);
   CHECK(host(&c,ZC_BEGIN,2,0,nullptr)==2);
   CHECK(host(&c,ZC_BEGIN,2,0,reinterpret_cast<uint64_t*>(UINTPTR_MAX-7))==2);
   CHECK(host(&c,ZC_BEGIN,2,0,reinterpret_cast<uint64_t*>(&c))==2);
   CHECK(host(&c,ZC_BEGIN,2,0,reinterpret_cast<uint64_t*>(reinterpret_cast<char*>(&scalar)+1))==2);
   for(uint32_t op=0;op<18;++op) {
     CHECK(host(&c,op,0,1,&scalar)==2);CHECK(scalar==0x123456789abcdef0ULL);CHECK(c.phase==Context::Fresh);
   }
   CHECK(c.traceSize==0);CHECK(host(&c,ZC_BEGIN,2,0,&scalar)==0);CHECK(scalar==0);
   for(uint64_t field=0;field<9;++field)CHECK(host(&c,ZC_GET,field,0,&scalar)==0);
   CHECK(host(&c,ZC_GET,9,0,&scalar)==2);
   CHECK(host(&c,ZC_GET,0,1,&scalar)==2); CHECK(host(&c,ZC_STEP_COMPRESS,0,0,&scalar)==2);
  }
  // Native full-width error code, exact exception_ptr and sticky pending.
  {auto out=initialized();auto old=out.ptr();DecompressionHandle h;Context c(1,"garbage",7,&out);c.decompression=h.value;
   CHECK(run(1,observing,&c)==1);CHECK(c.pending);CHECK(c.last>UINT32_MAX);safe(c,out,old);
   auto saved=c.pending;uint64_t value=77;size_t steps=c.steps;
   CHECK(host(&c,ZC_STEP_DECOMPRESS,0,0,&value)==2);CHECK(value==77);CHECK(c.pending==saved);CHECK(c.steps==steps);
   try {invoke(c);CHECK(false);}catch(...){CHECK(std::current_exception()==saved);}
   // Full bytes are initialized only because the entire backing allocation was filled.
   CHECK(out.size()>2);CHECK(out[0]==char(0xaa));CHECK(out[out.size()-1]==char(0x6d));
  }
  for(auto const& input: {empty,ByteArray("garbage",7),ByteArray("\x28\xb5\x2f\xfd\x00\x00\x19\x00\x00" "abc",12)}) {
    Context c(3,input.ptr(),input.size());CHECK(run(3,observing,&c)==1);CHECK(c.pending);CHECK(c.result.empty());if(input.size()==12)CHECK(c.last==ZSTD_CONTENTSIZE_UNKNOWN);
  }
  // Valid FCS, corrupt block: allocation happens before a native codec exception.
  {ByteArray bad(literal);bad[6]=char(0xff);Context c(3,bad.ptr(),bad.size());CHECK(run(3,observing,&c)==1);CHECK(c.pending);}
  // Counterfactual resize failure AFTER a real step (not an OOM claim).
  {CompressionHandle h;auto output=initialized();auto old=output.ptr();Context c(0,"abc",3,&output);c.compression=h.value;
   try{throw std::runtime_error("counterfactual resize sentinel");}catch(...){c.resizeFault=std::current_exception();}
   c.faultAfter=1;CHECK(run(0,observing,&c)==1);CHECK(c.steps==1);CHECK(c.pending==c.resizeFault);safe(c,output,old);CHECK(output.size()==2+ZSTD_CStreamOutSize());
   uint64_t value=99;CHECK(host(&c,ZC_STEP_COMPRESS,0,0,&value)==2);CHECK(c.steps==1);CHECK(value==99);
   try{invoke(c);CHECK(false);}catch(...){CHECK(std::current_exception()==c.resizeFault);}
   ByteArray later;Context next(0,"def",3,&later);next.compression=h.value;execute(next);CHECK(next.steps>0);
   ZstdReference::CompressionStream ref;ByteArray ignored,expected;ref.compress("abc",3,ignored);ref.compress("def",3,expected);CHECK(later==expected);
   CompressionHandle fresh;ByteArray freshOutput;Context first(0,"def",3,&freshOutput);first.compression=fresh.value;execute(first);CHECK(later!=freshOutput);
  }
  // Persistent decompression errors and subsequent calls retain native state.
  {DecompressionHandle h;ZstdReference::DecompressionStream ref;
   for(auto const& input: {ByteArray("garbage",7),literal,empty,literal}) {
     auto actual=initialized(),expected=initialized();auto old=actual.ptr(),refOld=expected.ptr();
     Context c(1,input.ptr(),input.size(),&actual);c.decompression=h.value;
     std::string candidateError,referenceError;
     try {execute(c);}catch(std::exception const& e){candidateError=e.what();}
     try {ref.decompress(input,expected);}catch(std::exception const& e){referenceError=e.what();}
     safe(c,actual,old);CHECK(expected.ptr()==refOld);CHECK(expected.size()<=8*1024*1024);
     CHECK(candidateError==referenceError);CHECK(actual==expected);
   }
  }
  {auto actual=initialized();actual.resize(literal.size());std::memcpy(actual.ptr(),literal.ptr(),literal.size());auto expected=initialized();expected.resize(literal.size());std::memcpy(expected.ptr(),literal.ptr(),literal.size());
   auto old=actual.ptr();DecompressionHandle h;ZstdReference::DecompressionStream ref;
   Context c(1,actual.ptr(),actual.size(),&actual);c.decompression=h.value;execute(c);safe(c,actual,old);
   ref.decompress(expected.ptr(),expected.size(),expected);CHECK(actual==expected);
  }
  // Failed one-shot publication leaves the prior destination unchanged.
  {ByteArray destination("prior",5);try{destination=oneShot(3,"garbage",7);CHECK(false);}catch(...){}CHECK(destination==ByteArray("prior",5));}
  for(size_t i=0;i<18;++i){CHECK(coverage[i]>0);std::cout<<"op "<<i<<" "<<coverage[i]<<"\n";}
  std::cout<<"PASS checks="<<checks<<"; finite prototype only; scripted ret>0/nonfull/consumed is COUNTERFACTUAL, not observed vendor defect\n";
}
