#if defined(LIGHTING_LAB_EXPECT_CPP) && defined(STAR_USE_RUST_LIGHTING)
#error "lighting_lab_cpp must compile with STAR_USE_RUST_LIGHTING undefined"
#endif
#include <StarCellularLightArray.hpp>
#include <StarRustLighting.h>
#include "oracle/StarCellularLightArray.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstddef>
#include <future>
#include <iomanip>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

using namespace Star;
namespace {
// Keep these independent of the adapter's marshalling assumptions.
static_assert(sizeof(StarLightingParameters) == 28 && alignof(StarLightingParameters) == 4);
static_assert(offsetof(StarLightingParameters, spread_passes) == 0);
static_assert(offsetof(StarLightingParameters, spread_max_air) == 4);
static_assert(offsetof(StarLightingParameters, spread_max_obstacle) == 8);
static_assert(offsetof(StarLightingParameters, point_max_air) == 12);
static_assert(offsetof(StarLightingParameters, point_max_obstacle) == 16);
static_assert(offsetof(StarLightingParameters, point_obstacle_boost) == 20);
static_assert(offsetof(StarLightingParameters, point_additive) == 24);
static_assert(sizeof(StarLightingCell) == 16 && alignof(StarLightingCell) == 4);
static_assert(offsetof(StarLightingCell, light) == 0 && offsetof(StarLightingCell, obstacle) == 12);
static_assert(sizeof(StarLightingSpreadLight) == 20 && alignof(StarLightingSpreadLight) == 4);
static_assert(offsetof(StarLightingSpreadLight, position) == 0 && offsetof(StarLightingSpreadLight, value) == 8);
static_assert(sizeof(StarLightingPointLight) == 36 && alignof(StarLightingPointLight) == 4);
static_assert(offsetof(StarLightingPointLight, position) == 0 && offsetof(StarLightingPointLight, value) == 8);
static_assert(offsetof(StarLightingPointLight, beam) == 20);
static_assert(offsetof(StarLightingPointLight, beam_angle) == 24);
static_assert(offsetof(StarLightingPointLight, beam_ambience) == 28);
static_assert(offsetof(StarLightingPointLight, as_spread) == 32);

constexpr double AbsTolerance = 1e-5;
constexpr double RelTolerance = 1e-5;

// Bit classification survives the production -ffast-math assumption of finiteness.
bool finite(float v) {
  uint32_t bits;
  std::memcpy(&bits, &v, sizeof(bits));
  return (bits & 0x7f800000u) != 0x7f800000u;
}
bool equal(float a, float b) {
  return finite(a) && finite(b) && std::abs(double(a) - b) <=
      AbsTolerance + RelTolerance * std::max(std::abs(double(a)), std::abs(double(b)));
}
struct Light {
  float x, y;
  Vec3F value;
  float beam = 0, angle = 0, ambience = 0;
  bool asSpread = false;
};
struct Input {
  std::string name;
  size_t w = 19, h = 17;
  size_t xmin = 1, ymin = 1, xmax = 18, ymax = 16;
  unsigned passes = 2;
  float spreadAir = 6, spreadObstacle = 2, pointAir = 7, pointObstacle = 2, boost = 0.8f;
  bool additive = false;
  std::vector<Vec3F> initial;
  std::vector<bool> obstacles;
  std::vector<Light> spread, point;
  // Negative means no independent expected-value assertion for this fixture.
  float expectedAt33 = -1;
  void clear() { initial.assign(w*h, Vec3F{}); obstacles.assign(w*h, false); }
};
void dump(Input const& c) {
  std::cerr << std::setprecision(9) << "input " << c.name << " size=" << c.w << ',' << c.h
    << " query=" << c.xmin << ',' << c.ymin << ',' << c.xmax << ',' << c.ymax
    << " parameters=" << c.passes << ',' << c.spreadAir << ',' << c.spreadObstacle << ','
    << c.pointAir << ',' << c.pointObstacle << ',' << c.boost << ',' << c.additive << '\n';
  for (size_t i=0;i<c.initial.size();++i) {
    auto v=c.initial[i];
    if (c.obstacles[i] || v[0] || v[1] || v[2])
      std::cerr << "cell " << i/c.h << ',' << i%c.h << " rgb=" << v[0] << ',' << v[1] << ',' << v[2] << " obstacle=" << c.obstacles[i] << '\n';
  }
  for (int kind=0;kind<2;++kind)
    for (auto const& l : kind ? c.point : c.spread)
      std::cerr << (kind ? "point " : "spread ") << l.x << ',' << l.y << " rgb=" << l.value[0] << ',' << l.value[1] << ',' << l.value[2]
        << " beam=" << l.beam << ',' << l.angle << ',' << l.ambience << " asSpread=" << l.asSpread << '\n';
}
template <typename Value> Value value(Vec3F const& v) {
  if constexpr (std::is_same_v<Value,float>) return v[0];
  else return v;
}
float channel(float v, size_t) { return v; }
float channel(Vec3F const& v, size_t i) { return v[i]; }
template <typename Array> void load(Array& a, Input const& c) {
  a.setParameters(c.passes,c.spreadAir,c.spreadObstacle,c.pointAir,c.pointObstacle,c.boost,c.additive);
  a.begin(c.w,c.h);
  for(size_t x=0;x<c.w;++x) for(size_t y=0;y<c.h;++y) {
    size_t i=x*c.h+y;
    // Check clearing before writing fixtures, otherwise stale begin() state is hidden.
    if(a.getLight(x,y)!=typename Array::LightValue{} || a.getObstacle(x,y))
      throw std::runtime_error("begin did not clear cells: "+c.name);
    auto v=value<typename Array::LightValue>(c.initial[i]);
    if(i%3==0) a.setLight(x,y,v);
    else if(i%3==1) a.cell(x,y).light=v;
    else a.cellAtIndex(i).light=v;
    a.setObstacle(x,y,c.obstacles[i]);
  }
  for(auto const& l:c.spread) a.addSpreadLight({Vec2F(l.x,l.y),value<typename Array::LightValue>(l.value)});
  for(auto const& l:c.point) a.addPointLight({Vec2F(l.x,l.y),value<typename Array::LightValue>(l.value),l.beam,l.angle,l.ambience,l.asSpread});
}
template <typename Array> void calculate(Array& a, Input const& c) { a.calculate(c.xmin,c.ymin,c.xmax,c.ymax); }
struct Statistics { size_t compared=0, failures=0; double maxAbsolute=0, maxRatio=0; };
template <typename Actual,typename Oracle> bool compare(Actual const& a, Oracle const& o, Input const& c, Statistics& s, bool inject, unsigned repeat) {
  constexpr size_t channels=std::is_same_v<typename Actual::LightValue,float> ? 1 : 3;
  bool ok=true;
  size_t worstX=0,worstY=0,worstChannel=0;
  float worstA=0,worstO=0;
  double worstRatio=-1;
  for(size_t x=0;x<c.w;++x) for(size_t y=0;y<c.h;++y) {
    if(a.getObstacle(x,y)!=o.getObstacle(x,y)) {ok=false; ++s.failures;}
    for(size_t k=0;k<channels;++k) {
      float av=channel(a.getLight(x,y),k), ov=channel(o.getLight(x,y),k);
      if(channel(a.cellAtIndex(x*c.h+y).light,k)!=av || channel(a.cell(x,y).light,k)!=av) {
        ok=false; ++s.failures;
      }
      if(inject && x==c.w/2 && y==c.h/2 && k==0) av+=0.125f;
      double error=std::abs(double(av)-ov);
      double ratio=error/(AbsTolerance+RelTolerance*std::max(std::abs(double(av)),std::abs(double(ov))));
      ++s.compared;
      s.maxAbsolute=std::max(s.maxAbsolute,error);
      s.maxRatio=std::max(s.maxRatio,ratio);
      if(!equal(av,ov)) {ok=false; ++s.failures;}
      if(!finite(av)||!finite(ov)||ratio>worstRatio) {worstRatio=ratio;worstX=x;worstY=y;worstChannel=k;worstA=av;worstO=ov;}
    }
  }
  if(!ok) {
    std::cerr << std::setprecision(10) << "MISMATCH mode=" << LIGHTING_LAB_MODE << " channels=" << channels << " repeat=" << repeat
      << " case=" << c.name << " worst=" << worstX << ',' << worstY << ',' << worstChannel
      << " actual=" << worstA << " oracle=" << worstO << " tolerance_ratio=" << worstRatio << '\n';
    dump(c);
  }
  return ok;
}
std::vector<Input> deterministic() {
  std::vector<Input> out;
  auto add=[&](Input c,std::string name) {c.name=std::move(name);out.push_back(std::move(c));};
  Input c; c.clear(); add(c,"empty");
  c.initial[8*c.h+8]=Vec3F(2.5f,0.7f,1.3f); c.initial[9*c.h+8]=Vec3F(0.1f,3.0f,0.2f);
  add(c,"initial-hdr-spread");
  c.spread={{8.25f,7.75f,Vec3F(2,0.4f,1.1f)},{-0.25f,4.25f,Vec3F(1,0.2f,0.5f)},
    {18.75f,16.75f,Vec3F(1,2,0.5f)},{-4,-4,Vec3F(2,2,2)}};
  add(c,"spread-placement-clipped");
  for(size_t y=1;y<c.h-1;++y)c.obstacles[10*c.h+y]=true;
  c.point={{7.5f,8.5f,Vec3F(2.4f,1.3f,0.7f)},{7.5f,8.5f,Vec3F(0.4f,1.2f,2.1f)},
    {-1,5,Vec3F(2,2,2)},{20,5,Vec3F(2,2,2)}};
  add(c,"obstacle-overlap-max-center");
  c.boost=-0.25f; add(c,"negative-obstacle-boost"); c.boost=0.8f;
  c.additive=true; add(c,"obstacle-overlap-additive-center");
  c.point[0].asSpread=true; c.point[1].asSpread=true; add(c,"as-spread-additive");
  c.additive=false; add(c,"as-spread-max");
  c.point[0].asSpread=false; c.point[1].asSpread=false;
  for(float beam:{0.00005f,0.0001f,0.0001001f,0.5f,4.0f}) {
    c.point[0].beam=beam; c.point[0].angle=1.3f; c.point[0].ambience=0.15f;
    add(c,"beam-threshold-1e8-units-"+std::to_string(int(beam*100000000)));
  }
  c.xmin=6;c.ymin=5;c.xmax=12;c.ymax=11;add(c,"query-subrect");
  c.xmax=c.xmin;c.ymax=c.ymin;add(c,"query-empty");
  c=Input{};c.clear();c.xmin=0;c.ymin=0;c.xmax=c.w;c.ymax=c.h;
  c.spread={{0,0,Vec3F(1,2,3)},{19,17,Vec3F(1,1,1)}};add(c,"full-grid-spread-only");
  c=Input{};c.w=3;c.h=3;c.xmax=2;c.ymax=2;c.clear();c.initial[4]=Vec3F(1,2,3);add(c,"minimum-safe-grid");
  c=Input{};c.clear();add(c,"empty-after-resize");add(c,"empty-same-size-begin");
  c=Input{};c.clear();c.passes=0;c.pointAir=5;c.additive=false;
  Light a{3.5f,3.5f,Vec3F(0.5f,0.5f,0.5f)}, b{4.5f,3.5f,Vec3F(1,1,1)};
  // At (3,3), A uses the distance-zero addition branch, even in max mode.
  // B contributes 1 - 1/5 = .8: max(.5,.8) != max(0,.8)+.5.
  c.point={a,b};c.expectedAt33=0.8f;add(c,"nonadditive-source-order-A-B");
  c.point={b,a};c.expectedAt33=1.3f;add(c,"nonadditive-source-order-B-A");
  for(bool steep:{false,true}) for(bool half:{false,true}) {
    c=Input{};c.w=83;c.h=83;c.xmin=2;c.ymin=2;c.xmax=81;c.ymax=81;
    c.passes=0;c.pointAir=128;c.pointObstacle=128;c.clear();
    // Long shallow/steep rays cross this wall and a staggered second wall.
    // Both endpoint pixels stay allocated, including zero-weight Wu neighbors.
    for(size_t minor=2;minor<81;++minor) {
      c.obstacles[steep ? minor*c.h+32 : 32*c.h+minor]=true;
      if(minor%3!=0)c.obstacles[steep ? minor*c.h+55 : 55*c.h+minor]=true;
    }
    float major=half?4.5f:4.25f, minor=half?6.5f:6.75f;
    c.point={{steep?minor:major,steep?major:minor,Vec3F(1,0.7f,0.4f)},
      {steep?15.25f:76.5f,steep?76.5f:15.25f,Vec3F(0.6f,1,0.8f)}};
    add(c,std::string("long-obstructed-")+(steep?"steep-":"shallow-")+(half?"half":"fractional"));
  }
  return out;
}
struct Random {
  std::mt19937 engine;
  explicit Random(uint32_t seed):engine(seed){}
  uint32_t n(uint32_t limit) {return engine()%limit;}
  float f(float max=1) {return (engine()>>8)*(1.0f/16777216.0f)*max;}
  Vec3F rgb() {return Vec3F(f(3),f(3),f(3));}
};
Input generated(Random& r,size_t index) {
  Input c;c.name="random-"+std::to_string(index);c.w=9+r.n(25);c.h=9+r.n(25);
  c.xmax=c.w-1;c.ymax=c.h-1;c.clear();c.passes=r.n(5);
  c.spreadAir=1+r.f(10);c.spreadObstacle=0.5f+r.f(4);c.pointAir=1+r.f(12);c.pointObstacle=0.5f+r.f(5);c.boost=r.f(2);c.additive=r.n(2);
  if(r.n(2)) {c.xmin=2;c.ymin=2;c.xmax=c.w-2;c.ymax=c.h-2;}
  for(size_t i=0;i<c.initial.size();++i) {c.obstacles[i]=r.n(5)==0;if(r.n(15)==0)c.initial[i]=r.rgb();}
  size_t ns=r.n(8),np=r.n(9);
  for(size_t i=0;i<ns;++i)c.spread.push_back({r.f(c.w+4)-2,r.f(c.h+4)-2,r.rgb()});
  // Inset sources and query keep both Wu endpoint pixels inside the oracle allocation.
  for(size_t i=0;i<np;++i)c.point.push_back({2+r.f(c.w-4),2+r.f(c.h-4),r.rgb(),r.n(3)?r.f(5):0,r.f(6.2831853f),r.f(),bool(r.n(2))});
  return c;
}
template <typename Actual,typename Oracle> bool suite(std::vector<Input> const& cases,Statistics& s,bool inject) {
  Actual actual;Oracle oracle;
  for(auto const& c:cases) {
    load(actual,c);load(oracle,c);
    if(actual.borderCells()!=oracle.borderCells())throw std::runtime_error("borderCells differs");
    for(unsigned repeat=0;repeat<2;++repeat) {
      calculate(actual,c);calculate(oracle,c);
      if(!compare(actual,oracle,c,s,inject,repeat))return false;
      if(c.expectedAt33>=0) {
        constexpr size_t channels=std::is_same_v<typename Actual::LightValue,float>?1:3;
        float expected=c.expectedAt33+0.5f*repeat;
        for(size_t k=0;k<channels;++k)
          if(!equal(channel(actual.getLight(3,3),k),expected) ||
              !equal(channel(oracle.getLight(3,3),k),expected))
            throw std::runtime_error("source-order expected value failed: "+c.name+" repeat="+std::to_string(repeat));
      }
    }
  }
  return true;
}
volatile double benchmarkSink=0;
template <typename Array> void benchmark(Input const& c,char const* name) {
  Array a;std::vector<double> times;double checksum=0;
  for(unsigned sample=0;sample<13;++sample) {
    load(a,c);
    auto start=std::chrono::steady_clock::now();calculate(a,c);auto end=std::chrono::steady_clock::now();
    if(sample>=2)times.push_back(std::chrono::duration<double,std::micro>(end-start).count());
    for(size_t x=0;x<c.w;++x)for(size_t y=0;y<c.h;++y) {
      constexpr size_t n=std::is_same_v<typename Array::LightValue,float>?1:3;
      for(size_t k=0;k<n;++k)checksum+=channel(a.getLight(x,y),k)*(1+(x*c.h+y)%17);
    }
  }
  benchmarkSink=checksum;std::sort(times.begin(),times.end());
  std::cout << "benchmark " << name << " median_us=" << times[times.size()/2] << " samples=" << times.size() << " checksum=" << std::setprecision(15) << checksum << '\n';
}
}
int main(int argc,char** argv) {
  try {
    uint32_t seed=1592594996;size_t randomCount=128;bool inject=false,selfTest=false,bench=false;
    for(int i=1;i<argc;++i) {
      std::string arg=argv[i];
      if(arg=="--seed"&&i+1<argc)seed=std::stoul(argv[++i],nullptr,0);
      else if(arg=="--random"&&i+1<argc)randomCount=std::stoul(argv[++i]);
      else if(arg=="--inject-mismatch")inject=true;
      else if(arg=="--self-test")selfTest=true;
      else if(arg=="--benchmark")bench=true;
      else if(arg=="--help") {std::cout<<"--seed N --random N --self-test --inject-mismatch --benchmark\n";return 0;}
      else throw std::runtime_error("invalid argument: "+arg);
    }
    if(selfTest) {
      Input c;c.clear();c.name="deliberate-perturbation";
      ScalarCellularLightArray a;LightingOracle::ScalarCellularLightArray o;load(a,c);load(o,c);
      calculate(a,c);calculate(o,c);
      Statistics s;bool detected=!compare(a,o,c,s,true,0);
      if(!detected || !equal(1.0f,1.000001f) || equal(1.0f,1.01f) || equal(NAN,0.0f))return 2;
      std::cout<<"self-test: deliberate output perturbation detected\n";return 0;
    }
    auto cases=deterministic();Random r(seed);
    for(size_t i=0;i<randomCount;++i)cases.push_back(generated(r,i));
    std::cout<<"mode="<<LIGHTING_LAB_MODE<<" seed="<<seed<<" cases="<<cases.size()<<" abs_tol="<<AbsTolerance<<" rel_tol="<<RelTolerance<<'\n';
    Statistics s;
    bool scalar=suite<ScalarCellularLightArray,LightingOracle::ScalarCellularLightArray>(cases,s,inject);
    bool rgb=suite<ColoredCellularLightArray,LightingOracle::ColoredCellularLightArray>(cases,s,inject);
    std::cout<<"compared="<<s.compared<<" failures="<<s.failures<<" max_abs="<<s.maxAbsolute<<" max_tolerance_ratio="<<s.maxRatio<<'\n';
    if(!scalar||!rgb)return 1;
    // Each worker owns its arrays and statistics; only immutable inputs are shared.
    // Compare the entire corpus again to catch cross-instance mutable state.
    auto scalarTask=std::async(std::launch::async,[&cases] {
      Statistics stats;
      if(!suite<ScalarCellularLightArray,LightingOracle::ScalarCellularLightArray>(cases,stats,false))
        throw std::runtime_error("concurrent scalar differential failed");
      return stats;
    });
    auto rgbTask=std::async(std::launch::async,[&cases] {
      Statistics stats;
      if(!suite<ColoredCellularLightArray,LightingOracle::ColoredCellularLightArray>(cases,stats,false))
        throw std::runtime_error("concurrent RGB differential failed");
      return stats;
    });
    auto cs=scalarTask.get(), cr=rgbTask.get();
    if(cs.compared+cr.compared!=s.compared || cs.failures+cr.failures!=0 ||
        std::max(cs.maxAbsolute,cr.maxAbsolute)!=s.maxAbsolute ||
        std::max(cs.maxRatio,cr.maxRatio)!=s.maxRatio)
      throw std::runtime_error("concurrent results differ from serial statistics");
    std::cout<<"concurrent: independent scalar/RGB instances, full corpus, compared="
      <<cs.compared+cr.compared<<" failures="<<cs.failures+cr.failures<<"; serial statistics match\n";
    if(bench) {
      Input c;c.name="benchmark";c.w=96;c.h=80;c.xmax=95;c.ymax=79;c.clear();c.additive=true;
      for(size_t i=0;i<c.obstacles.size();++i)c.obstacles[i]=r.n(7)==0;
      for(size_t i=0;i<48;++i) {Light l{2+r.f(c.w-4),2+r.f(c.h-4),r.rgb(),r.f(3),r.f(6),0.2f,bool(r.n(2))};c.point.push_back(l);c.spread.push_back(l);}
      benchmark<ScalarCellularLightArray>(c,"adapter-scalar");benchmark<LightingOracle::ScalarCellularLightArray>(c,"oracle-scalar");
      benchmark<ColoredCellularLightArray>(c,"adapter-rgb");benchmark<LightingOracle::ColoredCellularLightArray>(c,"oracle-rgb");
    }
    return 0;
  } catch(std::exception const& e) {std::cerr<<"lighting_lab: "<<e.what()<<'\n';return 2;}
}
