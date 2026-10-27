"""Typed JSON transport for evidence trees; never silently stringify native bytes.

Every node is tagged, so a user dictionary cannot impersonate a byte marker.
This codec has no filesystem effects and does not validate evidence provenance.
"""
import json
import re
import struct

FORMAT = "star-native-evidence-v1"


def dumps(value):
    active = set()

    def encode(v):
        t = type(v)
        if v is None:
            return ["none", None]
        if t is bool:
            return ["bool", v]
        if t is int:
            return ["int", str(v)]
        if t is float:
            return ["float64", struct.pack(">d", v).hex()]
        if t is str:
            return ["str", v]
        if t is bytes:
            return ["bytes", v.hex()]
        if t not in (list, tuple, dict):
            raise TypeError("unsupported evidence type: " + t.__name__)
        if id(v) in active:
            raise ValueError("cyclic evidence tree")
        active.add(id(v))
        try:
            if t is dict:
                return ["dict", [[encode(k), encode(x)] for k, x in v.items()]]
            return ["list" if t is list else "tuple", [encode(x) for x in v]]
        finally:
            active.remove(id(v))

    return json.dumps({"format": FORMAT, "root": encode(value)}, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False)


def loads(text):
    if type(text) is not str:
        raise TypeError("encoded JSON text required, not raw artifact bytes")

    def unique_object(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("duplicate JSON field")
            result[k] = v
        return result

    envelope = json.loads(text, object_pairs_hook=unique_object)
    if (type(envelope) is not dict or set(envelope) != {"format", "root"}
            or envelope["format"] != FORMAT):
        raise ValueError("unknown evidence envelope")

    def decode(node):
        if type(node) is not list or len(node) != 2 or type(node[0]) is not str:
            raise ValueError("malformed typed node")
        tag, v = node
        if tag == "none" and v is None:
            return None
        if tag == "bool" and type(v) is bool:
            return v
        if tag == "str" and type(v) is str:
            return v
        if tag == "int" and type(v) is str and re.fullmatch(r"0|-[1-9][0-9]*|[1-9][0-9]*", v):
            return int(v)
        if tag in ("bytes", "float64") and type(v) is str:
            if not re.fullmatch(r"(?:[0-9a-f]{2})*", v) or (tag == "float64" and len(v) != 16):
                raise ValueError("malformed binary payload")
            raw = bytes.fromhex(v)
            return raw if tag == "bytes" else struct.unpack(">d", raw)[0]
        if tag in ("list", "tuple", "dict") and type(v) is list:
            if tag != "dict":
                result = [decode(x) for x in v]
                return result if tag == "list" else tuple(result)
            result = {}
            for pair in v:
                if type(pair) is not list or len(pair) != 2:
                    raise ValueError("malformed mapping entry")
                key, item = decode(pair[0]), decode(pair[1])
                try:
                    if key in result:
                        raise ValueError("duplicate or colliding decoded key")
                    result[key] = item
                except TypeError as e:
                    raise ValueError("unhashable decoded key") from e
            return result
        raise ValueError("unknown tag or mismatched payload type")

    return decode(envelope["root"])
