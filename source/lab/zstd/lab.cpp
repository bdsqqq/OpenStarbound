#include "StarZSTDCompression.hpp"
#include "StarZSTDCompression.reference.hpp"
#include <zstd.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <memory>
#include <array>
#include <cstdlib>
#ifdef LAB_RUST
#include "StarRustZstd.h"
#endif
static std::array<uint64_t,12> counts(){
 std::array<uint64_t,12> r{};
#ifdef LAB_RUST
 for(unsigned m=0;m<4;++m)for(unsigned e=0;e<3;++e)r[m*3+e]=star_zstd_call_count(m,e);
#endif
 return r;
}
#ifdef LAB_REFERENCE
namespace C = ZstdReference;
#else
namespace C = Star;
#endif
std::string hex(char const* p,size_t n){static char const*h="0123456789abcdef";std::string s;s.reserve(n*2);for(size_t i=0;i<n;++i){unsigned char c=p[i];s+=h[c>>4];s+=h[c&15];}return s;}
std::string unhex(std::string s){std::string r;for(size_t i=0;i<s.size();i+=2)r+=char(std::stoi(s.substr(i,2),nullptr,16));return r;}
int main(int argc,char**argv)try{
 if(argc!=2)return 2;
 if(std::string(argv[1])=="--version"){std::cout<<ZSTD_versionString()<<'\n';return 0;}
 std::ifstream f(argv[1]);std::string line,group,previous;std::unique_ptr<C::CompressionStream> cs;std::unique_ptr<C::DecompressionStream> ds;
 while(std::getline(f,line)){
  std::istringstream row(line);std::string id,encoded;int mode,facade,level,alias;row>>id>>group>>mode>>facade>>level>>alias>>encoded;
  if(group!=previous){cs=std::make_unique<C::CompressionStream>();ds=std::make_unique<C::DecompressionStream>();previous=group;}
  auto bytes=unhex(encoded=="-"?"":encoded);Star::ByteArray input(bytes.data(),bytes.size()),out(8388608,char(0x6d));out.resize(2);out[0]=char(0xaa);out[1]=char(0x55);
  // Populate every byte of the allocation BEFORE shrinking: failed stream calls
  // retain grown logical sizes whose otherwise-uninitialized tails cannot be read.
  auto* stable=out.ptr();auto cap=out.capacity();if(alias){out.resize(bytes.size());for(size_t i=0;i<bytes.size();++i)out[i]=bytes[i];}
  Star::ByteArray const& in=alias?out:input;std::string error;
  auto before=counts();
  try{
   if(mode==0){switch(facade){case 0:out=C::ZstdCompression::compress(in.ptr(),in.size(),level);break;case 1:C::ZstdCompression::compress(in.ptr(),in.size(),out,level);break;case 2:out=C::ZstdCompression::compress(in,level);break;case 3:C::ZstdCompression::compress(in,out,level);break;}}
   if(mode==1){switch(facade){case 0:out=C::ZstdCompression::decompress(in.ptr(),in.size());break;case 1:C::ZstdCompression::decompress(in.ptr(),in.size(),out);break;case 2:out=C::ZstdCompression::decompress(in);break;case 3:C::ZstdCompression::decompress(in,out);break;}}
   if(mode==2){switch(facade){case 0:cs->compress(in.ptr(),in.size(),out);break;case 1:cs->compress(in,out);break;case 2:out=cs->compress(in.ptr(),in.size());break;case 3:out=cs->compress(in);break;}}
   if(mode==3){switch(facade){case 0:ds->decompress(in.ptr(),in.size(),out);break;case 1:ds->decompress(in,out);break;case 2:out=ds->decompress(in.ptr(),in.size());break;case 3:out=ds->decompress(in);break;}}
  }catch(std::exception const&e){error=Star::printException(e,false);}
  auto after=counts();
  if(auto path=std::getenv("ZSTD_RECEIPTS")){
   std::ofstream receipts(path,std::ios::app);receipts<<id;
   for(unsigned i=0;i<12;++i){auto delta=after[i]-before[i];receipts<<'\t'<<delta;
#ifdef LAB_RUST
    unsigned selected=(mode==0?2:mode==1?3:mode==2?0:1);unsigned event=i%3;
    uint64_t expected=i/3==selected && (event==0 || (event==1 && error.empty()) || (event==2 && !error.empty()));
    if(delta!=expected)throw std::runtime_error("Rust per-call receipt mismatch");
#else
    if(delta)throw std::runtime_error("native receipt nonzero");
#endif
   }receipts<<'\n';
  }
  if(mode>=2&&facade<2&&(out.ptr()!=stable||out.capacity()!=cap||out.size()>8388608))throw std::runtime_error("undefined allocation extent");
  // Returning stream failures leave the caller's initialized prefix untouched.
  std::cout<<id<<'\t'<<hex(error.data(),error.size())<<'\t'<<hex(out.ptr(),out.size())<<'\t'<<out.size()<<'\t'<<out.capacity()<<'\n';
 }
}catch(std::exception const&e){std::cerr<<e.what()<<'\n';return 1;}
