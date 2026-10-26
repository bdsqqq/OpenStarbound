// Diagnostic ownership contract, not evidence that a timed eviction occurred.
#include "StarAssets.hpp"
#include "StarImage.hpp"
#include <iostream>
#include <stdexcept>
using namespace Star;
int main(int argc, char**) {
  try {
    Assets::ImageData entry;
    entry.image = make_shared<Image>();
    if (entry.shouldPersist()) throw std::runtime_error("unheld image persisted");
    ImageConstPtr original;
    if (argc == 1) original = entry.image;
    if (!entry.shouldPersist()) throw std::runtime_error("original image ownership missing");
    entry.alias = true;
    if (entry.shouldPersist()) throw std::runtime_error("alias contract changed");
    entry.alias = false;
    original.reset();
    if (entry.shouldPersist()) throw std::runtime_error("released image persisted");
    entry.forcePersist = true;
    if (!entry.shouldPersist()) throw std::runtime_error("force persistence changed");
    std::cout << "native image ownership persistence controls pass\n";
    return 0;
  } catch (std::exception const& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
