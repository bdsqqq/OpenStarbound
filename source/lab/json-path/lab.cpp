#include "StarJsonPath.hpp"
#include "StarJsonPath.reference.hpp"
#ifdef STAR_USE_RUST_JSON_PATH
#include "StarRustJsonPath.h"
#endif
#include <iostream>
#include <random>
#include <vector>
#include <thread>
#include <clocale>
#include <fstream>
#include <cstdlib>
using namespace Star;
static uint64_t cases=0,checks=0,digest=14695981039346656037ull;
static std::ofstream stream;
static void check(bool b,char const*w){++checks;if(!b){std::cerr<<"COMPARISON "<<w<<" case="<<cases<<"\n";std::exit(1);}}
static void obs(uint64_t n){for(int i=0;i<8;++i){unsigned char b=(n>>(8*i))&255;digest^=b;digest*=1099511628211ull;if(stream.is_open())stream.put(char(b));}}
static void obs(std::string const&s){obs(s.size());for(unsigned char c:s)obs(uint64_t(c));}
struct Step{int hint;std::string buffer,error;ptrdiff_t offset;bool operator==(Step const&b)const{return hint==b.hint&&buffer==b.buffer&&error==b.error&&offset==b.offset;}};
using Trace=std::vector<Step>;
static Trace parse(bool reference,int kind,std::string const&s,size_t start,size_t finish,bool alias=false){String path(s),input(s),buf("previous");String&buffer=alias?path:buf;auto const&storage=alias?input:path;auto it=storage.begin();for(size_t i=0;i<start;++i)++it;auto end=storage.begin();for(size_t i=0;i<finish;++i)++end;auto base=it.base();Trace t;
 for(size_t count=0;count<s.size()+3;++count){int hint=-1;std::string error;auto prev=it;try{if(reference){auto fn=kind?JsonPathReference::JsonPath::parseQueryPath:JsonPathReference::JsonPath::parsePointer;hint=int(fn(buffer,path,it,end));}else{auto fn=kind?JsonPath::parseQueryPath:JsonPath::parsePointer;hint=int(fn(buffer,path,it,end));}}catch(std::exception const&e){error=printException(e,false);}t.push_back({hint,buffer.utf8(),error,it.base()-base});if(!error.empty()||it==end||it==prev)break;}
 return t;}
