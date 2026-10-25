#include "StarHostAddress.hpp"
#include "StarLexicalCast.hpp"
#include "StarNetImpl.hpp"

#ifdef STAR_USE_RUST_HOST_ADDRESS
#include "StarHostAddressHost.hpp"
namespace Star {
using HostAddressRust::Context;
HostAddress HostAddress::localhost(NetworkMode mode) {
  Context c(HA_LOCALHOST);
  c.requested = mode;
  c.run();
  return c.hostResult ? std::move(*c.hostResult) : std::move(c.lookup->right());
}
Either<String, HostAddress> HostAddress::lookup(String const& a) {
  Context c(HA_LOOKUP);
  c.input = &a;
  c.setString = [](Context& c, String const& s) { c.temporary->set(s); };
  c.run();
  return std::move(*c.lookup);
}
HostAddress::HostAddress(NetworkMode m, uint8_t* a) {
  Context c(HA_CTOR_RAW);
  c.requested = m;
  c.raw = a;
  c.destination = this;
  c.setRaw = [](Context& c, NetworkMode m, uint8_t const* p) { c.destination->set(m, p); };
  c.run();
}
HostAddress::HostAddress(String const& a) {
  Context c(HA_CTOR_STRING);
  c.input = &a;
  c.destination = this;
  c.run();
}
NetworkMode HostAddress::mode() const {
  Context c(HA_MODE);
  c.fieldMode = &m_mode;
  c.run();
  return c.nativeMode(c.scalar);
}
uint8_t const* HostAddress::bytes() const {
  Context c(HA_BYTES);
  c.fieldBytes = m_address;
  c.run();
  return c.pointerResult;
}
uint8_t HostAddress::octet(size_t i) const {
  Context c(HA_OCTET);
  c.fieldBytes = m_address;
  c.index = i;
  c.run();
  return uint8_t(c.scalar);
}
bool HostAddress::isLocalHost() const {
  Context c(HA_IS_LOCALHOST);
  c.subject = this;
  c.fieldMode = &m_mode;
  c.fieldBytes = m_address;
  c.run();
  return c.scalar;
}
bool HostAddress::isZero() const {
  Context c(HA_IS_ZERO);
  c.subject = this;
  c.run();
  return c.scalar;
}
size_t HostAddress::size() const {
  Context c(HA_SIZE);
  c.fieldMode = &m_mode;
  c.run();
  return c.scalar;
}
bool HostAddress::operator==(HostAddress const& a) const {
  Context c(HA_EQUAL);
  c.subject = this;
  c.other = &a;
  c.fieldMode = &m_mode;
  c.fieldBytes = m_address;
  c.run();
  return c.scalar;
}
void HostAddress::set(String const& a) {
  Context c(HA_SET_STRING);
  c.subject = this;
  c.input = &a;
  c.destination = this;
  c.setRaw = [](Context& c, NetworkMode m, uint8_t const* p) { c.destination->set(m, p); };
  c.run();
}
void HostAddress::set(NetworkMode m, uint8_t const* a) {
  Context c(HA_SET_RAW);
  c.requested = m;
  c.raw = a;
  c.writeMode = &m_mode;
  c.writeBytes = m_address;
  c.run();
}
std::ostream& operator<<(std::ostream& os, HostAddress const& a) {
  Context c(HA_STREAM);
  c.subject = &a;
  c.stream = &os;
  c.run();
  return os;
}
size_t hash<HostAddress>::operator()(HostAddress const& a) const {
  Context c(HA_HASH);
  c.subject = &a;
  c.run();
  return c.scalar;
}
Either<String, HostAddressWithPort> HostAddressWithPort::lookup(String const& a, uint16_t p) {
  Context c(HA_EP_LOOKUP);
  c.input = &a;
  c.supplied = p;
  c.run();
  return std::move(*c.endpointLookup);
}
Either<String, HostAddressWithPort> HostAddressWithPort::lookupWithPort(String const& a) {
  Context c(HA_EP_PARSE);
  c.input = &a;
  c.run();
  return std::move(*c.endpointLookup);
}
HostAddressWithPort::HostAddressWithPort() : m_port(0) {
  Context c(HA_EP_CTOR_DEFAULT);
  c.writePort = &m_port;
  c.run();
}
HostAddressWithPort::HostAddressWithPort(HostAddress const& a, uint16_t p) : m_address(a), m_port(p) {
  Context c(HA_EP_CTOR_HOST);
  c.subject = &a;
  c.supplied = p;
  c.writePort = &m_port;
  // The source member initializer already performed this native copy.
  c.copyEndpointHost = [](Context&, HostAddress const&) {};
  c.run();
}
HostAddressWithPort::HostAddressWithPort(NetworkMode m, uint8_t* a, uint16_t p) {
  Context c(HA_EP_CTOR_RAW);
  c.requested = m;
  c.raw = a;
  c.mutableRaw = a;
  c.supplied = p;
  c.writePort = &m_port;
  c.endpointDestination = this;
  c.copyEndpointHost = [](Context& c, HostAddress const& h) { c.endpointDestination->m_address = h; };
  c.run();
}
HostAddressWithPort::HostAddressWithPort(String const& a, uint16_t p) {
  Context c(HA_EP_CTOR_STRING_PORT);
  c.input = &a;
  c.supplied = p;
  c.endpointDestination = this;
  c.run();
}
HostAddressWithPort::HostAddressWithPort(String const& a) {
  Context c(HA_EP_CTOR_STRING);
  c.input = &a;
  c.endpointDestination = this;
  c.run();
}
HostAddress HostAddressWithPort::address() const {
  Context c(HA_EP_ADDRESS);
  c.subject = &m_address;
  c.run();
  return std::move(*c.hostResult);
}
uint16_t HostAddressWithPort::port() const {
  Context c(HA_EP_PORT);
  c.fieldPort = &m_port;
  c.run();
  return uint16_t(c.scalar);
}
bool HostAddressWithPort::operator==(HostAddressWithPort const& a) const {
  Context c(HA_EP_EQUAL);
  c.endpoint = this;
  c.otherEndpoint = &a;
  c.run();
  return c.scalar;
}
std::ostream& operator<<(std::ostream& os, HostAddressWithPort const& a) {
  Context c(HA_EP_STREAM);
  c.endpoint = &a;
  c.stream = &os;
  c.run();
  return os;
}
size_t hash<HostAddressWithPort>::operator()(HostAddressWithPort const& a) const {
  Context c(HA_EP_HASH);
  c.endpoint = &a;
  c.run();
  return c.scalar;
}
}// namespace Star

