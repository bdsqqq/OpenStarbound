#include "StarRustJsonPatch.h"
#include <array>
#include <vector>
#include <iostream>
#include <cstdlib>
#include <cstdint>
using Counts=std::array<std::array<uint64_t,3>,10>;
static int checks=0;
static void check(bool b,char const*s){++checks;if(!b){std::cerr<<"COMPARISON "<<s<<"\n";std::exit(1);}}
static Counts counts(){Counts c{};for(unsigned i=0;i<10;++i)for(unsigned j=0;j<3;++j)c[i][j]=star_json_patch_call_count(i,j);return c;}
struct Call{uint32_t op,a,b;uint64_t n;bool operator==(Call const&o)const{return op==o.op&&a==o.a&&b==o.b&&n==o.n;}};
struct Host {std::vector<Call> trace;uint32_t fault=99,status=0,secondFault=99,secondStatus=0;bool inverse=false,search=false,array=true,reenter=false;unsigned handler=JP_ADD;};
static uint32_t callback(void*p,uint32_t op,uint32_t a,uint32_t b,uint64_t n,uint64_t*out){
 if(!p){check(op==JP_PATCH_SIZE||op==JP_RESULT_BASE,"null context custom callback");if(op==JP_PATCH_SIZE)*out=0;return 0;}
 auto&h=*static_cast<Host*>(p);h.trace.push_back({op,a,b,n});check(op!=JP_RECEIPT,"Rust owns semantic counters, no receipt callback");
 if(h.reenter){h.reenter=false;uint64_t v=71;check(star_json_patch_run(JP_PATCH,callback,nullptr,&v)==0&&v==71,"reentrant controller");}
 if(op==h.fault)return h.status;if(op==h.secondFault)return h.secondStatus;
 switch(op){case JP_PATCH_SIZE:*out=1;break;case JP_LOOKUP_OPERATION:*out=h.handler;break;case JP_READ_INVERSE:*out=h.inverse;break;case JP_HAS_SEARCH:*out=h.search;break;case JP_READ_OPTIONAL_VALUE:*out=1;break;case JP_OPTIONAL_EQUALS_TEST:*out=1;break;case JP_FIND_IS_ARRAY:*out=h.array;break;case JP_FIND_ARRAY_SIZE:*out=3;break;case JP_FIND_MATCH_AT:*out=n==1;break;case JP_MAKE_FAILURE:return JP_TEST_FAIL;case JP_WRAP_JSON:return JP_JSON;default:break;}return 0;
}
static void delta(Counts const&before,unsigned e,uint64_t a,uint64_t s,uint64_t x){auto after=counts();check(after[e][0]-before[e][0]==a&&after[e][1]-before[e][1]==s&&after[e][2]-before[e][2]==x,"semantic counter delta");}
static void trace(Host const&h,std::initializer_list<unsigned> expected){check(h.trace.size()==expected.size(),"exact host trace length");unsigned i=0;for(auto op:expected){auto c=h.trace[i++];check(c.op==op,"exact lexical host order");if(op!=JP_FIND_MATCH_AT&&op!=JP_MAKE_FAILURE&&op!=JP_WRAP_JSON&&op!=JP_RESULT_SEARCH_ADD)check(c.a==0&&c.b==0&&c.n==0,"unused args zero");}}
int main(int argc,char**argv){
 uint64_t out=0xface;Host h;auto before=counts();
 for(unsigned e=0;e<10;++e){check(star_json_patch_run(e,nullptr,&h,&out)==JP_ABI_INVALID,"null host");check(star_json_patch_run(e,callback,&h,nullptr)==JP_ABI_INVALID,"null scalar");check(star_json_patch_run(e,callback,&h,reinterpret_cast<uint64_t*>(uintptr_t(-8)))==JP_ABI_INVALID,"wrapping scalar span");check(star_json_patch_run(e,callback,&h,reinterpret_cast<uint64_t*>(reinterpret_cast<char*>(&out)+1))==JP_ABI_INVALID,"unaligned scalar");}
 check(star_json_patch_run(10,callback,&h,&out)==JP_ABI_INVALID,"unknown entry");check(counts()==before&&h.trace.empty()&&out==0xface,"preflight zero counters/callbacks/output");check(star_json_patch_call_count(10,0)==0&&star_json_patch_call_count(0,3)==0,"invalid counter query");
 check(star_json_patch_run(JP_PATCH,callback,nullptr,&out)==0&&out==0xface,"opaque null custom context allowed");
 h=Host{};before=counts();check(star_json_patch_run(JP_FIND,callback,&h,&out)==0&&out==2,"find publishes index plus one");trace(h,{16,17,18,19,19,39});check(h.trace[3].n==0&&h.trace[4].n==1,"find zero based indices");delta(before,JP_FIND,1,1,0);
 h=Host{};h.search=true;before=counts();out=0xface;check(star_json_patch_run(JP_PATCH,callback,&h,&out)==0&&out==0xface,"non-find output remains untouched");trace(h,{0,1,3,2,4,5,6,10,11,12,16,17,18,19,19,39,25,40,41,34,20});delta(before,JP_PATCH,1,1,0);delta(before,JP_APPLY,1,1,0);delta(before,JP_ADD,1,1,0);delta(before,JP_FIND,1,1,0);check(h.trace[16].n==1,"search leaf converts once");
 h=Host{};h.fault=JP_GET_TEST_VALUE;h.status=JP_TRAVERSAL;h.inverse=true;before=counts();check(star_json_patch_run(JP_TEST,callback,&h,&out)==0,"inverse traversal recovery");trace(h,{4,6,9,10,13,14,37,20,40});delta(before,JP_TEST,1,1,0);
 h=Host{};h.fault=JP_READ_INVERSE;h.status=JP_TRAVERSAL;before=counts();check(star_json_patch_run(JP_TEST,callback,&h,&out)==1,"setup outside traversal catch");trace(h,{4,6,9,40});delta(before,JP_TEST,1,0,1);
 h=Host{};h.handler=JP_TEST;h.fault=JP_GET_TEST_VALUE;h.status=JP_TRAVERSAL;h.secondFault=JP_MAKE_FAILURE;h.secondStatus=JP_JSON;before=counts();check(star_json_patch_run(JP_APPLY,callback,&h,&out)==1,"catch body new JSON routed to outer apply only");trace(h,{3,2,4,6,9,10,13,14,35,40,41,36});delta(before,JP_TEST,1,0,1);delta(before,JP_APPLY,1,0,1);
 // A wrapping callback itself failing must not re-enter its sibling MAP catch.
 h=Host{};h.fault=JP_LOOKUP_OPERATION;h.status=JP_JSON;h.secondFault=JP_WRAP_JSON;h.secondStatus=JP_MAP;before=counts();check(star_json_patch_run(JP_APPLY,callback,&h,&out)==1,"catch body error exits wrapper");trace(h,{3,2,41,36});delta(before,JP_APPLY,1,0,1);
 h=Host{};h.fault=JP_READ_PATH;h.status=JP_TEST_FAIL;before=counts();check(star_json_patch_run(JP_PATCH,callback,&h,&out)==1,"test fail never JSON wrapped");trace(h,{0,1,3,2,4,40,41});delta(before,JP_PATCH,1,0,1);delta(before,JP_APPLY,1,0,1);delta(before,JP_ADD,1,0,1);
 h=Host{};h.fault=JP_FIND_IS_ARRAY;h.status=JP_HOST_ABI_INVALID;before=counts();check(star_json_patch_run(JP_FIND,callback,&h,&out)==JP_ABI_INVALID&&out==0xface,"host protocol abort no publication");delta(before,JP_FIND,1,0,0);
 h=Host{};h.reenter=true;before=counts();check(star_json_patch_run(JP_ADD,callback,&h,&out)==0,"reentrant TLS has no held borrow");delta(before,JP_ADD,1,1,0);delta(before,JP_PATCH,1,1,0);
 if(argc>1){if(argv[1][0]=='r')delta(before,JP_ADD,0,0,0);else {h.trace[0].op=99;trace(h,{4,5,6,10,22,40});}}
 std::cout<<"{\"status\":\"PASS\",\"checks\":"<<checks<<"}\n";
}
