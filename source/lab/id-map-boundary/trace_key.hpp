// Literal pre-protocol trace shard from frozen controls.cpp.
#pragma once
#include "StarDataStreamDevices.hpp"
#include <iostream>
#include <stdexcept>
#include <string>
#include <type_traits>
using namespace Star;
namespace {
void check(bool b,char const* why){if(!b)throw std::runtime_error(why);}
struct Marker{void const* identity;};
struct Key {
 static std::string trace;static bool failCopy;static int token;int value;
 Key(int v=0):value(v){trace+="V"+std::to_string(v)+";";}
 Key(Key const& k):value(k.value){trace+="C"+std::to_string(value)+";";if(failCopy)throw Marker{&token};}
 Key(Key&& k):value(k.value){trace+="M"+std::to_string(value)+";";}
 Key& operator=(Key const& k){value=k.value;trace+="A"+std::to_string(value)+";";return *this;}
 ~Key(){trace+="D"+std::to_string(value)+";";}
 friend bool operator>(Key const& a,Key const& b){return a.value>b.value;}
 friend bool operator>(Key const& a,int b){return a.value>b;}
 friend int operator-(Key const& a,Key const& b){return a.value-b.value;}
 friend bool operator<(Key const& a,Key const& b){return a.value<b.value;}
 friend bool operator>=(Key const& a,Key const& b){return a.value>=b.value;}
 friend bool operator==(Key const& a,Key const& b){return a.value==b.value;}
 friend Key operator+(Key const& a,int b){return Key(a.value+b);}
};
std::string Key::trace;bool Key::failCopy=false;int Key::token=0;
struct Opaque {Opaque()=default;Opaque(Opaque const&)=delete;};
// No mapped storage, copying or streaming API is needed by these operations.
struct TinyBase {
 using iterator=int*;using const_iterator=int const*;using key_type=Key;
 using mapped_type=Opaque;using value_type=std::pair<Key,Opaque>;
 static int occupancy;static bool collide;static int equality;
 int size()const{return occupancy;}bool contains(Key const& k)const{return collide&&k.value==10;}
 void clear(){}bool operator==(TinyBase const&)const{++equality;return true;}
 bool operator==(TinyBase const&){throw std::runtime_error("nonconst equality selected");}
 template<class A,class B>void insert(A const&,B const&)=delete;
 void keys();void values();void pairs();void empty();void get();void ptr();void maybe();void take();
 void maybeTake();void remove();void value();void begin();void end();void erase();
};
int TinyBase::occupancy=0;bool TinyBase::collide=false;int TinyBase::equality=0;
void keyTraces(){
 IdMapWrapper<TinyBase> map(Key(10),Key(12));
 for(bool collision:{false,true}){
  map.clear();TinyBase::collide=collision;Key::trace.clear();
  {auto id=map.nextId();check(id.value==(collision?11:10),"typed cursor result");std::cout<<"TRACE\tkey-"<<collision<<"\t"<<Key::trace<<'\n';}
 }
 TinyBase::collide=false;TinyBase::occupancy=9;Key::failCopy=true;Key::trace.clear();
 try{map.nextId();throw std::runtime_error("fullness missing");}catch(IdMapException const&){}
 std::cout<<"TRACE\tfull-before-copy\t"<<Key::trace<<'\n';
 TinyBase::occupancy=0;Key::trace.clear();
 try{map.nextId();throw std::runtime_error("copy failure missing");}catch(Marker const& m){check(m.identity==&Key::token,"copy exception identity");}
 Key::failCopy=false;std::cout<<"TRACE\tlocal-copy-failure\t"<<Key::trace<<'\n';
 IdMapWrapper<TinyBase> other(Key(10),Key(12)),different(Key(20),Key(22));
 TinyBase::equality=0;auto const& a=map;auto const& b=other;check(a==b,"const equal");check(!(a!=b),"nested not equal");check(!(a==different),"bounds short circuit");check(TinyBase::equality==2,"base equality short circuit and constness");
 std::cout<<"TRACE\tconst-equality\t"<<TinyBase::equality<<'\n';
#ifdef IDMAP_LAZY_AUTO_NEGATIVE
 map.add(Opaque{});
#endif
}

}
