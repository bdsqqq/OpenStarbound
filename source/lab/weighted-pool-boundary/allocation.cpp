// Only ordinary C++ operator-new calls are observed here, not Rust/runtime
// mallocs, platform OOM behavior, or performance. No tracing runs while armed.
#if !defined(WP_BOUNDARY_ON) || !WP_BOUNDARY_ON
#error "allocation fixture requires WP_BOUNDARY_ON=1"
#endif
#ifndef WP_ALLOCATION_HEADER
#define WP_ALLOCATION_HEADER "BoundaryWeightedPool.hpp"
#endif
#include WP_ALLOCATION_HEADER
#include "StarWeightedPool.hpp"
#include <cstdlib>
#include <iostream>
#include <new>
#include <stdexcept>

namespace {
bool tracking=false,deny=false;
size_t calls=0;
void* allocate(size_t bytes){
 if(tracking){++calls;if(deny)throw std::bad_alloc();}
 if(void* p=std::malloc(bytes?bytes:1))return p;
 throw std::bad_alloc();
}
struct Scope {
 explicit Scope(bool reject=false){calls=0;deny=reject;tracking=true;}
 ~Scope(){tracking=false;deny=false;}
 Scope(Scope const&)=delete;
};
// Empty range with native pointer cursors: no iterator/default/copy scaffolding.
struct EmptyContainer {
 Star::pair<double,int> const* begin()const{return nullptr;}
 Star::pair<double,int> const* end()const{return nullptr;}
};
struct Observation {size_t allocations;bool empty;size_t size,items,uniques,index;int selected;};
template<template<class> class Pool> Observation observe(bool reject){
 Observation o{};
 {
  Scope guard(reject);
  Pool<int> p(EmptyContainer{});
  auto unique=p.selectUniques(0,uint64_t(123));
  o.empty=p.empty();o.size=p.size();o.items=p.items().size();
  o.uniques=unique.size();o.index=p.selectIndex(uint64_t(123));
  o.selected=p.select(uint64_t(123));
  p.add(0,77);p.clear();
  o.empty=o.empty&&p.empty();o.size+=p.size();o.items+=p.items().size();
 }
 o.allocations=calls;
 return o;
}
bool sameState(Observation const&a,Observation const&b){
 return a.empty==b.empty&&a.size==b.size&&a.items==b.items&&a.uniques==b.uniques&&a.index==b.index&&a.selected==b.selected;
}
void need(bool value,char const*message){if(!value)throw std::runtime_error(message);}
}
void* operator new(size_t bytes){return allocate(bytes);}
void* operator new[](size_t bytes){return allocate(bytes);}
void operator delete(void* p)noexcept{std::free(p);}
void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,size_t)noexcept{std::free(p);}
void operator delete[](void* p,size_t)noexcept{std::free(p);}

int main(){
 try {
  auto original=observe<Star::WeightedPool>(false);
  need(original.allocations==0,"FAIL\toriginal empty native fixture unexpectedly allocated");
  need(original.empty&&original.size==0&&original.items==0&&original.uniques==0&&original.index==Star::NPos&&original.selected==0,"FAIL\toriginal empty native fixture state");
  auto originalDenied=observe<Star::WeightedPool>(true);
  need(sameState(original,originalDenied),"FAIL\toriginal denial changed native state");
  // Isolate the legacy closure allocation before the other boundary APIs. With
  // the retained header, constructing its range-loop std::function must throw.
  try {
   Scope guard(true);
   Star::BoundaryWeightedPool<int> p(EmptyContainer{});
  }catch(std::bad_alloc const&){
   std::cerr<<"FAIL\tboundary empty-container construction allocated native C++ storage\n";
   return 1;
  }
  auto boundary=observe<Star::BoundaryWeightedPool>(false);
  need(sameState(original,boundary),"FAIL\toriginal/boundary empty native state mismatch");
  need(boundary.allocations==original.allocations,"FAIL\tboundary added ordinary C++ operator-new calls");
  auto boundaryDenied=observe<Star::BoundaryWeightedPool>(true);
  need(sameState(original,boundaryDenied)&&boundaryDenied.allocations==0,"FAIL\tboundary denial changed native state or allocation count");
  std::cout<<"PASS\tnative-empty-allocation-parity\toriginal="<<original.allocations<<"\tboundary="<<boundary.allocations<<'\n'
           <<"PASS\tnative-closure-allocation-denied\tempty-container-and-seeded-zero-uniques\n";
  return 0;
 }catch(std::exception const&e){std::cerr<<e.what()<<'\n';return 1;}
}
