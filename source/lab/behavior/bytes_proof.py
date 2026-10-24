"""Independent fixed-width wire anchors and visible native Assets observation."""
import base64
import binascii

INPUT_HEX = "0603023fd0000000000000023fe0000000000000023fe8000000000000"
VALUES = [0.25, 0.5, 0.75]
COLOR = [64, 128, 192, 255]
VALUE = {"id": "byteslab", "version": 16909060, "content": VALUES, "subVersions": {}}
# Frozen before capture, from VersionedJson's production file format. The outer
# subversion map is raw, while its subVersions value carries JSON object tag07.
SAVE_HEX = ("5342564a30310862797465736c61620101020304" + INPUT_HEX
            + "00000001010b73756256657273696f6e730700")


def same(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(same(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(same(actual[k], expected[k]) for k in expected)
    return actual == expected


def keys(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError("invalid byte-order proof schema")


def calls(value, backend, expected=None):
    if not isinstance(value, list) or len(value) != 6 or any(type(n) is not int or not 0 <= n <= 1_000_000 for n in value):
        raise ValueError("invalid byte-order scoped receipt")
    if backend == "cpp":
        expected = [0] * 6
    if expected is not None:
        if value != expected:
            raise ValueError("byte-order scoped receipt mismatch")
    elif any((n > 0) != (i in (3, 5)) for i, n in enumerate(value)):
        raise ValueError("byte-order database scoped receipt mismatch")


def validate(receipt):
    p = receipt.get("bytesProof")
    keys(p, "version assets save packets database")
    if type(p["version"]) is not int or p["version"] != 1:
        raise ValueError("invalid byte-order proof version")
    a, s, k, d = (p[name] for name in ("assets", "save", "packets", "database"))
    keys(a, "backend inputHex values rustCalls visualColor")
    backend = a["backend"]
    if backend not in ("cpp", "rust"):
        raise ValueError("invalid byte-order backend")
    if a["inputHex"] != INPUT_HEX or not same(a["values"], VALUES) or not same(a["visualColor"], COLOR):
        raise ValueError("byte-order Assets differs from independent binary64 input")
    calls(a["rustCalls"], backend, [0, 0, 0, 0, 0, 3])
    keys(s, "wireHex value consumed writeCalls readCalls")
    if s["wireHex"] != SAVE_HEX or not same(s["value"], VALUE) or type(s["consumed"]) is not int or s["consumed"] != len(bytes.fromhex(SAVE_HEX)):
        raise ValueError("byte-order save differs from independent wire format")
    calls(s["writeCalls"], backend, [0, 0, 0, 5, 0, 0])
    calls(s["readCalls"], backend, [0, 0, 0, 0, 0, 5])
    keys(k, "currentInputHex legacyInputHex currentWireHex legacyWireHex currentConsumed legacyConsumed paused timescales writeCalls readCalls")
    if (k["currentInputHex"] != "013f000000" or k["currentWireHex"] != "013f000000"
            or k["legacyInputHex"] != "01" or k["legacyWireHex"] != "01"
            or type(k["currentConsumed"]) is not int or k["currentConsumed"] != 5
            or type(k["legacyConsumed"]) is not int or k["legacyConsumed"] != 1
            or not same(k["paused"], [True, True])
            # JSON may spell an integral float as 1; bool is NOT a number here.
            or not isinstance(k["timescales"], list) or len(k["timescales"]) != 2
            or any(type(n) not in (int, float) for n in k["timescales"])
            or k["timescales"] != [0.5, 1.0]):
        raise ValueError("byte-order PausePacket differs from independent binary32 inputs")
    calls(k["writeCalls"], backend, [0, 0, 0, 1, 0, 0])
    calls(k["readCalls"], backend, [0, 0, 0, 0, 0, 1])
    keys(d, "valueLengths foundHex pagesBase64 rustCalls")
    lengths = [127, 128, 700]
    expected = [bytes((i + seed) & 255 for i in range(n)).hex() for seed, n in enumerate(lengths)]
    if not same(d["valueLengths"], lengths) or d["foundHex"] != expected:
        raise ValueError("byte-order database values differ")
    if not isinstance(d["pagesBase64"], str) or len(d["pagesBase64"]) > 2_000_000:
        raise ValueError("invalid byte-order database page encoding")
    try:
        pages = base64.b64decode(d["pagesBase64"], validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("invalid byte-order database page encoding") from error
    if (len(pages) < 1024 or len(pages) % 512 or base64.b64encode(pages).decode() != d["pagesBase64"]
            or pages[:8] != b"BTreeDB5" or pages[8:12] != b"\x00\x00\x02\x00"
            or pages[28:32] != b"\x00\x00\x00\x20"):
        raise ValueError("byte-order database fixed-width header differs")
    calls(d["rustCalls"], backend)
    return {"version": 1,
            "assets": {key: value for key, value in a.items() if key not in ("backend", "rustCalls")},
            **{name: {key: value for key, value in p[name].items() if not key.endswith("Calls")}
               for name in ("save", "packets", "database")}}


def visible(frame, receipt):
    if receipt.get("cameraPosition") != [64, 48] or receipt.get("cameraPixelRatio") != 2 or min(frame.size) < 96:
        raise ValueError("invalid byte-order visual camera/viewport")
    x, y = frame.width // 2, frame.height // 2
    pixels = list(frame.crop((x - 40, y - 40, x + 40, y + 40)).convert("RGBA").getdata())
    if pixels.count(tuple(COLOR)) < 16:
        raise ValueError("byte-order decoded JSON has no visible result ink")
