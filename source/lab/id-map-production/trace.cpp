#include "StarIdMap.hpp"
#include "../id-map-boundary/trace_key.hpp"
#ifdef STAR_USE_RUST_ID_MAP
void productionRoots(){
 uint64_t before[10];for(unsigned m=0;m<10;++m)before[m]=sb_idmap_count(m,0);
 Star::IdMap<uint32_t,uint32_t> defaults,a(1,3),b(1,3);a.add(1,10);check(a.nextId()==2,"production collision");check(a.add(20)==3,"production autoadd");
 check(a!=b&&!(a==b),"production const comparison");Star::DataStreamBuffer stream;stream<<a;stream.seek(0);stream>>b;check(a==b,"production stream");a.clear();
 for(unsigned m=0;m<10;++m)check(sb_idmap_count(m,0)>before[m],"all production Rust roots");
 std::cout<<"PASS\tproduction-ten-rust-roots\n";
}
#endif
int main(){try{keyTraces();
#ifdef STAR_USE_RUST_ID_MAP
productionRoots();
#endif
return 0;}catch(std::exception const& e){std::cerr<<"FAIL\t"<<e.what()<<'\n';return 1;}catch(...){std::cerr<<"FAIL\tunknown\n";return 1;}}
