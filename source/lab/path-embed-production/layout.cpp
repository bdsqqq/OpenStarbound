#include "StarPathEmbed.hpp"
#include <cstdio>
int main() {
  std::printf("%zu %zu %zu %zu %zu %zu %zu %zu\n", sizeof(Star::String), alignof(Star::String), sizeof(Star::ByteArray), alignof(Star::ByteArray), sizeof(Star::EmbeddedCompressionMethod), alignof(Star::EmbeddedCompressionMethod), sizeof(Star::EmbeddedCompressionMethodNames), alignof(decltype(Star::EmbeddedCompressionMethodNames)));
}
