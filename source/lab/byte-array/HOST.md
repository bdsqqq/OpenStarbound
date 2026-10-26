# bytearray native opaque controller bundle

source-only prototype at base c0ee337660ece996ed2f638e7bd1dc62882d5c3e.
no native compilation/execution by the author; NOT native or Rust qualification.
only these seven files are owned. production and the frozen 987/14 corpora remain
unchanged. parent owns compilation, overlay coherence, replay, controls, review,
provenance and commits. no Rust, game, allocation-fault, sanitizer or performance
claim. source inspection is not behavioral acceptance.

## integration

`sb_byte_array_run(uint32_t, void*, SbByteArrayHost)` is the actual dispatch.
`sb_byte_array_call_count(mode,event)` reports thread-local wrapping uint64 counts:
0 attempt, 1 success, 2 pending-native-exception. reject null context/callback and
mode >=56 before counting. invalid protocol never counts success/pending.
returned status 3 is reserved for a foreign C++ callback throw caught by this
prototype controller; callbacks returning 3 or unknown status produce 2.
all real wrappers call the controller, not a synthetic counter route.

compile all 113 native core/extern objects and unchanged probes with ONE Clang VFS
overlay: actual source/core/StarByteArray.hpp -> host_header.hpp and .cpp ->
host_body.cpp. add this lab directory to include paths. link host_controller.cpp;
host_body.cpp defines the stream hex leaf. no old archive mixing. host_protocol.cpp
is a separate executable and uses explicit CHECK/abort, independent of NDEBUG.
compile host_api.h separately as strict C11. parent may wrap unchanged corpus main
and print counters to stderr; stdout remains the frozen expected stream.

header public declarations and three private data fields are preserved byte for
byte, except the permitted friend declaration. host_native.hpp is included after
the real class declaration. no class clone, field-layout mirror or pointer encoded
as integer crosses the C ABI. native uintptr values only validate output ranges.

## ownership and protocol

roles: 0 receiver, 1 other, 2 native optional result, 3 fixed smaller, 4 fixed larger.
ARG accepts index 0/1; wrapper arguments follow source parameter order, except
combine and built-in bitwise methods use arg0=extend; chars use unsigned-byte bits.
controller return scalar is stored with RETURN; pointers/references/iterators stay
in NativeCtx.pointer. signed compare -1 is UINT64_MAX. hash leaf receives native
plain char, retaining signed-char-to-size_t conversion.

all unused operands must be zero. scalar reads are ARG, GET_SIZE, GET_CAPACITY,
HAS_DATA, SAME, CAPTURE, GET_BYTE, STRLEN, ITER_DISTANCE and HASH_RESULT; all other
successful operations must return zero. booleans must be 0/1; bytes <=255.
FINISH is required for success and never inspects borrowed owners. every native
callback catches exceptions, retains the first exception_ptr, and returns 1;
controller stops immediately, wrapper rethrows the same exception. no rollback.
noexcept move/destructor specifications terminate on a thrown protocol fault.
busy belongs to each context; fresh contexts on the same owner remain allowed.

result optional is initially disengaged; INIT_RESULT constructs with a fresh
context. default constructor sets ready=false, so field-read guards reject without
inspecting uninitialized fields. borrowed backing ranges are captured once at
execute entry (constructor destination excluded), never refreshed after callbacks.
owned result backing can be checked while its optional is live. explicit index
and memory-span guards do not depend on starAssert. raw pointer wrappers record
the caller-provided external span; this does not prove arbitrary external memory
is actually allocated/initialized. ByteArray source capture uses physical capacity,
not logical size, preserving admitted sub/right copies. native copy operations
reject null even for zero length; the finite corpus already excludes those calls.
source unsigned size arithmetic wraps; no invented allocation-failure domain.

native allocation accepts exact controller-selected capacity, calls native
malloc/realloc/free, and commits pointer/capacity only after allocation succeeds.
controller selects first exact allocation or max(capacity*2,request,8).
memcpy and memmove remain distinct. capture occurs before append resize.

combine selects roles once (ties RHS), rereads smaller size every condition,
initializes result to initial smaller size, and rereads larger size for extension.
the typed expression leaf is exactly result[i]=function(smaller[i],larger[i]);
it includes implicit conversion, destination assignment and temporary destruction.
callable stays a typed lvalue reference, including function types and noncopyable
objects. no wrapper/FINISH/destructor reads a deleted larger input after the final
non-extend callback. stream prefix and hex insertion are separate leaves so user
stream code runs before hex reads the array.

## operation operands

