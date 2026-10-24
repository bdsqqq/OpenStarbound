#ifndef STAR_OPTION_PARSER_LAB_HOST_CONTRACT_H
#define STAR_OPTION_PARSER_LAB_HOST_CONTRACT_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Phase-one ABI: native ownership only. No native layout, text pointer, object
 * address encoded as an integer, or Rust reference crosses a callback. Scalar
 * outputs are live, writable, aligned eight-byte objects; checked ranges must
 * not wrap or overlap native context/storage. Liveness is a caller precondition,
 * not something integer-address validation can establish.
 *
 * Unused operands MUST be zero. Output is written only on success. Preserve the
 * first exception_ptr and partial native mutations. No foreign unwind. A busy
 * guard belongs to one context, never the parser: different invocations may
 * borrow the same parser during defined ostream callbacks.
 */
typedef uint32_t (*StarOptionParserLabHost)(void*, uint32_t, uint64_t,
                                          uint64_t, uint64_t, uint64_t*);

enum StarOptionParserLabStatus {
  STAR_OP_OK = 0,
  STAR_OP_PENDING = 1,
  STAR_OP_INVALID = 2,
  STAR_OP_PANIC = 3 /* runner only */
};

enum StarOptionParserLabMode {
  STAR_OP_SET_NAME = 0,
  STAR_OP_SET_SUMMARY = 1,
  STAR_OP_SET_ADDITIONAL = 2,
  STAR_OP_ADD_SWITCH = 3,
  STAR_OP_ADD_PARAMETER = 4,
  STAR_OP_ADD_ARGUMENT = 5,
  STAR_OP_PARSE = 6,
  STAR_OP_HELP = 7
};

/* All ordinary void successes return scalar zero. Native context validates
 * mode, phase, typed scratch and iterator liveness before touching storage.
 *
 * INSERT_* retains the exact native insert(flag, NativeRecord{...}) expression
 * (including by-value/move/temporary semantics) and returns .second. Rust owns
 * the duplicate branch and chooses THROW_FORMAT. Never call addSwitch(),
 * addParameter(), parseOptions(), printHelp(), or a whole validation handler.
 *
 * Formatting leaves retain each original native FULL EXPRESSION. Rust chooses
 * the template and WHEN to append/insert; native code performs only the chosen
 * strf/append or format(os,...) primitive. No callback chooses a help layout,
 * traverses a container, consumes a token conditionally, or validates counts.
 */
enum StarOptionParserLabOp {
  STAR_OP_MOVE_METADATA = 1,       /* a=field 0 name/1 summary/2 additional */
  STAR_OP_INSERT_SWITCH = 2,       /* payload-native args; out=inserted */
  STAR_OP_INSERT_PARAMETER = 3,    /* payload-native args; out=inserted */
  STAR_OP_APPEND_ARGUMENT = 4,     /* exact native append(Argument{...}) */
  STAR_OP_THROW_FORMAT = 5,        /* a=22 switch duplicate/23 flag duplicate */
  STAR_OP_INPUT_INIT = 6,          /* actual makeSIterator(input) */
  STAR_OP_INPUT_HAS_NEXT = 7,
  STAR_OP_INPUT_NEXT_TOKEN = 8,    /* borrow actual next String, no copy */
  STAR_OP_TOKEN_EQ_END = 9,        /* actual token == "--" */
  STAR_OP_TOKEN_BEGINS_DASH = 10,  /* actual token.beginsWith("-") */
  STAR_OP_FLAG_FROM_TOKEN = 11,    /* construct String flag=token.substr(1) */
  STAR_OP_LOOKUP = 12,             /* construct COPIED Maybe<Option> */
  STAR_OP_LOOKUP_PRESENT = 13,
  STAR_OP_IS_TYPE = 14,            /* a=0 lookup/1 current option; b=0 switch/1 parameter */
  STAR_OP_REQUIREMENT = 15,        /* a=0 lookup parameter/1 current parameter/2 current argument */
  STAR_OP_RESULT_HAS_PARAMETER = 17, /* a=0 flag/1 current option key */
  STAR_OP_COPY_NEXT_VALUE = 16,    /* construct String val=input.next() */
  STAR_OP_RESULT_ADD_SWITCH = 18,  /* exact switches.add(std::move(flag)) */
  STAR_OP_PARAMETER_SUBSCRIPT = 19,/* borrow native parameters[std::move(flag)] */
  STAR_OP_APPEND_VALUE = 20,      /* borrowed list.append(std::move(val)) */
  STAR_OP_APPEND_POSITIONAL = 21, /* arguments.append(borrowed token) */
  STAR_OP_TOKEN_SCOPE_END = 22,   /* reverse destruction: val, Maybe, flag; release token/list borrow */
  STAR_OP_ITER_BEGIN = 23,        /* a=0 options/1 arguments; FRESH native begin/end */
  STAR_OP_ITER_HAS_NEXT = 24,     /* a=iterator kind; actual current != end */
  STAR_OP_ITER_ADVANCE = 25,      /* a=iterator kind; native ++ */
  STAR_OP_ITER_END = 26,          /* a=iterator kind; destroy current/end scratch */
  STAR_OP_FIELD_EMPTY = 27,       /* a=0 name/1 summary/2 additional/3 switch desc/4 param desc/5 arg desc */
  STAR_OP_CMDLINE_INIT = 28,      /* construct native String AFTER header insertion */
  STAR_OP_CMDLINE_FORMAT = 29,    /* a=template 3..9, b=c=0 */
  STAR_OP_ERROR_FORMAT = 30,      /* a=template 16..21; b=expected/c=actual only for20/21 */
  STAR_OP_OSTREAM_FORMAT = 31,    /* a=0..2 or10..15; EXACT ONE original format(os,..) */
  STAR_OP_RESULT_ARGUMENT_COUNT = 32,
  STAR_OP_FINISH = 33             /* validate successful terminal phase; no early result publication */
};

