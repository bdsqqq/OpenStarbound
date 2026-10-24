// Standalone lab implementation inclusion exposes ONLY lab-private context to
// adversarial tests, not private production members or an alternate class layout.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "host_contract.cpp"
#include <cassert>
#include <iostream>
#include <sstream>
#include <vector>
using namespace Star;
namespace {
struct Script { std::vector<uint32_t> ops;uint64_t answer=0;uint32_t fail=0; };
uint32_t custom(void* p,uint32_t op,uint64_t a,uint64_t b,uint64_t* out) {
 if(!p){if(op==HA_READ_MODE){*out=0;return 0;}if(op==HA_SCALAR_RESULT){assert(a==4&&b==0);*out=0;return 0;}if(op==HA_FINISH){*out=0;return 0;}return 2;}
 auto& s=*static_cast<Script*>(p);s.ops.push_back(op);if(s.fail)return s.fail;
 if(op==HA_READ_MODE){assert(a==0&&b==0);*out=1;return 0;}
 if(op==HA_READ_BYTE){assert(a==0&&b<16);*out=b;return 0;}
 if(op==HA_SCALAR_RESULT){assert(b==0);s.answer=a;*out=0;return 0;}
 if(op==HA_FINISH){assert(a==0&&b==0);*out=0;return 0;}
 return 2;
}
uint32_t cppThrow(void*,uint32_t,uint64_t,uint64_t,uint64_t*){throw 17;}
}
int main(){
 assert(star_host_address_lab_run(HA_SIZE,nullptr,custom)==HA_OK);
 Script s;assert(star_host_address_lab_run(HA_HASH,&s,custom)==HA_OK);uint64_t h=0;for(uint64_t i=0;i<16;++i)h=h*101+i;assert(s.answer==h&&s.ops.back()==HA_FINISH);
 Script invalid;assert(star_host_address_lab_run(27,&invalid,custom)==HA_INVALID&&invalid.ops.empty());assert(star_host_address_lab_run(0,nullptr,nullptr)==HA_INVALID);
 for(auto x:{1u,2u,3u,99u}){Script f;f.fail=x;assert(star_host_address_lab_run(HA_SIZE,&f,custom)==(x==1?HA_PENDING:HA_INVALID));assert(f.ops.size()==1);}
 // C++-only containment test. This is NOT permission for foreign unwinding over
 // a future Rust ABI.
 assert(star_host_address_lab_run(HA_SIZE,nullptr,cppThrow)==HA_PANIC);
 NetworkMode m=NetworkMode::IPv6;Context c(HA_MODE);c.fieldMode=&m;alignas(8)uint64_t out=0xfeedface;
 assert(Context::callback(nullptr,HA_READ_MODE,0,0,&out)==HA_INVALID&&out==0xfeedface);
 assert(Context::callback(&c,HA_READ_MODE,0,1,&out)==HA_INVALID&&out==0xfeedface);
 assert(Context::callback(&c,HA_READ_MODE,0,0,reinterpret_cast<uint64_t*>(reinterpret_cast<uintptr_t>(&out)+1))==HA_INVALID);
 assert(Context::callback(&c,HA_READ_MODE,0,0,reinterpret_cast<uint64_t*>(UINTPTR_MAX-3))==HA_INVALID);
 assert(Context::callback(&c,HA_READ_MODE,0,0,reinterpret_cast<uint64_t*>(UINTPTR_MAX-7))==HA_INVALID);
 assert(Context::callback(&c,HA_READ_MODE,0,0,&c.scalar)==HA_INVALID);
 assert(Context::callback(&c,HA_INSERT_COLON,0,0,&out)==HA_INVALID);
 c.busy=true;assert(Context::callback(&c,HA_READ_MODE,0,0,&out)==HA_INVALID);c.busy=false;
 assert(Context::callback(&c,HA_READ_MODE,0,0,&out)==HA_OK&&out==1);
 assert(Context::callback(&c,HA_FINISH,0,0,&out)==HA_INVALID);
 assert(Context::callback(&c,HA_SCALAR_RESULT,1,0,&out)==HA_OK);
 assert(Context::callback(&c,HA_FINISH,0,0,&out)==HA_OK);
 assert(Context::callback(&c,HA_READ_MODE,0,0,&out)==HA_INVALID);
 Context life(HA_SET_STRING);out=99;
 for(auto op:{HA_RESOLVER_HAS,HA_RESOLVER_FAMILY,HA_RESOLVER_BYTE,HA_RESOLVER_NEXT,HA_RESOLVER_FREE})assert(Context::callback(&life,op,0,0,&out)==HA_INVALID&&out==99);
 String numeric("127.0.0.1");life.input=&numeric;
 assert(Context::callback(&life,HA_RESOLVE,0,0,&out)==HA_OK&&out==0);
 assert(Context::callback(&life,HA_RESOLVER_FREE,0,0,&out)==HA_OK&&life.result==nullptr&&life.current==nullptr&&life.resolverFreed);
 for(auto op:{HA_RESOLVE,HA_RESOLVER_HAS,HA_RESOLVER_FAMILY,HA_RESOLVER_BYTE,HA_RESOLVER_NEXT,HA_RESOLVER_FREE}){out=99;assert(Context::callback(&life,op,0,0,&out)==HA_INVALID&&out==99);}
 uint8_t raw4[4]={};Context rawContext(HA_SET_RAW);rawContext.raw=raw4;out=99;
 assert(Context::callback(&rawContext,HA_RAW_BYTE,0,4,&out)==HA_INVALID&&out==99);
 Context indexContext(HA_OCTET);indexContext.index=15;
 assert(Context::callback(&indexContext,HA_READ_INDEX,0,0,&out)==HA_OK&&out==15);
 assert(Context::callback(&indexContext,HA_RAW_BYTE,0,UINT64_MAX,&out)==HA_INVALID);
 Context network(HA_LOOKUP);network.pending=std::make_exception_ptr(NetworkException("test"));out=99;
 assert(Context::callback(&network,HA_CONSTRUCT,0,0,&out)==HA_PENDING&&out==99);
 assert(Context::callback(&network,HA_PENDING_NETWORK,0,0,&out)==HA_OK&&out==1&&network.pending);
 assert(Context::callback(&network,HA_CATCH_NETWORK,0,0,&out)==HA_OK&&!network.pending&&network.lookup->isLeft());
 int sentinel=7;Context other(HA_LOOKUP);other.pending=std::make_exception_ptr(&sentinel);auto identity=other.pending;
 assert(Context::callback(&other,HA_PENDING_NETWORK,0,0,&out)==HA_OK&&out==0&&other.pending==identity);
 try{other.run();assert(false);}catch(int* p){assert(p==&sentinel);}
 uint8_t b[16]={127,0,0,1};HostAddress a(NetworkMode::IPv4,b);assert(a.bytes()==a.bytes());assert(a.isLocalHost());auto copied=a;assert(copied==a&&copied.bytes()!=a.bytes());
 for(auto unknown:{2,-1,INT32_MAX}){HostAddress n(static_cast<NetworkMode>(unknown),nullptr);assert(n.size()==0&&!n.isZero()&&!n.isLocalHost()&&Star::hash<HostAddress>()(n)==0);auto copy=n;assert(copy==n);}
 HostAddressWithPort e(a,80);std::ostringstream os;os<<e;assert(os.str()=="127.0.0.1:80");
 std::cout<<"scalar-custom/nullctx/hash/status/preflight/native-pending/identity/copy/unknown PASS\n";
}