- ARG(a=index); GET_SIZE/GET_CAPACITY/HAS_DATA/FREE(a=role).
- INIT(a=0) initializes receiver fields without reading them.
- SET_SIZE(a=role,b=size); ALLOC(a=role,b=exact capacity,c=realloc boolean).
- TAKE() transfers native fields; SAME() compares receiver/other identity.
- CAPTURE(a=role,b=offset) stores native source pointer and physical remaining span,
  returning logical source size. COPY_IN/OUT(a=role,b=offset,c=count).
- MOVE_BYTES(a=0,b=source offset,c=count) moves to receiver offset zero.
- FILL_BYTES(a=role,b=byte); GET_BYTE(a=role,b=index);
  SET_BYTE(a=role,b=index,c=byte).
- POINTER(a=role,b=offset,c=0 raw/1 end/2 checked reference) stores native pointer.
- STRLEN() captures input string span including null; INIT_RESULT().
- ROLES(a=receiver smaller boolean); EXPR(a=index,b=0 generic/1 and/2 or/3 xor);
  TAIL_EXPR(a=index).
- ITER_DISTANCE(); ASSERT_INSERT(a=position); THROW_AT(a=index) MUST return pending.
- HASH_PUT(a=index); HASH_RESULT(); STREAM_PREFIX(); STREAM_HEX().
- RETURN(a=scalar); FINISH().

## acceptance still owed

parent must compile and execute native protocol and strict C11 probes, all 987+14
unchanged rows, route-counter checks, normally exiting controls and source review.
protocol tests are written, not executed: null/unknown/unused operands, bad status,
foreign callback containment, pending identity, output overlap, copy/index bounds,
constructor readiness, typed proxy/function callables, fresh reentry, both deleted
larger roles, and FINISH without owner reads. retained failure artifacts and source
review govern any later correction; no golden/model fitting is authorized.

## source-ordered mode map

0: fromCString — StarByteArray.cpp:6

1: fromCStringWithNull — StarByteArray.cpp:10

2: withReserve — StarByteArray.cpp:17

3: default constructor — StarByteArray.cpp:23

4: fill constructor — StarByteArray.cpp:29

5: pointer constructor — StarByteArray.cpp:34

6: copy constructor — StarByteArray.cpp:39

7: move constructor — StarByteArray.cpp:44

8: destructor — StarByteArray.cpp:49

9: copy assignment — StarByteArray.cpp:53

10: move assignment — StarByteArray.cpp:62

11: reset — StarByteArray.cpp:74

12: reserve — StarByteArray.cpp:83

13: resize filled — StarByteArray.cpp:102

14: fill sized — StarByteArray.cpp:112

15: fill current — StarByteArray.cpp:119

16: sub — StarByteArray.cpp:123

17: left — StarByteArray.cpp:131

18: right — StarByteArray.cpp:135

19: trimLeft — StarByteArray.cpp:144

20: trimRight — StarByteArray.cpp:153

21: diffChar — StarByteArray.cpp:160

22: compare — StarByteArray.cpp:173

23: andWith — StarByteArray.cpp:210

24: orWith — StarByteArray.cpp:214

25: xorWith — StarByteArray.cpp:218

26: insert index — StarByteArray.cpp:222

27: insert iterator — StarByteArray.cpp:230

28: push_back — StarByteArray.cpp:236

29: operator< — StarByteArray.cpp:241

30: operator== — StarByteArray.cpp:245

31: operator!= — StarByteArray.cpp:249

32: ostream — StarByteArray.cpp:253

33: clear — StarByteArray.hpp:126

34: resize raw — StarByteArray.hpp:130

35: append array — StarByteArray.hpp:135

36: append pointer — StarByteArray.hpp:139

37: appendByte — StarByteArray.hpp:144

38: empty — StarByteArray.hpp:149

39: ptr const — StarByteArray.hpp:153

40: ptr mutable — StarByteArray.hpp:157

41: size — StarByteArray.hpp:161

42: capacity — StarByteArray.hpp:165

43: copyTo length — StarByteArray.hpp:169

44: copyTo all — StarByteArray.hpp:174

45: copyTo range — StarByteArray.hpp:178

46: writeFrom — StarByteArray.hpp:186

47: combineWith — StarByteArray.hpp:194

48: begin mutable — StarByteArray.hpp:216

49: end mutable — StarByteArray.hpp:220

50: begin const — StarByteArray.hpp:224

51: end const — StarByteArray.hpp:228

52: index mutable — StarByteArray.hpp:232

53: index const — StarByteArray.hpp:237

54: at — StarByteArray.hpp:242

55: hash — StarByteArray.hpp:249

