#include "StarNetElement.hpp"


namespace Star {

uint64_t NetElementVersion::current() const {
  return m_version;
}

uint64_t NetElementVersion::increment() {
#ifdef STAR_USE_RUST_NET_GROUP
  m_version = NetElementDetail::scalar(SB_NET_SCALAR_VERSION_NEXT, 0, m_version, 0);
  return m_version;
#else
  return ++m_version;
#endif
}

void NetElement::enableNetInterpolation(float) {}

void NetElement::disableNetInterpolation() {}

void NetElement::tickNetInterpolation(float) {}

void NetElement::blankNetDelta(float) {}

}
