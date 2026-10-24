#include "StarJsonPatch.hpp"
#include "StarJsonPatch.reference.hpp"
#include "StarJsonPath.hpp"
#include <iostream>
#include <fstream>
#include <cstdlib>
#ifdef STAR_USE_RUST_JSON_PATCH
#include "StarRustJsonPatch.h"
#endif
using namespace Star;
namespace Star { size_t findJsonMatch(Json const&,Json const&,JsonPath::Pointer&); }
namespace JsonPatchReference { size_t findJsonMatch(Json const&,Json const&,JsonPath::Pointer&); }
static size_t cases=0,checks=0;static std::ofstream stream;
static void check(bool b,char const*s){++checks;if(!b){std::cerr<<"COMPARISON "<<s<<" case="<<cases<<"\n";std::exit(1);}}
static void obs(std::string const&s){uint64_t n=s.size();for(int i=0;i<8;++i)stream.put(char(n>>(8*i)));stream.write(s.data(),s.size());}
// JSON textual rendering preserves numeric type; recursive type tags guard cases
// where native equality intentionally considers integer and double equivalent.
static std::string typed(Json const&j){std::string s=std::to_string(int(j.type()))+":"+j.repr().utf8();if(j.isType(Json::Type::Array))for(auto const&v:j.toArray())s+="["+typed(v)+"]";if(j.isType(Json::Type::Object))for(auto const&k:j.toObject().keys().sorted())s+="["+k.utf8()+":"+typed(j.get(k))+"]";return s;}
struct Result{std::string value,error;int category=0;bool operator==(Result const&r)const{return value==r.value&&error==r.error&&category==r.category;}};
static Result execute(bool ref,int entry,Json const&b,Json const&o){Result r;try{Json v;
#define CALL(N) (ref?JsonPatchReference::JsonPatching::N(b,o):JsonPatching::N(b,o))
switch(entry){case 0:v=ref?JsonPatchReference::jsonPatch(b,o.toArray()):jsonPatch(b,o.toArray());break;case 1:v=ref?JsonPatchReference::JsonPatching::applyOperation(b,o,Json(999)):JsonPatching::applyOperation(b,o,Json(999));break;case 2:v=CALL(applyTestOperation);break;case 3:v=CALL(applyRemoveOperation);break;case 4:v=CALL(applyAddOperation);break;case 5:v=CALL(applyReplaceOperation);break;case 6:v=CALL(applyMoveOperation);break;case 7:v=CALL(applyCopyOperation);break;case 8:v=CALL(applyMergeOperation);break;case 9:{JsonPath::Pointer p("/x");v=Json(uint64_t(ref?JsonPatchReference::findJsonMatch(b,o,p):findJsonMatch(b,o,p)));break;}}
r.value=typed(v);
}catch(std::exception const&e){r.error=printException(e,false);if(dynamic_cast<JsonPatchTestFail const*>(&e)||dynamic_cast<JsonPatchReference::JsonPatchTestFail const*>(&e))r.category=1;else if(dynamic_cast<JsonPatchException const*>(&e)||dynamic_cast<JsonPatchReference::JsonPatchException const*>(&e))r.category=2;else if(dynamic_cast<JsonException const*>(&e))r.category=3;else if(dynamic_cast<JsonPath::TraversalException const*>(&e))r.category=4;else r.category=5;}
return r;}
static Result test(int entry,Json const&b,Json const&o){++cases;auto before=typed(b);auto opBefore=typed(o);
#ifdef STAR_USE_RUST_JSON_PATCH
 unsigned semantic=entry==9?2:(entry>=2?entry+1:entry);uint64_t counters[3];for(unsigned i=0;i<3;++i)counters[i]=star_json_patch_call_count(semantic,i);
#endif
 auto a=execute(false,entry,b,o),r=execute(true,entry,b,o);check(a==r,"typed value/full final error/category");check(typed(b)==before,"immutable base including failure");check(typed(o)==opBefore,"immutable operation including failure");
#ifdef STAR_USE_RUST_JSON_PATCH
 check(star_json_patch_call_count(semantic,0)==counters[0]+1,"semantic attempt count");check(star_json_patch_call_count(semantic,1)==counters[1]+uint64_t(a.category==0),"semantic success count");check(star_json_patch_call_count(semantic,2)==counters[2]+uint64_t(a.category!=0),"semantic native exception count");
#endif
obs(std::to_string(entry));obs(before);obs(typed(o));obs(a.value);obs(a.error);obs(std::to_string(a.category));return a;}
static void anchor(char const*b,char const*o,char const*v,int entry=1){auto r=test(entry,Json::parse(b),Json::parse(o));check(r.category==0&&r.value==typed(Json::parse(v)),"independent literal expected value and numeric types");}
int main(){auto p=std::getenv("LAB_OBSERVATIONS");check(p!=nullptr,"observation path");stream.open(p,std::ios::binary);check(bool(stream),"stream open");
// RFC 6902 appendix A, anchored independently rather than derived from clone.
anchor("{\"foo\":\"bar\"}","{\"op\":\"add\",\"path\":\"/baz\",\"value\":\"qux\"}","{\"foo\":\"bar\",\"baz\":\"qux\"}");
anchor("{\"foo\":[\"bar\",\"baz\"]}","{\"op\":\"add\",\"path\":\"/foo/1\",\"value\":\"qux\"}","{\"foo\":[\"bar\",\"qux\",\"baz\"]}");
anchor("{\"baz\":\"qux\",\"foo\":\"bar\"}","{\"op\":\"remove\",\"path\":\"/baz\"}","{\"foo\":\"bar\"}");
anchor("{\"foo\":[\"bar\",\"qux\",\"baz\"]}","{\"op\":\"remove\",\"path\":\"/foo/1\"}","{\"foo\":[\"bar\",\"baz\"]}");
anchor("{\"baz\":\"qux\"}","{\"op\":\"replace\",\"path\":\"/baz\",\"value\":\"boo\"}","{\"baz\":\"boo\"}");
anchor("{\"foo\":{\"bar\":\"baz\",\"waldo\":\"fred\"},\"qux\":{\"corge\":\"grault\"}}","{\"op\":\"move\",\"from\":\"/foo/waldo\",\"path\":\"/qux/thud\"}","{\"foo\":{\"bar\":\"baz\"},\"qux\":{\"corge\":\"grault\",\"thud\":\"fred\"}}");
anchor("{\"foo\":[\"all\",\"grass\",\"cows\",\"eat\"]}","{\"op\":\"move\",\"from\":\"/foo/1\",\"path\":\"/foo/3\"}","{\"foo\":[\"all\",\"cows\",\"eat\",\"grass\"]}");
anchor("{\"x\":[1,2,1]}","{\"op\":\"remove\",\"path\":\"/x\",\"search\":1}","{\"x\":[2,1]}");
anchor("{\"x\":[1,2]}","{\"op\":\"move\",\"from\":\"/x\",\"path\":\"/x/-\",\"search\":1}","{\"x\":[2]}");
anchor("{\"x\":{\"a\":1}}","{\"op\":\"merge\",\"path\":\"/x\",\"value\":null}","{\"x\":{\"a\":1}}");
anchor("{\"x\":1}","{\"op\":\"test\",\"path\":\"/x\",\"value\":null}","{\"x\":1}");
anchor("{\"x\":1}","[]","{\"x\":1}",0);
anchor("{\"x\":[[{\"a\":1}]]}","{\"op\":\"remove\",\"path\":\"/x\",\"search\":[{\"a\":1,\"b\":2}]}","{\"x\":[]}");
anchor("{\"x\":1}","{\"op\":\"replace\",\"path\":\"/x\",\"value\":1}","{\"x\":1}");
anchor("{\"x\":[1,2]}","{\"op\":\"add\",\"path\":\"/x\",\"search\":3,\"value\":9}","{\"x\":[1,2]}");
// Full final bytes, not what(): embedded NUL suffix is observable on direct test.
auto nul=test(2,Json::parse("{\"x\\u0000tail\":1}"),Json::parse("{\"path\":\"/x\\u0000tail\",\"inverse\":true}"));check(nul.category==1&&nul.error.find(std::string("\0tail",5))!=std::string::npos,"full final error bytes retain NUL suffix");
auto fail=test(0,Json::parse("{\"x\":1}"),Json::parse("[{\"op\":\"test\",\"path\":\"/x\",\"value\":2}]"));check(fail.category==1,"TestFail is not JsonException and escapes both wrappers");
auto direct=test(4,JsonObject{},JsonObject{}),wrapped=test(1,JsonObject{},Json::parse("{\"op\":\"add\"}"));check(direct.category==3&&wrapped.category==2,"direct handler not wrapped");
std::vector<Json> bases;for(char const*s:{"null","0","1.0","[]","{}","{\"x\":null}","{\"x\":[1,2,1]}","{\"x\":[{\"a\":1,\"b\":2},{\"a\":1}]}","{\"x\":[[1,2],[1]]}","{\"x\":{\"a\":1},\"y\":2}"})bases.push_back(Json::parse(s));
std::vector<Json> values;for(char const*s:{"null","0","1","1.0","2","[]","[1]","[1,2]","{}","{\"a\":1}"})values.push_back(Json::parse(s));
char const* names[]={"test","remove","add","replace","move","copy","merge"};
for(auto const&b:bases)for(int h=0;h<7;++h)for(char const*path:{"","/x","/x/0","/missing","/~2"})for(auto const&v:values)for(int mode=0;mode<5;++mode){JsonObject fields{{"op",names[h]},{"path",path},{"from","/x"}};if(mode!=0)fields["value"]=v;if(mode>=2)fields["search"]=v;if(mode==3)fields["inverse"]=true;if(mode==4)fields["from"]="/x/0";Json op(fields);test(h+2,b,op);test(1,b,op);test(0,b,JsonArray{op});}
for(auto const&b:bases)for(auto const&v:values)test(9,b,v);
for(auto const&b:bases)for(char const*s:{"{}","{\"op\":\"ADD\"}","{\"op\":1}","{\"op\":\"add\",\"path\":1}","{\"op\":\"replace\",\"path\":\"/~2\"}","{\"op\":\"test\",\"path\":\"/~2\",\"inverse\":true}","{\"op\":\"merge\",\"path\":\"/missing\"}","{\"op\":\"test\",\"path\":\"/missing\",\"inverse\":true}"}){auto o=Json::parse(s);test(1,b,o);test(0,b,JsonArray{Json::parse("{\"op\":\"add\",\"path\":\"/prefix\",\"value\":3}"),o});}
stream.close();std::cout<<"{\"cases\":"<<cases<<",\"checks\":"<<checks<<"}\n";
}
