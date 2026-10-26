// Finite zero-fill primitive regression. Other null spans remain invalid.
#include "StarByteArray.hpp"
#include <cstdio>
#include <array>
using namespace Star;
#ifdef STAR_USE_RUST_BYTE_ARRAY
static uint32_t fill(ByteArray& b,uint64_t role,uint64_t byte,uint64_t reserved,uint64_t& out) {
  ByteArrayRust::NativeCtx c;c.owner=&b;
  return ByteArrayRust::nativeHost(&c,SB_BA_FILL_BYTES,role,byte,reserved,&out);
}
#endif
int main() {
#ifdef STAR_USE_RUST_BYTE_ARRAY
  ByteArray b;uint64_t out=99;
  if(fill(b,0,37,0,out)!=0 || out!=0 || b.size()!=0 || b.ptr()!=nullptr) return 1;
  for(auto args : {std::array<uint64_t,3>{0,256,0}, {0,0,1}, {4,0,0}}) {
    out=99;if(fill(b,args[0],args[1],args[2],out)!=2 || out!=99) return 2;
  }
  ByteArrayNativeAccess::size(b)=1;
  out=99;auto rejected=fill(b,0,0,0,out);
  ByteArrayNativeAccess::size(b)=0;
  if(rejected!=2 || out!=99) return 3;
  ByteArray allocated(1,'K');auto size=allocated.size();
  ByteArrayNativeAccess::size(allocated)=allocated.capacity()+1;
  out=99;rejected=fill(allocated,0,0,0,out);
  ByteArrayNativeAccess::size(allocated)=size;
  if(rejected!=2 || out!=99 || allocated[0]!='K') return 4;
#endif
  std::puts("EMPTY_FILL_LEAF_GUARDS_PASS");return 0;
}
