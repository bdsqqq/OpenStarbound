#include "StarJsonBuilder.hpp"
#include "StarLexicalCast.hpp"
#include <cxxabi.h>
#include <cstring>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <typeinfo>
#include <vector>
using namespace Star;
static std::string hex(std::string const& s) { static char const h[]="0123456789abcdef"; std::string o; for(unsigned char c:s){o+=h[c>>4];o+=h[c&15];}return o; }
static std::string err(std::exception const& e){int s=0;std::unique_ptr<char,decltype(&std::free)> n(abi::__cxa_demangle(typeid(e).name(),nullptr,nullptr,&s),&std::free);return std::string(s==0?n.get():typeid(e).name())+":"+hex(e.what());}
static std::string typed(Json const& j){if(j.type()==Json::Type::Null)return "n";if(j.type()==Json::Type::Int)return "i"+std::to_string(j.toInt());if(j.type()==Json::Type::Float){double d=j.toDouble();uint64_t b;std::memcpy(&b,&d,8);std::ostringstream o;o<<'f'<<std::hex<<std::setw(16)<<std::setfill('0')<<b;return o.str();}throw std::runtime_error("unexpected type");}
struct ProtocolError:std::runtime_error{using std::runtime_error::runtime_error;};
enum class Op:unsigned {String=11,Lexical=23,Json=37,Append=41};
struct Frame {
  List<Maybe<Star::Json>> stack;
  char kind; char32_t const* units;size_t length;std::string mode;
  String* string=nullptr;Star::Json* json=nullptr;
  unsigned stringToken=0,jsonToken=0;bool stringLive=false,jsonLive=false;
  double d=0;long long i=0;std::exception_ptr pending;std::string trace;
  void mark(std::string const& x){if(!trace.empty())trace+=",";trace+=x;}
};
static void controller(Frame&,unsigned) noexcept;
static void rethrow(Frame& f){if(f.pending){f.mark(f.stringLive?"rethrow-live":"rethrow-dead");std::rethrow_exception(f.pending);}}
// The original String prvalue belongs to the caller's outer full-expression.
// This rvalue-reference parameter neither copies nor takes ownership of it.
static void with_string(String&& s,Frame& f){
 f.string=&s;f.stringToken=101;f.stringLive=true;f.mark("string-open");
 try {controller(f,1);if(f.mode=="pretend-release"&&f.pending){f.stringLive=false;f.stringToken=0;f.mark("pretend-release");}rethrow(f);}
 catch(...){f.mark("string-unwind");f.string=nullptr;f.stringToken=0;f.stringLive=false;throw;}
 f.mark("string-close");f.string=nullptr;f.stringToken=0;f.stringLive=false;
}
// Direct C++17 parameter construction from Json(parsed), matching push(Json).
// Only the original push's move into List<Maybe<Json>> occurs in Append.
static void with_json(Star::Json value,Frame& f){
 f.json=&value;f.jsonToken=203;f.jsonLive=true;f.mark("json-open");
 try{controller(f,2);rethrow(f);}
 catch(...){f.mark("json-unwind");f.json=nullptr;f.jsonToken=0;f.jsonLive=false;throw;}
 f.mark("json-close");f.json=nullptr;f.jsonToken=0;f.jsonLive=false;
}
// Every callback catches before returning to the scripted controller. Exceptions
// are rethrown only AFTER controller return, inside the native owning scope.
static bool dispatch(Frame& f,Op op,unsigned token) noexcept {
 try {
  switch(op){
   case Op::String:with_string(Star::String(f.units,f.length),f);break;
   case Op::Lexical:
    if(token!=101||f.stringToken!=token||!f.stringLive||!f.string)throw ProtocolError("String token expired");
    f.mark("lexical");
    // Unique String->StringView conversion is StringView(String const&).
    // std::move binds that same const& directly, with no extra String object.
    if(f.kind=='D')f.d=lexicalCast<double>(std::move(*f.string));
    else f.i=lexicalCast<long long>(std::move(*f.string));
    if(f.mode=="substitute"&&f.kind=='I'&&f.length==1&&f.units[0]=='1')f.i=2;
    f.mark("lexical-ok");break;
   case Op::Json:
    if(!f.stringLive||f.stringToken!=101)throw ProtocolError("Json requires live String");
    if(f.kind=='D')with_json(Star::Json(f.d),f);else with_json(Star::Json(f.i),f);break;
   case Op::Append:
    if(token!=203||f.jsonToken!=token||!f.jsonLive||!f.stringLive||!f.json)throw ProtocolError("append token invalid");
    if(f.mode=="mock-failure")throw std::runtime_error("mock-before-append");
    f.mark("append");f.stack.append(std::move(*f.json));break;
  }
  return true;
 }catch(...){f.pending=std::current_exception();f.mark("pending");return false;}
}
// Rust-free fixed script interpreter. It chooses every stage separately; no
// whole-expression putDouble callback is exposed. Native callbacks own objects.
static void controller(Frame& f,unsigned phase) noexcept {
 if(phase==0){dispatch(f,Op::String,0);return;}
 if(phase==1){
  if(f.mode=="early-release"){f.stringToken=0;f.mark("token-invalidated");}
  bool ok=dispatch(f,Op::Lexical,101);
  if(!ok){if(f.mode=="suppress"){f.pending=nullptr;f.mark("suppressed");return;}if(f.mode!="append-after-error")return;}
  dispatch(f,Op::Json,0);return;
 }
 if(f.mode!="skip-append")dispatch(f,Op::Append,203);else f.mark("skipped");
}
static std::string snapshot(List<Maybe<Json>> s){std::string o;while(!s.empty()){if(!o.empty())o+='|';o+=typed(s.takeLast().take());}return o;}
static std::string snapshot(JsonBuilderStream s){std::string o;while(s.stackSize()){if(!o.empty())o+='|';o+=typed(s.takeTop());}return o;}
int main(int argc,char** argv){
 if(argc!=2)return 2;std::string mode=argv[1],line;
 while(std::getline(std::cin,line)){
  std::istringstream in(line);std::string id,kind,payload;
  if(!std::getline(in,id,'\t')||!std::getline(in,kind,'\t')||!std::getline(in,payload)||kind.size()!=1)return 3;
  std::vector<char32_t> u;if(payload!="-"){std::istringstream p(payload);std::string x;while(std::getline(p,x,','))u.push_back(static_cast<char32_t>(std::stoul(x,nullptr,16)));}size_t n=u.size();u.push_back(0);
  Frame f;f.kind=kind[0];f.units=u.data();f.length=n;f.mode=mode;f.stack.append(Json());JsonBuilderStream ref;ref.putNull();
  std::string result="ok";
  try{if(mode=="reference"){if(f.kind=='D')ref.putDouble(u.data(),n);else ref.putInteger(u.data(),n);}else{controller(f,0);if(f.pending)std::rethrow_exception(f.pending);}}
  catch(std::exception const& e){result=err(e);}
  std::cout<<id<<'\t'<<"0"<<'\t'<<result<<'\t'<<(mode=="reference"?snapshot(ref):snapshot(f.stack))<<'\t'<<f.trace<<'\n';
  // Continue the same partially mutated native stack after the numeric event.
  char32_t next[]={U'1',U'7',0};f.units=next;f.length=2;f.kind='I';f.pending=nullptr;f.trace.clear();f.mode="correct";result="ok";
  try{if(mode=="reference")ref.putInteger(next,2);else{controller(f,0);if(f.pending)std::rethrow_exception(f.pending);}}catch(std::exception const& e){result=err(e);}
  std::cout<<id<<'\t'<<"1"<<'\t'<<result<<'\t'<<(mode=="reference"?snapshot(ref):snapshot(f.stack))<<'\t'<<f.trace<<'\n';
 }
}
