#include "facade.hpp"
#include <iostream>
#include <sstream>
#include <typeinfo>
using namespace Star;
std::string hex(std::string const& s) {
  static char const* digits="0123456789abcdef";
  std::string out; for (unsigned char c:s) { out+=digits[c>>4];out+=digits[c&15]; }return out;
}
std::string raw(std::string const& h) {
  std::string s;for(size_t i=0;i<h.size();i+=2)s+=static_cast<char>(std::stoul(h.substr(i,2),nullptr,16));return s;
}
int main() {
#ifndef LEAF_ONLY
  static_assert(None==0 && Gzip==1 && Zlib==2 && Zstd==3,"public enum");
  for(int i=0;i<4;++i)std::cout<<"enum-"<<i<<"\tok\t"<<hex(EmbeddedCompressionMethodNames.getRight(static_cast<EmbeddedCompressionMethod>(i)).utf8())<<'\n';
#endif
  std::string line;
  while(std::getline(std::cin,line)) {
    std::istringstream row(line);std::string name,op,method,h;
    std::getline(row,name,'\t');std::getline(row,op,'\t');std::getline(row,method,'\t');std::getline(row,h);
    auto bytes=raw(h);int m=std::stoi(method);
#ifdef LEAF_ONLY
    if(op!="C" || (m!=2 && m!=3))continue;
    ByteArray input(bytes.data(),bytes.size());
    auto output=m==2?compressData(input):ZstdCompression::compress(input);
    std::cout<<name<<"\tleaf\t"<<hex(output.empty() ? std::string{} : std::string(output.ptr(),output.size()))<<'\n';
#else
    try {
      String output;
      // Construct raw storage directly: String::size() would decode invalid UTF-8.
      if(op=="E")output=PathEmbedBoundary::escape(String(std::string(bytes)));
      else { ByteArray input(bytes.data(),bytes.size());auto e=static_cast<EmbeddedCompressionMethod>(m);output=PathEmbedBoundary::compress(input,e); }
      std::cout<<name<<"\tok\t"<<hex(output.utf8())<<'\n';
    }catch(StarException const& e) {
      std::cout<<name<<'\t'<<(typeid(e)==typeid(StarException)?"StarException":"derived-exception")<<'\t'<<hex(e.what())<<'\n';
    }
#endif
  }
}
