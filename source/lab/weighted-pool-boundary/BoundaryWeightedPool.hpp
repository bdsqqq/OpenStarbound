#pragma once

#include "StarRandom.hpp"
#include "StarSet.hpp"
#include "frame.hpp"

namespace Star {

template <typename Item>
struct BoundaryWeightedPool {
public:
  typedef pair<double, Item> ItemsType;
  typedef List<ItemsType> ItemsList;

  BoundaryWeightedPool();

  template <typename Container>
  explicit BoundaryWeightedPool(Container container);

  void add(double weight, Item item);
  void clear();

  ItemsList const& items() const;

  size_t size() const;
  pair<double, Item> const& at(size_t index) const;
  double weight(size_t index) const;
  Item const& item(size_t index) const;
  bool empty() const;

  // Return item using the given randomness source
  Item select(RandomSource& rand) const;
  // Return item using the global randomness source
  Item select() const;
  // Return item using fast static randomness from the given seed
  Item select(uint64_t seed) const;

  // Return a list of n items which are selected uniquely (by index), where
  // n is the lesser of the desiredCount and the size of the pool.
  // This INFLUENCES PROBABILITIES so it should not be used where a
  // correct statistical distribution is required.
  List<Item> selectUniques(size_t desiredCount) const;
  List<Item> selectUniques(size_t desiredCount, uint64_t seed) const;

  size_t selectIndex(RandomSource& rand) const;
  size_t selectIndex() const;
  size_t selectIndex(uint64_t seed) const;

private:
  size_t selectIndex(double target) const;


