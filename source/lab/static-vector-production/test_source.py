#!/usr/bin/env python3
"""byte-contract checks only; never preprocess, compile, configure, or link."""

import hashlib
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]
BEFORE = ROOT / "build/static-vector-production-source-r1/before"
SELECTOR = b"STAR_USE_RUST_STATIC_VECTOR"
ORIGINAL_SHA256 = "dafbafd5bc45329bab5da1fc02a360bc7c3e8e62323e77e61b496f4a2d0f5832"
CMAKE_SHA256 = "3874babf1a75277903f2f88cf29ef967e83558b9fc4fc7e6b898a1277455938e"
START = b"\ntemplate <typename Element, size_t MaxSize>\nStaticVector<Element, MaxSize>::StaticVector()"
INCLUDE = b'#ifdef STAR_USE_RUST_STATIC_VECTOR\n#include "StarStaticVectorHost.hpp"\n#endif\n'
BRANCH = b"\n#ifdef STAR_USE_RUST_STATIC_VECTOR\n"
ELSE = b"#else\n"
TAIL = b"#endif\n\n}\n"
OPTION = b'option(STAR_USE_RUST_STATIC_VECTOR "Use experimental Rust StaticVector controllers/policy" OFF)\n'
DEFINE = b"if(STAR_USE_RUST_STATIC_VECTOR)\n  add_compile_definitions(STAR_USE_RUST_STATIC_VECTOR)\nendif()\n\n"
ID_OPTION = b'option(STAR_USE_RUST_ID_MAP "Use experimental Rust IdMap controllers" OFF)\n'
ID_DEFINE = b"if(STAR_USE_RUST_ID_MAP)\n  add_compile_definitions(STAR_USE_RUST_ID_MAP)\nendif()\n\n"
BIMAP_OPTION = b'option(STAR_USE_RUST_BIMAP "Use experimental Rust BiMap controllers/policy" OFF)\n'
BIMAP_DEFINE = b"if(STAR_USE_RUST_BIMAP)\n  add_compile_definitions(STAR_USE_RUST_BIMAP)\nendif()\n\n"
BIMAP_MEMBER = b" OR STAR_USE_RUST_BIMAP)"
UUID_OPTION = b'option(STAR_USE_RUST_UUID "Use the Rust Uuid value operations" OFF)\n'
UUID_DEFINE = b"if(STAR_USE_RUST_UUID)\n  add_compile_definitions(STAR_USE_RUST_UUID)\nendif()\n\n"
UUID_MEMBER = b" OR STAR_USE_RUST_UUID)"
ORDERED_SET_OPTION = b'option(STAR_USE_RUST_ORDERED_SET "Use experimental Rust ordered-set controllers/policy" OFF)\n'
ORDERED_SET_DEFINE = b"if(STAR_USE_RUST_ORDERED_SET)\n  add_compile_definitions(STAR_USE_RUST_ORDERED_SET)\nendif()\n\n"
ORDERED_SET_MEMBER = b" OR STAR_USE_RUST_ORDERED_SET)"
SET_OPTION = b'option(STAR_USE_RUST_SET "Use experimental Rust set/hash-set controllers/policy" OFF)\n'
SET_DEFINE = b"if(STAR_USE_RUST_SET)\n  add_compile_definitions(STAR_USE_RUST_SET)\nendif()\n\n"
SET_MEMBER = b" OR STAR_USE_RUST_SET)"
FLAT_HASH_OPTION = b'option(STAR_USE_RUST_FLAT_HASH_TABLE "Use experimental Rust flat-hash controllers/policy" OFF)\n'
FLAT_HASH_DEFINE = b"if(STAR_USE_RUST_FLAT_HASH_TABLE)\n  add_compile_definitions(STAR_USE_RUST_FLAT_HASH_TABLE)\nendif()\n\n"
FLAT_HASH_MEMBER = b" OR STAR_USE_RUST_FLAT_HASH_TABLE)"
MAP_OPTION = b'option(STAR_USE_RUST_MAP "Use experimental Rust map controllers/policy" OFF)\n'
MAP_DEFINE = b"if(STAR_USE_RUST_MAP)\n  add_compile_definitions(STAR_USE_RUST_MAP)\nendif()\n\n"
MAP_MEMBER = b" OR STAR_USE_RUST_MAP)"
PERIODIC_OPTION = b'option(STAR_USE_RUST_PERIODIC "Use the Rust unsigned Periodic state machine" OFF)\n'
PERIODIC_DEFINE = b"if(STAR_USE_RUST_PERIODIC)\n  add_compile_definitions(STAR_USE_RUST_PERIODIC)\nendif()\n\n"
PERIODIC_MEMBER = b" OR STAR_USE_RUST_PERIODIC)"
WORKER_OPTION = b'option(STAR_USE_RUST_WORKER_POOL "Use experimental Rust worker-pool control policy" OFF)\n'
WORKER_DEFINE = b"if(STAR_USE_RUST_WORKER_POOL)\n  add_compile_definitions(STAR_USE_RUST_WORKER_POOL)\nendif()\n\n"
WORKER_MEMBER = b" OR STAR_USE_RUST_WORKER_POOL)"
TIME_OPTION = b'option(STAR_USE_RUST_TIME "Use Rust integer time conversions" OFF)\n'
TIME_DEFINE = b"if(STAR_USE_RUST_TIME)\n  add_compile_definitions(STAR_USE_RUST_TIME)\nendif()\n\n"
TIME_MEMBER = b" OR STAR_USE_RUST_TIME)"
NET_SIGNAL_OPTION = b'option(STAR_USE_RUST_NET_SIGNAL "Use Rust network signal queue policy" OFF)\n'
NET_SIGNAL_DEFINE = b"if(STAR_USE_RUST_NET_SIGNAL)\n  add_compile_definitions(STAR_USE_RUST_NET_SIGNAL)\nendif()\n\n"
NET_SIGNAL_MEMBER = b" OR STAR_USE_RUST_NET_SIGNAL)"
NET_FIELD_OPTION = b'option(STAR_USE_RUST_NET_FIELD "Use Rust basic network-field policy" OFF)\n'
NET_FIELD_DEFINE = b"if(STAR_USE_RUST_NET_FIELD)\n  add_compile_definitions(STAR_USE_RUST_NET_FIELD)\nendif()\n\n"
NET_FIELD_MEMBER = b" OR STAR_USE_RUST_NET_FIELD)"
NET_GROUP_OPTION = b'option(STAR_USE_RUST_NET_GROUP "Use Rust static network-group policy" OFF)\n'
NET_GROUP_DEFINE = b"if(STAR_USE_RUST_NET_GROUP)\n  add_compile_definitions(STAR_USE_RUST_NET_GROUP)\nendif()\n\n"
NET_GROUP_MEMBER = b" OR STAR_USE_RUST_NET_GROUP)"
NET_DYNAMIC_OPTION = b'option(STAR_USE_RUST_NET_DYNAMIC "Use Rust dynamic network-group policy" OFF)\n'
NET_DYNAMIC_DEFINE = b"if(STAR_USE_RUST_NET_DYNAMIC)\n  add_compile_definitions(STAR_USE_RUST_NET_DYNAMIC)\nendif()\n\n"
NET_DYNAMIC_MEMBER = b" OR STAR_USE_RUST_NET_DYNAMIC)"
JSON_RPC_OPTION = b'option(STAR_USE_RUST_JSON_RPC "Use Rust JSON-RPC dispatch and request sequencing" OFF)\n'
JSON_RPC_DEFINE = b"if(STAR_USE_RUST_JSON_RPC)\n  add_compile_definitions(STAR_USE_RUST_JSON_RPC)\nendif()\n\n"
JSON_RPC_MEMBER = b" OR STAR_USE_RUST_JSON_RPC)"


