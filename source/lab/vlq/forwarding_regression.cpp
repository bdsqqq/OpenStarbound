#include "StarVlqEncoding.hpp"
#include "reference.hpp"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

// Only the forwarding copy (depth two) acts; postfix and outer copies must not
// hide whether signed assignment precedes or follows its destruction.
struct DestructorIterator {
  uint8_t const* position;
  int64_t* destination;
  int depth = 0;
  bool shouldThrow = false;
  DestructorIterator(uint8_t const* p, int64_t* v, bool t) : position(p), destination(v), shouldThrow(t) {}
  DestructorIterator(DestructorIterator const& x)
    : position(x.position), destination(x.destination), depth(x.depth + 1), shouldThrow(x.shouldThrow) {}
  ~DestructorIterator() noexcept(false) {
    if (depth == 2) {
      *destination = 99;
      if (shouldThrow) throw 123;
    }
  }
  DestructorIterator operator++(int) { DestructorIterator old(*this); ++position; return old; }
  uint8_t operator*() const { return *position; }
};
struct CopyIterator {
  uint8_t* position;
  std::vector<int>* events;
  CopyIterator(uint8_t* p, std::vector<int>* e) : position(p), events(e) {}
  CopyIterator(CopyIterator const& x) : position(x.position), events(x.events) { events->push_back(1); }
  explicit CopyIterator(CopyIterator& x) : position(x.position), events(x.events) { events->push_back(2); }
  CopyIterator operator++(int) { CopyIterator old = *this; ++position; return old; }
  uint8_t& operator*() const { return *position; }
};
int main(int argc, char** argv) {
  std::string mode = argc > 1 ? argv[1] : "all";
  if (mode == "all" || mode == "destructor") {
    for (bool throwing : {false, true}) {
      uint8_t bytes[]{0x81, 0x01};
      int64_t reference = 42, actual = 42;
      bool referenceThrows = false, actualThrows = false;
      DestructorIterator a(bytes, &reference, throwing), b(bytes, &actual, throwing);
      try { FrozenReference::readVlqI(reference, a); } catch (int n) { referenceThrows = n == 123; }
      try { Star::readVlqI(actual, b); } catch (int n) { actualThrows = n == 123; }
      if (reference != actual || referenceThrows != actualThrows) {
        std::cerr << "COMPARISON forwarding-destructor ref=" << reference << " actual=" << actual << '\n';
        return 1;
      }
    }
  }
  if (mode == "all" || mode == "copy") {
    uint8_t aBytes[10]{}, bBytes[10]{};
    std::vector<int> aEvents, bEvents;
    CopyIterator a(aBytes, &aEvents), b(bBytes, &bEvents);
    auto aSize = FrozenReference::writeVlqI(-65, a);
    auto bSize = Star::writeVlqI(-65, b);
    if (aSize != bSize || aEvents != bEvents) {
      std::cerr << "COMPARISON forwarding-copy-initialization\n";
      return 1;
    }
    aEvents.clear(); bEvents.clear();
    CopyIterator aRead(aBytes, &aEvents), bRead(bBytes, &bEvents);
    int64_t av = 42, bv = 42;
    aSize = FrozenReference::readVlqI(av, aRead);
    bSize = Star::readVlqI(bv, bRead);
    if (aSize != bSize || av != bv || aEvents != bEvents) {
      std::cerr << "COMPARISON reader-copy-initialization\n";
      return 1;
    }
  }
  std::cout << "forwarding regressions passed\n";
}