static void test(int kind,std::string const&s,size_t start=0,size_t finish=size_t(-1),bool alias=false){++cases;String path(s);if(finish==size_t(-1))finish=path.size();auto a=parse(false,kind,s,start,finish,alias),b=parse(true,kind,s,start,finish,alias);check(a==b,"segment type/buffer/full error/iterator partial state");obs(kind);obs(start);obs(finish);obs(alias);obs(a.size());for(auto const&x:a){obs(uint64_t(x.hint));obs(x.buffer);obs(x.error);obs(uint64_t(x.offset));}}
static void anchor(int kind,std::string const&s,std::vector<std::pair<int,std::string>>const&want){auto t=parse(false,kind,s,0,String(s).size());check(t.size()==want.size(),"literal segment count");for(size_t i=0;i<want.size();++i)check(t[i].hint==want[i].first&&t[i].buffer==want[i].second&&t[i].error.empty(),"independent RFC/legacy literal segment");test(kind,s);}
static void anchors(){
 // RFC 6901 section 5 evaluation examples, plus literal host-specific hints.
 anchor(0,"/foo/0",{{1,"foo"},{0,"0"}});anchor(0,"/",{{1,""}});anchor(0,"/a~1b",{{1,"a/b"}});anchor(0,"/m~0n",{{1,"m~n"}});anchor(0,"/c%d",{{1,"c%d"}});anchor(0,"/e^f",{{1,"e^f"}});anchor(0,"/g|h",{{1,"g|h"}});anchor(0,"/i\\j",{{1,"i\\j"}});anchor(0,"/k\"l",{{1,"k\"l"}});anchor(0,"/ ",{{1," "}});anchor(0,"/~01",{{1,"~1"}});anchor(0,"/-",{{0,"-"}});anchor(0,"/-/x",{{1,"-"},{1,"x"}});
 anchor(1,"foo.bar[4].baz",{{1,"foo"},{1,"bar"},{0,"4"},{1,"baz"}});anchor(1,"[]",{{0,""}});anchor(1,"[00][1].x.",{{0,"00"},{0,"1"},{1,"x"}});anchor(1,"",{{1,""}});
 // what() is a C string and would hide the suffix after an embedded NUL.
 std::string bad("/~2\0tail",8);
 auto failed=parse(false,0,bad,0,String(bad).size());
 check(failed.size()==1&&failed[0].error==std::string("(ParsingException) Invalid escape sequence in Json pointer \"")+bad+"\"","literal full exception bytes include NUL");test(0,bad);
 // Real generic traversal and RFC 6902 add: dependencies are production Json.
 auto doc=Json::parse("{\"foo\":[\"bar\",\"baz\"],\"a/b\":7,\"m~n\":8}");check(JsonPath::Pointer("/foo/0").get(doc)==Json("bar"),"RFC6901 document evaluation");check(doc.query("foo[1]")==Json("baz"),"real Json query");check(JsonPath::Pointer("/a~1b").get(doc)==Json(7),"RFC escaped key");auto added=JsonPath::Pointer("/foo/-").add(doc,Json("qux"));check(added.query("foo[2]")==Json("qux"),"RFC6902 array append");check(JsonPath::Pointer("").get(doc)==doc&&doc.query("")==doc,"empty traversal identity");check(JsonPath::Pointer("/foo/0").remove(doc).query("foo[0]")==Json("baz"),"real remove");
}
#ifdef STAR_USE_RUST_JSON_PATH
struct Host{String input,buffer;String::const_iterator it,end;std::vector<uint32_t>ops;int abort=-1;bool nested=false;Host(char const*s):input(s),it(input.begin()),end(input.end()) {}};
static int32_t host(void*p,uint32_t op,uint32_t arg,uint32_t*out){auto&h=*static_cast<Host*>(p);h.ops.push_back(op);if(int(h.ops.size())-1==h.abort)return 1;if(h.nested){h.nested=false;Host n("/x");uint32_t t=99,e=99;check(star_json_path_parse(0,host,&n,&t,&e)==0&&t==1&&e==0,"reentrant host");}switch(op){case 0:h.buffer.clear();break;case 1:*out=h.it==h.end;break;case 2:*out=*h.it;break;case 3:++h.it;break;case 4:h.buffer.append(*h.it++);break;case 5:h.buffer.append(Utf32Type(arg));break;case 6:*out=maybeLexicalCast<size_t>(h.buffer).isValid();break;case 7:*out=h.buffer=="-";break;default:return 1;}return 0;}
static int32_t nullhost(void*,uint32_t op,uint32_t,uint32_t*out){if(op==2)*out='.';else *out=0;return 0;}
static void abi(){
 struct Sequence{uint32_t kind;char const*input;std::vector<uint32_t>ops;uint32_t hint,error;};
 for(auto const&s:std::vector<Sequence>{
  {0,"",{0,2},99,1},
  {1,"",{0,2,2,1,1},1,0},
  {0,"/0",{0,2,3,1,2,2,4,1,6},0,0},
  {0,"/-",{0,2,3,1,2,2,4,1,6,7,1},0,0},
  {0,"/~0",{0,2,3,1,2,2,3,1,2,5,3,1,6,7},1,0},
  {0,"/~1",{0,2,3,1,2,2,3,1,2,2,5,3,1,6,7},1,0},
  {1,"[]",{0,2,2,3,1,2,2,1,2,3,1},0,0},
  {0,"/~",{0,2,3,1,2,2,3,1},99,2},
  {0,"/~2",{0,2,3,1,2,2,3,1,2,2},99,3},
  {1,".",{0,2},99,4},
  {1,"[a",{0,2,2,3,1,2,2,1,2},99,5}}){
   Host h(s.input);uint32_t t=99,e=98;check(star_json_path_parse(s.kind,host,&h,&t,&e)==0&&t==s.hint&&e==s.error&&h.ops==s.ops,"literal full callback ordering grammar outputs");
   for(size_t i=0;i<s.ops.size();++i){Host a(s.input);a.abort=int(i);t=99;e=98;auto before=star_json_path_call_count(s.kind);check(star_json_path_parse(s.kind,host,&a,&t,&e)==1&&t==99&&e==98&&a.ops==std::vector<uint32_t>(s.ops.begin(),s.ops.begin()+i+1),"every literal callback abort prefix");check(star_json_path_call_count(s.kind)==before+1,"abort TLS accounting");}
 }
 for(uint32_t k:{0u,1u}){Host h(k?"a":"/a");uint32_t t=99,e=99;auto before=star_json_path_call_count(k);check(star_json_path_parse(k,host,&h,&t,&e)==0&&t==1&&e==0,"ABI success");check(star_json_path_call_count(k)==before+1,"ABI receipt");auto expected=k?std::vector<uint32_t>{0,2,2,1,2,2,4,1,1}:std::vector<uint32_t>{0,2,3,1,2,2,4,1,6,7};check(h.ops==expected,"exact ordered callback stream");for(size_t i=0;i<h.ops.size();++i){Host a(k?"a":"/a");a.abort=int(i);t=99;e=98;before=star_json_path_call_count(k);check(star_json_path_parse(k,host,&a,&t,&e)==1&&t==99&&e==98&&a.ops.size()==i+1,"all callback aborts outputs untouched");check(star_json_path_call_count(k)==before+1,"abort receipt");}}
 Host h("/a");uint32_t t=99,e=98;auto before=star_json_path_call_count(0);check(star_json_path_parse(2,host,&h,&t,&e)==2&&h.ops.empty()&&t==99&&e==98,"unknown kind validation first");check(star_json_path_parse(0,nullptr,&h,&t,&e)==2,"null callback");check(star_json_path_parse(0,host,&h,nullptr,&e)==2,"null output");check(star_json_path_parse(0,host,&h,&t,&t)==2,"overlap output");check(star_json_path_parse(0,host,&h,reinterpret_cast<uint32_t*>(uintptr_t(-4)),&e)==2,"output address arithmetic overflow");alignas(uint32_t) unsigned char bytes[12]={};check(star_json_path_parse(0,host,&h,reinterpret_cast<uint32_t*>(bytes+1),&e)==2,"unaligned output");check(star_json_path_call_count(0)==before&&h.ops.empty(),"invalid no receipt or callbacks");t=99;e=98;check(star_json_path_parse(1,nullhost,nullptr,&t,&e)==0&&t==99&&e==4,"nullable host context grammar failure preserves hint");h.nested=true;check(star_json_path_parse(0,host,&h,&t,&e)==0,"reentry success");uint64_t child=99;std::thread thr([&]{child=star_json_path_call_count(0)+star_json_path_call_count(1);});thr.join();check(child==0,"TLS receipts");
}
#endif
int main(int argc,char**){if(auto p=std::getenv("LAB_OBSERVATIONS")){stream.open(p,std::ios::binary);check(bool(stream),"open ordered observation stream");}anchors();std::vector<std::string> atoms={"","a","/","~","~0","~1","~2",".","[","]","[]","[0]","[00]","[1].","-","+1","01"," 1","18446744073709551616",std::string("\0",1),"é","😀"};for(int k:{0,1}){for(auto const&a:atoms)for(auto const&b:atoms)for(auto const&c:atoms)test(k,a+b+c);for(auto const&a:atoms){test(k,"/"+a);test(k,"xx"+a,2);if(String(a).size()>1)test(k,a,0,1);}}
 std::mt19937 rng(0x50415448);std::string alphabet="ab/.~[]01239-+ ";for(int k:{0,1})for(int n=0;n<9000;++n){std::string s;for(unsigned i=0,len=rng()%40;i<len;++i)s+=alphabet[rng()%alphabet.size()];test(k,s);}
 // Buffer may alias the diagnostic path, but never invalidate iterator storage.
 // Separate input also exposes errors formatted from a partially changed path.
 test(0,"invalid",0,size_t(-1),true);test(1,".",0,size_t(-1),true);
 test(0,"/a~",0,size_t(-1),true);test(1,"[1x]",0,size_t(-1),true);
 for(char const*locale:{"C","en_US.UTF-8"})if(std::setlocale(LC_ALL,locale)){for(char const*s:{"/00","/+1","/-1","/ 1","/18446744073709551615","/18446744073709551616","[00]","[]"})for(int k:{0,1})test(k,s);}std::setlocale(LC_ALL,"C");
 uint64_t receipt=0;
#ifdef STAR_USE_RUST_JSON_PATH
 abi();receipt=star_json_path_call_count(0)+star_json_path_call_count(1);check(receipt>0&&argc==1,"receipt missing");
#endif
 std::cout<<"{\"cases\":"<<cases<<",\"checks\":"<<checks<<",\"receipts\":"<<receipt<<",\"observation_digest\":\""<<std::hex<<digest<<"\"}\n";
}
