#pragma once
#include "abi.h"
#include <exception>
#include <stdexcept>
#include <cstdint>
#include <limits>
#include <cstddef>
namespace FilePrototype {
struct Context {
 Context* previous;
 std::exception_ptr pending;
 void* payload;
 uint64_t (*leaf)(void*,uint32_t,uint64_t);
 uint32_t operations;
 size_t payloadSize;
 static thread_local Context* active;
 Context(void* p,uint64_t(*f)(void*,uint32_t,uint64_t),uint32_t n,size_t bytes=0):previous(active),payload(p),leaf(f),operations(n),payloadSize(bytes){active=this;}
 ~Context(){active=previous;}
};
inline thread_local Context* Context::active=nullptr;
inline uint32_t host(void* p,uint32_t op,uint64_t a,uint64_t b,uint64_t c,uint64_t* out) noexcept {
 Context* ctx=Context::active;while(ctx&&ctx!=p)ctx=ctx->previous;
 if(!ctx||!out||op>=ctx->operations||b||c)return 2;
 auto address=reinterpret_cast<uintptr_t>(out),start=reinterpret_cast<uintptr_t>(ctx);
 if(address%alignof(uint64_t)||address>std::numeric_limits<uintptr_t>::max()-sizeof(uint64_t))return 2;
 auto overlaps=[&](uintptr_t begin,size_t bytes){return bytes && (begin>std::numeric_limits<uintptr_t>::max()-bytes || (address<begin+bytes&&begin<address+sizeof(uint64_t)));};
 if(overlaps(start,sizeof(Context))||overlaps(reinterpret_cast<uintptr_t>(ctx->payload),ctx->payloadSize))return 2;
 if(ctx->pending)return 1;
 try{auto value=ctx->leaf(ctx->payload,op,a);*out=value;return 0;}
 catch(...){ctx->pending=std::current_exception();return 1;}
}
template<class F> void invoke(uint32_t mode,uint32_t operations,F&& leaf){
 Context ctx(&leaf,[](void* p,uint32_t op,uint64_t a){return (*static_cast<F*>(p))(op,a);},operations,sizeof(F));
 auto status=file_host_run(mode,&ctx,host);
 // Rethrow while the wrapper's native locals are alive; their normal unwind
 // destroys target before source and inner traversal state before the caller.
 if(ctx.pending)std::rethrow_exception(ctx.pending);
 if(status)throw std::runtime_error("file native prototype protocol");
}
}