  template<unsigned Mode> struct NativeFrame : WpBoundary::Frame {
    BoundaryWeightedPool* pool; uint64_t a,b; RandomSource* random; Item* value; void const* borrowed=nullptr;
    NativeFrame(BoundaryWeightedPool const* p,uint64_t x=0,uint64_t y=0,RandomSource* r=nullptr,Item* v=nullptr):pool(const_cast<BoundaryWeightedPool*>(p)),a(x),b(y),random(r),value(v){
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
       case SB_WP_AT_BORROW:return Mode==6||(Mode==4&&arg==0);
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
       case SB_WP_READ_WEIGHT:case SB_WP_SCAN_SIZE:return Mode==18;
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
      case SB_WP_CLEAR_ITEMS:pool->m_items.clear();return reply();
      case SB_WP_READ_TOTAL:return reply(SB_WP_F64,bits(pool->m_totalWeight));
      case SB_WP_WRITE_TOTAL:pool->m_totalWeight=number(arg);return reply();
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

  ItemsList m_items;
  double m_totalWeight;
};

template <typename Item>
BoundaryWeightedPool<Item>::BoundaryWeightedPool()
  : m_totalWeight(0.0) {
#if WP_BOUNDARY_ON
NativeFrame<0> f(this); f.run(0);
#else

#endif
}

template <typename Item>
template <typename Container>
BoundaryWeightedPool<Item>::BoundaryWeightedPool(Container container)
  : BoundaryWeightedPool() {
#if WP_BOUNDARY_ON
WpBoundary::Frame root;
root.allowed=[](uint32_t op,uint64_t a){return op==SB_WP_CONTAINER_SCOPE&&!a;};
root.leaf=[&](uint32_t,uint64_t){
 using std::begin;using std::end;
 auto cursor=begin(container);auto finish=end(container);
 WpBoundary::Frame loop;
 loop.allowed=[](uint32_t op,uint64_t a){return !a&&(op==SB_WP_CONTAINER_END||op==SB_WP_CONTAINER_ADD_EXPRESSION||op==SB_WP_CONTAINER_NEXT);};
 loop.leaf=[&](uint32_t op,uint64_t){if(op==SB_WP_CONTAINER_END)return WpBoundary::reply(SB_WP_BOOL,!(cursor!=finish));if(op==SB_WP_CONTAINER_NEXT){++cursor;return WpBoundary::reply();} {auto const& pair=*cursor;add(get<0>(pair),get<1>(pair));}return WpBoundary::reply();};
 loop.run(1,1);return WpBoundary::reply();};root.run(1);
#else

  for (auto const& pair : container)
    add(get<0>(pair), get<1>(pair));

#endif
}

template <typename Item>
void BoundaryWeightedPool<Item>::add(double weight, Item item) {
#if WP_BOUNDARY_ON
NativeFrame<2> f(this,WpBoundary::bits(weight),0,nullptr,&item);f.run(2);
#else

  if (weight <= 0.0)
    return;

  m_items.append({weight, std::move(item)});
  m_totalWeight += weight;

#endif
}

template <typename Item>
void BoundaryWeightedPool<Item>::clear() {
#if WP_BOUNDARY_ON
NativeFrame<3> f(this);f.run(3);
#else

  m_items.clear();
  m_totalWeight = 0.0;

#endif
}

template <typename Item>
auto BoundaryWeightedPool<Item>::items() const -> ItemsList const & {
#if WP_BOUNDARY_ON
NativeFrame<4> f(this);f.run(4);return *static_cast<ItemsList const*>(f.borrowed);
#else

  return m_items;

#endif
}

template <typename Item>
size_t BoundaryWeightedPool<Item>::size() const {
#if WP_BOUNDARY_ON
NativeFrame<5> f(this);return f.run(5).value;
#else

  return m_items.count();

#endif
}

template <typename Item>
pair<double, Item> const& BoundaryWeightedPool<Item>::at(size_t index) const {
#if WP_BOUNDARY_ON
NativeFrame<6> f(this,index);f.run(6);return *static_cast<ItemsType const*>(f.borrowed);
#else

  return m_items.at(index);

#endif
}

template <typename Item>
double BoundaryWeightedPool<Item>::weight(size_t index) const {
#if WP_BOUNDARY_ON
NativeFrame<7> f(this,index);return WpBoundary::number(f.run(7).value);
#else

  return at(index).first;

#endif
}

template <typename Item>
Item const& BoundaryWeightedPool<Item>::item(size_t index) const {
#if WP_BOUNDARY_ON
NativeFrame<8> f(this,index);f.run(8);return *static_cast<Item const*>(f.borrowed);
#else

  return at(index).second;

#endif
}

template <typename Item>
bool BoundaryWeightedPool<Item>::empty() const {
#if WP_BOUNDARY_ON
NativeFrame<9> f(this);return f.run(9).value;
#else

  return m_items.empty();

#endif
}

template <typename Item>
Item BoundaryWeightedPool<Item>::select(RandomSource& rand) const {
#if WP_BOUNDARY_ON
NativeFrame<10> f(this,0,0,&rand);auto r=f.run(10);if(r.tag==SB_WP_DEFAULT_ITEM)return Item();if(r.tag!=SB_WP_ITEM_RESULT||r.value>=m_items.size())throw std::runtime_error("select tag");return m_items[r.value].second;
#else

  if (m_items.empty())
    return Item();

  return m_items[selectIndex(rand)].second;

#endif
}

template <typename Item>
Item BoundaryWeightedPool<Item>::select() const {
#if WP_BOUNDARY_ON
NativeFrame<11> f(this);auto r=f.run(11);if(r.tag==SB_WP_DEFAULT_ITEM)return Item();if(r.tag!=SB_WP_ITEM_RESULT||r.value>=m_items.size())throw std::runtime_error("select tag");return m_items[r.value].second;
#else

  if (m_items.empty())
    return Item();

  return m_items[selectIndex()].second;

#endif
}

template <typename Item>
Item BoundaryWeightedPool<Item>::select(uint64_t seed) const {
#if WP_BOUNDARY_ON
NativeFrame<12> f(this,seed);auto r=f.run(12);if(r.tag==SB_WP_DEFAULT_ITEM)return Item();if(r.tag!=SB_WP_ITEM_RESULT||r.value>=m_items.size())throw std::runtime_error("select tag");return m_items[r.value].second;
#else

  if (m_items.empty())
    return Item();

  return m_items[selectIndex(seed)].second;

#endif
}

template <typename Item>
List<Item> BoundaryWeightedPool<Item>::selectUniques(size_t desiredCount) const {
#if WP_BOUNDARY_ON
NativeFrame<13> f(this);return selectUniques(desiredCount,f.run(13).value);
#else

  return selectUniques(desiredCount, Random::randu64());

#endif
}

template <typename Item>
List<Item> BoundaryWeightedPool<Item>::selectUniques(size_t desiredCount, uint64_t seed) const {
#if WP_BOUNDARY_ON
NativeFrame<14> root(this,desiredCount);size_t targetCount=root.run(14).value;
Set<size_t> indices;
WpBoundary::Frame collect;
collect.allowed=[](uint32_t op,uint64_t a){return (op==SB_WP_ARG&&a<2)||(op==SB_WP_UNIQUE_SET_SIZE&&!a)||op==SB_WP_CALL_INDEX_SEED||op==SB_WP_UNIQUE_SET_ADD;};
collect.leaf=[&](uint32_t op,uint64_t a){if(op==SB_WP_ARG)return WpBoundary::reply(SB_WP_U64,a?seed:targetCount);if(op==SB_WP_UNIQUE_SET_SIZE)return WpBoundary::reply(SB_WP_U64,indices.size());if(op==SB_WP_CALL_INDEX_SEED)return WpBoundary::reply(SB_WP_U64,selectIndex(a));indices.add(a);return WpBoundary::reply();};
collect.run(14,2);
List<Item> result;
auto cursor=indices.begin();auto finish=indices.end();
WpBoundary::Frame append;
append.allowed=[](uint32_t op,uint64_t a){return !a&&(op==SB_WP_UNIQUE_END||op==SB_WP_UNIQUE_APPEND_EXPRESSION||op==SB_WP_UNIQUE_NEXT);};
append.leaf=[&](uint32_t op,uint64_t){if(op==SB_WP_UNIQUE_END)return WpBoundary::reply(SB_WP_BOOL,!(cursor!=finish));if(op==SB_WP_UNIQUE_NEXT){++cursor;return WpBoundary::reply();}result.append(m_items[*cursor].second);return WpBoundary::reply();};
append.run(14,3);return result;
#else

  size_t targetCount = std::min(desiredCount, size());
  Set<size_t> indices;
  while (indices.size() < targetCount)
    indices.add(selectIndex(++seed));
  List<Item> result;
  for (size_t i : indices)
    result.append(m_items[i].second);
  return result;

#endif
}

template <typename Item>
size_t BoundaryWeightedPool<Item>::selectIndex(RandomSource& rand) const {
#if WP_BOUNDARY_ON
NativeFrame<15> f(this,0,0,&rand);return selectIndex(WpBoundary::number(f.run(15).value));
#else

  return selectIndex(rand.randd());

#endif
}

template <typename Item>
size_t BoundaryWeightedPool<Item>::selectIndex() const {
#if WP_BOUNDARY_ON
NativeFrame<16> f(this);return selectIndex(WpBoundary::number(f.run(16).value));
#else

  return selectIndex(Random::randd());

#endif
}

template <typename Item>
size_t BoundaryWeightedPool<Item>::selectIndex(uint64_t seed) const {
#if WP_BOUNDARY_ON
NativeFrame<17> f(this,seed);return selectIndex(WpBoundary::number(f.run(17).value));
#else

  return selectIndex(staticRandomDouble(seed));

#endif
}

template <typename Item>
size_t BoundaryWeightedPool<Item>::selectIndex(double target) const {
#if WP_BOUNDARY_ON
NativeFrame<18> f(this,WpBoundary::bits(target));return f.run(18).value;
#else

  if (m_items.empty())
    return NPos;

  // Test a randomly generated target against each weighted item in turn, and
  // see if that weighted item's weight value crosses the target.  This way, a
  // random item is picked from the list, but (roughly) weighted to be
  // proportional to its weight over the weight of all entries.
  //
  // TODO: This is currently O(n), but can easily be made O(log(n)) by using a
  // tree.  If this shows up in performance measurements, this is an obvious
  // improvement.

  double accumulatedWeight = 0.0f;
  for (size_t i = 0; i < m_items.size(); ++i) {
    accumulatedWeight += m_items[i].first / m_totalWeight;
    if (target <= accumulatedWeight)
      return i;
  }

  // If we haven't crossed the target, just assume floating point error has
  // caused us to not quite make it to the last item.
  return m_items.size() - 1;

#endif
}

}
