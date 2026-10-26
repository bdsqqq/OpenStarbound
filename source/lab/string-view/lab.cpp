// Native calibration only. All views retain live, initialized backing storage.
#include "StarStringView.hpp"
#include "StarFormat.hpp"
#include <iostream>
#include <sstream>
#include <cstring>
#include <vector>
#include <stdexcept>
#include <type_traits>
static_assert(std::is_same_v<std::string_view::const_iterator,char const*>);
using namespace Star;
using V = StringView;
std::string hex(std::string_view s) { static char const* d="0123456789abcdef"; std::string r; for(unsigned char c:s){r+=d[c>>4];r+=d[c&15];}return r; }
std::string unhex(std::string s){std::string r; for(size_t i=0;i<s.size();i+=2)r+=char(std::stoi(s.substr(i,2),nullptr,16));return r;}
std::string num(size_t n){return n==NPos?"npos":std::to_string(n);}
std::vector<std::string> val;
void add(bool b){val.push_back(b?"1":"0");}
void addn(size_t n){val.push_back(num(n));}
void addv(V v){val.push_back(hex(v.utf8()));}
void split(V v,V p,bool any){auto cb=[&](V s,size_t o,size_t n){
#ifdef CONTROL_TRAILING
if(n==0 && o==v.utf8Size())return;
#endif
#ifdef CONTROL_OFFSETS
o=utf8Length(v.utf8Ptr(),o);
#endif
addv(s);addn(o);addn(n);}; if(any)v.forEachSplitAnyView(p,cb);else v.forEachSplitView(p,cb);}
int main(){std::string line;while(std::getline(std::cin,line)){
 std::vector<std::string> f;std::istringstream in(line);std::string x;while(std::getline(in,x,'\t'))f.push_back(x);
 auto id=f.at(0),op=f.at(1);std::string a=unhex(f.at(2)),b=unhex(f.at(3));size_t pos=std::stoull(f.at(4));bool ci=f.at(5)=="1";
 V v(a),p(b);auto cs=ci?String::CaseInsensitive:String::CaseSensitive;val.clear();
 if(op=="inspect") {addv(v);addn(v.utf8Size());addn(v.size());addn(v.length());add(v.isValid());add(v.empty());auto bytes=v.utf8Bytes();val.push_back(hex(std::string_view(bytes.ptr(),bytes.size())));add(v.utf8Ptr()==a.data());add(&v.utf8()==&v.utf8());for(V::const_iterator it=v.begin();it!=v.end();++it)addn(*it);}
 else if(op=="search"){
#ifdef CONTROL_EMPTY
addn(p.empty()?pos:v.find(p,pos,cs));
#else
addn(v.find(p,pos,cs));
#endif
addn(v.findLast(p,cs));add(v.contains(p,cs));add(v.beginsWith(p,cs));add(v.endsWith(p,cs));add(v.equals(p,cs));add(v.equalsIgnoreCase(p));int c=v.compare(p,cs);val.push_back(std::to_string((c>0)-(c<0)));add(ci || c==v.utf8().compare(p.utf8()));}
 else if(op=="char"){char32_t c=static_cast<char32_t>(std::stoul(b));addn(v.find(c,pos,cs));addn(v.findLast(c,cs));add(v.beginsWith(c,cs));add(v.endsWith(c,cs));add(v.hasChar(c));add(v.hasCharOrWhitespace(c));}
 else if(op=="of"){addn(v.findFirstOf(p,pos));addn(v.findFirstNotOf(p,pos));}
 else if(op=="boundary")addn(v.findNextBoundary(pos,ci));
 else if(op=="substr")addv(v.substr(pos,std::stoull(b)));
 else if(op=="substr-default")addv(v.substr(pos));
 else if(op=="throw-at" || op=="throw-substr"){
 try {if(op=="throw-at")v.at(pos);else v.substr(pos,0);val.push_back("no-throw");}
 catch(OutOfRangeException const& e){val.push_back("OutOfRangeException");val.push_back(hex(e.what()));}
 }
 else if(op=="at"){addn(v[pos]);addn(v.at(pos));}
 else if(op=="split" || op=="any")split(v,p,op=="any");
 else if(op=="free"){String s(b);add(v==b.c_str());add(v==b);add(v==s);add(v==p);add(v!=p);add(v<p);std::ostringstream os;auto& ref=(os<<v);val.push_back(hex(os.str()));add(&ref==&os);val.push_back(hex(fmt::format("{}",v)));}
 else if(op=="ctor"){
   V d; if(pos==0){addv(d);add(d.empty());}
   if(pos==1){V z(v);addv(z);add(z.utf8Ptr()==a.data());}
   if(pos==2){V z(std::move(v));addv(z);addv(v);add(z.utf8Ptr()==a.data());}
   if(pos==3){String s(a);V z(s);addv(z);add(z.utf8Ptr()==s.utf8Ptr());}
   if(pos==4){V z(a.c_str());addv(z);}
   if(pos==5){V z(a.data()+1,a.size()-2);addv(z);add(z.utf8Ptr()==a.data()+1);}
   if(pos==6){std::string_view s(a);V z(s);addv(z);}
   if(pos==7){V z{std::string_view(a)};addv(z);}
   if(pos==8){V z(a);addv(z);}
   // Character object representation, not Unicode encoding; memcpy initializes legal Char objects.
   if(pos==9||pos==10){V::Char backing[2];static_assert(sizeof(V::Char)==4);std::memcpy(backing,"ABCDEFGH",8);V z=pos==9?V(backing):V(backing,2);addv(z);}
   if(pos==11){auto s=v.takeUtf8();val.push_back(hex(s));add(v.empty());add(s.data()==a.data());}
   if(pos==12){auto& r=(d=v);addv(d);add(&r==&d);a[0]='Z';addv(d);}
   if(pos==13){String s(v);val.push_back(hex(s.utf8()));}
   if(pos==14){String s{std::string_view(a)};val.push_back(hex(s.utf8()));}
   if(pos==15){String s("!");auto& r=(s+=v);val.push_back(hex(s.utf8()));add(&r==&s);}
   if(pos==16){String s("!");auto& r=(s+=std::string_view(a));val.push_back(hex(s.utf8()));add(&r==&s);}
 }
 else if(op=="callback"){
   struct Marker:std::runtime_error{using std::runtime_error::runtime_error;};
   size_t calls=0;V replacement(b);std::exception_ptr saved;
   try {auto cb=[&](V s,size_t o,size_t n){addv(s);addn(o);addn(n);++calls;
      if(pos==0 && calls==2){try{throw Marker("split-marker");}catch(...){saved=std::current_exception();throw;}}
      if(pos==1 && calls==1)split(V("q::r:"),V(":"),ci);
      if(pos==2 && calls==1)a[2]='X';
      if(pos==3 && calls==1)v=replacement;
    };if(ci)v.forEachSplitAnyView(V(","),cb);else v.forEachSplitView(V(","),cb);
   }catch(Marker const& e){val.push_back(e.what());add(saved==std::current_exception());}
 }
 else if(op=="invalid"){add(v.isValid());addn(v.size());for(auto c:v)addn(c);}
 else throw std::runtime_error("unknown operation");
 std::cout<<"{\"id\":\""<<id<<"\",\"value\":[";for(size_t i=0;i<val.size();++i){if(i)std::cout<<',';std::cout<<'"'<<val[i]<<'"';}std::cout<<"]}\n";
 } }
