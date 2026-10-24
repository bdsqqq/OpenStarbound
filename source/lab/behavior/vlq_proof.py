"""Independent bytes and observed native I/O, never paired round-trip alone."""
import base64
import binascii
import re

PAIR_HEX = "0602048101048200"
STRING_HEX = "058100" + "78" * 128
VALUE = {"id": "vlqlab", "version": 1, "content": [-65, 128, "x" * 128], "subVersions": {"vlq": 128}}
# StarVersioningDatabase's file body: SBVJ01, String, Maybe<uint32>, binary
# JSON, uint32 sub-versioning=1, then a raw JsonObject map container (no
# outer JSON tag); its subVersions value is itself tagged binary JSON.
# Frozen before native capture; derived from the production format, not its output.
SAVE_BYTES = (b"SBVJ01\x06vlqlab\x01\x00\x00\x00\x01\x06\x03\x04\x81\x01\x04\x82\x00\x05\x81\x00"
              + b"x" * 128 + b"\x00\x00\x00\x01\x01\x0bsubVersions\x07\x01\x03vlq\x04\x82\x00")


def _same(value, expected):
    if type(value) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(value) == len(expected) and all(_same(a, b) for a, b in zip(value, expected))
    if isinstance(expected, dict):
        return value.keys() == expected.keys() and all(_same(value[k], expected[k]) for k in expected)
    return value == expected


def _keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError("invalid VLQ " + label + " schema")


def _calls(calls, backend, active=(), exact=None):
    if not isinstance(calls, list) or len(calls) != 6 or any(type(n) is not int or not 0 <= n <= 1_000_000 for n in calls):
        raise ValueError("invalid VLQ scoped receipt")
    if backend == "cpp":
        wanted = [0] * 6
    elif exact is not None:
        wanted = exact
    else:
        if any((n > 0) != (i in active) for i, n in enumerate(calls)):
            raise ValueError("VLQ scoped receipt mismatch")
        return
    if calls != wanted:
        raise ValueError("VLQ scoped receipt mismatch")


def _hex(value, maximum=2_000_000):
    if not isinstance(value, str) or len(value) > maximum or len(value) % 2 or not re.fullmatch(r"[0-9a-f]*", value):
        raise ValueError("invalid VLQ byte transcript")
    return bytes.fromhex(value)


def validate(receipt):
    p = receipt.get("vlqProof")
    _keys(p, "version assets save packets database eof", "proof")
    if type(p["version"]) is not int or p["version"] != 1:
        raise ValueError("invalid VLQ proof version")
    a, s, k, d, e = (p[name] for name in ("assets", "save", "packets", "database", "eof"))
    _keys(a, "backend pairInputHex pairValue stringInputHex stringValue readCalls visualColor", "asset")
    backend = a["backend"]
    if backend not in ("cpp", "rust"):
        raise ValueError("invalid VLQ backend")
    if (a["pairInputHex"] != PAIR_HEX or not _same(a["pairValue"], [-65, 128]) or a["stringInputHex"] != STRING_HEX
            or a["stringValue"] != "x" * 128 or not _same(a["visualColor"], [255, 0, 0, 255])):
        raise ValueError("VLQ embedded JSON differs from independent input/value")
    _keys(a["readCalls"], "pair string", "asset receipts")
    _calls(a["readCalls"]["pair"], backend, exact=[0, 0, 1, 0, 0, 2])
    _calls(a["readCalls"]["string"], backend, exact=[0, 0, 1, 0, 0, 0])
    _keys(s, "wireHex value consumed writeCalls readCalls", "save")
    wire = _hex(s["wireHex"])
    if wire != SAVE_BYTES or not _same(s["value"], VALUE) or type(s["consumed"]) is not int or s["consumed"] != len(wire):
        raise ValueError("VLQ save bytes/value/consumption differ from independent format")
    _calls(s["writeCalls"], backend, active=(0, 3))
    _calls(s["readCalls"], backend, active=(2, 5))
    _keys(k, "currentPingHex currentPongHex legacyPingHex legacyPongHex decodedTimes signedSize sizeCalls writeCalls readCalls", "packet")
    if (k["currentPingHex"] != "8101" or k["currentPongHex"] != "8200" or k["legacyPingHex"] != "00"
            or k["legacyPongHex"] != "00" or not _same(k["decodedTimes"], [-65, 128, 0, 0])
            or type(k["signedSize"]) is not int or k["signedSize"] != 2):
        raise ValueError("VLQ packet bytes/value differ from independent literals")
    _calls(k["sizeCalls"], backend, exact=[0, 0, 0, 0, 1, 0])
    _calls(k["writeCalls"], backend, exact=[0, 0, 0, 2, 0, 0])
    _calls(k["readCalls"], backend, exact=[0, 0, 0, 0, 0, 2])
    _keys(d, "valueLengths foundHex pagesBase64 rustCalls", "database")
    lengths = [127, 128, 700]
    expected = [bytes((i + seed) & 255 for i in range(n)).hex() for seed, n in enumerate(lengths)]
    if not _same(d["valueLengths"], lengths) or d["foundHex"] != expected:
        raise ValueError("VLQ database values differ")
    if not isinstance(d["pagesBase64"], str) or len(d["pagesBase64"]) > 2_000_000:
        raise ValueError("invalid VLQ database pages")
    try:
        pages = base64.b64decode(d["pagesBase64"], validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("invalid VLQ database page encoding") from error
    if len(pages) < 1024 or len(pages) % 512 or base64.b64encode(pages).decode() != d["pagesBase64"]:
        raise ValueError("invalid VLQ database page structure")
    _calls(d["rustCalls"], backend, active=(0, 1, 2))
    _keys(e, "kind unsignedValue consumed readCalls", "EOF")
    if (e["kind"] != "EofException" or type(e["unsignedValue"]) is not int or e["unsignedValue"] != 1
            or type(e["consumed"]) is not int or e["consumed"] != 1):
        raise ValueError("VLQ EOF type/prefix/consumption differ")
    _calls(e["readCalls"], backend, exact=[0, 0, 1, 0, 0, 0])
    return {"version": 1,
            "assets": {key: value for key, value in a.items() if key not in ("backend", "readCalls")},
            **{name: {key: value for key, value in p[name].items() if not key.endswith("Calls")}
               for name in ("save", "packets", "database", "eof")}}


def visible(frame, receipt):
    if receipt.get("cameraPosition") != [64, 48] or receipt.get("cameraPixelRatio") != 2 or min(frame.size) < 96:
        raise ValueError("invalid VLQ visual fixture camera/viewport")
    x, y = frame.width // 2, frame.height // 2
    pixels = list(frame.crop((x - 40, y - 40, x + 40, y + 40)).convert("RGBA").getdata())
    if pixels.count((255, 0, 0, 255)) < 16:
        raise ValueError("VLQ decoded JSON has no visible red fixture ink")
