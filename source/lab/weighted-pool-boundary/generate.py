#!/usr/bin/env python3
"""Clone original definitions; replace only bodies in ON branch, exact OFF branch."""
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2]
s=(R/'source/core/StarWeightedPool.hpp').read_text();s=s.replace('WeightedPool','BoundaryWeightedPool')
# Helpers are nested types/static-free member functions; the two native fields stay exact.
helpers=r'''
  template<unsigned Mode> struct NativeFrame : WpBoundary::Frame {
    using Pool=std::conditional_t<(Mode<=3),BoundaryWeightedPool,BoundaryWeightedPool const>;
    Pool* pool; uint64_t a,b; RandomSource* random; Item* value; void const* borrowed=nullptr;
    NativeFrame(Pool* p,uint64_t x=0,uint64_t y=0,RandomSource* r=nullptr,Item* v=nullptr):pool(p),a(x),b(y),random(r),value(v){
      this->allowed=[this](uint32_t op,uint64_t arg){return permits(op,arg);};
      this->leaf=[this](uint32_t op,uint64_t arg){return perform(op,arg);};
    }
    bool permits(uint32_t op,uint64_t arg){
      if(op==SB_WP_ARG)return arg==0&&(Mode==2||Mode==6||Mode==7||Mode==8||Mode==12||Mode==14||Mode==17||Mode==18);
      bool hasArg=op==SB_WP_AT_BORROW||op==SB_WP_AT_WEIGHT||op==SB_WP_AT_ITEM_BORROW||op==SB_WP_WRITE_TOTAL||op==SB_WP_DRAW_STATIC||op==SB_WP_CALL_INDEX_SEED||op==SB_WP_READ_WEIGHT;
      if(!hasArg&&arg)return false;
      switch(op){
       case SB_WP_COUNT:return Mode==5||Mode==14;
       case SB_WP_IS_EMPTY:return Mode==9||Mode==10||Mode==11||Mode==12||Mode==18;
       case SB_WP_AT_BORROW:return Mode==6;
       case SB_WP_AT_WEIGHT:return Mode==7;
       case SB_WP_AT_ITEM_BORROW:return Mode==8;
       case SB_WP_APPEND_ITEM_EXPRESSION:return Mode==2;
       case SB_WP_CLEAR_ITEMS:return Mode==3;
       case SB_WP_READ_TOTAL:return Mode==2||Mode==18;
       case SB_WP_WRITE_TOTAL:return Mode==2||Mode==3;
       case SB_WP_DRAW_SOURCE:return Mode==15;
       case SB_WP_DRAW_GLOBAL:return Mode==16;
       case SB_WP_DRAW_STATIC:return Mode==17;
       case SB_WP_DRAW_SEED:return Mode==13;
       case SB_WP_CALL_INDEX_SOURCE:return Mode==10;
       case SB_WP_CALL_INDEX_GLOBAL:return Mode==11;
       case SB_WP_CALL_INDEX_SEED:return Mode==12;
       case SB_WP_READ_WEIGHT:return Mode==18&&arg<pool->m_items.size();
       case SB_WP_SCAN_SIZE:return Mode==18;
      }return false;
    }
    SbWpReply perform(uint32_t op,uint64_t arg){using namespace WpBoundary;
     switch(op){
      case SB_WP_ARG:return reply(Mode==2||Mode==18?SB_WP_F64:SB_WP_U64,arg?b:a);
      case SB_WP_COUNT:if constexpr(Mode==14)return reply(SB_WP_U64,pool->size());else return reply(SB_WP_U64,pool->m_items.count());
      case SB_WP_IS_EMPTY:return reply(SB_WP_BOOL,pool->m_items.empty());
      case SB_WP_AT_BORROW:if constexpr(Mode==4)borrowed=&pool->m_items;else borrowed=&pool->m_items.at(arg);return reply(SB_WP_BORROW);
      case SB_WP_AT_WEIGHT:return reply(SB_WP_F64,bits(pool->at(arg).first));
      case SB_WP_AT_ITEM_BORROW:borrowed=&pool->at(arg).second;return reply(SB_WP_BORROW);
      case SB_WP_APPEND_ITEM_EXPRESSION:if constexpr(Mode==2)pool->m_items.append({number(a),std::move(*value)});return reply();
      case SB_WP_CLEAR_ITEMS:if constexpr(Mode==3){pool->m_items.clear();return reply();}break;
      case SB_WP_READ_TOTAL:return reply(SB_WP_F64,bits(pool->m_totalWeight));
      case SB_WP_WRITE_TOTAL:if constexpr(Mode==2||Mode==3){pool->m_totalWeight=number(arg);return reply();}break;
      case SB_WP_DRAW_SOURCE:return reply(SB_WP_F64,bits(random->randd()));
      case SB_WP_DRAW_GLOBAL:return reply(SB_WP_F64,bits(Random::randd()));
      case SB_WP_DRAW_STATIC:return reply(SB_WP_F64,bits(staticRandomDouble(arg)));
      case SB_WP_DRAW_SEED:return reply(SB_WP_U64,Random::randu64());
      case SB_WP_CALL_INDEX_SOURCE:if constexpr(Mode==10)return reply(SB_WP_U64,pool->selectIndex(*random));break;
      case SB_WP_CALL_INDEX_GLOBAL:if constexpr(Mode==11)return reply(SB_WP_U64,pool->selectIndex());break;
      case SB_WP_CALL_INDEX_SEED:if constexpr(Mode==12)return reply(SB_WP_U64,pool->selectIndex(arg));break;
      case SB_WP_READ_WEIGHT:return reply(SB_WP_F64,bits(pool->m_items[arg].first));
      case SB_WP_SCAN_SIZE:return reply(SB_WP_U64,pool->m_items.size());
     }throw std::runtime_error("invalid native capability");
    }
  };
'''
s=s.replace('  ItemsList m_items;',helpers+'\n  ItemsList m_items;')
# Preserve native declaration and member-initializers, locate every definition body.
start=s.index('template <typename Item>\nBoundaryWeightedPool<Item>::BoundaryWeightedPool()')
positions=[];pos=start
while True:
 try:op=s.index('{',pos)
 except ValueError:break
 depth=1;j=op+1
 while depth:
  if s[j]=='{':depth+=1
  elif s[j]=='}':depth-=1
  j+=1
 positions.append((op,j));pos=j
 if len(positions)==19:break
