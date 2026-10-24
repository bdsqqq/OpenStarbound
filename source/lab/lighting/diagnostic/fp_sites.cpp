// Standalone probes: frozen arithmetic is included, never modified.
#include "StarList.hpp"
#include "StarVector.hpp"
// Expose only the frozen class's private ray for a standalone diagnostic.
#define private public
#include "../oracle/StarCellularLightArray.hpp"
#undef private
#ifndef PROBE
#define PROBE precise
#endif
#define JOIN_(a,b) a##b
#define JOIN(a,b) JOIN_(a,b)
extern "C" void JOIN(PROBE,_spread)(float const* src, float const* dst, float drop, float* out) {
  auto v = Star::LightingOracle::ColoredLightTraits::spread(Star::Vec3F(src[0],src[1],src[2]),Star::Vec3F(dst[0],dst[1],dst[2]),drop);
  for(int i=0;i<3;++i) out[i]=v[i];
}
extern "C" void JOIN(PROBE,_subtract)(float const* src, float drop, float* out) {
  auto v = Star::LightingOracle::ColoredLightTraits::subtract(Star::Vec3F(src[0],src[1],src[2]),drop);
  for(int i=0;i<3;++i) out[i]=v[i];
}
extern "C" float JOIN(PROBE,_distance)(float x, float y) { return Star::Vec2F(x,y).magnitude(); }
extern "C" float JOIN(PROBE,_diag)(float air) { return 1.0f / air * Star::Constants::sqrt2; }
extern "C" float JOIN(PROBE,_circular)(float obstacleDistance,float directionMax) { return (1.0f/obstacleDistance)/directionMax; }
extern "C" void JOIN(PROBE,_source)(float xdist,float ydist,float att,float* out) {
 out[0]=att*(2.0f-(1.0f-xdist)-(1.0f-ydist));
 out[1]=att*(2.0f-(1.0f-xdist)-ydist);
 out[2]=att*(2.0f-xdist-(1.0f-ydist));
 out[3]=att*(2.0f-xdist-ydist);
}
extern "C" float JOIN(PROBE,_line)(float x,float y,float per,float limit) {
 Star::LightingOracle::ColoredCellularLightArray a;
 a.begin(32,32);
 for(size_t cx=0;cx<32;++cx) for(size_t cy=0;cy<32;++cy) a.setObstacle(cx,cy,cx==10||cy==12);
 return a.lineAttenuation(Star::Vec2F(4.5f,4.5f),Star::Vec2F(x,y),per,limit);
}
extern "C" void JOIN(PROBE,_direction)(float x,float y,float distance,float* out) {
 auto v=Star::Vec2F(x,y)/distance;out[0]=v[0];out[1]=v[1];
}
