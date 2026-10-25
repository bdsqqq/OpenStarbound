#pragma once
#include "StarBuffer.hpp"

namespace Star {
// BTree reserves device extents before writing, but Buffer growth deliberately
// does not initialize bytes. Fixtures that copy whole pages must seed *all*
// backing storage, including unused headers and blocks read before overwrite.
class BehaviorBTreeBuffer final : public Buffer {
public:
  static constexpr StreamOffset Capacity = 8192;
  explicit BehaviorBTreeBuffer(char fill = 0) : Buffer(ByteArray(Capacity, fill)) {
    Buffer::resize(0);
  }
  void resize(StreamOffset size) override {
    checkSpan(size, 0);
    Buffer::resize(size);
  }
  size_t write(char const* data, size_t size) override {
    checkSpan(Buffer::pos(), size);
    return Buffer::write(data, size);
  }
  size_t writeAbsolute(StreamOffset position, char const* data, size_t size) override {
    checkSpan(position, size);
    return Buffer::writeAbsolute(position, data, size);
  }
private:
  static void checkSpan(StreamOffset position, size_t size) {
    if (position < 0 || position > Capacity || size > size_t(Capacity - position))
      throw StarException("BehaviorLab: initialized BTree backing extent exceeded");
  }
};
}
