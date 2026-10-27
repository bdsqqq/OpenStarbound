#include "StarPathEmbed.hpp"
#include "aliases.h"
#include <cstdio>
#include <typeinfo>
int main() {
  Star::ByteArray data("a",1); auto none=Star::None, gzip=Star::Gzip;
  auto a=Star::embedAndCompressData(data,none);
  if(a.utf8()!="YQ" || pe_completed(0)!=1) return 1;
  try { Star::embedAndCompressData(data,gzip); return 2; }
  catch(Star::StarException const& e) {
    if(typeid(e)!=typeid(Star::StarException) || std::string(e.what())!="(StarException) Compressing data in gzip is unsupported." || pe_completed(0)!=2) return 3;
  }
  auto b=Star::embedEscapeText(Star::String("%"));
  auto c=Star::embedAndCompressData(data,none);
  if(b.utf8()!="%%" || c.utf8()!="YQ" || pe_completed(0)!=3 || pe_completed(1)!=1) return 4;
  std::puts("normal-error-normal: exact native exception, selector completed before throw, subsequent calls work");
}