enum StarOptionParserLabTemplate {
  STAR_OP_HEADER_BOTH = 0,        /* "{}: {}\n\n", name, summary */
  STAR_OP_HEADER_NAME = 1,        /* "{}:\n\n", name */
  STAR_OP_HEADER_SUMMARY = 2,     /* "{}\n\n", summary */
  STAR_OP_USAGE_SWITCH = 3,       /* " [-{}]", current option key */
  STAR_OP_USAGE_PARAMETER_OPTIONAL = 4, /* " [-{} <{}>]", parameter.flag/argument */
  STAR_OP_USAGE_PARAMETER_REQUIRED = 5, /* " -{} <{}>" */
  STAR_OP_USAGE_PARAMETER_MULTIPLE = 6, /* " [-{} <{}>]..." */
  STAR_OP_USAGE_ARGUMENT_OPTIONAL = 7, /* " [<{}>]", argumentName */
  STAR_OP_USAGE_ARGUMENT_REQUIRED = 8, /* " <{}>" */
  STAR_OP_USAGE_ARGUMENT_OTHER = 9,    /* " [<{}>...]", includes defined enum3 */
  STAR_OP_USAGE_WITHOUT_NAME = 10, /* "Command Line Usage:{}\n", cmdLineText */
  STAR_OP_USAGE_WITH_NAME = 11,    /* "Command Line Usage: {}{}\n", FRESH name, cmdLineText */
  STAR_OP_DESCRIPTION_SWITCH = 12, /* "  -{}\t- {}\n", flag, description */
  STAR_OP_DESCRIPTION_PARAMETER = 13, /* "  -{} <{}>\t- {}\n", flag, argument, description */
  STAR_OP_DESCRIPTION_ARGUMENT = 14, /* "  <{}>\t- {}\n", name, description */
  STAR_OP_ADDITIONAL_HELP = 15,    /* "\n{}\n", FRESH additionalHelp */
  STAR_OP_ERROR_UNKNOWN = 16,     /* "No such option '-{}'", flag */
  STAR_OP_ERROR_NO_VALUE = 17,    /* "Option '-{}' must be followed by an argument", flag */
  STAR_OP_ERROR_DUPLICATE = 18,   /* "Option with argument '-{}' specified multiple times", flag */
  STAR_OP_ERROR_REQUIRED = 19,    /* "Missing required flag with argument '-{}'", current option key */
  STAR_OP_ERROR_TOO_FEW = 20,     /* "Too few positional arguments given, expected at least {} got {}" */
  STAR_OP_ERROR_TOO_MANY = 21,    /* "Too many positional arguments given, expected at most {} got {}" */
  STAR_OP_ERROR_DUPLICATE_SWITCH = 22, /* "Duplicate switch '-{}' added", payload flag */
  STAR_OP_ERROR_DUPLICATE_FLAG = 23    /* "Duplicate flag '-{}' added", payload flag */
};

/* Blueprint executable only, not a production Rust entry or enabled selector.
 * RequirementMode is the native unfixed enum with enumerators0,1,2. Defined
 * non-enumerator3 is retained; arbitrary -1/UINT_MAX is NOT a justified domain.
 * Native size_t arithmetic is represented by uint64_t on the tested64-bit
 * target; wrapping and NPos remain controller decisions, not host validation.
 *
 * Ostream callbacks can change metadata and safely insert options into the
 * list-backed ordered map EVEN during its active description loop. Keep native
 * cached begin/end semantics, do not snapshot entries or counts. Vector-backed
 * positional List append during its active loop invalidates end (excluded).
 * Initialize each loop only when reached; first header sees old values, later
 * usage/description/additional fields are fresh. Same-context recursion invalid;
 * separate-context same-parser reentry is allowed where native-defined.
 *
 * On pending return, do not destroy live scratch outside native exception
 * unwinding merely to clear a phase. Rethrow captured exception while context is
 * alive; native RAII destroys val/Maybe/flag/iterators before enclosing errors
 * and result, in source-scope order. Normal iteration uses TOKEN_SCOPE_END.
 */
uint32_t star_option_parser_lab_controller(uint32_t, void*, StarOptionParserLabHost);

#ifdef __cplusplus
}
#endif
#endif
