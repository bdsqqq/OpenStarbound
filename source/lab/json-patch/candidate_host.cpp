#include "host_contract.cpp"
extern "C" uint32_t star_json_patch_run(uint32_t, StarJsonPatchHost, void*, uint64_t*);
static uint32_t rust_run(uint32_t entry, JsonPatchHostLab::Context& c, uint64_t* out) noexcept {return star_json_patch_run(entry,JsonPatchHostLab::host,&c,out);}
#define run rust_run
#include "StarJsonPatch.reference.hpp"
#include <iostream>
#include <vector>
#include <cstdlib>
using namespace Star;
using namespace JsonPatchHostLab;
namespace JsonPatchReference {size_t findJsonMatch(Json const&,Json const&,JsonPath::Pointer&);}
static uint64_t cases=0,checks=0;static std::array<uint64_t,42> coverage{};
static void check(bool b,char const* label){++checks;if(!b){std::cerr<<"COMPARISON "<<label<<" case="<<cases<<"\n";std::exit(1);}}
static std::string typed(Json const&j){std::string s=std::to_string(int(j.type()))+":"+j.repr().utf8();if(j.isType(Json::Type::Array))for(auto const&v:j.toArray())s+="["+typed(v)+"]";if(j.isType(Json::Type::Object))for(auto const&k:j.toObject().keys().sorted())s+="["+k.utf8()+":"+typed(j.get(k))+"]";return s;}
struct Observation {std::string value,error;int category=0;bool operator==(Observation const&o)const{return value==o.value&&error==o.error&&category==o.category;}};
static Observation observe(std::function<Json()> fn){Observation r;try{r.value=typed(fn());}catch(std::exception const&e){r.error=printException(e,false);if(dynamic_cast<JsonPatchTestFail const*>(&e)||dynamic_cast<JsonPatchReference::JsonPatchTestFail const*>(&e))r.category=1;else if(dynamic_cast<JsonPatchException const*>(&e)||dynamic_cast<JsonPatchReference::JsonPatchException const*>(&e))r.category=2;else if(dynamic_cast<JsonException const*>(&e))r.category=3;else r.category=5;}return r;}
static Json reference(int e,Json const&b,Json const&o){using namespace JsonPatchReference;switch(e){case 0:return JsonPatchReference::jsonPatch(b,o.toArray());case 1:return JsonPatchReference::JsonPatching::applyOperation(b,o,Json(999));case 2:{JsonPath::Pointer p("/x");return Json(uint64_t(JsonPatchReference::findJsonMatch(b,o,p)));}case 3:return JsonPatchReference::JsonPatching::applyTestOperation(b,o);case 4:return JsonPatchReference::JsonPatching::applyRemoveOperation(b,o);case 5:return JsonPatchReference::JsonPatching::applyAddOperation(b,o);case 6:return JsonPatchReference::JsonPatching::applyReplaceOperation(b,o);case 7:return JsonPatchReference::JsonPatching::applyMoveOperation(b,o);case 8:return JsonPatchReference::JsonPatching::applyCopyOperation(b,o);default:return JsonPatchReference::JsonPatching::applyMergeOperation(b,o);}}
static Observation test(int e,Json const&b,Json const&o){++cases;auto before=typed(b);Context c;JsonArray patch;JsonPath::Pointer p("/x");if(e==2){c.Searchable=b;c.SearchValue=o;c.ExternalFindPointer=&p;}else{c.B=b;c.Op=o;if(e==0){patch=o.toArray();c.Patch=&patch;}}uint64_t scalar=0xface;
 auto a=observe([&]{auto status=run(e,c,&scalar);if(status==JP_NATIVE_EXCEPTION_PENDING)std::rethrow_exception(c.Pending);check(status==0,"run valid");if(e==2)return Json(scalar);check(scalar==0xface,"non-find scalar unchanged");return *c.Result;});auto r=observe([&]{return reference(e,b,o);});if(!(a==r)){std::cerr<<"entry "<<e<<" base "<<b<<" op "<<o<<"\nactual "<<a.value<<" error "<<a.error<<" cat "<<a.category<<"\nreference "<<r.value<<" error "<<r.error<<" cat "<<r.category<<"\n";}check(a==r,"typed value/full final error/category");check(typed(b)==before,"base immutable");check(!c.traceOverflow,"trace bounded");if(e!=2)check(!c.MatchArray&&!c.Operation&&!c.Value&&!c.To,"lexical release");for(size_t i=0;i<42;++i)coverage[i]+=c.calls[i];return a;}