#else
namespace Star {

HostAddress HostAddress::localhost(NetworkMode mode) {
  if (mode == NetworkMode::IPv4) {
    uint8_t addr[4] = {127, 0, 0, 1};
    return HostAddress(mode, addr);
  } else if (mode == NetworkMode::IPv6) {
    uint8_t addr[16] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1};
    return HostAddress(mode, addr);
  }

  return HostAddress();
}

Either<String, HostAddress> HostAddress::lookup(String const& address) {
  try {
    HostAddress ha;
    ha.set(address);
    return makeRight(std::move(ha));
  } catch (NetworkException const& e) {
    return makeLeft(String(e.what()));
  }
}

HostAddress::HostAddress(NetworkMode mode, uint8_t* address) {
  set(mode, address);
}

HostAddress::HostAddress(String const& address) {
  auto a = lookup(address);
  if (a.isLeft())
    throw NetworkException(a.left().takeUtf8());
  else
    *this = std::move(a.right());
}

NetworkMode HostAddress::mode() const {
  return m_mode;
}

uint8_t const* HostAddress::bytes() const {
  return m_address;
}

uint8_t HostAddress::octet(size_t i) const {
  return m_address[i];
}

bool HostAddress::isLocalHost() const {
  if (m_mode == NetworkMode::IPv4) {
    return (m_address[0] == 127 && m_address[1] == 0 && m_address[2] == 0 && m_address[3] == 1);

  } else {
    for (size_t i = 0; i < 15; ++i) {
      if (m_address[i] != 0)
        return false;
    }

    return m_address[15] == 1;
  }
}

bool HostAddress::isZero() const {
  if (mode() == NetworkMode::IPv4)
    return m_address[0] == 0 && m_address[1] == 0 && m_address[2] == 0 && m_address[3] == 0;

  if (mode() == NetworkMode::IPv6) {
    for (size_t i = 0; i < 16; i++) {
      if (m_address[i] != 0)
        return false;
    }
    return true;
  }

  return false;
}

size_t HostAddress::size() const {
  switch (m_mode) {
    case NetworkMode::IPv4:
      return 4;
    case NetworkMode::IPv6:
      return 16;
    default:
      return 0;
  }
}

bool HostAddress::operator==(HostAddress const& a) const {
  if (m_mode != a.m_mode)
    return false;

  size_t len = a.size();
  for (size_t i = 0; i < len; i++) {
    if (m_address[i] != a.m_address[i])
      return false;
  }

  return true;
}