def require(condition, label):
    if not condition:
        raise ValueError(label)


def split_reference(data):
    # These are known artifact delimiters, not a general C++ parser. Preserving
    # whole definition regions also protects dependent expressions and spacing.
    require(data.count(START) == 1 and data.endswith(b"\n}\n"), "reference shape")
    index = data.index(START)
    return data[:index], data[index + 1:-3]


def split_header(data):
    # The include guard uses the same selector; anchor this split to the first
    # method template rather than confusing that guard with the body branch.
    require(data.count(BRANCH + START[1:]) == 1, "branch shape")
    common, branches = data.rsplit(BRANCH, 1)
    require(branches.count(ELSE) == 1 and branches.endswith(TAIL), "branch shape")
    on, off = branches[:-len(TAIL)].split(ELSE)
    return common, on, off


def check_common(data, original):
    common, _, _ = split_header(data)
    prefix, _ = split_reference(original)
    expected = prefix.replace(b'#include "StarFormat.hpp"\n', b'#include "StarFormat.hpp"\n' + INCLUDE)
    require(common == expected, "common declaration/includes")


def check_off(data, original):
    _, _, off = split_header(data)
    require(off == split_reference(original)[1], "off definitions")


def check_on(data, candidate):
    _, on, _ = split_header(data)
    require(on == split_reference(candidate)[1], "on definitions")


