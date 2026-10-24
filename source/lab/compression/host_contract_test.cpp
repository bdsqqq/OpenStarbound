#include "host_contract.cpp"
#include "StarCompression.reference.hpp"
#include <iostream>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <cstring>
using namespace CompressionHostLab;
static size_t checks = 0;
static void require(bool b, char const* why) { ++checks; if (!b) throw std::runtime_error(why); }
static std::string error(std::exception_ptr p) { if (!p) return {}; try { std::rethrow_exception(p); } catch (std::exception const& e) { return Star::printException(e, false); } }
static std::string bytes(ByteArray const& a) { return {a.ptr(), a.size()}; }
static std::string unhex(std::string s) { std::string r; if(s=="-")return r; for(size_t i=0;i<s.size();i+=2)r+=char(std::stoi(s.substr(i,2),nullptr,16));return r; }
static bool covered[16]{};
static void record(NativeContext const& x) { for(size_t i=0;i<x.traceSize;++i)covered[x.trace[i]]=true; }
static void reclaim(NativeContext& x) { if (x.initialized && !x.ended) { if(x.kind==SC_DEFLATE)zng_deflateEnd(&x.stream);else zng_inflateEnd(&x.stream); } }
size_t refAppends=0, refEnds=0, refFault=0;
bool cleanupMutant=false;
std::exception_ptr refInjected;
zng_stream* refStream=nullptr;
uint32_t refKind=SC_INFLATE;
static uint32_t refTrace[4096]{};
static size_t refTraceSize=0;
static bool refTraceValid=true;
static bool suppressStepTrace=false;
static bool forceDeflateStatus=false;
static void refEvent(uint32_t op) noexcept {
  if(refTraceSize==4096) {refTraceValid=false;return;}
  refTrace[refTraceSize++]=op;
}
static void resetRefTrace() noexcept {refTraceSize=0;refTraceValid=true;}
static bool sameCodecTrace(NativeContext const& ctx) noexcept {
  size_t j=0;
  if(!refTraceValid)return false;
  for(size_t i=0;i<ctx.traceSize;++i) {
    auto op=ctx.trace[i];
    if(op!=SC_INIT_CODEC&&op!=SC_STEP_FINISH&&op!=SC_END_CODEC&&op!=SC_APPEND_TEMP)continue;
    if(j==refTraceSize||refTrace[j++]!=op)return false;
  }
  return j==refTraceSize;
}
int labDefInit(zng_stream* s,int level) {refEvent(SC_INIT_CODEC);return zng_deflateInit(s,level);}
int labInfInit(zng_stream* s) {refEvent(SC_INIT_CODEC);return zng_inflateInit(s);}
int labGzipInit(zng_stream* s,int bits) {refEvent(SC_INIT_CODEC);return zng_inflateInit2(s,bits);}
int labDefStep(zng_stream* s,int flush) {if(!suppressStepTrace)refEvent(SC_STEP_FINISH);auto result=zng_deflate(s,flush);return forceDeflateStatus?Z_BUF_ERROR:result;}
int labInfStep(zng_stream* s,int flush) {if(!suppressStepTrace)refEvent(SC_STEP_FINISH);return zng_inflate(s,flush);}
void labAppend(Star::ByteArray& out, char const* p, size_t n) {
  ++refAppends;refEvent(SC_APPEND_TEMP);
  if(refAppends==refFault) {
    if(cleanupMutant) { ++refEnds;refEvent(SC_END_CODEC); if(refKind==SC_DEFLATE)zng_deflateEnd(refStream);else zng_inflateEnd(refStream); }
    std::rethrow_exception(refInjected);
  }
  out.append(p,n);
}
int labDefEnd(zng_stream* s) { ++refEnds;refEvent(SC_END_CODEC); return zng_deflateEnd(s); }
int labInfEnd(zng_stream* s) { ++refEnds;refEvent(SC_END_CODEC); return zng_inflateEnd(s); }
void labBind(zng_stream* s) { refStream=s; }
static void reference(uint32_t k,ByteArray const& in,ByteArray& out,size_t n,int level,size_t limit) {
  if(k==SC_DEFLATE)CompressionReference::compressData(in,out,level);
  else if(k==SC_INFLATE)CompressionReference::uncompressData(in.ptr(),n,out,limit);
  else CompressionReference::uncompressDataGzip(in.ptr(),n,out,limit);
}
static uint32_t calls=0;
static uint32_t badHost(void*,uint32_t,uint64_t,uint64_t*) { ++calls; return 9; }
static uint32_t deflateStatusHost(void* opaque,uint32_t op,uint64_t arg,uint64_t* out) noexcept {
  auto result=nativeHost(opaque,op,arg,out);
  if(result==SC_OK&&op==SC_STEP_FINISH) {
    static_cast<NativeContext*>(opaque)->stepCode=Z_BUF_ERROR;
    *out=uint32_t(Z_BUF_ERROR);
  }
  return result;
}
struct Reentry {
  NativeContext* outer;
  bool entered = false, failed = false;
  uint32_t same = 99, nested = 99;
};
static uint32_t reentryHost(void* opaque,uint32_t op,uint64_t arg,uint64_t* out) noexcept {
  auto& r = *static_cast<Reentry*>(opaque);
  try {
    auto result = nativeHost(r.outer,op,arg,out);
    if (result == SC_OK && op == SC_CLEAR_OUTPUT && !r.entered) {
      r.entered = true;
      auto before = bytes(r.outer->output);
      r.same = run(r.outer->kind,nativeHost,r.outer);
      if (bytes(r.outer->output) != before) r.failed = true;
      ByteArray input("nested",6), output("prior",5);
      NativeContext inner(SC_DEFLATE,input,output,input.size());
      r.nested = run(SC_DEFLATE,nativeHost,&inner);
      if (r.nested != SC_COMPLETE || output != CompressionReference::compressData(input)) r.failed = true;
      record(inner);
    }
    return result;
  } catch (...) { r.failed = true; return SC_HOST_INVALID; }
}
struct Script { uint32_t op; uint64_t value; uint32_t status; };
static Script script[64];static size_t cursor=0,scriptSize=0;
static uint32_t scripted(void*,uint32_t op,uint64_t,uint64_t* out) { require(cursor<scriptSize,"script exhausted");auto s=script[cursor++];require(s.op==op,"script ordering");if(!s.status)*out=s.value;return s.status; }
static void scripts() {
  for(uint32_t op=0;op<16;++op)for(uint32_t status=1;status<=3;++status){
    // Every leaf failure can be reached on one of these three concrete traces.
    for(int path=0;path<4;++path){
      scriptSize=cursor=0;
      auto add=[&](uint32_t o,uint64_t v=0){script[scriptSize++]={o,v,0};};
      add(0);add(1);add(2);add(3);add(4,path==1?uint32_t(-2):0);
      if(path==1)add(13);
      else {add(5);add(6);add(7,path>=2?uint32_t(-3):1);add(8,path==2?0:32763);
        if(path==2){add(9);add(6);add(10,1);add(11,32768);add(12);add(15);}
        else if(path==3){add(12);add(14);}
        else {add(12);add(8,32763);add(9);}}
      bool found=false;for(size_t i=0;i<scriptSize;++i)if(script[i].op==op){script[i].status=status;found=true;break;}
      if(!found)continue;
      require(run(1,scripted,nullptr)==(status==1?1u:2u),"host status transport");
    }
  }
  auto check=[&](std::initializer_list<Script> s){cursor=0;scriptSize=s.size();std::copy(s.begin(),s.end(),script);require(run(1,scripted,nullptr)==SC_INVALID,"protocol contradiction");};
  check({{0,0,0},{1,2,0}});
  check({{0,7,0}});
  check({{0,0,0},{1,0,0},{2,0,0},{3,0,0},{4,1ull<<32,0}});
  check({{0,0,0},{1,0,0},{2,0,0},{3,0,0},{4,uint32_t(-2),0},{13,0,0}});
  check({{0,0,0},{1,0,0},{2,0,0},{3,0,0},{4,0,0},{5,0,0},{6,0,0},{7,1,0},{8,32769,0}});
}
int main(int argc,char**argv) {try {
  bool known=argc>2 && std::string(argv[2])=="--known-fault";
  suppressStepTrace=argc>2 && std::string(argv[2])=="--known-missing-step";
  require(run(3,badHost,nullptr)==2 && !calls,"unknown kind preflight");
  require(run(0,nullptr,nullptr)==2 && !calls,"missing host preflight");
  require(run(0,badHost,nullptr)==2 && calls==1,"bad status");
  require(run(0,nativeHost,nullptr)==2,"null native"); scripts();
  ByteArray input("x",1), output("sentinel",8);NativeContext x(1,input,output,1);alignas(8) uint64_t scalar=0xface;
  auto invalid=[&](uint32_t op,uint64_t arg,uint64_t* p){auto before=bytes(output);auto phase=x.phase;auto trace=x.traceSize;require(nativeHost(&x,op,arg,p)==2,"native invalid");require(bytes(output)==before && x.phase==phase && x.traceSize==trace,"invalid mutation");require(scalar==0xface,"scalar canary");};
  invalid(99,0,&scalar);invalid(0,0,&scalar);invalid(0,1,nullptr);
  invalid(0,1,reinterpret_cast<uint64_t*>(UINTPTR_MAX-7));
  invalid(0,1,reinterpret_cast<uint64_t*>(reinterpret_cast<uintptr_t>(&x)+8));
  invalid(0,1,reinterpret_cast<uint64_t*>(reinterpret_cast<uintptr_t>(&scalar)+1));
  for(uint32_t op=1;op<16;++op)invalid(op,0,&scalar);
  x.callback=true;invalid(0,1,&scalar);require(run(1,nativeHost,&x)==2,"same active native callback reentry");x.callback=false;
  // Every otherwise-unused argument must fail before output/scalar mutation.
  for(uint32_t op=1;op<16;++op) if(op!=9 && op!=13 && op!=14) invalid(op,1,&scalar);
  invalid(13,1ull<<32,&scalar);invalid(14,1ull<<32,&scalar);invalid(9,32769,&scalar);
  NativeContext other(0,input,output,1);require(run(0,nativeHost,&other)==0,"separate context permitted");record(other);
  ByteArray outerInput("outer",5), outerOutput("prior",5);
  NativeContext outer(SC_DEFLATE,outerInput,outerOutput,outerInput.size());
  Reentry reentry{&outer};
  require(run(SC_DEFLATE,reentryHost,&reentry)==SC_COMPLETE,"actual nested callback completed");
  require(reentry.entered&&!reentry.failed&&reentry.same==SC_INVALID&&reentry.nested==SC_COMPLETE,"actual same/separate context reentry");
  require(outerOutput==CompressionReference::compressData(outerInput),"outer context survives reentry");record(outer);
  std::ifstream file(argv[1]);require(bool(file),"fixtures");std::string line;size_t cases=0;
  while(std::getline(file,line)) {
    std::istringstream row(line);std::string id,hex;int k,facade,level,alias;uint64_t len,limit;row>>id>>k>>facade>>level>>alias>>len>>limit>>hex;
    if(facade!=0)continue;
    auto data=unhex(hex);ByteArray a(data.data(),data.size()),b(data.data(),data.size()),oa("sentinel",8),ob("sentinel",8);
    a.reserve(262144);b.reserve(262144);oa.reserve(262144);ob.reserve(262144);
    auto& da=alias?a:oa;auto& db=alias?b:ob;
    NativeContext ctx(k,a,da,len,level,limit);auto result=run(k,nativeHost,&ctx);record(ctx);
    std::exception_ptr refError;refFault=0;resetRefTrace();
    try{reference(k,b,db,len,level,limit);}catch(...){refError=std::current_exception();}
    require(result==(refError?1u:0u),"reference status");
    require(error(ctx.pending)==error(refError),"reference full error");
    require(bytes(da)==bytes(db)&&bytes(a)==bytes(b),"reference output/input");
    require(da.capacity()==db.capacity(),"reference capacity");
#ifdef INSTRUMENTED
    require(sameCodecTrace(ctx),"COMPARISON complete codec/append call order");
#endif
    if(ctx.pending){uint64_t canary=42;require(nativeHost(&ctx,0,k,&canary)==2&&canary==42,"pending forbids ordinary operations");}
    if(ctx.ended){uint64_t canary=42;require(nativeHost(&ctx,12,0,&canary)==2&&canary==42,"double end");}
    reclaim(ctx);++cases;
  }
#ifdef INSTRUMENTED
  // Both wrappers call the REAL deflater, then substitute its status. This is
  // a counterfactual error-path/wording anchor, not a naturally observed error.
  {
    ByteArray in("x",1),a("prior",5),b("prior",5);
    NativeContext ctx(SC_DEFLATE,in,a,in.size());
    auto status=run(SC_DEFLATE,deflateStatusHost,&ctx);record(ctx);
    resetRefTrace();refFault=0;forceDeflateStatus=true;
    std::exception_ptr caught;try{reference(SC_DEFLATE,in,b,in.size(),5,0);}catch(...){caught=std::current_exception();}
    forceDeflateStatus=false;
    require(status==SC_NATIVE_PENDING&&caught,"COMPARISON forced deflate status");
    require(error(ctx.pending)==error(caught),"COMPARISON deflate legacy error wording");
    require(error(ctx.pending)=="(IOException) Internal error in uncompressData, deflate_res is -5","COMPARISON independent deflate typo anchor");
    require(bytes(a)==bytes(b)&&ctx.endCalls==1&&sameCodecTrace(ctx),"COMPARISON forced deflate bytes/End/order");
  }
  // Counterfactual append sentinel: NOT evidence of actual allocator exhaustion.
  for(size_t n:{size_t(5),size_t(32768),size_t(65536)}) for(size_t fault:{size_t(1),size_t(2)}) {
    ByteArray plain;plain.resize(n);auto wire=CompressionReference::compressData(plain,5);
    ByteArray a("prior",5),b("prior",5);auto sentinel=std::make_exception_ptr(std::runtime_error("append sentinel"));
    NativeContext ctx(1,wire,a,wire.size());ctx.faultAppend=fault;ctx.injected=sentinel;
    auto status=run(1,nativeHost,&ctx);record(ctx);
    refAppends=refEnds=0;refFault=fault;refInjected=sentinel;refKind=1;cleanupMutant=known;resetRefTrace();
    std::exception_ptr caught;try{reference(1,wire,b,wire.size(),5,0);}catch(...){caught=std::current_exception();}
    require(status==(caught?1u:0u),"COMPARISON fault status");
    require(ctx.pending==caught,"COMPARISON same exception_ptr");
    require(bytes(a)==bytes(b),"COMPARISON partial output");
    require(ctx.endCalls==refEnds,"COMPARISON cleanup End trace");
    require(sameCodecTrace(ctx),"COMPARISON fault codec/append call order");
    if(caught)require(ctx.pending==sentinel,"same injected pointer");
    reclaim(ctx);
    // Reference stream is stack-owned and no longer live: intentionally leave
    // bounded legacy abandoned streams to process exit, never copy stream state.
    refFault=0;
  }
#else
  require(!known,"known fault requires instrumented executable");
#endif
  // Init raise and codec raise are reached by fixtures; limit raise also covered.
  for(unsigned i=0;i<16;++i)require(covered[i],"opcode coverage");
  std::cout<<"PASS "<<cases<<" native controller cases, "<<checks<<" assertions, all 16 opcodes\n";
  return 0;
}catch(std::exception const& e){std::cerr<<e.what()<<'\n';return 1;}}
