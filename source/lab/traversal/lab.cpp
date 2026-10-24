#include "StarBlocksAlongLine.hpp"
#include "reference.hpp"
#ifdef TIE_MUTANT
#include "mutant.hpp"
#endif
#include <exception>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>
#include <climits>

using Cell = std::pair<int, int>;
struct Typed { void const* identity; };
struct Observation {
  std::vector<Cell> cells;
  std::vector<Cell> nested;
  int outcome = -1; // false=0, true=1, typed=2, nonstd=3
  void const* identity = nullptr;
  std::exception_ptr exception;
  bool operator==(Observation const& b) const {
    return cells == b.cells && nested == b.nested && outcome == b.outcome &&
      identity == b.identity && exception == b.exception;
  }
};
struct Production {
  template<class T, class F> bool operator()(Star::Vector<T,2> o, Star::Vector<T,2> d, F f) const {
#ifdef TIE_MUTANT
    return TraversalMutant::forBlocksAlongLine<T>(o,d,f);
#elif defined(ABORT_MUTANT)
    return Star::forBlocksAlongLine<T>(o,d,[&](int x,int y) { f(x,y); return true; });
#elif defined(EXCEPTION_MUTANT)
    try { return Star::forBlocksAlongLine<T>(o,d,f); } catch (...) { return false; }
#else
    return Star::forBlocksAlongLine<T>(o,d,f);
#endif
  }
};
struct Reference {
  template<class T, class F> bool operator()(Star::Vector<T,2> o, Star::Vector<T,2> d, F f) const {
    return TraversalReference::forBlocksAlongLine<T>(o,d,f);
  }
};
static size_t cases = 0, checks = 0;
static int sentinel;
static std::exception_ptr typedException = std::make_exception_ptr(Typed{&sentinel});
static std::exception_ptr nonstdException = std::make_exception_ptr(&sentinel);
void require(bool ok, char const* label) {
  ++checks;
  if (!ok) throw std::runtime_error(label);
}
// Side effects are recorded BEFORE returning/throwing, including the terminal callback.
template<class T, class Engine>
Observation observe(Engine engine, Star::Vector<T,2> o, Star::Vector<T,2> d,
                    int stop, int action, bool reenter = false) {
  Observation r;
  try {
    r.outcome = engine(o,d,[&](int x,int y) {
      int index = int(r.cells.size());
      r.cells.emplace_back(x,y);
      if (reenter && index == 0) {
        bool done = engine(Star::Vector<T,2>(T(-.5),T(.5)), Star::Vector<T,2>(T(1),T(-1)),
          [&](int a,int b) { r.nested.emplace_back(a,b); return true; });
        if (!done) throw std::runtime_error("nested result");
      }
      if (index == stop) {
        if (action == 1) return false;
        if (action == 2) std::rethrow_exception(typedException);
        if (action == 3) std::rethrow_exception(nonstdException);
      }
      return true;
    });
  } catch (Typed const& e) {
    r.outcome = 2; r.identity = e.identity; r.exception = std::current_exception();
  } catch (int* e) {
    r.outcome = 3; r.identity = e; r.exception = std::current_exception();
  }
  return r;
}

template<class T>
void exercise(Star::Vector<T,2> o, Star::Vector<T,2> d, int prefix = 0) {
  ++cases;
  if (prefix) {
    // No full traversal here: axis count and post-loop increments may not be defined.
    for (int k=0;k<prefix;++k) for (int action=1;action<=3;++action)
      require(observe(Reference{},o,d,k,action) == observe(Production{},o,d,k,action), "wide prefix");
    return;
  }
  auto baseline = observe(Reference{},o,d,-1,0);
  require(baseline.outcome == 1 && !baseline.cells.empty(), "reference completion");
  require(baseline == observe(Production{},o,d,-1,0), "ordered full traversal");
  for (int k=0;k<int(baseline.cells.size());++k) for (int action=1;action<=3;++action) {
    auto ref = observe(Reference{},o,d,k,action);
    int expected = action == 1 ? 0 : action;
    require(ref.cells.size() == size_t(k+1) && ref.outcome == expected &&
      (action == 1 || (ref.identity == &sentinel &&
        ref.exception == (action == 2 ? typedException : nonstdException))), "oracle callback contract");
    require(ref == observe(Production{},o,d,k,action), "abort/exception prefix or identity");
  }
  require(observe(Reference{},o,d,-1,0,true) == observe(Production{},o,d,-1,0,true), "reentrant effects");
}

