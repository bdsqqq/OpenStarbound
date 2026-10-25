#ifndef STAR_RUST_HOST_ADDRESS_H
#define STAR_RUST_HOST_ADDRESS_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Production scalar bridge; Rust owns all 27 controllers.
 * Callbacks retain all native objects, strings, Either, resolver nodes, stream,
 * pointers and exception_ptr. No object address is encoded in a scalar. The
 * controller sees only explicit selectors/scalars. Primitive output requires a
 * live aligned writable eight-byte allocation, nonwrapping/disjoint from known
 * native extents. Arbitrary liveness/heap aliasing remains a caller precondition.
 * Write scalar outputs only on success; unused operands must be zero.
 */
typedef uint32_t (*StarHostAddressHost)(void*, uint32_t, uint64_t, uint64_t, uint64_t*);
enum StarHostAddressStatus { HA_OK=0, HA_PENDING=1, HA_INVALID=2, HA_PANIC=3 };
enum StarHostAddressMode {
 HA_LOCALHOST=0, HA_LOOKUP=1, HA_CTOR_RAW=2, HA_CTOR_STRING=3,
 HA_MODE=4, HA_BYTES=5, HA_OCTET=6, HA_IS_LOCALHOST=7, HA_IS_ZERO=8,
 HA_SIZE=9, HA_EQUAL=10, HA_SET_STRING=11, HA_SET_RAW=12,
 HA_STREAM=13, HA_HASH=14, HA_EP_LOOKUP=15, HA_EP_PARSE=16,
 HA_EP_CTOR_DEFAULT=17, HA_EP_CTOR_HOST=18, HA_EP_CTOR_RAW=19,
 HA_EP_CTOR_STRING_PORT=20, HA_EP_CTOR_STRING=21, HA_EP_ADDRESS=22,
 HA_EP_PORT=23, HA_EP_EQUAL=24, HA_EP_STREAM=25, HA_EP_HASH=26
};

/* Slot identifiers are logical native bindings, NOT offsets/layouts. A mode
 * validates exactly which slots exist. Endpoint slots expose their HostAddress
 * only via public migrated getters/native copies; never access another class's
 * private fields. Requested-mode is a scalar payload, not an object slot.
 */
