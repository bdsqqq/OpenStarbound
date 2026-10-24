#pragma once
#include "StarHostAddress.hpp"

#include "StarString.hpp"
#include "StarEither.hpp"

namespace Star {


STAR_CLASS(HostAddressReference);


class HostAddressReference {
public:
  static HostAddressReference localhost(NetworkMode mode = NetworkMode::IPv4);

  // Returns either error or valid HostAddress
  static Either<String, HostAddressReference> lookup(String const& address);

  // If address is nullptr, constructs the zero address.
  HostAddressReference(NetworkMode mode = NetworkMode::IPv4, uint8_t* address = nullptr);
  // Throws if address is not valid
  explicit HostAddressReference(String const& address);

  NetworkMode mode() const;
  uint8_t const* bytes() const;
  uint8_t octet(size_t i) const;
  size_t size() const;

  bool isLocalHost() const;
  bool isZero() const;

  bool operator==(HostAddressReference const& a) const;

private:
  void set(String const& address);
  void set(NetworkMode mode, uint8_t const* addr);

  NetworkMode m_mode;
  uint8_t m_address[16];
};

std::ostream& operator<<(std::ostream& os, HostAddressReference const& address);

template <>
struct hash<HostAddressReference> {
  size_t operator()(HostAddressReference const& address) const;
};

class HostAddressWithPortReference {
public:
  // Returns either error or valid HostAddressWithPort
  static Either<String, HostAddressWithPortReference> lookup(String const& address, uint16_t port);
  // Format may have [] brackets around address or not, to distinguish address
  // portion from port portion.
  static Either<String, HostAddressWithPortReference> lookupWithPort(String const& address);

  HostAddressWithPortReference();
  HostAddressWithPortReference(HostAddressReference const& address, uint16_t port);
  HostAddressWithPortReference(NetworkMode mode, uint8_t* address, uint16_t port);
  // Throws if address or port is not valid
  HostAddressWithPortReference(String const& address, uint16_t port);
  explicit HostAddressWithPortReference(String const& address);

  HostAddressReference address() const;
  uint16_t port() const;

  bool operator==(HostAddressWithPortReference const& a) const;

private:
  HostAddressReference m_address;
  uint16_t m_port;
};

std::ostream& operator<<(std::ostream& os, HostAddressWithPortReference const& address);

template <>
struct hash<HostAddressWithPortReference> {
  size_t operator()(HostAddressWithPortReference const& address) const;
};

}

template <> struct fmt::formatter<Star::HostAddressReference> : ostream_formatter {};
template <> struct fmt::formatter<Star::HostAddressWithPortReference> : ostream_formatter {};
