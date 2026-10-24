#include "StarCompression.hpp"
#include "StarCompression.reference.hpp"
#include <zlib-ng.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <type_traits>
#ifdef LAB_RUST
#include "StarRustCompression.h"
#include <stdexcept>
#endif
static_assert(std::is_same_v<decltype(zng_stream{}.avail_in), uint32_t>);
static_assert(std::is_same_v<decltype(zng_stream{}.avail_out), uint32_t>);
#ifdef LAB_REFERENCE
namespace C = CompressionReference;
#else
namespace C = Star;
#endif
std::string hex(char const* p, size_t n) { static char const* h="0123456789abcdef"; std::string s; for(size_t i=0;i<n;++i){unsigned char c=p[i];s+=h[c>>4];s+=h[c&15];}return s; }
std::string unhex(std::string s) {std::string r; for(size_t i=0;i<s.size();i+=2)r+=char(std::stoi(s.substr(i,2),nullptr,16));return r;}
int main(int argc,char**argv) try {
 if(argc!=2)return 2;
 if(std::string(argv[1])=="--version") {std::cout<<zlibng_version()<<'\n';return 0;}
 std::ifstream f(argv[1]);std::string line;
 while(std::getline(f,line)) {
  std::istringstream row(line);std::string id,encoded;int mode,facade,level,alias;uint64_t len,limit;
  row>>id>>mode>>facade>>level>>alias>>len>>limit>>encoded;
  auto bytes=unhex(encoded=="-"?"":encoded);Star::ByteArray input(bytes.data(),bytes.size()), out("sentinel",8);std::string error;
  // Aliasing probes stay within an existing allocation; compressed input fits one slab,
  // so inflate consumes it before output overwrites those bytes. No dangling pointers.
  input.reserve(262144);out.reserve(262144);auto* stable=input.ptr();
  Star::ByteArray& dest=alias?input:out;
#ifdef LAB_RUST
  uint64_t counters[3][3];
  for(unsigned k=0;k<3;++k)for(unsigned e=0;e<3;++e)counters[k][e]=star_compression_call_count(k,e);
#endif
  try {
   if(mode==0) { if(facade==0) C::compressData(input,dest,level); else dest=C::compressData(input,level); }
   else if(mode==1) {switch(facade){
    case 0:C::uncompressData(input.ptr(),len,dest,limit);break;
    case 1:dest=C::uncompressData(input.ptr(),len,limit);break;
    case 2:C::uncompressData(input,dest,limit);break;
    case 3:dest=C::uncompressData(input,limit);break;
   }} else {switch(facade){
    case 0:C::uncompressDataGzip(input.ptr(),len,dest,limit);break;
    case 1:dest=C::uncompressDataGzip(input.ptr(),len,limit);break;
    case 2:C::uncompressDataGzip(input,dest,limit);break;
    case 3:dest=C::uncompressDataGzip(input,limit);break;
   }}
  } catch(std::exception const& e){error=Star::printException(e,false);}
#ifdef LAB_RUST
  for(unsigned k=0;k<3;++k)for(unsigned e=0;e<3;++e) {
   uint64_t expected=k==unsigned(mode) && (e==0 || (e==1 && error.empty()) || (e==2 && !error.empty()));
   if(star_compression_call_count(k,e)-counters[k][e]!=expected)throw std::runtime_error("COMPARISON selected controller TLS receipt");
  }
#endif
  std::cout<<id<<'\t'<<hex(error.data(),error.size())<<'\t'<<hex(dest.ptr(),dest.size())<<'\t'<<hex(input.ptr(),input.size())<<'\t'<<dest.capacity()<<'\t'<<(input.ptr()==stable)<<'\n';
 }
} catch(std::exception const& e) { std::cerr<<e.what()<<'\n'; return 1; }