enum StarHostAddressSlot {
 HA_SUBJECT=0, HA_OTHER=1, HA_LOOKUP_TEMP=2, HA_STREAM_TEMP=3,
 HA_ENDPOINT_ADDRESS=4, HA_OTHER_ENDPOINT_ADDRESS=5, HA_BUFFER=6,
 HA_REQUESTED_MODE=7
};
enum StarHostAddressOp {
 HA_READ_MODE=0,          /* a=slot, b=0; u32 bit pattern of native int enum */
 HA_READ_BYTE=1,          /* a=slot,b=index<16; caller-initialized byte, not limited by size() */
 HA_WRITE_MODE=2,         /* a=destination, b=u32 enum bits */
 HA_WRITE_BYTE=3,         /* a=destination, b=index<<8|octet */
 HA_RAW_PRESENT=4,        /* a=b=0; raw input pointer present */
 HA_RAW_BYTE=5,           /* a=0, b=index; valid input extent precondition */
 HA_PUBLISH_BYTES=6,      /* a=slot,b=0; native pointer result, scalar zero */
 HA_READ_PORT=7,          /* a=0 endpoint/1 other/2 supplied/3 parsed,b=0 */
 HA_WRITE_PORT=8,         /* a=0 destination,b=u16 */
 HA_STRING_EMPTY=9,       /* a=0 input/1 host scratch/2 port scratch,b=0 */
 HA_STRING_LITERAL=10,    /* a=0 star/1 zeroIPv4/2 zeroIPv6,b=0 */
 HA_STRING_COPY=11,       /* a=b=0; native host scratch from input */
 HA_STRING_REXTRACT=12,   /* a=b=0; exact host.rextract(":") into port scratch */
 HA_STRING_BEGINS=13,     /* a=b=0; host.beginsWith("[") */
 HA_STRING_ENDS=14,       /* a=b=0; host.endsWith("]") */
 HA_STRING_UNBRACKET=15,  /* a=b=0; exact host.substr(1,host.size()-2) */
 HA_PARSE_PORT=16,        /* a=b=0; native Maybe<uint16>, scalar presence */
 HA_RESOLVE=17,           /* a=b=0; exact native hints/query, u32 status bits */
 HA_RESOLVER_HAS=18,      /* a=b=0; native current != nullptr */
 HA_RESOLVER_FAMILY=19,   /* a=b=0; 0 other/1 AF_INET/2 AF_INET6 */
 HA_RESOLVER_BYTE=20,     /* a=index,b=0; native recognized sockaddr byte */
 HA_RESOLVER_NEXT=21,     /* a=b=0; native ai_next */
 HA_RESOLVER_FREE=22,     /* a=b=0; original result, NORMAL path only */
 HA_CONSTRUCT=23,         /* a=construction selector below,b=explicit slot/mode */
 HA_CHILD=24,             /* a=child selector below,b=explicit slot */
 HA_EITHER_LEFT=25,       /* a=0 host lookup/1 endpoint lookup,b=0 */
 HA_TRANSFER=26,          /* a=transfer selector below,b=explicit slot */
 HA_RAISE=27,             /* a=error selector below,b=0; MUST return pending */
 HA_STREAM_COPY=28,       /* a=b=0; endpoint.address() native COPY scratch */
 HA_FORMAT_ADDRESS=29,    /* a=0 IPv4/1 IPv6,b=slot; ONE original format(os,..) */
 HA_INSERT_COLON=30,      /* a=b=0; native os << ":" */
 HA_INSERT_PORT=31,       /* a=b=0; read CURRENT port then native os<<uint16 */
 HA_PORT_HASH=32,         /* a=0 endpoint/1 supplied/2 parsed,b=0; native hash<u16> */
 HA_SCALAR_RESULT=33,     /* a=computed scalar,b=0; publish into native result slot */
 HA_FINISH=34,            /* a=b=0; successful typed terminal phase */
 HA_PENDING_NETWORK=35,   /* a=b=0; classify pending exception, scalar bool */
 HA_CATCH_NETWORK=36,     /* a=b=0; source lookup catch constructs Either::Left */
 HA_READ_INDEX=37         /* a=b=0; native public octet(size_t) argument, NOT a byte read */
};
enum StarHostAddressConstruct {
 HA_DEFAULT_LOOKUP_HOST=0, HA_ZERO_BUFFER=1, HA_HOST_FROM_BUFFER=2,
 HA_HOST_COPY=3, HA_ENDPOINT_FROM_HOST_PORT=4, HA_ENDPOINT_FROM_RAW_PORT=5
};
enum StarHostAddressChild {
 HA_CHILD_SET_STRING=0, HA_CHILD_SET_RAW=1, HA_CHILD_HOST_LOOKUP=2,
 HA_CHILD_ENDPOINT_LOOKUP=3, HA_CHILD_ENDPOINT_PARSE=4,
 HA_CHILD_ADDRESS_STREAM=5
};
enum StarHostAddressTransfer {
 HA_HOST_RIGHT=0, HA_ENDPOINT_RIGHT=1, HA_PROPAGATE_LEFT=2,
 HA_ASSIGN_HOST_RIGHT=3, HA_ASSIGN_ENDPOINT_RIGHT=4,
 HA_COPY_ENDPOINT_HOST=5, HA_PORT_ERROR_LEFT=6, HA_COPY_HOST_INPUT=7
};
enum StarHostAddressError {
 HA_ERROR_RESOLVER=0, HA_ERROR_MODE=1, HA_ERROR_HOST_LEFT=2,
 HA_ERROR_ENDPOINT_LEFT=3
};

/* Modes follow source definition order. Mode 1 explicitly catches only native
 * NetworkException. HA_PENDING_NETWORK/HA_CATCH_NETWORK are the ONLY operations
 * allowed to inspect/consume that pending source catch. CATCH constructs native
 * String(e.what())/Either::Left before clearing the original. If that catch body
 * throws, replace pending with the NEW exception, as native C++ does. Ordinary
 * pending failures stop immediately: no cleanup/retry/auto-free through Rust.
 * Rethrow while native context lives, preserving source-scope RAII destruction.
 *
 * Public NetworkMode is enum class with fixed int underlying type. Preserve all
 * representable values. Unknown nonnull raw-set leaves bytes uninitialized;
 * unknown null raw-set initializes all16. IPv4 initializes only first4 bytes.
 * Never read inactive tails/padding or compare sizeof(native object).
 *
 * Endpoint output retains a native copied HostAddress through the ENTIRE full
 * expression: emit old copied address, emit colon, read fresh original port,
 * insert port with native locale/base/width semantics. User streambuf may mutate
 * the original endpoint at either insertion. Each context guards only its own
 * busy callback; separate-context same-object reentry is permitted where defined.
 *
 * Resolver fixtures are counterfactual unless explicitly real-numeric. Native
 * acquire uses AF_UNSPEC/SOCK_STREAM/IPPROTO_TCP/AI_ADDRCONFIG and native errno
 * error text. First recognized result wins. Free only at source normal location;
 * context destructor MUST NOT invent resolver cleanup on a pending error.
 * Native child operations invoke OTHER migrated controllers, never unchanged
 * legacy whole parsers/classifiers/hashes. Staging getters/raw-set bind actual
 * private field references inside authorized existing member definitions.
 *
 * Host status outside0/1/2 maps to invalid2. Scalar results use opcode33 rather
 * than a second unvalidated public output pointer. This keeps pointer/class
 * return values native and the future Rust ABI consistent with prior runners.
 */
uint32_t star_host_address_run(uint32_t, void*, StarHostAddressHost);
uint64_t star_host_address_call_count(uint32_t mode, uint32_t event);
#ifdef __cplusplus
}
#endif
#endif
