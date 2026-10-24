#include "StarRustCompression.h"
#include <cstdio>
#include <cstddef>
struct Event { uint32_t op; uint64_t scalar; uint32_t status; };
static Event const* events;
static size_t cursor, count;
static bool wrong;
static uint32_t host(void*, uint32_t op, uint64_t arg, uint64_t* scalar) noexcept {
  if(cursor==count) { wrong=true; return SC_HOST_INVALID; }
  auto e=events[cursor++];
  if(op!=e.op || (op!=SC_CLEAR_OUTPUT&&op!=SC_APPEND_TEMP&&op!=SC_RAISE_INIT&&op!=SC_RAISE_CODEC&&arg))wrong=true;
  if(e.status==SC_OK)*scalar=e.scalar;
  return wrong?SC_HOST_INVALID:e.status;
}
static bool replay(Event const* e,size_t n,uint32_t expected) {
  events=e;cursor=0;count=n;wrong=false;
  return star_compression_run(SC_INFLATE,host,nullptr)==expected&&!wrong&&cursor==count;
}
#define CHECK(x) do { if(!(x)){std::fprintf(stderr,"COMPARISON raw Rust ABI line %d\n",__LINE__);return 1;} } while(0)
int main() {
  CHECK(star_compression_call_count(99,0)==0&&star_compression_call_count(0,99)==0);
  CHECK(star_compression_run(99,host,nullptr)==SC_INVALID);
  CHECK(star_compression_run(0,nullptr,nullptr)==SC_INVALID);
  CHECK(star_compression_call_count(0,0)==0);
  Event empty[]={{0,0,0},{1,1,0}};
  CHECK(replay(empty,2,SC_COMPLETE));
  CHECK(star_compression_call_count(1,0)==1&&star_compression_call_count(1,1)==1&&star_compression_call_count(1,2)==0);
  Event pending[]={{0,0,1}};
  CHECK(replay(pending,1,SC_NATIVE_PENDING));
  CHECK(star_compression_call_count(1,0)==2&&star_compression_call_count(1,1)==1&&star_compression_call_count(1,2)==1);
  Event badRaise[]={{0,0,0},{1,0,0},{2,0,0},{3,0,0},{4,uint32_t(-2),0},{13,0,0}};
  CHECK(replay(badRaise,6,SC_INVALID));
  Event high[]={{0,0,0},{1,0,0},{2,0,0},{3,0,0},{4,1ull<<32,0}};
  CHECK(replay(high,5,SC_INVALID));
  // End's valid negative return must not overwrite the successful Step status.
  Event end[]={{0,0,0},{1,0,0},{2,0,0},{3,0,0},{4,0,0},{5,0,0},{6,0,0},{7,1,0},{8,32763,0},{12,uint32_t(-3),0},{8,32763,0},{9,0,0}};
  CHECK(replay(end,12,SC_COMPLETE));
  // The source while loop permits another non-full OK Step without a Reset.
  Event nonfull[]={{0,0,0},{1,0,0},{2,0,0},{3,0,0},{4,0,0},{5,0,0},{6,0,0},{7,0,0},{8,32763,0},{7,1,0},{8,32763,0},{12,0,0},{8,32763,0},{9,0,0}};
  CHECK(replay(nonfull,14,SC_COMPLETE));
  Event full[]={{0,0,0},{1,0,0},{2,0,0},{3,0,0},{4,0,0},{5,0,0},{6,0,0},{7,uint32_t(-5),0},{8,0,0},{9,0,0},{6,0,0},{10,0,0},{7,1,0},{8,32768,0},{12,0,0},{8,32768,0},{9,0,0}};
  CHECK(replay(full,17,SC_COMPLETE));
  CHECK(star_compression_call_count(1,0)==7&&star_compression_call_count(1,1)==4&&star_compression_call_count(1,2)==1);
  std::puts("PASS actual Rust ABI TLS/preflight/null-context/low32/raise-success/End/nonfull/zero-limit");
}
