#include "StarTtlCache.hpp"
#include "cache.hpp"
struct Nonassignable {
 Nonassignable()=default;Nonassignable(Nonassignable const&)=default;Nonassignable(Nonassignable&&)=default;
 Nonassignable& operator=(Nonassignable const&)=delete;
 Nonassignable& operator=(Nonassignable&&)=delete;
};
struct MoveOnly {
 MoveOnly()=default;MoveOnly(MoveOnly const&)=delete;MoveOnly(MoveOnly&&)=default;
 MoveOnly& operator=(MoveOnly const&)=delete;MoveOnly& operator=(MoveOnly&&)=delete;
};
template<class C> void reads(){C c(10,0,8,false);(void)c.timeToLive();(void)c.timeSmear();(void)c.maxSize();(void)c.currentSize();(void)c.ttlUpdateEnabled();(void)c.ptr(1);(void)c.keys();c.cleanup();c.clear();}
template void reads<Star::BoundaryTtlCache<int,Nonassignable>>();
template void reads<Star::BoundaryHashTtlCache<int,Nonassignable>>();
template void reads<Star::BoundaryTtlCache<int,MoveOnly>>();
template void reads<Star::BoundaryHashTtlCache<int,MoveOnly>>();
static_assert(sizeof(Star::BoundaryTtlCache<int,Nonassignable>)==sizeof(Star::TtlCache<int,Nonassignable>));
