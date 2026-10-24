#include "StarText.hpp"
#include "StarText.reference.hpp"
#include <fstream>
#include <iostream>
#include <vector>
#include <exception>
#include <sys/mman.h>
#include <unistd.h>
#ifdef LAB_RUST
#include "StarRustTextScan.h"
#endif
using Star::StringView;
using Callback=Star::Text::TextCallback;
using Process=bool(*)(StringView,Callback,Callback,bool);
static void check(bool b,char const* m){if(!b)throw std::runtime_error(std::string("COMPARISON ")+m);}
static std::string hex(std::string_view s){static char const d[]="0123456789abcdef";std::string o;for(unsigned char c:s){o+=d[c>>4];o+=d[c&15];}return o;}
struct Event{int kind;size_t offset;std::string bytes;bool operator==(Event const& b)const{return kind==b.kind&&offset==b.offset&&bytes==b.bytes;}};
struct Result{std::vector<Event> events;bool value=false;int exception=0;std::string finalBytes;bool operator==(Result const& b)const{return events==b.events&&value==b.value&&exception==b.exception&&finalBytes==b.finalBytes;}};
static unsigned long cases=0;
static std::ofstream stream;
static std::exception_ptr sentinel;
static Result observe(Process fn,std::string input,bool commands,bool sides,int stop=-1,int throwing=-1,bool emptyText=false,int mutation=0,bool nested=false,bool receipt=false){
 Result r; std::vector<StringView> retained; unsigned long attempts=0,texts=0,cmds=0,nestedCalls=0;
#ifdef LAB_RUST
 uint64_t before[3]={};if(receipt)for(int i=0;i<3;++i)before[i]=star_text_scan_call_count(i);
#endif
 auto cb=[&](int kind,StringView v){++attempts;if(kind)++cmds;else ++texts;auto s=v.utf8();check(s.data()>=input.data()&&s.data()+s.size()<=input.data()+input.size(),"view range");r.events.push_back({kind,size_t(s.data()-input.data()),std::string(s)});retained.push_back(v);
  if(mutation==1&&kind==0&&attempts==1){input[2]='Z';input[3]='!';} // end and command span already selected
  if(mutation==2&&kind==1&&attempts==1){input[3]='^';input[4]='b';input[5]=';';} // next scan must see edits
  if(nested&&attempts==1){++nestedCalls;bool ok=fn(StringView("^n;Q"),[&](StringView x){check(x.utf8()=="Q","nested text");++texts;return true;},[&](StringView x){check(x.utf8()=="n","nested command");++cmds;return true;},false);check(ok,"nested return");}
  if(int(attempts)==throwing)std::rethrow_exception(sentinel);
  return int(attempts)!=stop;
 };
 Callback text=emptyText?Callback():Callback([&](StringView v){return cb(0,v);});
 Callback command=commands?Callback([&](StringView v){return cb(1,v);}):Callback();
 try{r.value=fn(StringView(input.data(),input.size()),text,command,sides);}catch(std::bad_function_call const&){r.exception=1;++texts;}catch(...){check(std::current_exception()==sentinel,"exception_ptr identity");r.exception=2;}
 for(auto v:retained)check(v.utf8().data()>=input.data()&&v.utf8().data()+v.utf8().size()<=input.data()+input.size(),"retained view lifetime");
#ifdef LAB_RUST
 if(receipt){check(star_text_scan_call_count(0)-before[0]==1+nestedCalls,"semantic invocation attempts");check(star_text_scan_call_count(1)-before[1]==texts,"semantic text attempts");check(star_text_scan_call_count(2)-before[2]==cmds,"semantic command attempts");check(star_text_scan_call_count(999)==0,"unknown receipt");}
#endif
 r.finalBytes=input;return r;
}
static void record(Result const& r){stream<<r.value<<':'<<r.exception<<':'<<hex(r.finalBytes)<<'|';for(auto const&e:r.events)stream<<e.kind<<','<<e.offset<<','<<hex(e.bytes)<<';';stream<<'\n';}
static Result test(std::string s,bool cmd=true,bool sides=false,int stop=-1,int throwing=-1,bool empty=false,int mutation=0,bool nested=false){auto ref=observe(TextReference::Text::processText,s,cmd,sides,stop,throwing,empty,mutation,nested);auto got=observe(Star::Text::processText,s,cmd,sides,stop,throwing,empty,mutation,nested,true);check(got==ref,"ordered typed stream / return / exception / mutation");record(ref);++cases;return got;}
static void anchor(std::string s,std::vector<Event> want,bool sides=false){auto r=test(s,true,sides);check(r.events==want&&r.value&&!r.exception,"independent literal anchor");}
struct CopyProbe{std::vector<int>* log;int id;CopyProbe(std::vector<int>*l,int i):log(l),id(i){log->push_back(10+id);}CopyProbe(CopyProbe const&b):log(b.log),id(b.id){log->push_back(20+id);}~CopyProbe(){log->push_back(30+id);}bool operator()(StringView){log->push_back(40+id);return true;}};
static std::vector<int> copies(Process fn){std::vector<int> events;{Callback text=CopyProbe(&events,0),commands=CopyProbe(&events,1);fn(StringView("A^x;B"),text,commands,false);}return events;}
static void guardPages(){size_t page=sysconf(_SC_PAGESIZE);auto p=(char*)mmap(nullptr,page*3,PROT_NONE,MAP_PRIVATE|MAP_ANON,-1,0);check(p!=MAP_FAILED,"mmap");check(mprotect(p+page,page,PROT_READ|PROT_WRITE)==0,"mprotect");for(std::string s:std::vector<std::string>{"","^","^^","^;","^red;T^reset;",std::string("\0\xff^;",4)}){for(int side=0;side<2;++side){char* start=side?p+page:p+2*page-s.size();std::copy(s.begin(),s.end(),start);for(Process fn:{Star::Text::processText,TextReference::Text::processText}){std::string events;bool ok=fn(StringView(start,s.size()),[&](StringView v){events+=hex(v.utf8());return true;},[&](StringView v){events+=hex(v.utf8());return true;},true);check(ok,"guard page return");}}}check(munmap(p,page*3)==0,"munmap");}
int main(){try{sentinel=std::make_exception_ptr(73);char const* path=std::getenv("LAB_OBSERVATIONS");check(path,"observation output required");stream.open(path,std::ios::binary);check(bool(stream),"observation open");
 anchor("A^^red;B^reset;C",{{0,0,"A^"},{1,3,"red"},{0,7,"B"},{1,9,"reset"},{0,15,"C"}});
 anchor("^a^b;",{{0,0,"^a"},{1,3,"b"}});anchor("^;",{});anchor("^;",{{1,0,"^;"}},true);anchor("^^",{{0,0,"^^"}});anchor(std::string("\x1bgreen;G"),{{1,1,"green"},{0,7,"G"}});
 std::vector<std::string> corpus={"","plain","^","^^","^^^","A^","^;","^^;","^a^b;","A^^red;B^reset;C","^red;TEXT^reset;","A^x;tail","^a;123","^a;^b;Z",std::string("\0^\xff;\x80\0",6),std::string("\x1b\x1bX;A\x1b^Y;B")};std::string all;for(int i=0;i<256;++i)all+=char(i);corpus.push_back(all);
 unsigned state=0x328947;for(int n=0;n<400;++n){std::string s;for(int i=0;i<n%80;++i){state=state*1664525+1013904223;unsigned x=state>>24;s+=x<50?"^^;\x1b"[x%4]:char(x);}corpus.push_back(s);}
 for(auto const&s:corpus)for(bool cmd:{false,true})for(bool sides:{false,true}){test(s,cmd,sides);for(int i=1;i<=4;++i){test(s,cmd,sides,i);test(s,cmd,sides,-1,i);}test(s,cmd,sides,-1,-1,true);}
 check(test("A^x;tail",true,false,-1,-1,false,1).events==std::vector<Event>{{0,0,"A"},{1,2,"Z"},{0,4,"tail"}},"independent mutation cached boundary");check(test("^a;123",true,false,-1,-1,false,2).events==std::vector<Event>{{1,1,"a"},{1,4,"b"}},"independent mutation future scan");test("A^x;Z",true,false,-1,-1,false,0,true);guardPages();check(copies(Star::Text::processText)==copies(TextReference::Text::processText),"callback by-value copy destructor order");stream.close();std::cout<<"{\"cases\":"<<cases<<",\"guard_pages\":true,\"status\":\"PASS\"}\n";return 0;
 }catch(std::exception const&e){std::cerr<<e.what()<<'\n';return 1;}}