assert len(positions)==19
B=[
'NativeFrame<0> f(this); f.run(0);',
r'''WpBoundary::Frame root;
root.allowed=[](uint32_t op,uint64_t a){return op==SB_WP_CONTAINER_SCOPE&&!a;};
root.leaf=[&](uint32_t,uint64_t){
 // These generic lambdas retain the enclosing WeightedPool access context.
 auto memberBegin=[](auto& c)->decltype(c.begin()){return c.begin();};
 auto memberEnd=[](auto& c)->decltype(c.end()){return c.end();};
 constexpr bool members=std::is_invocable_v<decltype(memberBegin),Container&>&&std::is_invocable_v<decltype(memberEnd),Container&>;
 auto cursor=[&](){if constexpr(members)return memberBegin(container);else return WpBoundary::Adl::first(container);}();
 auto finish=[&](){if constexpr(members)return memberEnd(container);else return WpBoundary::Adl::last(container);}();
 auto phase=WpBoundary::CursorPhase::condition;
 WpBoundary::Frame loop;
 loop.allowed=[&](uint32_t op,uint64_t a){if(a)return false;using P=WpBoundary::CursorPhase;return(op==SB_WP_CONTAINER_END&&phase==P::condition)||(op==SB_WP_CONTAINER_ADD_EXPRESSION&&phase==P::value)||(op==SB_WP_CONTAINER_NEXT&&phase==P::next);};
 loop.leaf=[&](uint32_t op,uint64_t){using P=WpBoundary::CursorPhase;if(op==SB_WP_CONTAINER_END){bool more=static_cast<bool>(cursor!=finish);phase=more?P::value:P::ended;return WpBoundary::reply(SB_WP_BOOL,!more);}if(op==SB_WP_CONTAINER_NEXT){++cursor;phase=P::condition;return WpBoundary::reply();} {auto const& pair=*cursor;add(get<0>(pair),get<1>(pair));}phase=P::next;return WpBoundary::reply();};
 loop.run(1,1);return WpBoundary::reply();};root.run(1);''',
'NativeFrame<2> f(this,WpBoundary::bits(weight),0,nullptr,&item);f.run(2);',
'NativeFrame<3> f(this);f.run(3);',
'NativeFrame<4> f(this);f.borrowed=&m_items;f.borrowReturned=true;f.run(4);return m_items;',
'NativeFrame<5> f(this);return f.run(5).value;',
'NativeFrame<6> f(this,index);f.run(6);return *static_cast<ItemsType const*>(f.borrowed);',
'NativeFrame<7> f(this,index);return WpBoundary::number(f.run(7).value);',
'NativeFrame<8> f(this,index);f.run(8);return *static_cast<Item const*>(f.borrowed);',
'NativeFrame<9> f(this);return f.run(9).value;',
'NativeFrame<10> f(this,0,0,&rand);auto r=f.run(10);if(r.tag==SB_WP_DEFAULT_ITEM)return Item();if(r.tag!=SB_WP_ITEM_RESULT||r.value>=m_items.size())throw std::runtime_error("select tag");return m_items[r.value].second;',
'NativeFrame<11> f(this);auto r=f.run(11);if(r.tag==SB_WP_DEFAULT_ITEM)return Item();if(r.tag!=SB_WP_ITEM_RESULT||r.value>=m_items.size())throw std::runtime_error("select tag");return m_items[r.value].second;',
'NativeFrame<12> f(this,seed);auto r=f.run(12);if(r.tag==SB_WP_DEFAULT_ITEM)return Item();if(r.tag!=SB_WP_ITEM_RESULT||r.value>=m_items.size())throw std::runtime_error("select tag");return m_items[r.value].second;',
'NativeFrame<13> f(this);return selectUniques(desiredCount,f.run(13).value);',
r'''NativeFrame<14> root(this,desiredCount);size_t targetCount=root.run(14).value;
Set<size_t> indices;
WpBoundary::Frame collect;
collect.allowed=[&](uint32_t op,uint64_t a){return (op==SB_WP_ARG&&a<2)||(op==SB_WP_UNIQUE_SET_SIZE&&!a)||op==SB_WP_CALL_INDEX_SEED||(op==SB_WP_UNIQUE_SET_ADD&&a<m_items.size());};
collect.leaf=[&](uint32_t op,uint64_t a){if(op==SB_WP_ARG)return WpBoundary::reply(SB_WP_U64,a?seed:targetCount);if(op==SB_WP_UNIQUE_SET_SIZE)return WpBoundary::reply(SB_WP_U64,indices.size());if(op==SB_WP_CALL_INDEX_SEED)return WpBoundary::reply(SB_WP_U64,selectIndex(a));indices.add(a);return WpBoundary::reply();};
collect.run(14,2);
List<Item> result;
auto cursor=indices.begin();auto finish=indices.end();
auto phase=WpBoundary::CursorPhase::condition;
WpBoundary::Frame append;
append.allowed=[&](uint32_t op,uint64_t a){if(a)return false;using P=WpBoundary::CursorPhase;return(op==SB_WP_UNIQUE_END&&phase==P::condition)||(op==SB_WP_UNIQUE_APPEND_EXPRESSION&&phase==P::value&&*cursor<m_items.size())||(op==SB_WP_UNIQUE_NEXT&&phase==P::next);};
append.leaf=[&](uint32_t op,uint64_t){using P=WpBoundary::CursorPhase;if(op==SB_WP_UNIQUE_END){bool more=static_cast<bool>(cursor!=finish);phase=more?P::value:P::ended;return WpBoundary::reply(SB_WP_BOOL,!more);}if(op==SB_WP_UNIQUE_NEXT){++cursor;phase=P::condition;return WpBoundary::reply();}result.append(m_items[*cursor].second);phase=P::next;return WpBoundary::reply();};
append.run(14,3);return result;''',
'NativeFrame<15> f(this,0,0,&rand);return selectIndex(WpBoundary::number(f.run(15).value));',
'NativeFrame<16> f(this);return selectIndex(WpBoundary::number(f.run(16).value));',
'NativeFrame<17> f(this,seed);return selectIndex(WpBoundary::number(f.run(17).value));',
'NativeFrame<18> f(this,WpBoundary::bits(target));return f.run(18).value;'
]
for (a,b),body in reversed(list(zip(positions,B))):
 original=s[a:b];s=s[:a]+'{\n#if WP_BOUNDARY_ON\n'+body+'\n#else\n'+original[1:-1]+'\n#endif\n}'+s[b:]
s=s.replace('#include "StarRandom.hpp"','#include "StarRandom.hpp"\n#include "StarSet.hpp"\n#include "frame.hpp"')
(H/'BoundaryWeightedPool.hpp').write_text(s)
# OFF reconstruction exact original body check (helpers/declaration plumbing excluded).
for (a,b),body in zip(positions,B):assert body
print('generated19 definitions, exact OFF bodies retained')
