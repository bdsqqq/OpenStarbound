#include "aliases.h"
#include <array>
#include <cstdio>
#include <cstring>
#include <thread>
static unsigned checks = 0;
#define CHECK(x) do { ++checks; if (!(x)) { std::printf("FAIL %u line %u\n", checks, __LINE__); return 1; } } while (0)
int main() {
  uint32_t action = 88;
  for (uint32_t m = 0; m < 4; ++m) CHECK(pe_select(m, &action) == 0 && action == m);
  CHECK(pe_completed(0) == 4 && pe_completed(1) == 0);
  for (auto m : {4u, UINT32_MAX}) { action=88; CHECK(pe_select(m,&action)==2 && action==88 && pe_completed(0)==4); }
  CHECK(pe_select(0,nullptr)==2 && pe_completed(0)==4);
  alignas(size_t) std::array<uint8_t,64> owned{};
  owned.fill(0x55); auto original=owned;
  CHECK(pe_select(0,reinterpret_cast<uint32_t*>(owned.data()+1))==2 && owned==original);
  uint8_t input[] = {'%',':','?',';','/',0,255};
  size_t written=999;
  auto reject=[&](uint8_t const* in,size_t n,uint8_t* out,size_t cap,size_t* w) {
    auto before=owned; auto old=written; auto calls=pe_completed(1);
    return pe_escape(in,n,out,cap,w)==2 && owned==before && written==old && pe_completed(1)==calls;
  };
  CHECK(reject(input,7,owned.data(),13,&written));
  CHECK(reject(nullptr,7,owned.data(),14,&written));
  CHECK(reject(input,7,nullptr,14,&written));
  CHECK(reject(input,7,owned.data(),14,nullptr));
  CHECK(reject(input,SIZE_MAX,owned.data(),64,&written));
  CHECK(reject(input,7,owned.data(),SIZE_MAX,&written));
  CHECK(reject(owned.data(),7,owned.data()+2,14,&written));
  CHECK(reject(input,7,owned.data(),14,reinterpret_cast<size_t*>(owned.data())));
  CHECK(reject(owned.data(),16,owned.data()+32,32,reinterpret_cast<size_t*>(owned.data())));
  CHECK(reject(input,7,owned.data(),14,reinterpret_cast<size_t*>(owned.data()+17)));
  CHECK(pe_escape(input,7,owned.data(),14,&written)==0 && written==12);
  uint8_t expected[]={'%','%','%','c','%','q','%','s','%','b',0,255};
  CHECK(std::memcmp(owned.data(),expected,12)==0 && pe_completed(1)==1);
  CHECK(pe_escape(nullptr,0,nullptr,0,&written)==0 && written==0 && pe_completed(1)==2);
  CHECK(pe_span_eligible(static_cast<size_t>(PTRDIFF_MAX)/2,static_cast<size_t>(PTRDIFF_MAX)-1)==1);
  CHECK(pe_span_eligible(static_cast<size_t>(PTRDIFF_MAX)/2+1,static_cast<size_t>(PTRDIFF_MAX))==0);
  CHECK(pe_span_eligible(0,SIZE_MAX)==0 && pe_completed(99)==0);
  bool tls=false; std::thread other([&]{uint32_t a;tls=pe_completed(0)==0 && pe_completed(1)==0 && pe_select(2,&a)==0 && a==2 && pe_completed(0)==1;});other.join();
  CHECK(tls && pe_completed(0)==4 && pe_completed(1)==2);
  std::printf("protocol %u checks passed; counters selector=4 escape=2\n",checks);
}
