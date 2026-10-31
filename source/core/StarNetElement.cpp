#include "StarNetElement.hpp"


namespace Star {

uint64_t NetElementVersion::current() const {
#ifdef STAR_USE_RUST_NET_GROUP
  return NetElementDetail::version(SB_NET_VERSION_CURRENT, &m_state);
#else
  return m_version;
#endif
}

uint64_t NetElementVersion::increment() {
#ifdef STAR_USE_RUST_NET_GROUP
  return NetElementDetail::version(SB_NET_VERSION_ADVANCE, &m_state);
#else
  return ++m_version;
#endif
}

void NetElement::enableNetInterpolation(float) {}

void NetElement::disableNetInterpolation() {}

void NetElement::tickNetInterpolation(float) {}

void NetElement::blankNetDelta(float) {}

}
