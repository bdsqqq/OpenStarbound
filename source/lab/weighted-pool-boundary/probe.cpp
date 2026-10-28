#include "BoundaryWeightedPool.hpp"
#include "StarWeightedPool.hpp"
#include "StarWeightedPool.original.hpp"
#include <iostream>
#include <type_traits>
#include <stdexcept>
using namespace Star;
static void need(bool b,char const* why){if(!b)throw std::runtime_error(why);}
struct Lazy {int value;Lazy()=delete;explicit Lazy(int v):value(v){}Lazy(Lazy&&)=default;Lazy(Lazy const&)=delete;Lazy&operator=(Lazy&&)=default;};
struct Custom {pair<double,int> v[2]{{1,30},{1,40}};struct End{pair<double,int>* p;};struct It {pair<double,int>*p;auto const& operator*()const{return *p;}void operator++(){++p;}bool operator!=(End e)const{return p!=e.p;}};It begin(){return {v};}End end(){return {v+2};}};
namespace Adl {struct Range {pair<double,int> v[2]{{1,50},{1,60}};};auto begin(Range& r){return r.v;}auto end(Range& r){return r.v+2;}}
static void controls(){using namespace WpBoundary;int touched=0,sentinel=0;bool throwing=false;auto f=makeFrame([](uint32_t op,uint64_t a){return op==SB_WP_COUNT&&!a;},[&](uint32_t,uint64_t){if(throwing)throw &sentinel;++touched;return reply(SB_WP_U64,7);});SbWpRequest q{24,1,SB_WP_COUNT,0,0};
 for(int k=0;k<12;++k){auto x=q;auto r=reply();switch(k){case 0:x.size=23;break;case 1:x.version=2;break;case 2:x.reserved=1;break;case 3:x.op=0;break;case 4:x.op=29;break;case 5:x.op=SB_WP_CLEAR_ITEMS;break;case 6:x.arg=1;break;case 7:r.size=23;break;case 8:r.version=2;break;case 9:r.tag=SB_WP_U64;break;case 10:r.reserved=1;break;case 11:r.value=1;break;}need(Frame::host(f.context(),&x,&r)==SB_WP_INVALID&&touched==0,"incoming malformed touched native");}
 auto r=reply();need(Frame::host(f.context(),&q,&r)==0&&touched==1&&r.value==7,"positive host");
 for(int k=0;k<7;++k){r=reply();uint32_t m=0,s=0;switch(k){case 0:m=19;break;case 1:s=4;break;case 2:s=1;break;case 3:r.size=8;break;case 4:r.version=2;break;case 5:r.tag=7;break;case 6:r.value=1;break;}need(sb_wp_run(m,s,f.context(),Frame::host,&r)==SB_WP_INVALID,"mock malformed accepted");}
 throwing=true;r=reply();need(Frame::host(f.context(),&q,&r)==SB_WP_EXCEPTION,"pointer throw not stopped");bool identity=false;try{f.run(5);}catch(int* e){identity=e==&sentinel;}need(identity,"native pointer exception identity");std::cout<<"PASS\t19-malformed-controls-native-pointer-exception\n";
}
static void real(){
 static_assert(sizeof(BoundaryWeightedPool<int>)==sizeof(WeightedPool<int>));static_assert(alignof(BoundaryWeightedPool<int>)==alignof(WeightedPool<int>));
 static_assert(std::is_standard_layout<BoundaryWeightedPool<int>>::value==std::is_standard_layout<WeightedPool<int>>::value);
 BoundaryWeightedPool<Lazy> lazy;lazy.add(1,Lazy(9));need(lazy.items()[0].second.value==9,"lazy add items");lazy.clear();
 BoundaryWeightedPool<int> a;WeightedPool<int>b;ReferenceWeightedPool<int>c;
 a.add(-1,9);b.add(-1,9);c.add(-1,9);for(int i=0;i<4;++i){a.add(1<<i,i);b.add(1<<i,i);c.add(1<<i,i);}
 need(&a.at(0)==&a.items()[0]&&&a.item(0)==&a.at(0).second&&a.weight(1)==2&&a.size()==4&&!a.empty(),"accessor aliases");
 for(uint64_t seed=0;seed<128;++seed){need(a.select(seed)==b.select(seed)&&a.select(seed)==c.select(seed),"real selection parity");need(a.selectIndex(seed)==b.selectIndex(seed)&&a.selectIndex(seed)==c.selectIndex(seed),"real scan parity");need(a.selectUniques(4,seed)==b.selectUniques(4,seed)&&a.selectUniques(4,seed)==c.selectUniques(4,seed),"real unique parity");}
 RandomSource ra(123),rb(123);for(int i=0;i<64;++i)need(a.select(ra)==b.select(rb),"source parity");
 Random::init(999);auto u=a.selectUniques(4);auto v=a.select();auto ix=a.selectIndex();Random::init(999);need(u==b.selectUniques(4)&&v==b.select()&&ix==b.selectIndex(),"global parity");
 auto copy=a;auto moved=std::move(copy);a.clear();need(a.empty()&&moved.size()==4,"implicit copy move");
 BoundaryWeightedPool<int> custom(Custom{});BoundaryWeightedPool<int> adl(Adl::Range{});need(custom.item(1)==40&&adl.item(1)==60,"member sentinel and ADL container");
 std::string actual,expected;try{moved.item(999);}catch(OutOfRangeException const&e){actual=e.what();}try{b.item(999);}catch(OutOfRangeException const&e){expected=e.what();}need(!actual.empty()&&actual==expected,"native what parity");
#if WP_BOUNDARY_ON
 for(unsigned m=0;m<19;++m)need(sb_wp_count(m,0)>0,"missing original root");for(unsigned s=1;s<4;++s)need(sb_wp_count(s==1?1:14,s)>0,"missing stage");
#endif
 std::cout<<"PASS\t19-root-4-stage-real-reference-layout-lazy-custom-containers\n";
}
int main(int argc,char**argv){try{controls();if(argc>1&&std::string(argv[1])=="known-failure"){need(false,"isolated known failing fixture");}real();return 0;}catch(std::exception const&e){std::cerr<<e.what()<<'\n';return 1;}}
