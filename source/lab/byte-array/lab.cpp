// Source-only native public-class probe. No StarJson dependency or layout mirror.
#include "StarByteArray.hpp"
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
using Star::ByteArray;
static_assert(sizeof(size_t) == 8 && std::is_signed<char>::value, "Apple signed-char/64-bit contract");
namespace {
unsigned char const pattern[] = {0x80,0xff,0x01,0x00,0x7f,0x41,0xa5,0x10};
ByteArray seed(size_t n) {
  ByteArray a(64, '\0');
  for (size_t i=0;i<64;++i) a[i]=char(pattern[i%8]);
  a.resize(n);
  return a;
}
std::string hex(char const* p, size_t n) {
  char const* digits="0123456789abcdef";
  std::string s;
  for(size_t i=0;i<n;++i) { unsigned char c=p[i]; s+=digits[c>>4]; s+=digits[c&15]; }
  return s;
}
std::string hex(ByteArray const& a) { return hex(a.ptr(),a.size()); }
size_t serial=0;
void emit(std::string const& action,size_t n,size_t p,size_t q,ByteArray const& a,
          std::string const& value="",std::string const& extra="",size_t calls=0,
          std::string const& outcome="ok") {
  // All strings are fixed vocabulary, decimal integers, or lowercase hex.
  std::cout << "{\"case\":\"b" << serial++ << "\",\"options\":{\"action\":\"" << action
    << "\",\"n\":" << n << ",\"p\":" << p << ",\"q\":" << q << "},\"size\":" << a.size()
    << ",\"capacity\":" << a.capacity() << ",\"null\":" << (a.ptr()==nullptr?"true":"false")
    << ",\"bytes\":\"" << hex(a) << "\",\"value\":\"" << value << "\",\"extra\":\"" << extra
    << "\",\"calls\":" << calls << ",\"outcome\":\"" << outcome << "\"}\n";
}
void run(std::string const& op,size_t n=0,size_t p=0,size_t q=0) {
  auto out=[&](ByteArray const& a,std::string v="",std::string e="",size_t calls=0,std::string outcome="ok") {
    emit(op,n,p,q,a,v,e,calls,outcome);
  };
  if(op=="default") {
    ByteArray a; a=a; a=std::move(a); a.clear(); a.resize(0); a.reset();
    ByteArray const& c=a;
    out(a,std::to_string(c.empty())+","+std::to_string(a.begin()==nullptr)+","+std::to_string(a.end()==nullptr)+","+std::to_string(c.begin()==nullptr)+","+std::to_string(c.end()==nullptr)); return;
  }
  if(op=="reserve_first") { auto a=ByteArray::withReserve(p); out(a); return; }
  if(op=="cstring") { auto a=ByteArray::fromCString("A\x80"); out(a); return; }
  if(op=="cstring_null") { auto a=ByteArray::fromCStringWithNull(p?"A\x80":""); out(a); return; }
  if(op=="reserve_growth") { auto a=ByteArray::withReserve(n); a.reserve(p); out(a); return; }
  if(op=="empty_move") { ByteArray a; ByteArray b(std::move(a)); auto r=seed(2); r=std::move(b); out(r,"",std::to_string(a.ptr()==nullptr)+","+std::to_string(b.ptr()==nullptr)); return; }
  auto a=seed(n);
  if(op=="access") {
    ByteArray const& c=a; std::string v;
    for(size_t i=0;i<n;++i) { a[i]=char((unsigned char)a[i]^0x11); v+=hex(&c.ptr()[i],1); (void)c[i]; (void)c.at(i); }
    out(a,v,std::to_string(a.end()-a.begin())+","+std::to_string(c.end()-c.begin())+","+std::to_string(c.empty()));
  } else if(op=="fill_ctor") { ByteArray r(n,char(0xa5)); out(r); }
  else if(op=="ptr_ctor") { ByteArray r(a.ptr(),n); out(r); }
  else if(op=="copy_ctor") { ByteArray r(a); out(r, "",hex(a)); }
  else if(op=="move_ctor") { ByteArray r(std::move(a)); out(r,"",std::to_string(a.size())+","+std::to_string(a.capacity())+","+std::to_string(a.ptr()==nullptr)); }
  else if(op=="copy_assign") { auto r=seed(2); bool same=&(r=a)==&r; out(r,std::to_string(same),hex(a)); }
  else if(op=="move_assign") { auto r=seed(2); bool same=&(r=std::move(a))==&r; out(r,std::to_string(same),std::to_string(a.size())+","+std::to_string(a.capacity())+","+std::to_string(a.ptr()==nullptr)); }
  else if(op=="self") { bool x=&(a=a)==&a; bool y=&(a=std::move(a))==&a; out(a,std::to_string(x)+","+std::to_string(y)); }
  else if(op=="reset") { a.reset(); a.reset(); out(a); }
  else if(op=="clear") { a.clear(); out(a); }
  else if(op=="reserve") { a.reserve(p); out(a); }
  else if(op=="resize_fill") { a.resize(p,char(0xa5)); out(a); }
  else if(op=="resize_write") { a.resize(n+3); for(size_t i=n;i<n+3;++i) a[i]=char(0x42); out(a); }
  else if(op=="fill") { a.fill(char(0xa5)); out(a); }
  else if(op=="fill_size") { a.fill(p,char(0xa5)); out(a); }
  else if(op=="append_ptr") { char data[]={char(0xff),0x01,0x42}; a.append(data,p); out(a); }
  else if(op=="append_array") { auto b=seed(p); a.append(b); out(a); }
  else if(op=="append_self") { a.append(a); out(a); }
  else if(op=="append_byte") { a.appendByte(char(0xfe)); out(a); }
  else if(op=="push") { a.push_back(char(0xfe)); out(a); }
  else if(op=="copy_all" || op=="copy_len" || op=="copy_range") {
    char data[16]; for(char& c:data)c=char(0x5a);
    if(op=="copy_all")a.copyTo(data); else if(op=="copy_len")a.copyTo(data,p); else a.copyTo(data,p,q);
    out(a,hex(data,16));
  } else if(op=="write") { char data[]={char(0xff),0x01,0x42}; a.writeFrom(data,p,q); out(a); }
  else if(op=="sub") { auto r=a.sub(p,q); out(r); }
  else if(op=="left") { auto r=a.left(p); out(r); }
  else if(op=="right") { auto r=a.right(p); out(r); }
  else if(op=="trim_left") { a.trimLeft(p); out(a); }
  else if(op=="trim_right") { a.trimRight(p); out(a); }
  else if(op=="insert" || op=="insert_iter") {
    if(op=="insert") { a.insert(p,char(0xfe)); out(a); }
    else { auto it=a.insert(a.begin()+p,char(0xfe)); out(a,std::to_string(it-a.begin())); }
  } else if(op=="at") {
    try { char c=a.at(p); out(a,hex(&c,1)); }
    catch(Star::OutOfRangeException const&) { out(a,"","",0,"out_of_range"); }
  } else if(op=="compare") {
    auto b=seed(p); if(q && p)b[0]=char(q==1?1:0xff);
    out(a,std::to_string(a.diffChar(b))+","+std::to_string(a.compare(b))+","+std::to_string(a<b)+","+std::to_string(a==b)+","+std::to_string(a!=b),hex(b));
  } else if(op=="hash") { out(a,std::to_string(Star::hash<ByteArray>()(a))); }
  else if(op=="stream") { std::ostringstream s; auto* same=&(s<<a); out(a,s.str(),std::to_string(same==&s)); }
  else if(op=="and" || op=="or" || op=="xor" || op=="custom") {
    auto b=seed(p); for(size_t i=0;i<p;++i)b[i]=char((unsigned char)b[i]^0x55);
    if(op=="and") { auto r=a.andWith(b,q); out(r,"",hex(a)+":"+hex(b)); }
    else if(op=="or") { auto r=a.orWith(b,q); out(r,"",hex(a)+":"+hex(b)); }
    else if(op=="xor") { auto r=a.xorWith(b,q); out(r,"",hex(a)+":"+hex(b)); }
    else {
      struct Token {} token; size_t calls=0; std::string trace;
      try {
        auto r=a.combineWith([&](char x,char y) {
          ++calls; trace+=hex(&x,1)+"/"+hex(&y,1)+";";
          // Mutate live objects, with fixed sizes; copied callback arguments stay values.
          if(n)a[0]=char((unsigned char)a[0]^1);
          if(p)b[0]=char((unsigned char)b[0]^2);
          if(q/2==calls)throw &token;
          return char(((unsigned char)x+3*(unsigned char)y)&255);
        },b,q%2);
        out(r,trace,hex(a)+":"+hex(b),calls);
      } catch(Token* e) { out(a,trace,hex(b),calls,e==&token?"same_token":"wrong_token"); }
    }
  } else { throw std::logic_error("unknown action"); }
}
}
int main(int argc,char**) {
  if(argc!=1)return 2;
  run("default");
  for(size_t p:{0,1,7,8,33,65,129,256})run("reserve_first",0,p);
  for(size_t n:{1,3,7,64,127})for(size_t p:{n,n+1,size_t(8),size_t(17),size_t(256)})run("reserve_growth",n,p);
  run("empty_move");
  run("cstring"); for(size_t p:{0,1})run("cstring_null",0,p);
  for(size_t n=0;n<=8;++n) {
    for(auto op:{"access","move_ctor","move_assign","self","reset","clear","resize_write","fill","append_self","append_byte","push","copy_all","hash","stream"})run(op,n);
    if(n)for(auto op:{"fill_ctor","ptr_ctor","copy_ctor","copy_assign"})run(op,n);
    for(size_t p:{0,3,65,129,256})run("reserve",n,p);
    for(size_t p:{0,3,12,65})run("resize_fill",n,p);
    for(size_t p:{0,3,12})run("fill_size",n,p);
    for(size_t p:{0,1,3})for(auto op:{"append_ptr","append_array","copy_len"})run(op,n,p);
    for(size_t p:{0,2,12})for(size_t q:{0,3}) { run("copy_range",n,p,q); run("write",n,p,q); }
    for(size_t p:{0,1,9})for(auto op:{"trim_left","trim_right","at"})run(op,n,p);
    for(size_t p:{size_t(0),n})for(auto op:{"insert","insert_iter"})run(op,n,p);
    if(n) {
      for(size_t p:{size_t(0),size_t(1),n})for(size_t q:{1,3})run("sub",n,p,q);
      for(size_t p:{size_t(0),size_t(1),n,n+1})for(auto op:{"left","right"})if(p || std::string(op)=="right")run(op,n,p);
    }
    for(size_t p:{0,1,5})for(size_t q:{0,1,2})run("compare",n,p,q);
  }
  for(size_t n:{0,1,2,5})for(size_t p:{0,1,2,5}) {
    for(size_t q:{0,1})for(auto op:{"and","or","xor"})run(op,n,p,q);
    for(size_t q=0;q<6;++q)run("custom",n,p,q);
  }
  return 0;
}
