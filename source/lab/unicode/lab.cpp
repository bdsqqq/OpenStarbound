#include "StarUnicode.hpp"
#include "StarUnicode.reference.hpp"
#ifdef STAR_USE_RUST_UNICODE
#include "StarRustUnicode.h"
#endif
#include <array>
#include <cstring>
#include <iostream>
#include <random>
#include <sys/mman.h>
#include <unistd.h>
namespace R = UnicodeReference;
static uint64_t checks=0,cases=0; static bool missingReceipt=false;
static void check(bool b,const char* label){++checks;if(!b){std::cerr<<"COMPARISON "<<label<<" case="<<cases<<"\n";std::exit(1);}}
static uint64_t observation=14695981039346656037ull;
static void observe(uint64_t value){for(unsigned i=0;i<8;++i){observation^=(value>>(i*8))&255;observation*=1099511628211ull;}}
static void observeText(std::string const& s){observe(s.size());for(unsigned char c:s)observe(c);}
template<class F> static std::string outcome(F f){std::string s;try{s="OK:"+f();}catch(std::exception const& e){s=std::string("ERR:")+e.what();}observeText(s);return s;}
static std::string pairText(Star::pair<char32_t,Star::Maybe<char32_t>> p){return std::to_string(uint32_t(p.first))+":"+(p.second?std::to_string(uint32_t(*p.second)):"none");}
static void raw(const char* p,size_t n){++cases;auto valid=Star::isValidUtf8(p,n);auto length=Star::utf8Length(p,n);observe(valid);observe(length);check(valid==R::isValidUtf8(p,n),"validate");check(length==R::utf8Length(p,n),"length");char32_t a=0xdeadbeef,b=a;auto x=Star::utf8DecodeChar(p,&a,n),y=R::utf8DecodeChar(p,&b,n);observe(x);observe(a);check(x==y&&a==b,"decode output and consumption");}
static void encode(uint32_t cp){++cases;for(size_t cap=0;cap<=6;++cap){std::array<char,12>a,b;a.fill(char(0xa5));b=a;auto x=Star::utf8EncodeChar(a.data()+2,cp,cap),y=R::utf8EncodeChar(b.data()+2,cp,cap);observe(x);for(unsigned char byte:a)observe(byte);check(x==y&&a==b,"encode capacity/tail/canary");}char generated[5]={};size_t width=R::utf8EncodeChar(generated,cp,4);raw(generated,width);raw(generated,Star::NPos);check(Star::isUtf16LeadSurrogate(cp)==R::isUtf16LeadSurrogate(cp),"lead predicate");check(Star::isUtf16TrailSurrogate(cp)==R::isUtf16TrailSurrogate(cp),"trail predicate");check(outcome([&]{return pairText(Star::utf32ToUtf16SurrogatePair(cp));})==outcome([&]{return pairText(R::utf32ToUtf16SurrogatePair(cp));}),"pair to/error");}
static void hex(std::string const& s,Star::Maybe<char32_t> prev={}){++cases;check(outcome([&]{return std::to_string(uint32_t(Star::hexStringToUtf32(s,prev)));})==outcome([&]{return std::to_string(uint32_t(R::hexStringToUtf32(s,prev)));}),"hex to/error precedence");}
static void anchors(){
 struct A{std::string bytes;uint32_t cp;size_t used;bool valid;};
 for(auto const& a:std::vector<A>{{"A",65,1,true},{std::string("\0Z",2),0,1,true},{"\xc3\xa9",0xe9,2,true},{"\xf0\x9f\x98\x80",0x1f600,4,true},{"\xed\xa0\x80",0xfffd,1,false},{"\xc0\x80",0xfffd,1,false},{"\xf4\x8f\xbf\xbf",0x10ffff,4,true},{"\xf4\x90\x80\x80",0xfffd,1,false},{"\xf8\x88\x80\x80\x80",0xfffd,1,false},{"\xfc\x84\x80\x80\x80\x80",0xfffd,1,false}}){char32_t c=123;check(Star::utf8DecodeChar(a.bytes.data(),&c,a.bytes.size())==a.used&&uint32_t(c)==a.cp,"literal UTF8 decode");check(Star::isValidUtf8(a.bytes.data(),a.bytes.size())==a.valid,"literal validate");raw(a.bytes.data(),a.bytes.size());}
 char out[8];std::memset(out,0x66,8);check(Star::utf8EncodeChar(out,0x1f600,8)==4&&std::memcmp(out,"\xf0\x9f\x98\x80\x66\x66\x66\x66",8)==0,"literal UTF8 encode");
 check(Star::hexStringToUtf32("D83D")==0xd83d&&Star::hexStringToUtf32("DE00",char32_t(0xd83d))==0x1f600,"literal UTF16 decode");check(Star::hexStringFromUtf32(0x1f600)=="d83dde00","literal UTF16 hex");check(Star::utf32FromUtf16SurrogatePair(0xd83d,0xde00)==0x1f600,"literal pair arithmetic");
 check(Star::utf8Length("A\0Z",3)==3&&Star::utf8Length("A\0Z",Star::NPos)==1,"NUL length policy");
 check(Star::hexStringToUtf32("G1")==1&&Star::hexStringToUtf32("1G")==16&&Star::hexStringToUtf32("123")==0x12,"invalid nibble/odd tail");
 check(outcome([]{return std::to_string(Star::utf32FromUtf16SurrogatePair(0,0));})=="ERR:(UnicodeException) Invalid lead surrogate passed to utf32FromUtf16SurrogatePair","literal lead error precedence");
 check(outcome([]{return std::to_string(Star::utf32FromUtf16SurrogatePair(0xd800,0));})=="ERR:(UnicodeException) Invalid trail surrogate passed to utf32FromUtf16SurrogatePair","literal trail error");
 check(outcome([]{return pairText(Star::utf32ToUtf16SurrogatePair(0x110000));})=="ERR:(UnicodeException) Invalid codepoint passed to utf32ToUtf16SurrogatePair","literal pair codepoint error");
 check(outcome([]{return Star::hexStringFromUtf32(0x110000);})=="ERR:(UnicodeException) Codepoint too big in hexStringFromUtf32","literal hex codepoint error");
 check(outcome([]{return std::to_string(Star::hexStringToUtf32("1234567890",char32_t(0xd800)));})=="ERR:(UnicodeException) Codepoint size is too big in parseUnicodeCodepoint","literal hex size before pair error");
 for(auto n:{size_t(0),size_t(1),Star::NPos}){alignas(char32_t) char32_t a=0,b=0;reinterpret_cast<char*>(&a)[0]=0;reinterpret_cast<char*>(&b)[0]=0;auto x=Star::utf8DecodeChar(reinterpret_cast<char*>(&a),&a,n),y=R::utf8DecodeChar(reinterpret_cast<char*>(&b),&b,n);check(x==y&&a==b,"public input/output alias zero");}
 for(size_t n:{size_t(0),size_t(4),Star::NPos}){alignas(char32_t) char32_t a,b;std::memcpy(&a,"\xf0\x9f\x98\x80",4);b=a;auto x=Star::utf8DecodeChar(reinterpret_cast<char*>(&a),&a,n),y=R::utf8DecodeChar(reinterpret_cast<char*>(&b),&b,n);check(x==y&&a==b,"public input/output alias char32");}
 // Guard-page reads are a positive test. A fault is FAILURE, never a negative pass.
 size_t page=size_t(sysconf(_SC_PAGESIZE));char* mem=static_cast<char*>(mmap(nullptr,page*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0));check(mem!=MAP_FAILED,"mmap");check(mprotect(mem+page,page,PROT_NONE)==0,"mprotect");
 for(std::string s:{std::string("\0",1),std::string("A\0",2),std::string("\xc2\0",2),std::string("\xe0\0",2),std::string("\xf0\0",2),std::string("\xe1\x80\0",3)}){char* p=mem+page-s.size();std::memcpy(p,s.data(),s.size());raw(p,Star::NPos);for(size_t n=0;n<=s.size();++n)raw(p,n);}
 raw(mem+page,0);munmap(mem,page*2);
 std::memset(out,0x66,8);check(Star::utf8EncodeChar(out,65,Star::NPos)==1&&out[0]=='A'&&out[1]==0x66,"huge capacity only actual bytes");
}
#ifdef STAR_USE_RUST_UNICODE
static void abi(){
 auto counted=[](unsigned op,int expect,auto f){std::array<uint64_t,10> before;for(unsigned i=0;i<10;++i)before[i]=star_unicode_call_count(i);check(f()==expect,"ABI status");for(unsigned i=0;i<10;++i)check(star_unicode_call_count(i)==before[i]+((expect==0||expect==4||expect==5||expect==6)&&i==op),"exact public receipt/no helper doublecount");};
 uint32_t a=0x12345678,b=a,c=a;size_t n=987;uint8_t data[8]={0x41,0,0xa5,0xa5,0xa5,0xa5,0xa5,0xa5};
 counted(0,2,[&]{return star_unicode_validate(nullptr,1,&a);});check(a==0x12345678,"invalid ABI unchanged validate");
 counted(1,2,[&]{return star_unicode_length(data,1,nullptr);});
 counted(2,2,[&]{return star_unicode_decode(data,1,nullptr,&n);});check(n==987,"invalid ABI unchanged decode consumption");
 counted(2,0,[&]{return star_unicode_decode(nullptr,0,&a,&n);});check(a==0x12345678&&n==0,"zero decode codepoint unchanged");
 counted(2,0,[&]{return star_unicode_decode(data+1,Star::NPos,&a,&n);});check(a==0x12345678&&n==0,"sentinel decode codepoint unchanged");
 counted(3,0,[&]{return star_unicode_encode(data,0,0x1f600,&n);});check(n==0&&data[0]==0x41,"ABI capacity no partial write");
 counted(3,0,[&]{return star_unicode_encode(data,Star::NPos,65,&n);});check(n==1&&data[1]==0,"ABI huge capacity");
 counted(4,2,[&]{return star_unicode_hex_to(65,0,2,&a);});check(a==0x12345678,"has_previous enum invalid preserves");
 counted(4,5,[&]{return star_unicode_hex_to(65,0xd800,1,&a);});check(a==0x12345678,"hex semantic output unchanged");
 counted(4,0,[&]{return star_unicode_hex_to(65,0xdc00,1,&a);});check(a==65,"nonlead previous ignored");a=0x12345678;
 counted(5,6,[&]{return star_unicode_hex_from(0x110000,&a,&b,&c);});check(a==0x12345678&&b==a&&c==a,"hex from semantic unchanged");
 counted(6,0,[&]{return star_unicode_is_lead(0xd800,&a);});check(a==1,"ABI lead");
 counted(7,0,[&]{return star_unicode_is_trail(0xdc00,&a);});check(a==1,"ABI trail");a=0x12345678;
 counted(8,4,[&]{return star_unicode_pair_from(0,0,&a);});check(a==0x12345678,"pair invalid lead precedence/output");
 counted(8,5,[&]{return star_unicode_pair_from(0xd800,0,&a);});check(a==0x12345678,"pair invalid trail/output");
 counted(9,6,[&]{return star_unicode_pair_to(0x110000,&a,&b,&c);});check(a==0x12345678&&b==a&&c==a,"pair to semantic unchanged");
 counted(9,0,[&]{return star_unicode_pair_to(0xd800,&a,&b,&c);});check(a==0xd800&&b==0&&c==0,"pair unused trail zero including surrogate scalar");
 check(star_unicode_call_count(10)==0&&star_unicode_call_count(0xffffffff)==0,"invalid receipt index");
}
#endif
int main(int argc,char**argv){missingReceipt=argc>1&&std::string(argv[1])=="missing-receipt";anchors();
#ifdef STAR_USE_RUST_UNICODE
abi();
#endif
 for(uint32_t cp=0;cp<=0x110000;++cp)encode(cp);
 for(uint32_t cp:{0u,65u,0xd800u,0xdfffu,0xffffu,0x10000u,0x1f600u,0x10ffffu,0x110000u,0xffffffffu}){check(outcome([&]{return Star::hexStringFromUtf32(cp);})==outcome([&]{return R::hexStringFromUtf32(cp);}),"hex from literal boundaries/errors");}
 std::mt19937 rng(0x554e4943);for(int i=0;i<18000;++i){std::array<char,20> b{};size_t n=rng()%17;for(size_t j=0;j<n;++j)b[j]=char(rng());raw(b.data(),n);raw(b.data(),Star::NPos);}
 for(int i=0;i<1800;++i){std::string s;for(unsigned j=0,n=rng()%12;j<n;++j)s.push_back("0123456789aAbBcCdDeEfFgGZ \0"[rng()%25]);hex(s);hex(s,char32_t(0xd800));uint32_t cp=rng()%0x120000;check(outcome([&]{return Star::hexStringFromUtf32(cp);})==outcome([&]{return R::hexStringFromUtf32(cp);}),"random hex from/error");}
 for(auto const&s:std::vector<std::string>{"","0","00","aBcD","GGGG","123456789","1234567890",std::string("12\0ff",5),"\xc3\xa9","d800","dc00","ffffffff"})for(auto prev:std::vector<Star::Maybe<char32_t>>{{},char32_t(65),char32_t(0xd800),char32_t(0xdbff),char32_t(0xdc00)})hex(s,prev);
 for(uint32_t lead:{0u,0xd7ffu,0xd800u,0xdbffu,0xdc00u,0xffffffffu})for(uint32_t trail:{0u,0xdbffu,0xdc00u,0xdfffu,0xe000u}){++cases;check(outcome([&]{return std::to_string(uint32_t(Star::utf32FromUtf16SurrogatePair(lead,trail)));})==outcome([&]{return std::to_string(uint32_t(R::utf32FromUtf16SurrogatePair(lead,trail)));}),"pair errors lead before trail");}
 std::cout<<"{\"cases\":"<<cases<<",\"checks\":"<<checks<<",\"receipts\":[";
 for(unsigned op=0;op<10;++op){uint64_t count=0;
#ifdef STAR_USE_RUST_UNICODE
 count=star_unicode_call_count(op);check(count>0&&!missingReceipt,"receipt missing");
#endif
 if(op)std::cout<<',';std::cout<<count;}
 std::cout<<"],\"observation_digest\":\""<<std::hex<<observation<<"\"}\n";
}