template<class T> void suite() {
  using V = Star::Vector<T,2>;
  // Exact anchors make the harness more than agreement between two C++ copies.
  require(observe(Reference{},V(T(.5),T(.5)),V(T(2),T(2)),-1,0).cells ==
    std::vector<Cell>{{0,0},{1,1},{2,2}}, "anchor: corner skips side cells");
  require(observe(Reference{},V(T(-.5),T(-.5)),V(T(0),T(0)),-1,0).cells ==
    std::vector<Cell>{{-1,-1}}, "anchor: negative floor zero length");
  for (int ox=-2;ox<=2;++ox) for (int oy=-2;oy<=2;++oy)
    for (int dx=-3;dx<=3;++dx) for (int dy=-3;dy<=3;++dy) {
      exercise(V(T(ox),T(oy)),V(T(dx),T(dy)));
      exercise(V(T(ox)+T(.5),T(oy)+T(.5)),V(T(dx),T(dy)));
    }
  // Boundary neighbors are rounded in Scalar, not reconstructed in double.
  for (T edge : {T(-1), T(0), T(1)}) {
    T below = std::nextafter(edge,T(-2));
    T above = std::nextafter(edge,T(2));
    for (T value : {below,edge,above}) {
      exercise(V(value,T(.5)),V(T(1),T(1)));
      exercise(V(T(.5),value),V(T(-1),T(-1)));
    }
  }
  T near = std::nextafter(T(1),T(2));
  for (int sx : {-1,1}) for (int sy : {-1,1}) {
    exercise(V(T(.5),T(.5)), V(T(sx)*near,T(sy)));
    exercise(V(T(.5),T(.5)), V(T(sx),T(sy)*near));
    exercise(V(T(-1),T(-1)), V(T(sx)*T(0.000001),T(sy)*T(0.000001)));
  }
  // Float addition rounds 16777216+1 back to 16777216, before floor/double.
  exercise(V(T(16777216),T(.5)),V(T(1),T(0)));
  if (sizeof(T)==4)
    require(observe(Reference{},V(T(16777216),T(.5)),V(T(1),T(0)),-1,0).cells ==
      std::vector<Cell>{{16777216,0}}, "anchor: scalar endpoint rounding");
  std::mt19937 rng(0x51a7);
  for (int i=0;i<1000;++i) {
    auto value = [&] { return T(int(rng()%32769)-16384)/T(1024); };
    T x=value(), y=value(), dx=value(), dy=value();
    exercise(V(x,y),V(dx,dy));
  }
  // Axis spans beyond INT_MAX cells are legal when aborted before loop increment overflow.
  exercise(V(T(-2000000000),T(0)), V(T(4000000000.0),T(0)),3);
  exercise(V(T(0),T(2000000000)), V(T(0),T(-4000000000.0)),3);
  // INT_MIN zero-length decrements out of range only after a true callback; abort is defined.
  exercise(V(T(INT_MIN),T(INT_MIN)),V(T(0),T(0)),1);
  // Nonaxis setup remains representable even for this long unexecuted suffix.
  exercise(V(T(-500000000),T(-500000000)),V(T(1000000000),T(1000000000)),3);
  if (sizeof(T)==8) {
    // At the final boundary callback, false/throw avoids otherwise undefined
    // post-last-cell axis increment and nonaxis tie step at INT_MAX.
    exercise(V(T(INT_MAX-1),T(0)),V(T(1),T(0)),2);
    exercise(V(T(INT_MAX-1),T(INT_MAX-1)),V(T(1),T(1)),2);
  }
}
int main() {
  try {
    suite<float>(); suite<double>();
    std::cout << "{\"cases\":" << cases << ",\"checks\":" << checks << ",\"status\":\"pass\"}\n";
    return 0;
  } catch (std::exception const& e) {
    std::cerr << "FAIL after " << cases << " cases / " << checks << " checks: " << e.what() << '\n';
    return 1;
  }
}
