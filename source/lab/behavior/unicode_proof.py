"""Independent escaped text, scalar lengths, JSON and VersionedJson anchors."""
SOURCE = b'{"text":"\\u0041\\u00e9\\uD83D\\uDE00\\u0000Z","label":"UNICODE"}\n'
TEXT_BYTES = bytes.fromhex("41c3a9f09f9880005a")
TEXT = "A\u00e9\U0001f600\x00Z"
COLOR = [65, 195, 169, 255]
JSON_BYTES = bytes.fromhex("2241c3a9f09f98805c75303030305a22")
VALUE = {"id": "unicodelab", "version": 1, "content": {"text": TEXT}, "subVersions": {}}
# Frozen from the production format BEFORE capture, not from either backend.
SAVE_BYTES = (b"SBVJ01\x0aunicodelab\x01\x00\x00\x00\x01\x07\x01\x04text\x05\x09"
              + TEXT_BYTES + b"\x00\x00\x00\x01\x01\x0bsubVersions\x07\x00")


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
        raise ValueError("invalid Unicode proof schema")


def calls(value, backend, required=(), exact=None):
    if not isinstance(value, list) or len(value) != 10 or any(type(n) is not int or not 0 <= n <= 1_000_000 for n in value):
        raise ValueError("invalid Unicode scoped receipt")
    if backend == "cpp":
        exact = [0] * 10
    if exact is not None:
        if value != exact:
            raise ValueError("Unicode scoped receipt mismatch")
    elif any(value[i] == 0 for i in required):
        raise ValueError("missing Unicode consumer execution receipt")


def validate(receipt):
    p = receipt.get("unicodeProof")
    keys(p, "version assets string json save")
    if type(p["version"]) is not int or p["version"] != 1:
        raise ValueError("invalid Unicode proof version")
    a, s, j, v = (p[name] for name in ("assets", "string", "json", "save"))
    keys(a, "backend sourceHex textHex parseCalls visualColor label")
    backend = a["backend"]
    if backend not in ("cpp", "rust"):
        raise ValueError("invalid Unicode backend")
    if (a["sourceHex"] != SOURCE.hex() or a["textHex"] != TEXT_BYTES.hex()
            or not same(a["visualColor"], COLOR) or a["label"] != "UNICODE"):
        raise ValueError("Unicode Assets differs from independent escape/byte anchors")
    calls(a["parseCalls"], backend, required=(1, 3, 4, 6))
    keys(s, "boundedLength sentinelLength validUtf8 rustCalls")
    if (type(s["boundedLength"]) is not int or s["boundedLength"] != 5
            or type(s["sentinelLength"]) is not int or s["sentinelLength"] != 3
            or s["validUtf8"] is not True):
        raise ValueError("Unicode actual String bounded/NUL/validation mismatch")
    calls(s["rustCalls"], backend, exact=[1, 2, 0, 0, 0, 0, 0, 0, 0, 0])
    keys(j, "wireHex textHex writeCalls readCalls")
    if j["wireHex"] != JSON_BYTES.hex() or j["textHex"] != TEXT_BYTES.hex():
        raise ValueError("Unicode JSON differs from independent literal")
    calls(j["writeCalls"], backend, required=(5,))
    calls(j["readCalls"], backend, required=(3, 4, 6))
    keys(v, "wireHex value consumed writeCalls readCalls")
    if (v["wireHex"] != SAVE_BYTES.hex() or not same(v["value"], VALUE)
            or type(v["consumed"]) is not int or v["consumed"] != len(SAVE_BYTES)):
        raise ValueError("Unicode save differs from independent literal format")
    # Raw binary String I/O may bypass Unicode operations; do not attribute it
    # to this backend just because its bytes were preserved.
    calls(v["writeCalls"], backend)
    calls(v["readCalls"], backend)
    return {"version": 1,
            "assets": {key: value for key, value in a.items() if key not in ("backend", "parseCalls")},
            **{name: {key: value for key, value in p[name].items() if not key.endswith("Calls")}
               for name in ("string", "json", "save")}}


def visible(frame, receipt):
    if receipt.get("cameraPosition") != [64, 48] or receipt.get("cameraPixelRatio") != 2 or min(frame.size) < 200:
        raise ValueError("invalid Unicode visual fixture camera/viewport")
    x, y = frame.width // 2, frame.height // 2
    pixels = list(frame.crop((x - 40, y - 40, x + 40, y + 40)).convert("RGBA").getdata())
    if pixels.count(tuple(COLOR)) < 16:
        raise ValueError("Unicode decoded bytes have no visible result ink")
    label = list(frame.crop((x - 100, y - 100, x + 100, y - 40)).convert("RGBA").getdata())
    if label.count((255, 255, 255, 255)) < 8:
        raise ValueError("Unicode normal-font ASCII label has no visible ink")
