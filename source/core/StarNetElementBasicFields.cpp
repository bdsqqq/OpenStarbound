#include "StarNetElementBasicFields.hpp"
#ifdef STAR_USE_RUST_NET_FIELD
#include "StarRustNetScalar.h"
#endif

namespace Star {
#ifdef STAR_USE_RUST_NET_FIELD
namespace {
SbNetScalarReply netScalar(uint32_t mode, uint32_t bits, uint64_t value, uint64_t previous = 0) {
  SbNetScalarReply reply{};
  if (sb_net_scalar_run(mode, bits, value, previous, &reply) != SB_NET_SCALAR_OK)
    throw std::logic_error("Network scalar Rust kernel protocol failure");
  return reply;
}
static_assert(sizeof(size_t) == 4 || sizeof(size_t) == 8, "Network size word ABI");
}
#endif

void NetElementSize::readData(DataStream& ds, size_t& v) const {
  uint64_t s = ds.readVlqU();
#ifdef STAR_USE_RUST_NET_FIELD
  v = static_cast<size_t>(netScalar(SB_NET_SCALAR_SIZE_DECODE, sizeof(size_t) * 8, s).value);
#else
  if (s == 0)
    v = NPos;
  else
    v = s - 1;
#endif
}

void NetElementSize::writeData(DataStream& ds, size_t const& v) const {
#ifdef STAR_USE_RUST_NET_FIELD
  ds.writeVlqU(netScalar(SB_NET_SCALAR_SIZE_ENCODE, sizeof(size_t) * 8, v).value);
#else
  if (v == NPos)
    ds.writeVlqU(0);
  else
    ds.writeVlqU(v + 1);
#endif
}

void NetElementBool::readData(DataStream& ds, bool& v) const {
  ds.read(v);
}

void NetElementBool::writeData(DataStream& ds, bool const& v) const {
  ds.write(v);
}

void NetElementEvent::trigger() {
#ifdef STAR_USE_RUST_NET_FIELD
  set(netScalar(SB_NET_SCALAR_NEXT, 0, get()).value);
#else
  set(get() + 1);
#endif
}

uint64_t NetElementEvent::pullOccurrences() {
  uint64_t occurrences = get();
  starAssert(occurrences >= m_pulledOccurrences);
#ifdef STAR_USE_RUST_NET_FIELD
  auto result = netScalar(SB_NET_SCALAR_PULL, 0, occurrences, m_pulledOccurrences);
  uint64_t unchecked = result.value;
  m_pulledOccurrences = result.pulled;
#else
  uint64_t unchecked = occurrences - m_pulledOccurrences;
  m_pulledOccurrences = occurrences;
#endif
  return unchecked;
}

bool NetElementEvent::pullOccurred() {
  return pullOccurrences() != 0;
}

void NetElementEvent::ignoreOccurrences() {
  m_pulledOccurrences = get();
}

void NetElementEvent::setIgnoreOccurrencesOnNetLoad(bool ignoreOccurrencesOnNetLoad) {
  m_ignoreOccurrencesOnNetLoad = ignoreOccurrencesOnNetLoad;
}

void NetElementEvent::netLoad(DataStream& ds, NetCompatibilityRules rules) {
  NetElementUInt::netLoad(ds, rules);
  if (m_ignoreOccurrencesOnNetLoad)
    ignoreOccurrences();
}

void NetElementEvent::updated() {
  NetElementBasicField::updated();
#ifdef STAR_USE_RUST_NET_FIELD
  m_pulledOccurrences = netScalar(SB_NET_SCALAR_CLAMP, 0, get(), m_pulledOccurrences).value;
#else
  if (m_pulledOccurrences > get())
    m_pulledOccurrences = get();
#endif
}

}
