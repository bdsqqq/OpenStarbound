#pragma once
// Private native owner: no C++ object layout or exception crosses the Rust ABI.
#include "StarHostAddress.hpp"
#include "StarLexicalCast.hpp"
#include "StarNetImpl.hpp"
#include "StarRustHostAddress.h"
#include <limits>
#include <optional>

namespace Star {
namespace HostAddressRust {
struct Stop {
  uint32_t status;
};
using HostResult = Either<String, HostAddress>;
using EndpointResult = Either<String, HostAddressWithPort>;
// All pointers bind actual native objects. No private-layout mirror or integer
// object encoding. Private setters are supplied from their legal member scope.
struct Context {
  uint32_t invocation;
  bool busy = false, finished = false, published = false;
  uint64_t scalar = 0, index = 0;
  std::exception_ptr pending;
  HostAddress const* subject = nullptr;
  HostAddress const* other = nullptr;
  NetworkMode const* fieldMode = nullptr;
  NetworkMode* writeMode = nullptr;
  uint8_t const* fieldBytes = nullptr;
  uint8_t* writeBytes = nullptr;
  HostAddress* destination = nullptr;
  HostAddressWithPort* endpointDestination = nullptr;
  HostAddressWithPort const* endpoint = nullptr;
  HostAddressWithPort const* otherEndpoint = nullptr;
  uint16_t const* fieldPort = nullptr;
  uint16_t* writePort = nullptr;
  String const* input = nullptr;
  uint8_t const* raw = nullptr;
  uint8_t* mutableRaw = nullptr;
  NetworkMode requested = NetworkMode::IPv4;
  uint16_t supplied = 0, parsed = 0;
  String hostScratch, portScratch;
  uint8_t buffer[16];
  std::optional<HostAddress> temporary, streamTemporary, hostResult;
  std::optional<HostResult> lookup;
  std::optional<EndpointResult> endpointLookup;
  std::optional<HostAddressWithPort> endpointResult;
  uint8_t const* pointerResult = nullptr;
  std::ostream* stream = nullptr;
  addrinfo* result = nullptr;
  addrinfo* current = nullptr;
  bool resolved = false, resolverFreed = false;
  uint32_t resolverStatus = 0;
  void (*setString)(Context&, String const&) = nullptr;
  void (*setRaw)(Context&, NetworkMode, uint8_t const*) = nullptr;
  void (*copyEndpointHost)(Context&, HostAddress const&) = nullptr;
  // Resolver release belongs only to the source normal path. In particular,
  // pending exceptions must not acquire destructor cleanup or an implicit retry.
  explicit Context(uint32_t m) : invocation(m) {}
  HostAddress const& slot(uint64_t s) {
    switch (s) {
    case HA_SUBJECT:
      if (subject)
        return *subject;
      break;
    case HA_OTHER:
      if (other)
        return *other;
      break;
    case HA_LOOKUP_TEMP:
      if (temporary)
        return *temporary;
      break;
    case HA_STREAM_TEMP:
      if (streamTemporary)
        return *streamTemporary;
      break;
    case HA_ENDPOINT_ADDRESS:
      check(endpoint);
      temporary = endpoint->address();
      return *temporary;
    case HA_OTHER_ENDPOINT_ADDRESS:
      check(otherEndpoint);
      hostResult = otherEndpoint->address();
      return *hostResult;
    }
    throw Stop{HA_INVALID};
  }
  uint32_t bits(NetworkMode m) { return static_cast<uint32_t>(static_cast<int>(m)); }
  NetworkMode nativeMode(uint64_t n) {
    if (n > UINT32_MAX)
      throw Stop{HA_INVALID};
    int32_t i;
    uint32_t u = uint32_t(n);
    memcpy(&i, &u, 4);
    return static_cast<NetworkMode>(i);
  }
  uint64_t readMode(uint64_t s) {
    if (s == HA_REQUESTED_MODE)
      return bits(requested);
    if (s == HA_SUBJECT && fieldMode)
      return bits(*fieldMode);
    return bits(slot(s).mode());
  }
  uint64_t readByte(uint64_t s, uint64_t i) {
    if (i > 15)
      throw Stop{HA_INVALID};
    if (s == HA_BUFFER)
      return buffer[i];
    if (s == HA_SUBJECT && fieldBytes)
      return fieldBytes[i];
    return slot(s).octet(i);
  }
  void check(bool ok) {
    if (!ok)
      throw Stop{HA_INVALID};
  }
  bool allows(uint32_t op) const {
    if (op == HA_FINISH)
      return true;
    switch (invocation) {
    case HA_LOCALHOST: return op == HA_READ_MODE || op == HA_CONSTRUCT || op == HA_WRITE_BYTE || op == HA_TRANSFER;
    case HA_LOOKUP: return op == HA_CONSTRUCT || op == HA_CHILD || op == HA_TRANSFER || op == HA_PENDING_NETWORK || op == HA_CATCH_NETWORK;
    case HA_CTOR_RAW: return op == HA_CHILD;
    case HA_CTOR_STRING:
    case HA_EP_CTOR_STRING_PORT:
    case HA_EP_CTOR_STRING: return op == HA_CHILD || op == HA_EITHER_LEFT || op == HA_RAISE || op == HA_TRANSFER;
    case HA_MODE:
    case HA_SIZE: return op == HA_READ_MODE || op == HA_SCALAR_RESULT;
    case HA_BYTES: return op == HA_PUBLISH_BYTES;
    case HA_OCTET: return op == HA_READ_INDEX || op == HA_READ_BYTE || op == HA_SCALAR_RESULT;
    case HA_IS_LOCALHOST:
    case HA_IS_ZERO:
    case HA_EQUAL:
    case HA_HASH: return op == HA_READ_MODE || op == HA_READ_BYTE || op == HA_SCALAR_RESULT;
    case HA_SET_STRING: return op == HA_STRING_EMPTY || op == HA_STRING_LITERAL || op == HA_CONSTRUCT || op == HA_WRITE_MODE || op == HA_CHILD || op == HA_WRITE_BYTE || (op >= HA_RESOLVE && op <= HA_RESOLVER_FREE) || op == HA_RAISE;
    case HA_SET_RAW: return op == HA_READ_MODE || op == HA_WRITE_MODE || op == HA_WRITE_BYTE || op == HA_RAW_PRESENT || op == HA_RAW_BYTE;
    case HA_STREAM: return op == HA_READ_MODE || op == HA_RAISE || op == HA_FORMAT_ADDRESS;
    case HA_EP_LOOKUP: return op == HA_CHILD || op == HA_EITHER_LEFT || op == HA_TRANSFER || op == HA_CONSTRUCT;
    case HA_EP_PARSE: return (op >= HA_STRING_COPY && op <= HA_PARSE_PORT) || op == HA_CHILD || op == HA_EITHER_LEFT || op == HA_TRANSFER || op == HA_CONSTRUCT;
    case HA_EP_CTOR_DEFAULT: return op == HA_WRITE_PORT;
    case HA_EP_CTOR_HOST: return op == HA_TRANSFER || op == HA_READ_PORT || op == HA_WRITE_PORT;
    case HA_EP_CTOR_RAW: return op == HA_CONSTRUCT || op == HA_READ_PORT || op == HA_WRITE_PORT;
    case HA_EP_ADDRESS: return op == HA_TRANSFER;
    case HA_EP_PORT: return op == HA_READ_PORT || op == HA_SCALAR_RESULT;
    case HA_EP_EQUAL: return op == HA_READ_MODE || op == HA_READ_BYTE || op == HA_READ_PORT || op == HA_SCALAR_RESULT;
    case HA_EP_STREAM: return op == HA_STREAM_COPY || op == HA_CHILD || op == HA_INSERT_COLON || op == HA_INSERT_PORT;
    case HA_EP_HASH: return op == HA_READ_MODE || op == HA_READ_BYTE || op == HA_PORT_HASH || op == HA_SCALAR_RESULT;
    }
    return false;
  }
  bool overlaps(uintptr_t u, void const* p, size_t n) const {
    if (!p || !n)
      return false;
    auto v = reinterpret_cast<uintptr_t>(p);
    return u <= v ? v - u < 8 : u - v < n;
  }
  bool outputAlias(uintptr_t u) const {
    if ((input && overlaps(u, input->utf8Ptr(), input->utf8Size() + 1)) || overlaps(u, hostScratch.utf8Ptr(), hostScratch.utf8Size() + 1) || overlaps(u, portScratch.utf8Ptr(), portScratch.utf8Size() + 1))
      return true;
    if (lookup && lookup->isLeft() && overlaps(u, lookup->left().utf8Ptr(), lookup->left().utf8Size() + 1))
      return true;
    if (endpointLookup && endpointLookup->isLeft() && overlaps(u, endpointLookup->left().utf8Ptr(), endpointLookup->left().utf8Size() + 1))
      return true;
    if (resolved && !resolverFreed && resolverStatus == 0 && (overlaps(u, result, result ? sizeof(*result) : 0) || overlaps(u, current, current ? sizeof(*current) : 0) || (current && overlaps(u, current->ai_addr, current->ai_addrlen))))
      return true;
    return overlaps(u, this, sizeof(*this)) || overlaps(u, subject, subject ? sizeof(*subject) : 0) || overlaps(u, other, other ? sizeof(*other) : 0) || overlaps(u, endpoint, endpoint ? sizeof(*endpoint) : 0) || overlaps(u, otherEndpoint, otherEndpoint ? sizeof(*otherEndpoint) : 0) || overlaps(u, destination, destination ? sizeof(*destination) : 0) || overlaps(u, endpointDestination, endpointDestination ? sizeof(*endpointDestination) : 0) || overlaps(u, fieldMode, fieldMode ? sizeof(*fieldMode) : 0) || overlaps(u, writeMode, writeMode ? sizeof(*writeMode) : 0) || overlaps(u, fieldBytes, fieldBytes ? 16 : 0) || overlaps(u, writeBytes, writeBytes ? 16 : 0) || overlaps(u, fieldPort, fieldPort ? sizeof(*fieldPort) : 0) || overlaps(u, writePort, writePort ? sizeof(*writePort) : 0) || overlaps(u, raw, raw ? (requested == NetworkMode::IPv4 ? 4 : requested == NetworkMode::IPv6 ? 16
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  : 0)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           : 0)
      || overlaps(u, input, input ? sizeof(*input) : 0) || overlaps(u, stream, stream ? sizeof(*stream) : 0);
  }
  uint64_t operation(uint32_t op, uint64_t a, uint64_t b) {
    switch (op) {
    case HA_READ_MODE: check(b == 0); return readMode(a);
    case HA_READ_BYTE: return readByte(a, b);
    case HA_WRITE_MODE:
      if (a == HA_REQUESTED_MODE)
        requested = nativeMode(b);
      else {
        check(a == HA_SUBJECT && writeMode);
        *writeMode = nativeMode(b);
      }
      return 0;
    case HA_WRITE_BYTE: {
      auto i = b >> 8;
      check(i < 16);
      if (a == HA_BUFFER)
        buffer[i] = uint8_t(b);
      else {
        check(a == HA_SUBJECT && writeBytes);
        writeBytes[i] = uint8_t(b);
      }
      return 0;
    }
    case HA_RAW_PRESENT: check(a == 0 && b == 0); return raw != nullptr;
    case HA_RAW_BYTE: check(a == 0 && raw && b < (requested == NetworkMode::IPv4 ? 4u : requested == NetworkMode::IPv6 ? 16u
                                                                                                                       : 0u));
      return raw[b];
    case HA_READ_INDEX: check(a == 0 && b == 0 && invocation == HA_OCTET); return index;
    case HA_PUBLISH_BYTES:
      check(a == HA_SUBJECT && b == 0 && fieldBytes);
      pointerResult = fieldBytes;
      return 0;
    case HA_READ_PORT:
      check(b == 0);
      if (a == 0) {
        if (fieldPort)
          return *fieldPort;
        check(endpoint);
        return endpoint->port();
      }
      if (a == 1) {
        check(otherEndpoint);
        return otherEndpoint->port();
      }
      if (a == 2)
        return supplied;
      if (a == 3)
        return parsed;
      throw Stop{HA_INVALID};
    case HA_WRITE_PORT:
      check(a == 0 && b <= 65535 && writePort);
      *writePort = uint16_t(b);
      return 0;
    case HA_STRING_EMPTY: check(b == 0 && a < 3 && input); return a == 0 ? input->empty() : a == 1 ? hostScratch.empty()
                                                                                                   : portScratch.empty();
    case HA_STRING_LITERAL: check(b == 0 && a < 3 && input); return input->compare(a == 0 ? "*" : a == 1 ? "0.0.0.0"
                                                                                                         : "::")
      == 0;
    case HA_STRING_COPY:
      check(a == 0 && b == 0 && input);
      hostScratch = *input;
      return 0;
    case HA_STRING_REXTRACT:
      check(a == 0 && b == 0);
      portScratch = hostScratch.rextract(":");
      return 0;
    case HA_STRING_BEGINS: check(a == 0 && b == 0); return hostScratch.beginsWith("[");
    case HA_STRING_ENDS: check(a == 0 && b == 0); return hostScratch.endsWith("]");
    case HA_STRING_UNBRACKET:
      check(a == 0 && b == 0);
      hostScratch = hostScratch.substr(1, hostScratch.size() - 2);
      return 0;
    case HA_PARSE_PORT: {
      check(a == 0 && b == 0);
      auto p = maybeLexicalCast<uint16_t>(portScratch);
      if (p)
        parsed = *p;
      return bool(p);
    }
    case HA_RESOLVE: {
      check(a == 0 && b == 0 && input && !resolved);
      addrinfo hints;
      memset(&hints, 0, sizeof(hints));
      hints.ai_family = AF_UNSPEC;
      hints.ai_socktype = SOCK_STREAM;
      hints.ai_protocol = IPPROTO_TCP;
      hints.ai_flags = AI_ADDRCONFIG;
      auto n = ::getaddrinfo(input->utf8Ptr(), nullptr, &hints, &result);
      resolved = true;
      resolverStatus = uint32_t(n);
      current = n == 0 ? result : nullptr;
      return resolverStatus;
    }
    case HA_RESOLVER_HAS: check(a == 0 && b == 0 && resolved && !resolverFreed && resolverStatus == 0); return current != nullptr;
    case HA_RESOLVER_FAMILY: check(a == 0 && b == 0 && resolved && !resolverFreed && resolverStatus == 0 && current); return current->ai_family == AF_INET ? 1 : current->ai_family == AF_INET6 ? 2
                                                                                                                                                                                                : 0;
    case HA_RESOLVER_BYTE:
      check(b == 0 && resolved && !resolverFreed && resolverStatus == 0 && current);
      if (current->ai_family == AF_INET) {
        check(a < 4);
        return reinterpret_cast<uint8_t*>(&reinterpret_cast<sockaddr_in*>(current->ai_addr)->sin_addr)[a];
      }
      check(current->ai_family == AF_INET6 && a < 16);
      return reinterpret_cast<uint8_t*>(&reinterpret_cast<sockaddr_in6*>(current->ai_addr)->sin6_addr)[a];
    case HA_RESOLVER_NEXT:
      check(a == 0 && b == 0 && resolved && !resolverFreed && resolverStatus == 0 && current);
      current = current->ai_next;
      return 0;
    case HA_RESOLVER_FREE:
      check(a == 0 && b == 0 && resolved && !resolverFreed && resolverStatus == 0);
      ::freeaddrinfo(result);
      resolverFreed = true;
      result = current = nullptr;
      return 0;
    case HA_CONSTRUCT:
      switch (a) {
      case HA_DEFAULT_LOOKUP_HOST:
        check(b == 0);
        temporary.emplace();
        break;
      case HA_ZERO_BUFFER:
        check(b == 0);
        memset(buffer, 0, 16);
        break;
      case HA_HOST_FROM_BUFFER: hostResult.emplace(nativeMode(b), buffer); break;
      case HA_HOST_COPY: hostResult.emplace(slot(b)); break;
      case HA_ENDPOINT_FROM_HOST_PORT:
        check(b == 2 || b == 3);
        endpointResult.emplace(lookup->right(), b == 2 ? supplied : parsed);
        break;
      case HA_ENDPOINT_FROM_RAW_PORT:
        check(b == 0 && copyEndpointHost);
        copyEndpointHost(*this, HostAddress(requested, mutableRaw));
        break;
      default: throw Stop{HA_INVALID};
      }
      return 0;
    case HA_CHILD:
      switch (a) {
      case HA_CHILD_SET_STRING:
        check(b == HA_LOOKUP_TEMP && temporary && setString);
        setString(*this, *input);
        break;
      case HA_CHILD_SET_RAW:
        check((b == HA_SUBJECT || b == HA_BUFFER) && setRaw);
        setRaw(*this, requested, b == HA_BUFFER ? buffer : raw);
        break;
      case HA_CHILD_HOST_LOOKUP:
        check((b == 0 || b == HA_LOOKUP_TEMP) && input);
        lookup = HostAddress::lookup(b == 0 ? *input : hostScratch);
        break;
      case HA_CHILD_ENDPOINT_LOOKUP:
        check(b == 0 && input);
        endpointLookup = HostAddressWithPort::lookup(*input, supplied);
        break;
      case HA_CHILD_ENDPOINT_PARSE:
        check(b == 0 && input);
        endpointLookup = HostAddressWithPort::lookupWithPort(*input);
        break;
      case HA_CHILD_ADDRESS_STREAM:
        check(b == HA_STREAM_TEMP && streamTemporary && stream);
        *stream << *streamTemporary;
        break;
      default: throw Stop{HA_INVALID};
      }
      return 0;
    case HA_EITHER_LEFT: check(b == 0 && a < 2 && (a == 0 ? bool(lookup) : bool(endpointLookup))); return a == 0 ? lookup->isLeft() : endpointLookup->isLeft();
    case HA_TRANSFER:
      switch (a) {
      case HA_HOST_RIGHT:
        check(b == 0 && temporary);
        lookup = makeRight(std::move(*temporary));
        break;
      case HA_ENDPOINT_RIGHT:
        check(b == 0 && endpointResult);
        endpointLookup = makeRight(std::move(*endpointResult));
        break;
      case HA_PROPAGATE_LEFT:
        check(b == 0 && lookup);
        endpointLookup = makeLeft(std::move(lookup->left()));
        break;
      case HA_ASSIGN_HOST_RIGHT:
        check(b == 0 && destination);
        *destination = std::move(lookup->right());
        break;
      case HA_ASSIGN_ENDPOINT_RIGHT:
        check(b == 0 && endpointDestination);
        *endpointDestination = std::move(endpointLookup->right());
        break;
      case HA_COPY_ENDPOINT_HOST:
        check(b == 0 && subject);
        hostResult.emplace(*subject);
        break;
      case HA_PORT_ERROR_LEFT:
        check(b == 0);
        endpointLookup = makeLeft(strf("Could not parse port portion of HostAddressWithPort '{}'", portScratch));
        break;
      case HA_COPY_HOST_INPUT:
        check(b == 0 && copyEndpointHost && subject);
        copyEndpointHost(*this, *subject);
        break;
      default: throw Stop{HA_INVALID};
      }
      return 0;
    case HA_RAISE:
      check(b == 0);
      if (a == HA_ERROR_RESOLVER)
        throw NetworkException(strf("Failed to determine address for '{}' ({})", *input, netErrorString()));
      if (a == HA_ERROR_MODE)
        throw NetworkException(strf("Unknown address mode ({})", int(slot(HA_SUBJECT).mode())));
      if (a == HA_ERROR_HOST_LEFT)
        throw NetworkException(lookup->left().takeUtf8());
      if (a == HA_ERROR_ENDPOINT_LEFT)
        throw NetworkException(endpointLookup->left().takeUtf8());
      throw Stop{HA_INVALID};
    case HA_STREAM_COPY:
      check(a == 0 && b == 0 && endpoint);
      streamTemporary.emplace(endpoint->address());
      return 0;
    case HA_FORMAT_ADDRESS: {
      check(a < 2 && b == HA_SUBJECT && stream);
      auto const& h = slot(b);
      if (a == 0)
        format(*stream, "{}.{}.{}.{}", h.octet(0), h.octet(1), h.octet(2), h.octet(3));
      else
        format(*stream, "{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}:{:02x}{:02x}", h.octet(0), h.octet(1), h.octet(2), h.octet(3), h.octet(4), h.octet(5), h.octet(6), h.octet(7), h.octet(8), h.octet(9), h.octet(10), h.octet(11), h.octet(12), h.octet(13), h.octet(14), h.octet(15));
      return 0;
    }
    case HA_INSERT_COLON:
      check(a == 0 && b == 0 && stream);
      *stream << ":";
      return 0;
    case HA_INSERT_PORT:
      check(a == 0 && b == 0 && stream && endpoint);
      *stream << endpoint->port();
      return 0;
    case HA_PORT_HASH: check(b == 0 && a < 3); return Star::hash<uint16_t>()(a == 0 ? endpoint->port() : a == 1 ? supplied
                                                                                                                : parsed);
    case HA_SCALAR_RESULT:
      check(b == 0 && !published);
      scalar = a;
      published = true;
      return 0;
    case HA_FINISH:
      check(a == 0 && b == 0 && !finished);
      if (invocation == HA_MODE || invocation == HA_OCTET || invocation == HA_IS_LOCALHOST || invocation == HA_IS_ZERO || invocation == HA_SIZE || invocation == HA_EQUAL || invocation == HA_HASH || invocation == HA_EP_PORT || invocation == HA_EP_EQUAL || invocation == HA_EP_HASH)
        check(published);
      if (invocation == HA_LOOKUP)
        check(bool(lookup));
      if (invocation == HA_LOCALHOST)
        check(bool(hostResult) || bool(lookup));
      if (invocation == HA_EP_LOOKUP || invocation == HA_EP_PARSE)
        check(bool(endpointLookup));
      if (invocation == HA_EP_ADDRESS)
        check(bool(hostResult));
      if (invocation == HA_BYTES)
        check(pointerResult);
      finished = true;
      return 0;
    case HA_PENDING_NETWORK:
      check(a == 0 && b == 0 && pending && invocation == HA_LOOKUP);
      try {
        std::rethrow_exception(pending);
      } catch (NetworkException const&) { return 1; } catch (...) {
        return 0;
      }
    case HA_CATCH_NETWORK:
      check(a == 0 && b == 0 && pending && invocation == HA_LOOKUP);
      try {
        std::rethrow_exception(pending);
      } catch (NetworkException const& e) {
        lookup = makeLeft(String(e.what()));
        pending = nullptr;
        return 0;
      }
    }
    throw Stop{HA_INVALID};
  }
  static uint32_t callback(void* p, uint32_t op, uint64_t a, uint64_t b, uint64_t* out) noexcept {
    if (!p || !out)
      return HA_INVALID;
    auto& c = *static_cast<Context*>(p);
    auto u = reinterpret_cast<uintptr_t>(out);
    if ((u & 7) || u > UINTPTR_MAX - sizeof(uint64_t) || c.busy || c.finished || !c.allows(op) || c.outputAlias(u))
      return HA_INVALID;
    if (c.pending && op != HA_PENDING_NETWORK && op != HA_CATCH_NETWORK)
      return HA_PENDING;
    c.busy = true;
    try {
      auto value = c.operation(op, a, b);
      *out = value;
      c.busy = false;
      return HA_OK;
    } catch (Stop const& s) {
      c.busy = false;
      return s.status;
    } catch (...) {
      c.pending = std::current_exception();
      c.busy = false;
      return HA_PENDING;
    }
  }
  void run() {
    auto s = star_host_address_run(invocation, this, callback);
    if (pending)
      std::rethrow_exception(pending);
    if (s != HA_OK || !finished)
      throw std::logic_error("host-address Rust protocol failure");
  }
};
}// namespace HostAddressRust
}// namespace Star
