#include "StarLine.hpp"
#include "reference.hpp"
#include "mutants.hpp"
#include <cstdint>
#include <cstring>
#include <iostream>
#include <fstream>
#include <string>
#include <vector>

// This is the observation boundary. Future production adapters must return this
// complete tuple; the frozen reference and independent anchors stay unchanged.
template <typename T> struct Observation {
  bool intersects, coincides, glances, predicate;
  T x, y, t, projection, distance;
};
template <typename T, typename L>
Observation<T> observe(L const& a, L const& b, Star::Vector<T,2> const& p, bool infinite) {
  auto r = a.intersection(b, infinite);
  return {r.intersects,r.coincides,r.glances,a.intersects(b,infinite),r.point[0],r.point[1],r.t,
    a.lineProjection(p),a.distanceTo(p,infinite)};
}
#include "Production.hpp"

template <typename T> uint64_t bits(T value) {
  using U = typename std::conditional<sizeof(T)==4,uint32_t,uint64_t>::type;
  U u; std::memcpy(&u,&value,sizeof(T)); return u;
}
template <typename T> bool nanBits(T value) {
  uint64_t u=bits(value), exp=sizeof(T)==4?0x7f800000ULL:0x7ff0000000000000ULL;
  uint64_t mant=sizeof(T)==4?0x007fffffULL:0x000fffffffffffffULL;
  return (u&exp)==exp && (u&mant)!=0;
}
template <typename T> bool same(T a,T b) {
  // NaN is classified, never approximately equal to a number. No promise about
  // NaN payload/sign propagation; ALL other values, including +/-0, are bit exact.
  return bits(a)==bits(b) || (nanBits(a)&&nanBits(b));
}
size_t checks=0,cases=0,failures=0,nonfinite=0;
uint64_t rustCalls=0;
std::string mutation;
std::ofstream observations;
template <typename T> void writeObservation(Observation<T> const& r) {
  observations << int(r.intersects) << int(r.coincides) << int(r.glances) << int(r.predicate);
  for(T n:{r.x,r.y,r.t,r.projection,r.distance}) observations << ' ' << std::hex << bits(n) << std::dec;
}
void check(bool ok,std::string const& what) {
  ++checks;
  if (!ok) { ++failures; if(failures<12) std::cerr<<"FAIL "<<what<<'\n'; }
}
template <typename T> void compare(Observation<T> const& a,Observation<T> const& b,std::string const& label) {
  check(a.intersects==b.intersects,label+" intersects");
  check(a.coincides==b.coincides,label+" coincides");
  check(a.glances==b.glances,label+" glances");
  check(a.predicate==b.predicate,label+" predicate");
  check(same(a.x,b.x),label+" point.x"); check(same(a.y,b.y),label+" point.y");
  check(same(a.t,b.t),label+" t"); check(same(a.projection,b.projection),label+" projection");
  check(same(a.distance,b.distance),label+" distance");
}
template <typename T> void test(T ax,T ay,T bx,T by,T cx,T cy,T dx,T dy,T px,T py,bool infinite) {
  using V=Star::Vector<T,2>; using L=Star::Line<T,2>; using F=FrozenReference::Line<T,2>;
  auto expected=observe<T>(F(V(ax,ay),V(bx,by)),F(V(cx,cy),V(dx,dy)),V(px,py),infinite);
  L a(V(ax,ay),V(bx,by)),b(V(cx,cy),V(dx,dy));
#if defined(STAR_USE_RUST_LINE_QUERY) || defined(STAR_LINE_LAB_DIRECT_ABI)
  auto before=star_line_query_call_count();
#endif
  auto actual=Production::query<T>(a,b,V(px,py),infinite);
#if defined(STAR_USE_RUST_LINE_QUERY) || defined(STAR_LINE_LAB_DIRECT_ABI)
  auto calls=star_line_query_call_count()-before;
  rustCalls+=calls;
  check(calls==4,"four successful Rust query receipts");
#endif
  if(mutation=="direction") actual=observe<T>(DirectionMutant::Line<T,2>(V(ax,ay),V(bx,by)),DirectionMutant::Line<T,2>(V(cx,cy),V(dx,dy)),V(px,py),infinite);
  if(mutation=="coincident-selection") actual=observe<T>(CoincidentMutant::Line<T,2>(V(ax,ay),V(bx,by)),CoincidentMutant::Line<T,2>(V(cx,cy),V(dx,dy)),V(px,py),infinite);
  if(mutation=="glancing") actual=observe<T>(GlancingMutant::Line<T,2>(V(ax,ay),V(bx,by)),GlancingMutant::Line<T,2>(V(cx,cy),V(dx,dy)),V(px,py),infinite);
  if(mutation=="point") actual.x=T(123);
  if(mutation=="t") actual.t=T(123);
  if(mutation=="projection-clamp") actual.projection=Star::clamp<T>(actual.projection,0,1);
  if(mutation=="numeric-field") actual.distance=T(123);
  if(observations.is_open()) {
    observations << (sizeof(T)==4?"f32":"f64") << ' ' << infinite;
    for(T n:{ax,ay,bx,by,cx,cy,dx,dy,px,py}) observations << ' ' << std::hex << bits(n) << std::dec;
    observations << " | "; writeObservation(expected);
    observations << " | "; writeObservation(actual); observations << '\n';
  }
  compare(expected,actual,std::to_string(cases++)+(sizeof(T)==4?" f32":" f64")+(infinite?" infinite":" segment"));
  for(T n:{expected.x,expected.y,expected.t,expected.projection,expected.distance}) {
    uint64_t mask=sizeof(T)==4?0x7f800000ULL:0x7ff0000000000000ULL;
    if((bits(n)&mask)==mask) ++nonfinite;
  }
}
uint64_t seed=0x6c696e6551756572ULL;
uint64_t randomWord(){ seed^=seed<<13; seed^=seed>>7; seed^=seed<<17; return seed; }
template <typename T> T raw() {
  using U=typename std::conditional<sizeof(T)==4,uint32_t,uint64_t>::type;
  U u=U(randomWord()); T t; std::memcpy(&t,&u,sizeof(T)); return t;
}
template <typename T> void suite() {
  using V=Star::Vector<T,2>; using F=FrozenReference::Line<T,2>;
  // Independently calculated anchors, NOT candidate/reference agreement.
  auto cross=observe<T>(F(V(0,0),V(2,0)),F(V(1,-1),V(1,1)),V(3,0),false);
  check(cross.intersects&&!cross.coincides&&!cross.glances&&cross.predicate,"cross flags anchor");
  check(cross.x==T(1)&&cross.y==T(0)&&cross.t==T(.5),"cross point/t anchor");
  check(cross.projection==T(1.5)&&cross.distance==T(1),"unclamped projection/clamped distance anchor");
  auto overlap=observe<T>(F(V(0,0),V(4,0)),F(V(2,0),V(6,0)),V(3,4),false);
  check(overlap.intersects&&overlap.coincides&&overlap.glances&&overlap.x==T(2)&&overlap.t==T(.5),"coincident anchor");
  auto miss=observe<T>(F(V(0,0),V(1,0)),F(V(2,-1),V(2,1)),V(2,0),false);
  check(!miss.intersects&&miss.x==T(2)&&miss.t==T(2),"false flag computed fields anchor");
  auto reversed=observe<T>(F(V(4,0),V(0,0)),F(V(-2,0),V(2,0)),V(0,0),false);
  check(!reversed.intersects&&reversed.coincides&&reversed.x==T(0)&&reversed.t==T(.5),"lexicographic reversed default point anchor");
  auto endpoint=observe<T>(F(V(0,0),V(2,0)),F(V(2,0),V(2,2)),V(3,0),false);
  check(endpoint.intersects&&endpoint.glances&&endpoint.t==T(1),"endpoint glancing anchor");
  T outside=T(1)+std::numeric_limits<T>::epsilon();
  auto nearMiss=observe<T>(F(V(0,0),V(1,0)),F(V(outside,-1),V(outside,1)),V(0,0),false);
  check(!nearMiss.intersects&&!nearMiss.glances&&nearMiss.x==outside&&nearMiss.t==outside,"epsilon near-miss no false-positive flags anchor");
  auto parallel=observe<T>(F(V(0,0),V(2,0)),F(V(0,1),V(2,1)),V(0,0),false);
  check(!parallel.intersects&&!parallel.coincides&&!parallel.glances&&parallel.x==T(0)&&parallel.y==T(0)&&parallel.t==std::numeric_limits<T>::max(),"parallel default point and sentinel anchor");
  auto infiniteCross=observe<T>(F(V(0,0),V(1,0)),F(V(2,-1),V(2,1)),V(3,4),true);
  check(infiniteCross.intersects&&!infiniteCross.glances&&infiniteCross.t==T(2)&&infiniteCross.projection==T(3)&&infiniteCross.distance==T(4),"infinite projection/distance anchor");
  auto infiniteOverlap=observe<T>(F(V(0,0),V(4,0)),F(V(2,0),V(6,0)),V(0,0),true);
  check(infiniteOverlap.intersects&&infiniteOverlap.coincides&&infiniteOverlap.glances&&infiniteOverlap.x==-std::numeric_limits<T>::max()&&infiniteOverlap.y==-std::numeric_limits<T>::max()&&infiniteOverlap.t==T(.5),"infinite coincident sentinel anchor");
  std::vector<T> special={T(0),-T(0),T(1),T(-1),T(.1),T(.3),T(2),T(1)+std::numeric_limits<T>::epsilon(),std::numeric_limits<T>::min(),T(2)*std::numeric_limits<T>::min(),std::numeric_limits<T>::denorm_min(),std::numeric_limits<T>::max(),std::numeric_limits<T>::infinity(),-std::numeric_limits<T>::infinity(),std::numeric_limits<T>::quiet_NaN()};
  for(bool inf:{false,true}) {
    for(T v:special) {
      test<T>(0,0,2,0,v,-1,v,1,3,4,inf);
      test<T>(0,0,v,0,0,v,2,v,v,v,inf);
      test<T>(v,v,v,v,0,0,0,0,1,1,inf);
      test<T>(4,0,0,0,v,0,6,0,3,4,inf);
    }
    for(int i=0;i<5000;++i) {
      T v[10]; for(auto& n:v) n=i%2 ? raw<T>() : T(int64_t(randomWord()%200001)-100000)/T(317);
      test<T>(v[0],v[1],v[2],v[3],v[4],v[5],v[6],v[7],v[8],v[9],inf);
    }
    // Explicit endpoints, parallel disjoint, overlaps, reversal and zero length.
    test<T>(0,0,2,0,2,0,2,2,3,0,inf);
    test<T>(0,0,2,0,0,1,2,1,3,0,inf);
    test<T>(0,0,2,0,3,0,4,0,3,0,inf);
    test<T>(0,0,0,0,1,1,2,2,0,0,inf);
  }
  // Replay EVERY independent anchor through the candidate seam as well.
  test<T>(0,0,2,0,1,-1,1,1,3,0,false);
  test<T>(0,0,4,0,2,0,6,0,3,4,false);
  test<T>(0,0,1,0,2,-1,2,1,2,0,false);
  test<T>(4,0,0,0,-2,0,2,0,0,0,false);
  test<T>(0,0,2,0,2,0,2,2,3,0,false);
  test<T>(0,0,1,0,outside,-1,outside,1,0,0,false);
  test<T>(0,0,2,0,0,1,2,1,0,0,false);
  test<T>(0,0,1,0,2,-1,2,1,3,4,true);
  test<T>(0,0,4,0,2,0,6,0,0,0,true);
}
int main(int argc,char** argv) {
  if(argc>1) mutation=argv[1];
  if(argc>2) { observations.open(argv[2]); if(!observations) return 2; }
  suite<float>(); suite<double>();
  std::cout<<"{\"cases\":"<<cases<<",\"checks\":"<<checks<<",\"failures\":"<<failures<<",\"nonfinite_fields\":"<<nonfinite<<",\"rust_calls\":"<<rustCalls<<"}\n";
  return failures?1:0;
}
