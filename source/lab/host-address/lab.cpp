#include "StarHostAddress.hpp"
#ifdef LAB_REFERENCE
#include "StarHostAddress.reference.hpp"
using Address=Star::HostAddressReference;
using Endpoint=Star::HostAddressWithPortReference;
#else
using Address=Star::HostAddress;
using Endpoint=Star::HostAddressWithPort;
#endif
#include "StarNetImpl.hpp"
#include <dlfcn.h>
#include <sstream>
#include <iostream>
#include <functional>
#include <iomanip>
using namespace Star;
namespace {
int fixture=0, calls=0, frees=0; bool realQuery=false; std::string query; int family=0, socktype=0, protocol=0, flags=0, seenErrno=0; std::string families;
addrinfo records[3]; sockaddr_in a4[3]; sockaddr_in6 a6[3];
std::string hex(std::string const&s){static char const*d="0123456789abcdef";std::string r;for(unsigned char c:s){r+=d[c>>4];r+=d[c&15];}return r;}
void reset(int f=0){fixture=f;calls=frees=0;query.clear();families.clear();family=socktype=protocol=flags=seenErrno=0;errno=0;}
void trace(){std::cout<<"|resolver="<<calls<<","<<frees<<","<<hex(query)<<","<<family<<","<<socktype<<","<<protocol<<","<<flags<<","<<seenErrno<<","<<families;}
template<class A> void address(A const&a){std::cout<<"mode="<<int(a.mode())<<"|size="<<a.size()<<"|bytes=";for(size_t i=0;i<a.size();++i)std::cout<<hex(std::string(1,char(a.octet(i))));std::cout<<"|zero="<<a.isZero()<<"|local="<<a.isLocalHost()<<"|hash="<<Star::hash<A>()(a)<<"|alias="<<(a.bytes()==a.bytes());try{std::ostringstream s;s<<a;std::cout<<"|text="<<hex(s.str());}catch(NetworkException const&e){std::cout<<"|exception=NetworkException:"<<hex(e.what());}}
void endpoint(Endpoint const&e){address(e.address());std::ostringstream s;s<<e;std::cout<<"|port="<<e.port()<<"|ehash="<<Star::hash<Endpoint>()(e)<<"|endpoint="<<hex(s.str());}
struct Sentinel{}; Sentinel sentinel;
struct Buffer:std::streambuf {std::string output, chunks;std::function<void(int)> callback;int n=0, syncs=0, kind=0;std::streamsize xsputn(char const*p,std::streamsize z)override{++n;chunks+=std::to_string(z)+",";if(kind==1){output.append(p,z/2);return z/2;}if(kind==2)throw &sentinel;output.append(p,z);if(callback){if(z==1&&p[0]==':')callback(2);else if(n==1)callback(1);}return z;}int overflow(int c)override{if(c!=EOF)output+=char(c);return c;}int sync()override{++syncs;return 0;}};
}
extern "C" int getaddrinfo(char const*node,char const*service,addrinfo const*h,addrinfo**result){
 ++calls;query=node?node:"";family=h->ai_family;socktype=h->ai_socktype;protocol=h->ai_protocol;flags=h->ai_flags;
 if(realQuery){if(query!="127.0.0.1"||service)std::abort();auto fn=reinterpret_cast<decltype(&getaddrinfo)>(dlsym(RTLD_NEXT,"getaddrinfo"));int r=fn(node,service,h,result);seenErrno=errno;for(auto*p=*result;p;p=p->ai_next)families+=std::to_string(p->ai_family)+",";return r;}
 if(fixture==4||fixture==5){errno=fixture==4?22:0;seenErrno=errno;*result=nullptr;return EAI_NONAME;}
 memset(records,0,sizeof(records));memset(a4,0,sizeof(a4));memset(a6,0,sizeof(a6));
 int fs[3]={AF_INET,AF_INET6,AF_INET};if(fixture==1){fs[0]=AF_UNIX;fs[1]=AF_INET6;}if(fixture==2)fs[0]=fs[1]=fs[2]=AF_UNIX;if(fixture==3)fs[0]=AF_INET6;
 for(int i=0;i<3;++i){records[i].ai_family=fs[i];families+=std::to_string(fs[i])+",";records[i].ai_next=i<2?&records[i+1]:nullptr;
 if(fs[i]==AF_INET){a4[i].sin_family=AF_INET;uint8_t b[4]={127,0,0,uint8_t(i?2:1)};memcpy(&a4[i].sin_addr,b,4);records[i].ai_addr=reinterpret_cast<sockaddr*>(&a4[i]);records[i].ai_addrlen=sizeof(a4[i]);}
 else{a6[i].sin6_family=AF_INET6;a6[i].sin6_addr.s6_addr[15]=uint8_t(i+1);records[i].ai_addr=reinterpret_cast<sockaddr*>(&a6[i]);records[i].ai_addrlen=sizeof(a6[i]);}}
 *result=records;return 0;
}
extern "C" void freeaddrinfo(addrinfo*p){++frees;if(realQuery){auto fn=reinterpret_cast<decltype(&freeaddrinfo)>(dlsym(RTLD_NEXT,"freeaddrinfo"));fn(p);}else if(p!=records)std::abort();}
int main(){
 std::cout<<"abi|size_t="<<sizeof(size_t)<<"|mode="<<sizeof(NetworkMode)<<"|AF_INET="<<AF_INET<<"|AF_INET6="<<AF_INET6<<"|AI_ADDRCONFIG="<<AI_ADDRCONFIG<<"\n";
 for(int mode:{0,1,2,-1,2147483647}){Address a(static_cast<NetworkMode>(mode),nullptr);std::cout<<"null/"<<mode<<"|";address(a);auto b=a;std::cout<<"|copyeq="<<(a==b)<<"\nlocalhost/"<<mode<<"|";address(Address::localhost(static_cast<NetworkMode>(mode)));std::cout<<"\n";}
 // bytes() exposes const storage, but these objects are mutable: removing the
 // view's constness and writing the initialized uint8_t array is defined. This
 // reaches the source's non-IPv4 localhost branch without any indeterminate read.
 for(int mode:{2,-1,2147483647}){Address a(static_cast<NetworkMode>(mode),nullptr),zero(static_cast<NetworkMode>(mode),nullptr);auto p=const_cast<uint8_t*>(a.bytes());p[15]=1;std::cout<<"unknown-initialized/"<<mode<<"|";address(a);std::cout<<"|zeroeq="<<(a==zero)<<"|octet15="<<unsigned(a.octet(15))<<"\n";}
 {Address a(NetworkMode::IPv4,nullptr),zero(NetworkMode::IPv4,nullptr);const_cast<uint8_t*>(a.bytes())[15]=1;std::cout<<"initialized-tail-ipv4|";address(a);std::cout<<"|octet15="<<unsigned(a.octet(15))<<"|zeroeq="<<(a==zero)<<"\n";}
 for(int mode:{0,1})for(int pattern=0;pattern<16;++pattern){uint8_t b[16]={};for(int i=0;i<16;++i)b[i]=pattern<4?uint8_t(pattern):(uint8_t)(i*pattern+193);if(pattern==3){memset(b,0,16);b[mode==0?3:15]=1;if(mode==0)b[0]=127;}if(pattern==4&&mode==0){b[0]=127;b[1]=b[2]=0;b[3]=2;}Address a(static_cast<NetworkMode>(mode),b);auto copy=a;std::cout<<"raw/"<<mode<<"/"<<pattern<<"|";address(a);b[0]^=255;Address other(static_cast<NetworkMode>(mode),b);std::cout<<"|copyeq="<<(a==copy)<<"|othereq="<<(a==other)<<"\n";for(uint16_t port:{uint16_t(0),uint16_t(80),uint16_t(65535)}){Endpoint e(a,port),e2(e);std::cout<<"endpoint/"<<mode<<"/"<<pattern<<"/"<<port<<"|";endpoint(e);std::cout<<"|copyeq="<<(e==e2)<<"\n";}}
 std::vector<std::string> texts={"","*","0.0.0.0","::","127.0.0.1","hostname.invalid","[::1]"," café",std::string("127.0.0.1\0suffix",16)};
 for(int f=0;f<6;++f)for(size_t i=0;i<texts.size();++i){reset(f);String s(texts[i]);auto a=Address::lookup(s);std::cout<<"lookup/"<<f<<"/"<<i<<"|";if(a.isLeft())std::cout<<"left="<<hex(a.left().utf8());else address(a.right());trace();std::cout<<"\n";reset(f);std::cout<<"ctor/"<<f<<"/"<<i<<"|";try{Address a(s);address(a);}catch(NetworkException const&e){std::cout<<"exception=NetworkException:"<<hex(e.what());}trace();std::cout<<"\n";reset(f);auto e=Endpoint::lookup(s,65535);std::cout<<"lookup-port/"<<f<<"/"<<i<<"|";if(e.isLeft())std::cout<<"left="<<hex(e.left().utf8());else endpoint(e.right());trace();std::cout<<"\n";}
 {Endpoint e;std::cout<<"endpoint-default|";endpoint(e);std::cout<<"\n";uint8_t b[4]={127,0,0,1};Endpoint other(NetworkMode::IPv4,b,1);std::cout<<"endpoint-inequality|same="<<(e==other)<<"\n";}
 for(int f:{0,4}){reset(f);std::cout<<"endpoint-two-ctor/"<<f<<"|";try{Endpoint e(String("scripted"),123);endpoint(e);}catch(NetworkException const&e){std::cout<<"exception=NetworkException:"<<hex(e.what());}trace();std::cout<<"\n";}
 std::vector<std::string> ports={"","0","80","65535","65536","999999999999999999999999999999999","-1","+1"," 1","1 ",std::string("1\0x",3),"１２"};
 for(auto const&host:std::vector<std::string>{"","*","::","[::]","[::1]","[bad","bad]","bad"})for(size_t p=0;p<ports.size();++p){reset();String s(host+":"+ports[p]);std::cout<<"parse/"<<hex(host)<<"/"<<p<<"|";try{auto a=Endpoint::lookupWithPort(s);if(a.isLeft())std::cout<<"left="<<hex(a.left().utf8());else endpoint(a.right());}catch(OutOfRangeException const&e){std::cout<<"exception=OutOfRangeException:"<<hex(e.what());}trace();std::cout<<"\n";}
 for(auto const&s:std::vector<std::string>{"123","65536","","abc","[::1]:80"}){reset();std::cout<<"endpoint-ctor/"<<hex(s)<<"|";try{Endpoint e{String(s)};endpoint(e);}catch(NetworkException const&e){std::cout<<"exception=NetworkException:"<<hex(e.what());}trace();std::cout<<"\n";}
 for(int change:{0,1,2})for(int kind:{0,1,2})for(int mask:{0,1}){uint8_t b[4]={127,0,0,1},c[4]={10,1,2,3};Endpoint e(NetworkMode::IPv4,b,80);Buffer buffer,tied;buffer.kind=kind;buffer.callback=[&](int n){if(n==change)e=Endpoint(NetworkMode::IPv4,c,443);};std::ostream os(&buffer),tie(&tied);os.tie(&tie);os<<std::hex<<std::left<<std::setfill('_')<<std::setw(14);if(mask)os.exceptions(std::ios::badbit|std::ios::failbit);std::string escaped="none";try{os<<e;}catch(Sentinel*p){escaped=p==&sentinel?"sentinel":"other";}catch(std::exception const&){escaped="std";}std::cout<<"stream/"<<change<<"/"<<kind<<"/"<<mask<<"|text="<<hex(buffer.output)<<"|chunks="<<buffer.chunks<<"|sync="<<tied.syncs<<"|state="<<os.rdstate()<<"|width="<<os.width()<<"|escaped="<<escaped<<"|port="<<e.port()<<"\n";}
 realQuery=true;for(int i=0;i<2;++i){reset();auto a=Address::lookup("127.0.0.1");std::cout<<"real-numeric/"<<i<<"|";if(a.isLeft())std::cout<<"left="<<hex(a.left().utf8());else address(a.right());trace();std::cout<<"\n";}
}
