#include "StarUuid.hpp"
#include "StarRandom.hpp"
#include "StarFormat.hpp"
#include "StarEncode.hpp"
#ifdef STAR_USE_RUST_UUID
#include "StarRustUuid.h"
#endif

namespace Star {
#ifdef STAR_USE_RUST_UUID
namespace {
void requireUuidResult(uint32_t status) {
  if (status != SB_UUID_OK)
    throw UuidException("Invalid Rust UUID boundary result");
}
int32_t uuidOrder(Uuid const& left, Uuid const& right) {
  int32_t order = 0;
  // Array<char,16> orders native char values. Treating these as unsigned bytes
  // would silently reverse comparisons involving the high bit on signed-char hosts.
  requireUuidResult(sb_uuid_compare(reinterpret_cast<uint8_t const*>(left.ptr()),
      reinterpret_cast<uint8_t const*>(right.ptr()), std::is_signed<char>::value, &order));
  return order;
}
}
#endif

Uuid::Uuid() : Uuid(Random::randBytes(UuidSize)) {}

Uuid::Uuid(ByteArray const& bytes) {
#ifdef STAR_USE_RUST_UUID
  auto status = sb_uuid_from_bytes(reinterpret_cast<uint8_t const*>(bytes.ptr()), bytes.size(),
      reinterpret_cast<uint8_t*>(m_data.ptr()));
  if (status == SB_UUID_BAD_LENGTH)
    throw UuidException(strf("Size mismatch in reading Uuid from ByteArray: {} vs {}", bytes.size(), UuidSize));
  requireUuidResult(status);
#else
  if (bytes.size() != UuidSize)
    throw UuidException(strf("Size mismatch in reading Uuid from ByteArray: {} vs {}", bytes.size(), UuidSize));

  bytes.copyTo(m_data.ptr(), UuidSize);
#endif
}

Uuid::Uuid(String const& hex) : Uuid(hexDecode(hex)) {}

char const* Uuid::ptr() const {
  return m_data.ptr();
}

ByteArray Uuid::bytes() const {
  return ByteArray(m_data.ptr(), UuidSize);
}

String Uuid::hex() const {
  return hexEncode(m_data.ptr(), UuidSize);
}

bool Uuid::operator==(Uuid const& u) const {
#ifdef STAR_USE_RUST_UUID
  return uuidOrder(*this, u) == 0;
#else
  return m_data == u.m_data;
#endif
}

bool Uuid::operator!=(Uuid const& u) const {
#ifdef STAR_USE_RUST_UUID
  return uuidOrder(*this, u) != 0;
#else
  return m_data != u.m_data;
#endif
}

bool Uuid::operator<(Uuid const& u) const {
#ifdef STAR_USE_RUST_UUID
  return uuidOrder(*this, u) < 0;
#else
  return m_data < u.m_data;
#endif
}

bool Uuid::operator<=(Uuid const& u) const {
#ifdef STAR_USE_RUST_UUID
  return uuidOrder(*this, u) <= 0;
#else
  return m_data <= u.m_data;
#endif
}

bool Uuid::operator>(Uuid const& u) const {
#ifdef STAR_USE_RUST_UUID
  return uuidOrder(*this, u) > 0;
#else
  return m_data > u.m_data;
#endif
}

bool Uuid::operator>=(Uuid const& u) const {
#ifdef STAR_USE_RUST_UUID
  return uuidOrder(*this, u) >= 0;
#else
  return m_data >= u.m_data;
#endif
}

size_t hash<Uuid>::operator()(Uuid const& u) const {
  size_t hashval = 0;
#ifdef STAR_USE_RUST_UUID
  requireUuidResult(sb_uuid_hash(reinterpret_cast<uint8_t const*>(u.ptr()),
      std::is_signed<char>::value, &hashval));
#else
  for (size_t i = 0; i < UuidSize; ++i)
    hashCombine(hashval, u.ptr()[i]);
#endif
  return hashval;
}

DataStream& operator>>(DataStream& ds, Uuid& uuid) {
  uuid = Uuid(ds.readBytes(UuidSize));
  return ds;
}

DataStream& operator<<(DataStream& ds, Uuid const& uuid) {
  ds.writeData(uuid.ptr(), UuidSize);
  return ds;
}

}
