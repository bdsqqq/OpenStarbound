#include "trace_shim.hpp"
#include <array>
#include <exception>
#include <sstream>
#include <stdexcept>
namespace {
struct Event { uint64_t op,a,b,c,d,e,f; };
std::array<Event,4096> events;
size_t count=0,compressCalls=0,decompressCalls=0;
int selected=0; bool overflow=false,changed=false,faultThisCase=false;
bool processFaultInjected=false; std::exception_ptr fault;
void record(Event e) noexcept {
  if(count==events.size()){overflow=true;return;}
  events[count++]=e;
}
}
void labTraceReset(int mode){
 count=compressCalls=decompressCalls=0;selected=mode;overflow=changed=faultThisCase=false;
}
void labTraceResize(Star::ByteArray& out,size_t size){
 record({0,out.size(),size,out.capacity(),0,0,0});
 if(selected==4 && compressCalls && !processFaultInjected){
  processFaultInjected=faultThisCase=true;
  try{throw std::runtime_error("TRACE_RESIZE_SENTINEL");}catch(...){fault=std::current_exception();}
  std::rethrow_exception(fault);
 }
 out.resize(size);
}
size_t labTraceCompress(ZSTD_CCtx* c,ZSTD_outBuffer* out,ZSTD_inBuffer* in,ZSTD_EndDirective directive){
 ++compressCalls;
 // mode2 is a valid smaller native destination span, chosen for the literal
 // three-byte raw-block flush fixture. It is NOT a natural frozen-controller
 // buffer size. Require the actual codec to produce full/ret0/consumed below.
 bool small=selected==2 && !changed;
 if(small){if(out->size<12)throw std::runtime_error("TRACE fixture capacity");out->size=12;}
 size_t actual=ZSTD_compressStream2(c,out,in,directive),result=actual;
 if(selected==1&&!changed){
  if(actual!=0||out->pos==out->size||in->pos!=in->size)
   throw std::runtime_error("TRACE counterfactual precondition");
  result=1;changed=true; // explicitly counterfactual returned status only
 }
 if(small){
  if(actual!=0||out->pos!=12||in->pos!=in->size)
   throw std::runtime_error("TRACE exact-full fixture not established");
  changed=true;
 }
 record({1,out->size,out->pos,in->pos,in->size,actual,result});
 return result;
}
size_t labTraceDecompress(ZSTD_DCtx* c,ZSTD_outBuffer* out,ZSTD_inBuffer* in){
 // Only the tiny truncated-frame control uses this guard. It exposes extra
 // real steps rather than letting a require-ret0 mutant run forever.
 if(selected==3 && decompressCalls==8)throw std::runtime_error("TRACE_STEP_BUDGET");
 ++decompressCalls;
 size_t result=ZSTD_decompressStream(c,out,in);
 record({2,out->size,out->pos,in->pos,in->size,result,result});return result;
}
void labTraceCaught(){
 if(selected==4 && faultThisCase && std::current_exception()!=fault)
  throw std::runtime_error("TRACE_EXCEPTION_IDENTITY");
}
std::string labTraceSerialize(){
 if(overflow)throw std::runtime_error("TRACE_OVERFLOW");
 if((selected==1||selected==2)&&!changed)throw std::runtime_error("TRACE fixture unused");
 std::ostringstream s;
 for(size_t i=0;i<count;++i){auto e=events[i];s<<e.op<<':'<<e.a<<':'<<e.b<<':'<<e.c<<':'<<e.d<<':'<<e.e<<':'<<e.f<<';';}
 return s.str();
}
