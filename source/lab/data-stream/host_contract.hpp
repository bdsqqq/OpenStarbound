#ifndef DATA_STREAM_LAB_HOST_CONTRACT_HPP
#define DATA_STREAM_LAB_HOST_CONTRACT_HPP
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Native-calibrated contract; Rust integration remains unqualified.
 * No C++ layout, object pointers or byte views cross
 * this ABI. ctx is opaque, and NULL is valid for a custom host. Native owners,
 * typed caller references, temporary strings and iterator lifetimes stay C++.
 * 0=success, 1=pending native exception, 2=invalid protocol. 3 contains a foreign
 * C++ callback throw in this prototype ONLY; it is not a future Rust guarantee.
 * Every host call receives an aligned, nonwrapping uint64_t output span, even
 * for operations with no result. Unknown host statuses map to 2. */
typedef uint32_t (*data_stream_lab_host)(void*, uint32_t, uint64_t, uint64_t, uint64_t*);
enum data_stream_lab_mode {
 DS_CTOR=0, DS_GET_ORDER, DS_SET_ORDER, DS_GET_NULL, DS_SET_NULL,
 DS_GET_VERSION, DS_SET_VERSION, DS_SET_RULES, DS_READ_BYTES, DS_WRITE_BYTES,
 DS_WRITE_BOOL, DS_WRITE_CHAR, DS_WRITE_I8, DS_WRITE_U8, DS_WRITE_I16,
 DS_WRITE_U16, DS_WRITE_I32, DS_WRITE_U32, DS_WRITE_I64, DS_WRITE_U64,
 DS_WRITE_F32, DS_WRITE_F64, DS_READ_BOOL, DS_READ_CHAR, DS_READ_I8,
 DS_READ_U8, DS_READ_I16, DS_READ_U16, DS_READ_I32, DS_READ_U32,
 DS_READ_I64, DS_READ_U64, DS_READ_F32, DS_READ_F64,
 DS_WRITE_VLQU, DS_WRITE_VLQI, DS_WRITE_VLQS, DS_READ_VLQU, DS_READ_VLQI,
 DS_READ_VLQS, DS_VALUE_VLQU, DS_VALUE_VLQI, DS_VALUE_VLQS,
 DS_WRITE_CSTRING, DS_WRITE_STDSTRING, DS_WRITE_ARRAY, DS_WRITE_STRING,
 DS_READ_STDSTRING, DS_READ_ARRAY, DS_READ_STRING, DS_WRITE_STRING_DATA
};
/* Modes follow the 51 production .cpp definition order exactly. Slots below
 * select capabilities bound by that member, never addresses or magic indices.
 * All unused a/b arguments MUST be zero. No retry after pending/error, and no
 * implicit rollback/cleanup. Finish is single-use per invocation. This native
 * prototype is qualified only for the sealed 64-bit little-endian profile;
 * UINT64_MAX below denotes that profile's native NPos, never a slot selector.
 * Guards cover selected capability/argument/span/alias states, not a complete
 * per-mode protocol automaton or arbitrary pointer validity. */
enum data_stream_lab_op {
 DS_CONFIG_GET=0, /* a: 0 order,1 null,2 version,3 rules.version,4 native
                     CurrentStreamVersion,5 platform order; b=0; out=value. */
 DS_CONFIG_SET,   /* a:0 order(32-bit pattern),1 null(0/1),2 version(u32);
                     b=value within that domain; out=0. */
 DS_ARGUMENT,     /* a=b=0; out=native scalar argument (signed as bit pattern). */
 DS_RESULT,       /* a=0,b=value; native scalar result slot only; out=0. */
 DS_SCALAR_IO,    /* a:0 read DIRECT caller bytes (bool instead binds a native
                     uint8 temporary then DS_BOOL_ASSIGN),1 write native local; b=0. */
 DS_CONVERT,      /* a=byte order bit pattern,b=0; native typed assignment via
                     existing Bytes dependency: TO for writes, FROM for reads,
                     called UNCONDITIONALLY for wide primitives at the source
                     point, even native/NoConversion order. No float arithmetic
                     in ABI. Order patterns 0=big,1=little,2=no conversion;
                     unknown int32 patterns retain native Bytes semantics. */
 DS_BOOL_ASSIGN,  /* a=b=0; native bool = (native uint8 temporary != 0). */
 DS_SIZE,         /* a=b=0; out=current native container size. */
 DS_CAPTURE,      /* a=b=0; capture native pointer AND size together, out=size.
                     ByteArray capture occurs AFTER prefix callbacks. String
                     input capture occurs BEFORE private child/prefix. */
 DS_VIEW_IO,      /* a:0 read,1 write;b=0; exact captured ptr/size, including 0.
                     No view/reference in the controller crosses a callback. */
 DS_RESIZE,       /* a=0,b=size; native stdstring/ByteArray resize before IO. */
 DS_CLEAR,        /* a=b=0; clear bound native stdstring immediately. */
 DS_APPEND,       /* a=0,b=byte; append to native stdstring. */
 DS_CHAR_READ,    /* a=b=0; virtual read of native char temporary; out=byte. */
 DS_CHILD,        /* a:0 migrated writeVlqU(b),1 migrated readVlqU()(b=0),
                     2 private writeStringData(captured view)(b=0),
                     3 migrated stdstring read into native temp(b=0),
                     4 migrated uint8 write(b=0..255; terminator uses 0),
                     5/6/7 migrated U/I/S
                     reference reads into bound native
                     temporaries (all b=0); out=count/value/0. */
 DS_VLQ,          /* a:0 lower writeU,1 lower writeI,2 lower readU,3 lower readI;
                     b=input bits for writes,0 for reads; out=count/NPos.
                     Existing VLQ + native function iterators are dependencies,
                     NOT a newly ported DataStream whole-method callback. */
 DS_VLQ_VALUE,    /* a:0 U,1 I bits,2 size; b=0; out=bound native
                     temporary AFTER successful child. */
 DS_ASSIGN_SIZE,  /* a=0,b=decoded size; mutate native caller size_t. */
 DS_ASSIGN_STRING,/* a=b=0; exact native String = std::move(stdstring temp),
                     only after child success; temp lives in member scope. */
 DS_RAISE_VLQ,    /* a=b=0; must return pending=1; success is contradictory. */
 DS_FINISH        /* a=b=0; seal invocation, out=0; later calls invalid. */
};
uint32_t data_stream_lab_run(uint32_t mode, void* ctx, data_stream_lab_host host);
#ifdef __cplusplus
}
#endif
#endif
