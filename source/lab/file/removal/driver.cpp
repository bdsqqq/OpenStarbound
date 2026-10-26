#include "StarFile.hpp"
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
struct Marker {};
std::exception_ptr pending;
Marker const* identity = nullptr;
size_t ordinal = 0;
size_t throwAt = 0;
}
namespace Star {
// Sole replacement leaf: no filesystem operation or fallback exists here.
void removalInstrumentedLeaf(String const& path) {
  ++ordinal;
  std::cout << ordinal << ':';
  static char const digits[] = "0123456789abcdef";
  for (unsigned char c : path.utf8())
    std::cout << digits[c >> 4] << digits[c & 15];
  std::cout << '\n';
  if (ordinal == throwAt)
    std::rethrow_exception(pending);
}
}
int main(int argc, char** argv) {
  if (argc != 3) return 2;
  throwAt = std::stoul(argv[2]);
  try { throw Marker{}; }
  catch (Marker const& e) { identity = &e; pending = std::current_exception(); }
  try {
    Star::File::removeDirectoryRecursive(Star::String(argv[1]));
    if (throwAt) return 3;
    std::cout << "return\n";
  } catch (Marker const& e) {
    if (!throwAt || ordinal != throwAt || &e != identity) return 4;
    std::cout << "same-exception\n";
  } catch (...) { return 5; }
}