def check_helper(helper, frame):
    require(helper == frame, "helper bytes")


def check_no_lab(data, helper):
    includes = re.findall(rb'^\s*#\s*include\s*[<"]([^>"\n]+)', data + helper, re.M)
    require(all(b"lab" not in path.lower() and path != b"frame.hpp" for path in includes), "production lab include")


def check_option(cmake):
    options = re.findall(rb'^option\(STAR_USE_RUST_STATIC_VECTOR\b[^\n]*\)\n', cmake, re.M)
    require(options == [OPTION], "default-off option")


def aggregate_gate(cmake):
    # Match the specific existing root gate, rather than counting every if in
    # CMake (the option description itself contains a parenthesis elsewhere).
    gates = re.findall(rb'^if\(([^\n]+)\)\n  include\(Rust\)\nendif\(\)', cmake, re.M)
    require(len(gates) == 1, "aggregate gate shape")
    return gates[0].split(b" OR ")


def check_gate(cmake, before):
    old = aggregate_gate(before)
    require(aggregate_gate(cmake) == old + [SELECTOR], "aggregate root membership")


def check_define(cmake):
    require(cmake.count(DEFINE) == 1, "conditional define")
    require(cmake.count(b"add_compile_definitions(STAR_USE_RUST_STATIC_VECTOR)") == 1, "conditional define")


