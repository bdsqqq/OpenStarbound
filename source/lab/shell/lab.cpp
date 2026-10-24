#include "StarShellParser.hpp"
#include "StarShellParser.reference.hpp"
#ifdef STAR_USE_RUST_SHELL
#include "StarRustShell.h"
#endif
#include <iostream>
#include <random>
#include <vector>
#include <thread>
#include <cctype>
using Words=std::vector<std::string>;
static uint64_t cases=0,checks=0,digest=14695981039346656037ull;
static void check(bool b,char const* why){++checks;if(!b){std::cerr<<"COMPARISON "<<why<<" case="<<cases<<"\n";std::exit(1);}}
static void obs(uint64_t n){for(int i=0;i<8;++i){digest^=(n>>(8*i))&255;digest*=1099511628211ull;}}
static void observe(Words const&w){obs(w.size());for(auto const&s:w){obs(s.size());for(unsigned char c:s)obs(c);}}
template<class P> static Words tokens(P&p,Star::String const&s){Words w;for(auto const&t:p.tokenize(s)){check(int(t.type)==0,"Word token type");w.push_back(t.token.utf8());}return w;}
template<class P> static Words strings(P&p,Star::String const&s){Words w;for(auto const&t:p.tokenizeToStringList(s))w.push_back(t.utf8());return w;}
static Star::ShellParser candidate;static ShellReference::ShellParser reference;
static void test(std::string const&s){++cases;Star::String input(s);auto a=tokens(candidate,input);auto b=tokens(reference,input);observe(a);check(a==b,"token bytes/order");auto c=strings(candidate,input);observe(c);check(c==b,"StringList/parser reuse");check(tokens(candidate,Star::String("reset"))==Words{"reset"},"reuse reset");}
static void anchor(std::string const&s,Words const&expected){check(tokens(candidate,Star::String(s))==expected,"independent literal anchor");check(strings(candidate,Star::String(s))==expected,"literal StringList");test(s);}
static void anchors(){
 anchor("",{});anchor(" ",{ "" });anchor("  \t\r\n",{""});anchor("a ",{"a"});anchor("a  ",{"a",""});anchor("a b",{"a","b"});
 anchor("''",{""});anchor("\"\"",{""});anchor("a''b",{"ab"});anchor("'a b",{"a b"});anchor("\"a' b\"",{"a' b"});anchor("'a\" b'",{"a\" b"});
 anchor("\\q",{"q"});anchor("\\",{"\\"});anchor("'\\n'",{"\n"});anchor("\\n\\t\\r\\b\\v\\f\\a",{std::string("\n\t\r\b\v\f\a",7)});
 anchor("\\0Z",{std::string("\0Z",2)});anchor(std::string("A\0Z",3),{std::string("A\0Z",3)});anchor("\xef\xbb\xbf" "a",{"a"});anchor("a\xc2\xa0" "b",{"a\xc2\xa0" "b"});anchor("\xc3\xa9 \xe6\x97\xa5",{"\xc3\xa9","\xe6\x97\xa5"});
 anchor("\\u",{"u"});anchor("\\u0",{"\xef\xbf\xbd"});anchor("\\u00",{"\xef\xbf\xbd"});anchor("\\u000",{"\xef\xbf\xbd"});anchor("\\u0041",{"A"});anchor("\\u0041Z",{"AZ"});anchor("\\u  X",{"\xef\xbf\xbd","X"});anchor("\\uGfoo",{"\xef\xbf\xbd" "foo"});
 anchor("\\uD83D\\uDE00",{"\xf0\x9f\x98\x80"});anchor("\\uD83DZ",{"\xef\xbf\xbdZ"});anchor("\\uD83D\\q",{"\xef\xbf\xbdq"});anchor("\\uD83D",{"\xef\xbf\xbd"});anchor("\\uD83D\\u0041",{"\xef\xbf\xbd"});
 // StarUnicode.cpp:302 replaces isolated surrogate scalars during String::append.
 anchor("\\uDE00",{"\xef\xbf\xbd"});
}
#ifdef STAR_USE_RUST_SHELL
struct Ctx{std::vector<uint32_t> input;std::vector<uint64_t> events;int abortAt=-1;int calls=0;bool mutate=false,reenter=false;};
static int32_t classify(void* p,uint32_t cp,uint32_t* hex){auto&c=*static_cast<Ctx*>(p);c.events.push_back((uint64_t(2)<<32)|cp);*hex=std::isxdigit(int(cp))!=0;return c.calls++==c.abortAt?1:0;}
static int32_t emit(void*p,uint32_t event,uint32_t cp){auto&c=*static_cast<Ctx*>(p);c.events.push_back((uint64_t(event)<<32)|cp);if(c.mutate&&c.input.size()>1)c.input[1]='Z';if(c.reenter){c.reenter=false;Ctx nested;size_t n=9;uint32_t q=9;check(star_shell_tokenize(nullptr,0,classify,emit,&nested,&n,&q)==0&&n==0&&q==0,"ABI reentry");}return c.calls++==c.abortAt?1:0;}
static int32_t nullClass(void*,uint32_t,uint32_t*h){*h=0;return 0;}static int32_t nullEmit(void*,uint32_t,uint32_t){return 0;}
static void abi(){
 auto call=[](Ctx&c,size_t&n,uint32_t&q){auto before=star_shell_call_count();bool nested=c.reenter;int s=star_shell_tokenize(c.input.data(),c.input.size(),classify,emit,&c,&n,&q);check(star_shell_call_count()==before+((s==0||s==1)?1:0)+(nested?1:0),"ABI exact receipt");return s;};
 size_t n=99;uint32_t q=99;Ctx c;c.input={'a','b'};check(call(c,n,q)==0&&n==1&&q==0&&c.events==std::vector<uint64_t>{'a','b',uint64_t(1)<<32},"ABI append/end order");
 c=Ctx{};c.input={'a','b'};c.mutate=true;c.reenter=true;check(call(c,n,q)==0&&c.events==std::vector<uint64_t>{'a','Z',uint64_t(1)<<32},"ABI mutation future input/reentry");
 for(int abort:{0,1}){c=Ctx{};c.input={'a'};c.abortAt=abort;n=99;q=99;check(call(c,n,q)==1&&n==0&&q==0,"ABI abort character/boundary partial count");}
 c=Ctx{};c.input={'\\','u','0','0','4','1'};c.abortAt=0;check(call(c,n,q)==1&&n==0&&c.events==std::vector<uint64_t>{(uint64_t(2)<<32)|'0'},"ABI classification abort/order");
 c=Ctx{};c.input={'\'' ,'a'};check(call(c,n,q)==0&&q=='\''&&n==1,"ABI final quote");
 auto before=star_shell_call_count();n=99;q=99;check(star_shell_tokenize(nullptr,0,nullptr,emit,&c,&n,&q)==2&&n==99&&q==99,"ABI missing classify unchanged");check(star_shell_tokenize(nullptr,0,classify,nullptr,&c,&n,&q)==2&&n==99&&q==99,"ABI missing emit unchanged");check(star_shell_tokenize(nullptr,1,classify,emit,&c,&n,&q)==2&&n==99&&q==99,"ABI null input unchanged");check(star_shell_tokenize(nullptr,0,classify,emit,&c,nullptr,&q)==2&&q==99,"ABI null output");check(star_shell_call_count()==before,"invalid ABI uncounted");
 check(star_shell_tokenize(nullptr,0,nullClass,nullEmit,nullptr,&n,&q)==0&&n==0&&q==0,"ABI null root context");
 uint64_t child=99;std::thread t([&]{child=star_shell_call_count();});t.join();check(child==0,"ABI thread local receipt");
}
#endif
int main(int argc,char**){anchors();
 std::vector<std::string> atoms={"a"," ","  ","'","\"","\\","\\q","\\n","\\u","\\u0041","\\uD800","\\uDC00","\\uD800\\uDC00","\\uD800\\x","\\u12Z","\t","\xef\xbb\xbf",std::string("\0",1)};
 for(auto const&a:atoms)for(auto const&b:atoms)for(auto const&c:atoms)test(a+b+c);
 std::mt19937 rng(0x5348454c);std::string alphabet="ab  \t\r\n'\"\\u01239abcdefGZ";for(int i=0;i<12000;++i){std::string s;for(unsigned j=0,n=rng()%65;j<n;++j)s+=alphabet[rng()%alphabet.size()];test(s);}
 uint64_t receipt=0;
#ifdef STAR_USE_RUST_SHELL
 abi();receipt=star_shell_call_count();check(receipt>0&&argc==1,"receipt missing");
#endif
 std::cout<<"{\"cases\":"<<cases<<",\"checks\":"<<checks<<",\"receipts\":"<<receipt<<",\"observation_digest\":\""<<std::hex<<digest<<"\"}\n";
}
