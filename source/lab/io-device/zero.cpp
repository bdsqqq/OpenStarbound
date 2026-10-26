#undef NDEBUG
#include "StarIODevice.hpp"
#include <cassert>
#include <iostream>
using namespace Star;
struct Zero:IODevice {
 std::string trace;
 size_t read(char*p,size_t n)override{trace+="r/"+std::to_string(p==nullptr)+"/"+std::to_string(n)+";";assert(!n);return 0;}
 size_t write(char const*p,size_t n)override{trace+="w/"+std::to_string(p==nullptr)+"/"+std::to_string(n)+";";assert(!n);return 0;}
 StreamOffset pos()override{trace+="p;";return 0;}void seek(StreamOffset,IOSeek)override{trace+="s;";}IODevicePtr clone()override{return {};}
};
int main(){Zero z;char nonnull='Q';z.readFull(nullptr,0);z.writeFull(nullptr,0);z.readFull(&nonnull,0);z.writeFull(&nonnull,0);ByteArray empty;assert(empty.ptr()==nullptr);z.writeBytes(empty);z.writeBytesAbsolute(0,empty);z.readFullAbsolute(0,nullptr,0);z.writeFullAbsolute(0,nullptr,0);auto bytes=z.readBytes(0);auto absolute=z.readBytesAbsolute(0,0);assert(bytes.empty()&&absolute.empty());std::cout<<z.trace<<"\n";}
