#include "BoundaryWeightedPool.hpp"
#include "StarWeightedPool.hpp"
#include <iostream>
#include <stdexcept>
namespace WpIntegration {
using namespace Star;
static void need(bool b,char const*w){if(!b)throw std::runtime_error(w);}
struct Stats {int begins=0,ends=0,compares=0,converts=0;};
struct Boolean {bool value;Stats*stats;explicit operator bool(){++stats->converts;return value;}bool operator!(){throw std::runtime_error("range-for must not call overloaded operator!");}};
struct FriendRange final {
 friend struct Star::WeightedPool<int>;friend struct Star::BoundaryWeightedPool<int>;
 explicit FriendRange(Stats& s):stats(&s){}
private:
 Stats*stats;pair<double,int> values[2]{{1,71},{1,72}};
 struct End {pair<double,int>*p;};
 struct It {pair<double,int>*p;Stats*s;It(pair<double,int>*x,Stats*y):p(x),s(y){}It(It const&)=delete;It(It&&)=default;auto const&operator*()const{return *p;}void operator++(){++p;}Boolean operator!=(End e)const{++s->compares;return {p!=e.p,s};}};
 It begin(){++stats->begins;return {values,stats};}End end(){++stats->ends;return {values+2};}
};
static void run(){
 Stats original,continued;WeightedPool<int> native(FriendRange{original});BoundaryWeightedPool<int>boundary(FriendRange{continued});need(native.items()==boundary.items(),"private-friend range values");need(original.begins==1&&original.ends==1&&original.compares==3&&original.converts==3,"original private range observation");need(continued.begins==1&&continued.ends==1&&continued.compares==3&&continued.converts==3,"continued range repeated comparison/access");
 using namespace WpBoundary;int touched=0,sentinel=0;int outcome=0;auto f=makeFrame([](uint32_t op,uint64_t a){return op==SB_WP_COUNT&&!a;},[&](uint32_t,uint64_t){++touched;if(outcome==1)throw &sentinel;return reply(SB_WP_U64,outcome==2?42:9);});SbWpRequest q{24,1,SB_WP_COUNT,0,0};auto output=reply(UINT32_MAX,UINT64_MAX);need(Frame::host(f.context(),&q,&output)==0&&touched==1&&output.tag==SB_WP_U64&&output.value==9,"Rust sentinel destination");
 auto initial=reply(SB_WP_U64,0xfeedface);need(sb_wp_run(0,0,f.context(),Frame::host,&initial)==0&&initial.tag==SB_WP_VOID&&!initial.value,"canonical root destination tags");
 auto unknown=+[](void*,SbWpRequest const*,SbWpReply*)->uint32_t{return 99;};auto unchanged=reply(SB_WP_U64,0xfeedface);auto before=unchanged;need(sb_wp_run(5,0,f.context(),unknown,&unchanged)==SB_WP_INVALID&&unchanged.tag==before.tag&&unchanged.value==before.value,"unknown host status normalization");
 outcome=1;output=reply();need(Frame::host(f.context(),&q,&output)==SB_WP_EXCEPTION&&touched==2,"captured native exception");outcome=2;output=reply();need(Frame::host(f.context(),&q,&output)==SB_WP_EXCEPTION&&touched==2,"pending exception must prevent later native mutation");bool same=false;try{f.run(5);}catch(int*e){same=e==&sentinel;}need(same,"pending exception pointer identity");
 std::cout<<"PASS\tprivate-friend-moveonly-cursor-distinct-sentinel-contextual-bool\nPASS\trust-destination-sentinel-root-tags-status-normalization\nPASS\tpending-native-exception-no-later-mutation\n";
}
}
#if WP_BOUNDARY_ATTACKS
extern "C" void sb_wp_mock_attacks(bool);
extern "C" uint64_t sb_wp_mock_rejected();
#endif