void HostAddress::set(String const& address) {
  if (address.empty())
    return;

  if (address.compare("*") == 0 || address.compare("0.0.0.0") == 0) {
    uint8_t inaddr_any[4];
    memset(inaddr_any, 0, sizeof(inaddr_any));
    set(NetworkMode::IPv4, inaddr_any);
  } else if (address.compare("::") == 0) {
    // NOTE: This will likely bind to both IPv6 and IPv4, but it does depending
    // on the OS settings
    uint8_t inaddr_any[16];
    memset(inaddr_any, 0, sizeof(inaddr_any));
    set(NetworkMode::IPv6, inaddr_any);
  } else {
    struct addrinfo* result = NULL;
    struct addrinfo* ptr = NULL;
    struct addrinfo hints;

    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    // Eliminate duplicates being returned one for each socket type.
    // As we're not using the return socket type or protocol this doesn't effect
    // us.
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_protocol = IPPROTO_TCP;
    // Request only usable addresses e.g. IPv6 only if IPv6 is available
    hints.ai_flags = AI_ADDRCONFIG;

    if (::getaddrinfo(address.utf8Ptr(), NULL, &hints, &result) != 0)
      throw NetworkException(strf("Failed to determine address for '{}' ({})", address, netErrorString()));

    for (ptr = result; ptr != NULL; ptr = ptr->ai_next) {
      NetworkMode mode;
      switch (ptr->ai_family) {
        case AF_INET:
          mode = NetworkMode::IPv4;
          break;
        case AF_INET6:
          mode = NetworkMode::IPv6;
          break;
        default:
          continue;
      }
      if (mode == NetworkMode::IPv4) {
        struct sockaddr_in* info = (struct sockaddr_in*)ptr->ai_addr;
        set(mode, (uint8_t*)(&info->sin_addr));
      } else {
        struct sockaddr_in6* info = (struct sockaddr_in6*)ptr->ai_addr;
        set(mode, (uint8_t*)(&info->sin6_addr));
      }
      break;
    }
    freeaddrinfo(result);
  }
}

void HostAddress::set(NetworkMode mode, uint8_t const* addr) {
  m_mode = mode;
  if (addr)
    memcpy(m_address, addr, size());
  else
    memset(m_address, 0, 16);
}

std::ostream& operator<<(std::ostream& os, HostAddress const& address) {
  switch (address.mode()) {
    case NetworkMode::IPv4:
      format(os, "{}.{}.{}.{}", address.octet(0), address.octet(1), address.octet(2), address.octet(3));
      break;

    case NetworkMode::IPv6:
      format(os,
          "{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}",
          address.octet(0),
          address.octet(1),
          address.octet(2),
          address.octet(3),
          address.octet(4),
          address.octet(5),
          address.octet(6),
          address.octet(7),
          address.octet(8),
          address.octet(9),
          address.octet(10),
          address.octet(11),
          address.octet(12),
          address.octet(13),
          address.octet(14),
          address.octet(15));
      break;

    default:
      throw NetworkException(strf("Unknown address mode ({})", (int)address.mode()));
  }
  return os;
}

size_t hash<HostAddress>::operator()(HostAddress const& address) const {
  PLHasher hash;
  for (size_t i = 0; i < address.size(); ++i)
    hash.put(address.octet(i));
  return hash.hash();
}

Either<String, HostAddressWithPort> HostAddressWithPort::lookup(String const& address, uint16_t port) {
  auto hostAddress = HostAddress::lookup(address);
  if (hostAddress.isLeft())
    return makeLeft(std::move(hostAddress.left()));
  else
    return makeRight(HostAddressWithPort(std::move(hostAddress.right()), port));
}

Either<String, HostAddressWithPort> HostAddressWithPort::lookupWithPort(String const& address) {
  String host = address;
  String port = host.rextract(":");
  if (host.beginsWith("[") && host.endsWith("]"))
    host = host.substr(1, host.size() - 2);

  auto portNum = maybeLexicalCast<uint16_t>(port);
  if (!portNum)
    return makeLeft(strf("Could not parse port portion of HostAddressWithPort '{}'", port));

  auto hostAddress = HostAddress::lookup(host);
  if (hostAddress.isLeft())
    return makeLeft(std::move(hostAddress.left()));

  return makeRight(HostAddressWithPort(std::move(hostAddress.right()), *portNum));
}

HostAddressWithPort::HostAddressWithPort() : m_port(0) {}

HostAddressWithPort::HostAddressWithPort(HostAddress const& address, uint16_t port)
  : m_address(address), m_port(port) {}

HostAddressWithPort::HostAddressWithPort(NetworkMode mode, uint8_t* address, uint16_t port) {
  m_address = HostAddress(mode, address);
  m_port = port;
}

HostAddressWithPort::HostAddressWithPort(String const& address, uint16_t port) {
  auto a = lookup(address, port);
  if (a.isLeft())
    throw NetworkException(a.left().takeUtf8());
  *this = std::move(a.right());
}

HostAddressWithPort::HostAddressWithPort(String const& address) {
  auto a = lookupWithPort(address);
  if (a.isLeft())
    throw NetworkException(a.left().takeUtf8());
  *this = std::move(a.right());
}

HostAddress HostAddressWithPort::address() const {
  return m_address;
}

uint16_t HostAddressWithPort::port() const {
  return m_port;
}

bool HostAddressWithPort::operator==(HostAddressWithPort const& rhs) const {
  return tie(m_address, m_port) == tie(rhs.m_address, rhs.m_port);
}

std::ostream& operator<<(std::ostream& os, HostAddressWithPort const& addressWithPort) {
  os << addressWithPort.address() << ":" << addressWithPort.port();
  return os;
}

size_t hash<HostAddressWithPort>::operator()(HostAddressWithPort const& addressWithPort) const {
  return hashOf(addressWithPort.address(), addressWithPort.port());
}

}
#endif