def normalize_current_cmake(cmake):
    require(cmake.count(JSON_RPC_OPTION) == 1 and cmake.count(JSON_RPC_DEFINE) == 1 and
            cmake.count(JSON_RPC_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_JSON_RPC") == 1,
            "JsonRpc integration shape")
    cmake = cmake.replace(JSON_RPC_OPTION, b"").replace(JSON_RPC_DEFINE, b"").replace(JSON_RPC_MEMBER, b")")
    require(b"STAR_USE_RUST_JSON_RPC" not in cmake, "JsonRpc integration shape")
    require(cmake.count(NET_DYNAMIC_OPTION) == 1 and cmake.count(NET_DYNAMIC_DEFINE) == 1 and
            cmake.count(NET_DYNAMIC_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_NET_DYNAMIC") == 1,
            "NetDynamic integration shape")
    cmake = cmake.replace(NET_DYNAMIC_OPTION, b"").replace(NET_DYNAMIC_DEFINE, b"").replace(NET_DYNAMIC_MEMBER, b")")
    require(b"STAR_USE_RUST_NET_DYNAMIC" not in cmake, "NetDynamic integration shape")
    require(cmake.count(NET_GROUP_OPTION) == 1 and cmake.count(NET_GROUP_DEFINE) == 1 and
            cmake.count(NET_GROUP_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_NET_GROUP") == 1,
            "NetGroup integration shape")
    cmake = cmake.replace(NET_GROUP_OPTION, b"").replace(NET_GROUP_DEFINE, b"").replace(NET_GROUP_MEMBER, b")")
    require(b"STAR_USE_RUST_NET_GROUP" not in cmake, "NetGroup integration shape")
    require(cmake.count(NET_FIELD_OPTION) == 1 and cmake.count(NET_FIELD_DEFINE) == 1 and
            cmake.count(NET_FIELD_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_NET_FIELD") == 1,
            "NetField integration shape")
    cmake = cmake.replace(NET_FIELD_OPTION, b"").replace(NET_FIELD_DEFINE, b"").replace(NET_FIELD_MEMBER, b")")
    require(b"STAR_USE_RUST_NET_FIELD" not in cmake, "NetField integration shape")
    require(cmake.count(NET_SIGNAL_OPTION) == 1 and cmake.count(NET_SIGNAL_DEFINE) == 1 and
            cmake.count(NET_SIGNAL_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_NET_SIGNAL") == 1,
            "NetSignal integration shape")
    cmake = cmake.replace(NET_SIGNAL_OPTION, b"").replace(NET_SIGNAL_DEFINE, b"").replace(NET_SIGNAL_MEMBER, b")")
    require(b"STAR_USE_RUST_NET_SIGNAL" not in cmake, "NetSignal integration shape")
    require(cmake.count(TIME_OPTION) == 1 and cmake.count(TIME_DEFINE) == 1 and
            cmake.count(TIME_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_TIME") == 1,
            "Time integration shape")
    cmake = cmake.replace(TIME_OPTION, b"").replace(TIME_DEFINE, b"").replace(TIME_MEMBER, b")")
    require(b"STAR_USE_RUST_TIME" not in cmake, "Time integration shape")
    require(cmake.count(WORKER_OPTION) == 1 and cmake.count(WORKER_DEFINE) == 1 and
            cmake.count(WORKER_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_WORKER_POOL") == 1,
            "WorkerPool integration shape")
    cmake = cmake.replace(WORKER_OPTION, b"").replace(WORKER_DEFINE, b"").replace(WORKER_MEMBER, b")")
    require(b"STAR_USE_RUST_WORKER_POOL" not in cmake, "WorkerPool integration shape")
    require(cmake.count(PERIODIC_OPTION) == 1 and cmake.count(PERIODIC_DEFINE) == 1 and
            cmake.count(PERIODIC_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_PERIODIC") == 1,
            "Periodic integration shape")
    cmake = cmake.replace(PERIODIC_OPTION, b"").replace(PERIODIC_DEFINE, b"").replace(PERIODIC_MEMBER, b")")
    require(b"STAR_USE_RUST_PERIODIC" not in cmake, "Periodic integration shape")
    require(cmake.count(MAP_OPTION) == 1 and cmake.count(MAP_DEFINE) == 1 and
            cmake.count(MAP_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_MAP") == 1,
            "Map integration shape")
    cmake = cmake.replace(MAP_OPTION, b"").replace(MAP_DEFINE, b"").replace(MAP_MEMBER, b")")
    require(b"STAR_USE_RUST_MAP" not in cmake, "Map integration shape")
    require(cmake.count(FLAT_HASH_OPTION) == 1 and cmake.count(FLAT_HASH_DEFINE) == 1 and
            cmake.count(FLAT_HASH_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_FLAT_HASH_TABLE") == 1,
            "FlatHashTable integration shape")
    cmake = cmake.replace(FLAT_HASH_OPTION, b"").replace(FLAT_HASH_DEFINE, b"").replace(FLAT_HASH_MEMBER, b")")
    require(b"STAR_USE_RUST_FLAT_HASH_TABLE" not in cmake, "FlatHashTable integration shape")
    require(cmake.count(SET_OPTION) == 1 and cmake.count(SET_DEFINE) == 1 and
            cmake.count(SET_MEMBER) == 1 and aggregate_gate(cmake).count(b"STAR_USE_RUST_SET") == 1,
            "Set integration shape")
    cmake = cmake.replace(SET_OPTION, b"").replace(SET_DEFINE, b"").replace(SET_MEMBER, b")")
    require(b"STAR_USE_RUST_SET" not in cmake, "Set integration shape")
    require(cmake.count(ORDERED_SET_OPTION) == 1 and cmake.count(ORDERED_SET_DEFINE) == 1 and
            cmake.count(ORDERED_SET_MEMBER) == 1 and
            aggregate_gate(cmake).count(b"STAR_USE_RUST_ORDERED_SET") == 1,
            "OrderedSet integration shape")
    cmake = cmake.replace(ORDERED_SET_OPTION, b"").replace(ORDERED_SET_DEFINE, b"").replace(ORDERED_SET_MEMBER, b")")
    require(b"STAR_USE_RUST_ORDERED_SET" not in cmake, "OrderedSet integration shape")
    # Reverse only UUID's exact three integration edits before the existing
    # BiMap projection; neither historical snapshot nor pinned hash changes.
    require(cmake.count(UUID_OPTION) == 1 and cmake.count(UUID_DEFINE) == 1 and
            cmake.count(UUID_MEMBER) == 1 and
            aggregate_gate(cmake).count(b"STAR_USE_RUST_UUID") == 1,
            "UUID integration shape")
    cmake = cmake.replace(UUID_OPTION, b"", 1).replace(UUID_DEFINE, b"", 1)
    cmake = cmake.replace(UUID_MEMBER, b")", 1)
    require(b"STAR_USE_RUST_UUID" not in cmake, "UUID integration shape")
    require(cmake.count(BIMAP_OPTION) == 1 and cmake.count(BIMAP_DEFINE) == 1 and
            cmake.count(BIMAP_MEMBER) == 1 and
            aggregate_gate(cmake).count(b"STAR_USE_RUST_BIMAP") == 1,
            "BiMap integration shape")
    restored = cmake.replace(BIMAP_OPTION, b"", 1).replace(BIMAP_DEFINE, b"", 1)
    restored = restored.replace(BIMAP_MEMBER, b")", 1)
    require(b"STAR_USE_RUST_BIMAP" not in restored, "BiMap integration shape")
    return restored


def check_cmake_scope(cmake, before):
    # Reverse ONLY the three authorized edits. Exact equality then excludes new
    # crates, runtime/linker/provider settings and changes to existing defaults.
    restored = cmake.replace(OPTION, b"", 1).replace(DEFINE, b"", 1)
    restored = restored.replace(b" OR STAR_USE_RUST_STATIC_VECTOR)", b")", 1)
    require(restored == before, "cmake scope")


class SourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (BEFORE / "StarStaticVector.hpp.data").read_bytes()
        cls.before = (BEFORE / "CMakeLists.txt.data").read_bytes()
        require(hashlib.sha256(cls.original).hexdigest() == ORIGINAL_SHA256, "raw original pin")
        require(hashlib.sha256(cls.before).hexdigest() == CMAKE_SHA256, "raw cmake pin")
        cls.header = (ROOT / "source/core/StarStaticVector.hpp").read_bytes()
        cls.helper = (ROOT / "source/core/StarStaticVectorHost.hpp").read_bytes()
        cls.candidate = (ROOT / "source/lab/static-vector-frames/StaticVector.hpp").read_bytes()
        cls.frame = (ROOT / "source/lab/static-vector-frames/frame.hpp").read_bytes()
        cls.current_cmake = (ROOT / "source/CMakeLists.txt").read_bytes()
        cls.cmake = normalize_current_cmake(cls.current_cmake)

    def test_common_declaration_fields_exception_and_guarded_include(self):
        check_common(self.header, self.original)

    def test_off_definitions_verbatim(self):
        check_off(self.header, self.original)

    def test_on_definitions_verbatim(self):
        check_on(self.header, self.candidate)

    def test_helper_verbatim(self):
        check_helper(self.helper, self.frame)

    def test_no_production_lab_includes(self):
        check_no_lab(self.header, self.helper)

    def test_default_off_option(self):
        check_option(self.cmake)

    def test_existing_aggregate_root_membership(self):
        check_gate(self.cmake, self.before)
        self.assertEqual(len(aggregate_gate(self.before)), 29)
        self.assertEqual(len(aggregate_gate(self.cmake)), 30)

    def test_conditional_define(self):
        check_define(self.cmake)

    def test_only_three_cmake_edits(self):
        check_cmake_scope(self.cmake, self.before)
        self.assertIn(ID_OPTION + OPTION, self.cmake)
        self.assertIn(ID_DEFINE + DEFINE, self.cmake)

    def test_41_definition_regions_and_ten_unchanged_views(self):
        _, on, off = split_header(self.header)
        delimiter = b"template <typename Element, size_t MaxSize>\n"
        original_regions = split_reference(self.original)[1].split(delimiter)[1:]
        on_regions = on.split(delimiter)[1:]
        off_regions = off.split(delimiter)[1:]
        self.assertEqual(len(original_regions), 41)
        self.assertEqual(len(on_regions), 41)
        self.assertEqual(len(off_regions), 41)
        views = [i for i, region in enumerate(original_regions)
                 if re.search(rb'::(?:begin|end|rbegin|rend|ptr)\(', region)]
        self.assertEqual(len(views), 10)
        for i in views:
            self.assertEqual(on_regions[i], original_regions[i])
            self.assertEqual(off_regions[i], original_regions[i])

    def reject(self, label, checker, *args):
        with self.assertRaisesRegex(ValueError, "^" + re.escape(label) + "$"):
            checker(*args)

    def test_bad_field(self):
        mutant = self.header.replace(b"  size_t m_size;", b"  unsigned m_size;", 1)
        self.reject("common declaration/includes", check_common, mutant, self.original)

    def test_bad_off_body(self):
        common, on, off = split_header(self.header)
        mutant = common + BRANCH + on + ELSE + off.replace(b": m_size(0)", b": m_size(1)", 1) + TAIL
        self.reject("off definitions", check_off, mutant, self.original)

    def test_bad_on_body(self):
        common, on, off = split_header(self.header)
        mutant = common + BRANCH + on.replace(b"SB_STATIC_VECTOR_DEFAULT_CTOR", b"SB_STATIC_VECTOR_CLEAR", 1) + ELSE + off + TAIL
        self.reject("on definitions", check_on, mutant, self.candidate)

    def test_bad_helper(self):
        mutant = self.helper.replace(b"std::rethrow_exception(exception);", b"return reply;", 1)
        self.reject("helper bytes", check_helper, mutant, self.frame)

    def test_bad_default_on(self):
        mutant = self.cmake.replace(OPTION, OPTION.replace(b" OFF)", b" ON)"), 1)
        self.reject("default-off option", check_option, mutant)

    def test_bad_missing_root_enable(self):
        mutant = self.cmake.replace(b" OR STAR_USE_RUST_STATIC_VECTOR)", b")", 1)
        self.reject("aggregate root membership", check_gate, mutant, self.before)

    def test_bad_unguarded_define(self):
        mutant = self.cmake.replace(DEFINE, b"add_compile_definitions(STAR_USE_RUST_STATIC_VECTOR)\n\n", 1)
        self.reject("conditional define", check_define, mutant)

    def test_bad_unguarded_host_include(self):
        mutant = self.header.replace(INCLUDE, b'#include "StarStaticVectorHost.hpp"\n', 1)
        self.reject("common declaration/includes", check_common, mutant, self.original)

    def test_bad_production_lab_include(self):
        mutant = self.helper + b'\n#include "../lab/static-vector-frames/frame.hpp"\n'
        self.reject("production lab include", check_no_lab, self.header, mutant)

    def test_bad_bimap_integration(self):
        bad = [self.current_cmake.replace(BIMAP_OPTION, BIMAP_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(BIMAP_OPTION, b"", 1),
               self.current_cmake + BIMAP_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_BIMAP", b"", 1),
               self.current_cmake.replace(BIMAP_DEFINE, b"add_compile_definitions(STAR_USE_RUST_BIMAP)\n\n", 1)]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("BiMap integration shape", normalize_current_cmake, mutant)

    def test_bad_uuid_integration(self):
        bad = [self.current_cmake.replace(UUID_OPTION, UUID_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(UUID_OPTION, b"", 1),
               self.current_cmake + UUID_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_UUID", b"", 1),
               self.current_cmake.replace(UUID_DEFINE, b"add_compile_definitions(STAR_USE_RUST_UUID)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_UUID ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("UUID integration shape", normalize_current_cmake, mutant)

    def test_bad_ordered_set_integration(self):
        bad = [self.current_cmake.replace(ORDERED_SET_OPTION, ORDERED_SET_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(ORDERED_SET_OPTION, b"", 1),
               self.current_cmake + ORDERED_SET_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_ORDERED_SET", b"", 1),
               self.current_cmake.replace(ORDERED_SET_DEFINE, b"add_compile_definitions(STAR_USE_RUST_ORDERED_SET)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_ORDERED_SET ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("OrderedSet integration shape", normalize_current_cmake, mutant)

    def test_bad_set_integration(self):
        bad = [self.current_cmake.replace(SET_OPTION, SET_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(SET_OPTION, b"", 1), self.current_cmake + SET_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_SET", b"", 1),
               self.current_cmake.replace(SET_DEFINE, b"add_compile_definitions(STAR_USE_RUST_SET)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_SET ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("Set integration shape", normalize_current_cmake, mutant)

    def test_bad_flat_hash_integration(self):
        bad = [self.current_cmake.replace(FLAT_HASH_OPTION, FLAT_HASH_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(FLAT_HASH_OPTION, b"", 1), self.current_cmake + FLAT_HASH_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_FLAT_HASH_TABLE", b"", 1),
               self.current_cmake.replace(FLAT_HASH_DEFINE, b"add_compile_definitions(STAR_USE_RUST_FLAT_HASH_TABLE)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_FLAT_HASH_TABLE ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("FlatHashTable integration shape", normalize_current_cmake, mutant)

    def test_bad_map_integration(self):
        bad = [self.current_cmake.replace(MAP_OPTION, MAP_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(MAP_OPTION, b"", 1), self.current_cmake + MAP_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_MAP", b"", 1),
               self.current_cmake.replace(MAP_DEFINE, b"add_compile_definitions(STAR_USE_RUST_MAP)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_MAP ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("Map integration shape", normalize_current_cmake, mutant)

    def test_bad_periodic_integration(self):
        bad = [self.current_cmake.replace(PERIODIC_OPTION, PERIODIC_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(PERIODIC_OPTION, b"", 1), self.current_cmake + PERIODIC_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_PERIODIC", b"", 1),
               self.current_cmake.replace(PERIODIC_DEFINE, b"add_compile_definitions(STAR_USE_RUST_PERIODIC)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_PERIODIC ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("Periodic integration shape", normalize_current_cmake, mutant)

    def test_bad_worker_pool_integration(self):
        bad = [self.current_cmake.replace(WORKER_OPTION, WORKER_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(WORKER_OPTION, b"", 1), self.current_cmake + WORKER_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_WORKER_POOL", b"", 1),
               self.current_cmake.replace(WORKER_DEFINE, b"add_compile_definitions(STAR_USE_RUST_WORKER_POOL)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_WORKER_POOL ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("WorkerPool integration shape", normalize_current_cmake, mutant)

    def test_bad_time_integration(self):
        bad = [self.current_cmake.replace(TIME_OPTION, TIME_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(TIME_OPTION, b"", 1), self.current_cmake + TIME_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_TIME", b"", 1),
               self.current_cmake.replace(TIME_DEFINE, b"add_compile_definitions(STAR_USE_RUST_TIME)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_TIME ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("Time integration shape", normalize_current_cmake, mutant)

    def test_bad_net_signal_integration(self):
        bad = [self.current_cmake.replace(NET_SIGNAL_OPTION, NET_SIGNAL_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(NET_SIGNAL_OPTION, b"", 1), self.current_cmake + NET_SIGNAL_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_NET_SIGNAL", b"", 1),
               self.current_cmake.replace(NET_SIGNAL_DEFINE, b"add_compile_definitions(STAR_USE_RUST_NET_SIGNAL)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_NET_SIGNAL ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("NetSignal integration shape", normalize_current_cmake, mutant)

    def test_bad_net_field_integration(self):
        bad = [self.current_cmake.replace(NET_FIELD_OPTION, NET_FIELD_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(NET_FIELD_OPTION, b"", 1), self.current_cmake + NET_FIELD_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_NET_FIELD", b"", 1),
               self.current_cmake.replace(NET_FIELD_DEFINE, b"add_compile_definitions(STAR_USE_RUST_NET_FIELD)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_NET_FIELD ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("NetField integration shape", normalize_current_cmake, mutant)

    def test_bad_net_group_integration(self):
        bad = [self.current_cmake.replace(NET_GROUP_OPTION, NET_GROUP_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(NET_GROUP_OPTION, b"", 1), self.current_cmake + NET_GROUP_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_NET_GROUP", b"", 1),
               self.current_cmake.replace(NET_GROUP_DEFINE, b"add_compile_definitions(STAR_USE_RUST_NET_GROUP)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_NET_GROUP ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("NetGroup integration shape", normalize_current_cmake, mutant)

    def test_bad_net_dynamic_integration(self):
        bad = [self.current_cmake.replace(NET_DYNAMIC_OPTION, NET_DYNAMIC_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(NET_DYNAMIC_OPTION, b"", 1), self.current_cmake + NET_DYNAMIC_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_NET_DYNAMIC", b"", 1),
               self.current_cmake.replace(NET_DYNAMIC_DEFINE, b"add_compile_definitions(STAR_USE_RUST_NET_DYNAMIC)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_NET_DYNAMIC ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("NetDynamic integration shape", normalize_current_cmake, mutant)

    def test_bad_json_rpc_integration(self):
        bad = [self.current_cmake.replace(JSON_RPC_OPTION, JSON_RPC_OPTION.replace(b" OFF)", b" ON)"), 1),
               self.current_cmake.replace(JSON_RPC_OPTION, b"", 1), self.current_cmake + JSON_RPC_OPTION,
               self.current_cmake.replace(b" OR STAR_USE_RUST_JSON_RPC", b"", 1),
               self.current_cmake.replace(JSON_RPC_DEFINE, b"add_compile_definitions(STAR_USE_RUST_JSON_RPC)\n\n", 1),
               self.current_cmake + b"\nset(STAR_USE_RUST_JSON_RPC ON)\n"]
        for mutant in bad:
            with self.subTest(size=len(mutant)):
                self.reject("JsonRpc integration shape", normalize_current_cmake, mutant)

    def test_bad_extra_runtime_configuration(self):
        mutant = self.cmake + b"\nset(STAR_RUST_TARGET_DIR unexpected)\n"
        self.reject("cmake scope", check_cmake_scope, mutant, self.before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