static void anchor(char const*b,char const*o,char const*v,int e=1){auto r=test(e,Json::parse(b),Json::parse(o));check(!r.category&&r.value==typed(Json::parse(v)),"independent literal");}
int main(int argc,char**){
// These ignored-output operations expose arithmetic-invalid metadata without
// dereferencing the forged pointer: the broken prototype must fail cleanly.
Context spanProbe;spanProbe.B=JsonObject{};JsonArray emptyPatch;spanProbe.Patch=&emptyPatch;
auto overflowing=reinterpret_cast<uint64_t*>(uintptr_t(-8));
check(host(&spanProbe,JP_RESULT_BASE,0,0,0,overflowing)==JP_HOST_ABI_INVALID,"overflowing callback output span");
check(run(JP_PATCH,spanProbe,overflowing)==JP_ABI_INVALID,"overflowing controller scalar span");
anchor("{\"a\":[1,2],\"b\":[]}","{\"op\":\"remove\",\"path\":\"/a\",\"search\":1}","{\"a\":[2],\"b\":[]}");
anchor("{\"a\":[1,2],\"b\":[]}","{\"op\":\"add\",\"path\":\"/a\",\"search\":2,\"value\":9}","{\"a\":[1,9,2],\"b\":[]}");
anchor("{\"a\":[1,2],\"b\":[]}","{\"op\":\"replace\",\"path\":\"/a\",\"search\":2,\"value\":9}","{\"a\":[1,9],\"b\":[]}");
anchor("{\"a\":[1,2],\"b\":[]}","{\"op\":\"move\",\"path\":\"/b/-\",\"from\":\"/a\",\"search\":1}","{\"a\":[2],\"b\":[1]}");
anchor("{\"a\":[1,2],\"b\":[]}","{\"op\":\"copy\",\"path\":\"/b/-\",\"from\":\"/a\",\"search\":1}","{\"a\":[1,2],\"b\":[1]}");
anchor("{\"a\":[{\"x\":1}]}","{\"op\":\"merge\",\"path\":\"/a\",\"search\":{\"x\":1},\"value\":{\"y\":2}}","{\"a\":[{\"x\":1,\"y\":2}]}");
anchor("{\"a\":[{\"x\":1}]}","{\"op\":\"merge\",\"path\":\"/a\",\"value\":null}","{\"a\":[{\"x\":1}]}");
anchor("[[{\"x\":1}]]","[{\"x\":1,\"y\":2}]","1",2);
anchor("{\"x\":[1,2]}","{\"op\":\"move\",\"path\":\"/x/-\",\"from\":\"/x\",\"search\":1}","{\"x\":[2]}");
std::vector<Json> bases,values;for(char const*s:{"null","0","1.0","[]","{}","{\"x\":null}","{\"x\":[1,2,1]}","{\"x\":[{\"a\":1,\"b\":2},{\"a\":1}]}","{\"x\":[[1,2],[1]]}","{\"x\":{\"a\":1},\"y\":2}"})bases.push_back(Json::parse(s));for(char const*s:{"null","0","1","1.0","2","[]","[1]","[1,2]","{}","{\"a\":1}"})values.push_back(Json::parse(s));char const*names[]={"test","remove","add","replace","move","copy","merge"};
for(auto const&b:bases)for(int h=0;h<7;++h)for(char const*path:{"","/x","/x/0","/missing","/~2"})for(auto const&v:values)for(int mode=0;mode<5;++mode){JsonObject fields{{"op",names[h]},{"path",path},{"from","/x"}};if(mode)fields["value"]=v;if(mode>=2)fields["search"]=v;if(mode==3)fields["inverse"]=true;if(mode==4)fields["from"]="/x/0";Json o(fields);test(h+3,b,o);test(1,b,o);test(0,b,JsonArray{o});}
for(auto const&b:bases)for(auto const&v:values)test(2,b,v);
for(auto const&b:bases)for(char const*s:{"{}","{\"op\":\"TEST\"}","{\"op\":1}","{\"op\":\"add\",\"path\":\"bad\"}","{\"op\":\"replace\",\"path\":\"bad\",\"value\":1}","{\"op\":\"test\",\"path\":\"bad\",\"inverse\":true}","{\"op\":\"test\",\"path\":\"/x\",\"inverse\":\"bad\"}","{\"op\":\"test\",\"path\":\"/missing\",\"inverse\":true}"}){auto o=Json::parse(s);test(1,b,o);test(0,b,JsonArray{Json::parse("{\"op\":\"add\",\"path\":\"/prefix\",\"value\":3}"),o});}
test(3,Json::parse("{\"x\\u0000tail\":1}"),Json::parse("{\"path\":\"/x\\u0000tail\",\"inverse\":true}"));test(0,JsonObject{},Json::parse("[]"));
// Leaf-to-expression comparison is compiler-bound. Merge leaves have competing
// missing-value and traversal errors; the other leaves use a traversal error
// with valid typed operands (invalid array/index operands are ABI rejections).
for(uint32_t opcode:{24u,25u,26u,32u,33u}){
 Context c;c.B=JsonObject{};c.To.emplace("/missing/child");c.Searchable=JsonArray{Json(1)};c.Value=Json(9);c.Op=JsonObject{};uint64_t scalar=91;
 auto actual=observe([&]{auto s=host(&c,opcode,0,0,0,&scalar);if(s&&c.Pending)std::rethrow_exception(c.Pending);check(s==0,"leaf status");return *c.Result;});
 Json base=JsonObject{},searchable=JsonArray{Json(1)},value=Json(9),op=JsonObject{};JsonPath::Pointer pointer("/missing/child");
 auto expected=observe([&]{switch(opcode){case 24:return pointer.add(pointer.remove(base),searchable.eraseIndex(0));case 25:return pointer.add(pointer.remove(base),searchable.insert(0,value));case 26:return pointer.add(pointer.remove(base),searchable.set(0,value));case 32:return pointer.add(pointer.remove(base),searchable.set(0,jsonMerge(searchable.get(0),op.get("value"))));default:return pointer.add(pointer.remove(base),jsonMerge(pointer.get(base),op.get("value")));}});
 check(actual==expected,"compound leaf exact expression compiler-bound");check(scalar==91,"failed leaf scalar unchanged");
}
// Fault injection models failures in catch bodies, not actual allocation exhaustion.
for(int fault:{1,2})for(int e:{0,1}){Context c;c.B=JsonObject{};c.Op=Json::parse(fault==1?"{\"op\":\"TEST\"}":"{\"op\":\"add\"}");JsonArray patch{*c.Op};c.Patch=&patch;c.fault=fault;uint64_t scalar=77;check(run(e,c,&scalar)==JP_NATIVE_EXCEPTION_PENDING,"fault pending");check(c.calls[35]==uint64_t(fault==1),"map catch second read");check(c.calls[36]==uint64_t(fault==1?(e==0?1:0):1),"catch body not sibling rerouted");check(c.PendingClass==uint32_t(fault==1?JP_JSON:JP_OTHER),"fault class");check(scalar==77,"failure scalar unchanged");}
// Unknown arguments/fields and invalid transitions reject without semantic work.
Context empty;uint64_t out=42;for(uint32_t op=0;op<42;++op){auto s=host(&empty,op,999,999,999,&out);check(s==JP_HOST_ABI_INVALID&&out==42,"unlisted args rejected");}
check(host(&empty,42,0,0,0,&out)==6,"unknown opcode");check(host(nullptr,0,0,0,0,&out)==6,"null context");check(host(&empty,0,0,0,0,nullptr)==6,"null out");check(host(&empty,0,0,0,0,reinterpret_cast<uint64_t*>(reinterpret_cast<char*>(&out)+1))==6,"misaligned out");check(run(10,empty,&out)==2&&run(0,empty,nullptr)==2,"run ABI");check(host(&empty,37,0,0,0,&out)==6,"no pending recovery");empty.Pending=std::make_exception_ptr(JsonException("pending",false));empty.PendingClass=JP_JSON;empty.B=Json();check(host(&empty,20,0,0,0,&out)==6,"pending forbids ordinary semantic work");check(host(&empty,38,3,1,0,&out)==6,"pending forbids success receipt");check(host(&empty,39,0,0,0,&out)==0&&bool(empty.Pending),"cleanup preserves pending");empty.Pending={};empty.PendingClass=0;check(host(&empty,11,3,0,0,&out)==6,"bad selector");check(host(&empty,19,0,0,0,&out)==6,"missing typed array");JsonArray none;empty.Patch=&none;check(host(&empty,1,0,0,0,&out)==6,"patch bounds");empty.MatchArray=JsonArray{};empty.SearchValue=Json();check(host(&empty,19,0,0,0,&out)==6,"match bounds");
// Known verifier fault: runtime mismatch must be caught, not a compilation error.
if(argc>1){auto r=test(1,JsonObject{},Json::parse("{\"op\":\"add\",\"path\":\"/x\",\"value\":1}"));r.value=typed(Json("wrong handler value"));check(r==observe([&]{return reference(1,JsonObject{},Json::parse("{\"op\":\"add\",\"path\":\"/x\",\"value\":1}"));}),"deliberate wrong typed handler");}
for(size_t i=0;i<coverage.size();++i)check(i==38?coverage[i]==0:coverage[i]>0,"all native opcodes except reserved receipt exercised");std::cout<<"{\"status\":\"PASS\",\"cases\":"<<cases<<",\"checks\":"<<checks<<",\"coverage\":[";for(size_t i=0;i<42;++i)std::cout<<(i?",":"")<<coverage[i];std::cout<<"]}\n";
}
