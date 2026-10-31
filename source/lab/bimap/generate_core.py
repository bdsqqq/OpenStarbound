#!/usr/bin/env python3
"""Generate a LAB ONLY partial BiMap core adapter; never compile or run it.

The frozen class, fields and signatures remain native. Forwarding, views, get,
default wrappers and iterator operations remain original partial-port work.
Only the listed bodies and include plumbing change. This is not production
selection, nontrivial-value qualification, or native differential evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN_SHA = "7c24d65672b14d03234cdc09f67e3c6f5c1786c71c610ac1c017cca71e37c011"
NATIVE_SHA = "e194e36911bdce30ad9585f9cc57ca7ba42c70ff2e5d22c68e6613c313edf065"
SHIM_SHA = "ff32626a52918f028329ddc3fba25ad35cd1be0ae4709d3df7d011e49ec58c22"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique_replace(text, old, new):
    if not old or text.count(old) != 1:
        raise ValueError("oldText must match exactly once: " + old[:160])
    return text.replace(old, new, 1)


def pinned(path, expected):
    data = path.read_bytes()
    if sha(data) != expected:
        raise ValueError("byte pin mismatch: " + str(path))
    return data


def bodies():
    # Explicit oldText, not brace scanning, broad regex, or fixture-output fitting.
    result = []

    def add(signature, old, new):
        prefix = signature + " {\n"
        result.append((signature, prefix + old + "\n}", prefix + new + "\n}"))

    base = "BiMap<LeftT, RightT, LeftMapT, RightMapT>::"
    add(base + "BiMap(InputIterator beg, InputIterator end)", '''  while (beg != end) {
    insert(*beg);
    ++beg;
  }''', '''  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_ITERATOR_PRESENT: return BiMapFrames::boolReply(static_cast<bool>(beg != end));
      case SB_BIMAP_INSERT_CURRENT_IGNORED: { insert(*beg); return BiMapFrames::voidReply(); }
      case SB_BIMAP_ADVANCE_ITERATOR: ++beg; return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_RANGE_INSERT);''')
    add(base + "BiMap(std::initializer_list<value_type> list)", '''  for (value_type const& v : list) {
    if (!insert(v.first, v.second))
      throw MapException::format("Repeat pair in BiMap initializer_list construction: ({}, {})", outputAny(v.first), outputAny(v.second));
  }''', '''  auto cursor = list.begin();
  auto last = list.end();
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_ITERATOR_PRESENT: return BiMapFrames::boolReply(cursor != last);
      case SB_BIMAP_INSERT_CURRENT_CHECKED: {
        value_type const& v = *cursor;
        return BiMapFrames::boolReply(insert(v.first, v.second));
      }
      case SB_BIMAP_THROW_CURRENT_DUPLICATE: {
        value_type const& v = *cursor;
        throw MapException::format("Repeat pair in BiMap initializer_list construction: ({}, {})", outputAny(v.first), outputAny(v.second));
      }
      case SB_BIMAP_ADVANCE_ITERATOR: ++cursor; return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_LIST_INSERT);''')
    for signature, old, mode, op, expr, kind in [
        ("bool " + base + "hasLeftValue(Left const& left) const", "  return m_leftMap.contains(left);", "HAS_LEFT", "HAS_LEFT", "m_leftMap.contains(left)", "bool"),
        ("bool " + base + "hasRightValue(Right const& right) const", "  return m_rightMap.contains(right);", "HAS_RIGHT", "HAS_RIGHT", "m_rightMap.contains(right)", "bool"),
        ("size_t " + base + "size() const", "  return m_leftMap.size();", "SIZE", "SIZE", "m_leftMap.size()", "size"),
        ("bool " + base + "empty() const", "  return m_leftMap.empty();", "EMPTY", "EMPTY", "m_leftMap.empty()", "bool"),
    ]:
        add(signature, old, f'''  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {{
    if (req.op == SB_BIMAP_{op}) return BiMapFrames::{kind}Reply({expr});
    return BiMapFrames::invalidReply();
  }});
  return frame.run(SB_BIMAP_MODE_{mode}).value;''')
    add("void " + base + "clear()", '''  m_leftMap.clear();
  m_rightMap.clear();''', '''  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_CLEAR_LEFT: m_leftMap.clear(); return BiMapFrames::voidReply();
      case SB_BIMAP_CLEAR_RIGHT: m_rightMap.clear(); return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_CLEAR);''')
    add("BiMap<LeftT, RightT, LeftMapT, RightMapT>& " + base + "operator=(BiMap const& map)", '''  if (this != &map) {
    clear();
    for (auto const& p : map)
      insert(p);
  }
  return *this;''', '''  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_ASSIGN_DISTINCT: return BiMapFrames::boolReply(static_cast<bool>(this != &map));
      case SB_BIMAP_CLEAR_LEFT: m_leftMap.clear(); return BiMapFrames::voidReply();
      case SB_BIMAP_CLEAR_RIGHT: m_rightMap.clear(); return BiMapFrames::voidReply();
      case SB_BIMAP_COPY_ENTRIES: {
        auto cursor = map.begin();
        auto last = map.end();
        auto loop = BiMapFrames::makeFrame([&](SbBiMapRequest const& step) -> SbBiMapReply {
          switch (step.op) {
            case SB_BIMAP_ITERATOR_PRESENT: return BiMapFrames::boolReply(cursor != last);
            case SB_BIMAP_INSERT_CURRENT_IGNORED: {
              auto const& p = *cursor; insert(p);
              return BiMapFrames::voidReply();
            }
            case SB_BIMAP_ADVANCE_ITERATOR: ++cursor; return BiMapFrames::voidReply();
            default: return BiMapFrames::invalidReply();
          }
        });
        loop.run(SB_BIMAP_MODE_COPY_ENTRIES);
        return BiMapFrames::voidReply();
      }
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_COPY_ASSIGN);
  return *this;''')
    add("auto " + base + "insert(value_type const& val) -> pair<iterator, bool>", '''  auto leftRes = m_leftMap.insert(make_pair(val.first, nullptr));
  if (!leftRes.second)
    return {BiMapIterator{leftRes.first}, false};

  auto rightRes = m_rightMap.insert(make_pair(val.second, nullptr));
  starAssert(rightRes.second == true);
  leftRes.first->second = &rightRes.first->first;
  rightRes.first->second = &leftRes.first->first;
  return {BiMapIterator{leftRes.first}, true};''', '''  auto leftRes = m_leftMap.insert(make_pair(val.first, nullptr));
  auto route = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    if (req.op == SB_BIMAP_LEFT_INSERTED) return BiMapFrames::boolReply(!static_cast<bool>(!leftRes.second));
    return BiMapFrames::invalidReply();
  });
  if (!route.run(SB_BIMAP_MODE_INSERT_ROUTE).value)
    return {BiMapIterator{leftRes.first}, false};

  auto rightRes = m_rightMap.insert(make_pair(val.second, nullptr));
  auto link = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_ASSERT_RIGHT_INSERTED: starAssert(rightRes.second == true); return BiMapFrames::voidReply();
      case SB_BIMAP_LINK_LEFT: leftRes.first->second = &rightRes.first->first; return BiMapFrames::voidReply();
      case SB_BIMAP_LINK_RIGHT: rightRes.first->second = &leftRes.first->first; return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  link.run(SB_BIMAP_MODE_INSERT_LINK);
  return {BiMapIterator{leftRes.first}, true};''')
    add("void " + base + "add(Left const& left, Right const& right)", '''  if (m_leftMap.contains(left))
    throw MapException(strf("BiMap already contains left side value '{}'", outputAny(left)));

  if (m_rightMap.contains(right))
    throw MapException(strf("BiMap already contains right side value '{}'", outputAny(right)));

  insert(left, right);''', '''  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_HAS_LEFT: return BiMapFrames::boolReply(m_leftMap.contains(left));
      case SB_BIMAP_HAS_RIGHT: return BiMapFrames::boolReply(m_rightMap.contains(right));
      case SB_BIMAP_THROW_LEFT: throw MapException(strf("BiMap already contains left side value '{}'", outputAny(left)));
      case SB_BIMAP_THROW_RIGHT: throw MapException(strf("BiMap already contains right side value '{}'", outputAny(right)));
      case SB_BIMAP_INSERT_IGNORED: insert(left, right); return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_ADD);''')
    add("void " + base + "overwrite(Left const& left, Right const& right)", '''  removeLeft(left);
  removeRight(right);
  insert(left, right);''', '''  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_REMOVE_LEFT_IGNORED: removeLeft(left); return BiMapFrames::voidReply();
      case SB_BIMAP_REMOVE_RIGHT_IGNORED: removeRight(right); return BiMapFrames::voidReply();
      case SB_BIMAP_INSERT_IGNORED: insert(left, right); return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  frame.run(SB_BIMAP_MODE_OVERWRITE);''')
    add("bool " + base + "removeLeft(Left const& left)", '''  if (auto right = m_leftMap.value(left)) {
    m_rightMap.remove(*right);
    m_leftMap.remove(left);
    return true;
  }

  return false;''', '''  Right const* right = nullptr;
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_RIGHT_FOR_LEFT_PRESENT: right = m_leftMap.value(left); return BiMapFrames::boolReply(right);
      case SB_BIMAP_REMOVE_RIGHT_USING_FOUND: m_rightMap.remove(*right); return BiMapFrames::voidReply();
      case SB_BIMAP_REMOVE_LEFT_IGNORED: m_leftMap.remove(left); return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  return frame.run(SB_BIMAP_MODE_REMOVE_LEFT).value;''')
    add("bool " + base + "removeRight(Right const& right)", '''  if (auto left = m_rightMap.value(right)) {
    m_leftMap.remove(*left);
    m_rightMap.remove(right);
    return true;
  }

  return false;''', '''  Left const* left = nullptr;
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_LEFT_FOR_RIGHT_PRESENT: left = m_rightMap.value(right); return BiMapFrames::boolReply(left);
      case SB_BIMAP_REMOVE_LEFT_USING_FOUND: m_leftMap.remove(*left); return BiMapFrames::voidReply();
      case SB_BIMAP_REMOVE_RIGHT_IGNORED: m_rightMap.remove(right); return BiMapFrames::voidReply();
      default: return BiMapFrames::invalidReply();
    }
  });
  return frame.run(SB_BIMAP_MODE_REMOVE_RIGHT).value;''')
    add("bool " + base + "operator==(BiMap const& m) const", '''  if (&m == this)
    return true;

  if (size() != m.size())
    return false;

  for (auto const& pair : *this) {
    if (auto p = m.rightPtr(pair.first))
      if (!p || *p != pair.second)
        return false;
  }

  return true;''', '''  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
    switch (req.op) {
      case SB_BIMAP_SELF_EQUAL: return BiMapFrames::boolReply(static_cast<bool>(&m == this));
      case SB_BIMAP_SIZE: return BiMapFrames::sizeReply(size());
      case SB_BIMAP_OTHER_SIZE: return BiMapFrames::sizeReply(m.size());
      case SB_BIMAP_EQUAL_ENTRIES: {
        auto cursor = begin();
        auto last = end();
        auto loop = BiMapFrames::makeFrame([&](SbBiMapRequest const& step) -> SbBiMapReply {
          switch (step.op) {
            case SB_BIMAP_ITERATOR_PRESENT: return BiMapFrames::boolReply(cursor != last);
            case SB_BIMAP_ADVANCE_ITERATOR: ++cursor; return BiMapFrames::voidReply();
            case SB_BIMAP_COMPARE_CURRENT_SCOPED: {
              auto const& pair = *cursor;
              Right const* p = nullptr;
              auto current = BiMapFrames::makeFrame([&](SbBiMapRequest const& leaf) -> SbBiMapReply {
                switch (leaf.op) {
                  case SB_BIMAP_FIND_CURRENT_RIGHT: p = m.rightPtr(pair.first); return BiMapFrames::boolReply(p);
                  case SB_BIMAP_CURRENT_RIGHT_NOT_EQUAL: return BiMapFrames::boolReply(static_cast<bool>(!p || *p != pair.second));
                  default: return BiMapFrames::invalidReply();
                }
              });
              return BiMapFrames::boolReply(current.run(SB_BIMAP_MODE_EQUAL_PAIR).value);
            }
            default: return BiMapFrames::invalidReply();
          }
        });
        return BiMapFrames::boolReply(loop.run(SB_BIMAP_MODE_EQUAL_SCOPED_ENTRIES).value);
      }
      default: return BiMapFrames::invalidReply();
    }
  });
  return frame.run(SB_BIMAP_MODE_EQUAL).value;''')
    # Keep value construction and return initialization native; Rust decides
    # presence/removal only, never storing a Maybe or an element across the ABI.
    for side, key_type, key, native_map in [
        ("Right", "Left", "left", "m_leftMap"),
        ("Left", "Right", "right", "m_rightMap"),
    ]:
        add(f"Maybe<{side}T> " + base + f"maybe{side}({key_type} const& {key}) const", f'''  auto i = {native_map}.find({key});
  if (i != {native_map}.end())
    return *i->second;
  return {{}};''', f'''  auto i = {native_map}.find({key});
  auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {{
    if (req.op == SB_BIMAP_PRESENT) return BiMapFrames::boolReply((bool)(i != {native_map}.end()));
    return BiMapFrames::invalidReply();
  }});
  if (frame.run(SB_BIMAP_MODE_PRESENT).value)
    return *i->second;
  return {{}};''')
        value = side.lower()
        pointer = value + "Ptr"
        opposite_map = "m_" + value + "Map"
        add(f"Maybe<{side}T> " + base + f"maybeTake{side}({key_type} const& {key})", f'''  if (auto {pointer} = {native_map}.maybeTake({key}).value()) {{
    {side} {value} = *{pointer};
    {opposite_map}.remove(*{pointer});
    return {value};
  }} else {{
    return {{}};
  }}''', f'''  auto {pointer} = {native_map}.maybeTake({key}).value();
  auto present = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {{
    if (req.op == SB_BIMAP_PRESENT) return BiMapFrames::boolReply((bool){pointer});
    return BiMapFrames::invalidReply();
  }});
  if (present.run(SB_BIMAP_MODE_PRESENT).value) {{
    {side} {value} = *{pointer};
    auto remove = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {{
      if (req.op == SB_BIMAP_REMOVE_TAKEN) {{ {opposite_map}.remove(*{pointer}); return BiMapFrames::voidReply(); }}
      return BiMapFrames::invalidReply();
    }});
    remove.run(SB_BIMAP_MODE_REMOVE_TAKEN);
    return {value};
  }} else {{
    return {{}};
  }}''')
        # The empty Maybe must die before formatting/throwing the missing key.
        add(f"{side}T " + base + f"take{side}({key_type} const& {key})", f'''  if (auto {value} = maybeTake{side}({key}))
    return {value}.take();
  throw MapException::format("No such key in BiMap::take{side}", outputAny({key}));''', f'''  {{
    auto {value} = maybeTake{side}({key});
    auto present = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {{
      if (req.op == SB_BIMAP_PRESENT) return BiMapFrames::boolReply((bool){value});
      return BiMapFrames::invalidReply();
    }});
    if (present.run(SB_BIMAP_MODE_PRESENT).value)
      return {value}.take();
  }}
  auto missing = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {{
    if (req.op == SB_BIMAP_THROW_TAKE)
      throw MapException::format("No such key in BiMap::take{side}", outputAny({key}));
    return BiMapFrames::invalidReply();
  }});
  missing.run(SB_BIMAP_MODE_THROW_TAKE);
  throw std::logic_error("Invalid BiMap boundary protocol");''')
    # Range-for iterators die before the original NRVO-eligible return.
    add("auto " + base + "pairs() const -> List<value_type>", '''  List<value_type> values;
  for (auto const& p : *this)
    values.append(p);
  return values;''', '''  List<value_type> values;
  {
    auto cursor = begin();
    auto last = end();
    auto frame = BiMapFrames::makeFrame([&](SbBiMapRequest const& req) -> SbBiMapReply {
      switch (req.op) {
        case SB_BIMAP_ITERATOR_PRESENT: return BiMapFrames::boolReply((bool)(cursor != last));
        case SB_BIMAP_APPEND_CURRENT: {
          auto const& p = *cursor;
          values.append(p);
          return BiMapFrames::voidReply();
        }
        case SB_BIMAP_ADVANCE_ITERATOR: ++cursor; return BiMapFrames::voidReply();
        default: return BiMapFrames::invalidReply();
      }
    });
    frame.run(SB_BIMAP_MODE_PAIRS);
  }
  return values;''')
    return result


def generate(output, real_support=False):
    # Caller owns admission, artifact conservation, compilation and execution.
    # Refuse overwrite, aliases and implicit parent creation.
    if not output.is_absolute() or output != output.resolve():
        raise ValueError("--output-dir must be an absolute canonical new directory")
    if not output.parent.is_dir() or output.exists() or output.is_symlink():
        raise ValueError("output parent must exist and output must be new")
    frozen = pinned(HERE / "StarBiMap.original.hpp", FROZEN_SHA)
    native = pinned(HERE / "native.cpp", NATIVE_SHA)
    pinned(HERE / "StarString.hpp", SHIM_SHA)
    original = frozen.decode("utf-8")
    generated = original
    source_projection = original
    body_projection = original
    records = []
    replacements = bodies()
    for index, (signature, old, new) in enumerate(replacements):
        marker = signature + " {\n/* BIMAP_CORE_BODY_" + str(index) + " */\n}"
        generated = unique_replace(generated, old, new)
        source_projection = unique_replace(source_projection, old, marker)
        body_projection = unique_replace(body_projection, old, new)
        records.append({"signature": signature, "original_sha256": sha(old.encode()),
                        "generated_sha256": sha(new.encode())})
    for index, (signature, old, new) in enumerate(replacements):
        marker = signature + " {\n/* BIMAP_CORE_BODY_" + str(index) + " */\n}"
        body_projection = unique_replace(body_projection, new, marker)
    if source_projection != body_projection:
        raise ValueError("non-core body projection drift")
    include_old = '#include "StarString.hpp"'
    support = ROOT / "source/core/StarString.hpp" if real_support else HERE / "StarString.hpp"
    include_new = '#include "' + str(support) + '"\n#include "' + str(HERE / "frame.hpp") + '"'
    generated = unique_replace(generated, include_old, include_new)
    candidate = unique_replace(native.decode("utf-8"), '#include "StarBiMap.original.hpp"', '#include "StarBiMap.generated.hpp"')
    old_main = "  try { Fixture::cases(); return 0; }"
    new_main = '''  try {
    Fixture::cases();
    std::cerr << "BIMAP_RUST_COUNTS [";
    for (uint32_t mode = 0; mode < SB_BIMAP_MODE_COUNT; ++mode) {
      if (mode) std::cerr << ',';
      std::cerr << sb_bimap_count(mode);
    }
    std::cerr << "]\\n";
    return 0;
  }'''
    candidate = unique_replace(candidate, old_main, new_main)
    # Reversing precisely the two authorized fixture edits proves ALL case and
    # support function body bytes unchanged, not just selected named cases.
    reverse = unique_replace(candidate, new_main, old_main)
    reverse = unique_replace(reverse, '#include "StarBiMap.generated.hpp"', '#include "StarBiMap.original.hpp"')
    if reverse.encode() != native:
        raise ValueError("candidate fixture projection drift")
    inputs = [HERE / "StarBiMap.original.hpp", HERE / "native.cpp", HERE / "StarString.hpp",
              HERE / "frame.hpp", Path(__file__).resolve(), ROOT / "source/core/StarRustBiMap.h",
              ROOT / "source/rust/ffi/src/bimap.rs"]
    if real_support:
        inputs.append(support)
    manifest = {
        "schema": 1, "scope": "lab-only partial scalar core adapter; NOT production dispatch",
        "support": {"kind": "real" if real_support else "shim", "path": str(support),
                    "sha256": sha(support.read_bytes())},
        "pending_native_original": ["forwarding", "views", "get", "default wrappers", "iterator operations"],
        "inputs": [{"path": str(p), "sha256": sha(p.read_bytes())} for p in inputs],
        "body_replacements": records,
        "body_projection": {"sha256": sha(source_projection.encode()), "equal": True,
                            "fixture_reverse_projection_sha256": sha(reverse.encode())},
        "include_edits": [{"oldText": include_old, "newText": include_new}],
        "outputs": {"StarBiMap.generated.hpp": sha(generated.encode()), "candidate.cpp": sha(candidate.encode())},
        "requires": "C++17; compiler -I source/core; fresh existing Rust aggregate with additive modes17..22 and ops32..36; candidate.cpp remains historical shim fixture, use separate fixture for real support",
        "execution": "NOT RUN by generator; parent owns all compilation, differential checks and qualification",
    }
    # All pins/projections are checked before the first output write.
    output.mkdir()
    (output / "StarBiMap.generated.hpp").write_bytes(generated.encode())
    (output / "candidate.cpp").write_bytes(candidate.encode())
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--real-support", action="store_true",
                        help="include absolute production StarString.hpp; not production dispatch")
    args = parser.parse_args()
    generate(args.output_dir, real_support=args.real_support)


if __name__ == "__main__":
    main()
