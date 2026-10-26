// Source-derived empty-fill regression; no legacy-UB equivalence claim.
#include "StarByteArray.hpp"
#include "StarBuffer.hpp"
#include "StarDataStreamDevices.hpp"
#include <cstdio>
#include <cstring>
using namespace Star;
int main(int argc, char** argv) {
  if (argc != 2) return 2;
  try {
    if (!std::strcmp(argv[1], "default")) {
      ByteArray b; auto p=b.ptr(); auto c=b.capacity(); b.fill(size_t{0}, char{37});
      if (b.size()!=0 || b.ptr()!=p || b.capacity()!=c) return 3;
    } else if (!std::strcmp(argv[1], "moved")) {
      ByteArray b(1,'x'); ByteArray taken(std::move(b)); b.fill(size_t{0},char{37});
      if (b.size()!=0 || b.ptr()!=nullptr || b.capacity()!=0 || taken.size()!=1 || taken[0]!='x') return 4;
    } else if (!std::strcmp(argv[1], "reserved")) {
      ByteArray b(4,'Q'); auto p=b.ptr(); auto c=b.capacity(); b.fill(size_t{0},char{37});
      if(b.size()!=0 || b.ptr()!=p || b.capacity()!=c) return 5;
      for(unsigned i=0;i<4;++i) if(p[i]!='Q') return 6;
    } else if (!std::strcmp(argv[1], "buffer")) {
      Buffer b; b.write("x",1); auto taken=b.takeData();
      if(b.dataSize()!=0 || b.pos()!=0 || taken.size()!=1 || taken[0]!='x') return 7;
      b.write("y",1); if(b.dataSize()!=1) return 8;
    } else if (!std::strcmp(argv[1], "stream")) {
      auto bytes=DataStreamBuffer::serialize(uint8_t{42});
      if(bytes.size()!=1 || static_cast<unsigned char>(bytes[0])!=42) return 9;
    } else return 2;
    std::puts("EMPTY_FILL_CASE_PASS"); return 0;
  } catch(std::exception const& e) { std::fprintf(stderr,"EMPTY_FILL_EXCEPTION %s\n",e.what()); return 10; }
}
