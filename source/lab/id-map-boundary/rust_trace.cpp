#include "StarIdMap.hpp"
#include "trace_key.hpp"
namespace {
void actualRoots(){
 uint64_t before[10][2];for(unsigned m=0;m<10;++m)for(unsigned st=0;st<2;++st)before[m][st]=sb_idmap_count(m,st);
 IdMap<uint32_t,uint32_t> defaults;IdMap<uint32_t,uint32_t> a(1,3),b(1,3);
 a.add(1,10);check(a.nextId()==2,"actual Rust collision loop");check(a.add(20)==3,"actual Rust named insertion");
 try{a.add(1,99);throw std::runtime_error("duplicate missing");}catch(IdMapException const&){}
 a.add(2,30);try{a.nextId();throw std::runtime_error("fullness missing");}catch(IdMapException const&){}
 check(a!=b&&!(a==b),"actual Rust equal/negation");DataStreamBuffer stream;stream<<a;stream.seek(0);stream>>b;check(a==b,"actual Rust stream sequence");a.clear();b.clear();
 for(unsigned m=0;m<10;++m){check(sb_idmap_count(m,0)>before[m][0],"every actual Rust root entered");check((sb_idmap_count(m,1)>before[m][1])==(m==SB_IDMAP_NEXT||m==SB_IDMAP_ADD_AUTO),"only two continuation routes");}
 check(sb_idmap_count(10,0)==0&&sb_idmap_count(0,2)==0,"invalid counter routes");
 std::cout<<"PASS\tactual-rust-ten-roots-two-continuations\n";
 int token=0;auto f=IdMapBoundary::makeFrame(SB_IDMAP_NEXT,SB_IDMAP_ROOT,[](uint32_t op){return op==SB_IDMAP_FULL;},[&](uint32_t)->SbIdMapReply{throw Marker{&token};},[]{return false;});
 bool caught=false;try{f.run();}catch(Marker const& e){caught=e.identity==&token;}check(caught,"native exception identity outside actual Rust");
 std::cout<<"PASS\tactual-rust-native-exception-identity\n";
}
struct Foreign{unsigned touched=0;uint32_t status=99;};
uint32_t foreign(void* c,SbIdMapRequest const*,SbIdMapReply* out)noexcept{auto& f=*static_cast<Foreign*>(c);++f.touched;*out=IdMapBoundary::boolReply(false);return f.status;}
void abiControls(){
 Foreign f;auto result=IdMapBoundary::voidReply();auto q=result;
 check(sb_idmap_run(SB_IDMAP_NEXT,SB_IDMAP_ROOT,&f,foreign,&result)==SB_IDMAP_INVALID&&f.touched==1&&result.tag==q.tag&&!result.value,"actual Rust unknown status normalization/output unchanged");
 for(auto status:{SB_IDMAP_EXCEPTION,SB_IDMAP_INVALID,SB_IDMAP_PANIC}){f.status=status;check(sb_idmap_run(SB_IDMAP_NEXT,SB_IDMAP_ROOT,&f,foreign,&result)==uint32_t(status)&&!result.value,"actual Rust upstream status propagation");}
 auto before=f.touched;
 check(sb_idmap_run(10,0,&f,foreign,&result)==SB_IDMAP_INVALID&&sb_idmap_run(0,2,&f,foreign,&result)==SB_IDMAP_INVALID&&sb_idmap_run(0,0,nullptr,foreign,&result)==SB_IDMAP_INVALID&&sb_idmap_run(0,0,&f,nullptr,&result)==SB_IDMAP_INVALID&&sb_idmap_run(0,0,&f,foreign,nullptr)==SB_IDMAP_INVALID&&before==f.touched,"actual Rust route/null guards before native host");
 alignas(SbIdMapReply) unsigned char bytes[sizeof(SbIdMapReply)+1]{};check(sb_idmap_run(0,0,&f,foreign,reinterpret_cast<SbIdMapReply*>(bytes+1))==SB_IDMAP_INVALID&&before==f.touched,"actual Rust alignment guard");
 std::cout<<"PASS\tactual-rust-status-output-route-null-alignment\n";
}
}
int main(){try{keyTraces();actualRoots();abiControls();return 0;}catch(std::exception const& e){std::cerr<<"FAIL\t"<<e.what()<<'\n';return 1;}catch(...){std::cerr<<"FAIL\tunknown\n";return 1;}}
