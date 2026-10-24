"""Literal JSON patch/query anchors; counters attribute the real consumer calls."""
SOURCE = '{"a/b":{"~é":[64,128]},"visual":{"rgb":[],"scale":4,"label":"JSONPATH"}}\n'.encode()
PATCH = ('[{"op":"copy","from":"/a~1b/~0é/0","path":"/visual/rgb/-"},'
         '{"op":"copy","from":"/a~1b/~0é/1","path":"/visual/rgb/-"},'
         '{"op":"add","path":"/visual/rgb/-","value":192}]\n').encode()
BASE = "/behaviorlab/jsonpath-input.json"
COLOR = [64, 128, 192, 255]


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
        raise ValueError("invalid JSON-path proof schema")


def calls(actual, backend, expected):
    if not same(actual, expected if backend == "rust" else [0, 0]):
        raise ValueError("JSON-path scoped consumer receipts differ")


def validate(receipt):
    p = receipt.get("jsonPathProof")
    keys(p, "version assets script visual")
    if type(p["version"]) is not int or p["version"] != 1:
        raise ValueError("invalid JSON-path proof version")
    a, s, v = (p[k] for k in ("assets", "script", "visual"))
    keys(a, "backend sourceHex patchHex rgb scale label")
    backend = a["backend"]
    if backend not in ("cpp", "rust"):
        raise ValueError("invalid JSON-path backend")
    if a["sourceHex"] != SOURCE.hex() or a["patchHex"] != PATCH.hex():
        raise ValueError("JSON-path source/patch differs from independent literals")
    for name, value, counts in (("rgb", COLOR[:3], [21, 2]), ("scale", 4, [0, 2]), ("label", "JSONPATH", [0, 2])):
        row = a[name]
        keys(row, "path value rustCalls")
        if row["path"] != BASE + ":visual." + name or not same(row["value"], value):
            raise ValueError("JSON-path actual Assets patch/query result differs")
        calls(row["rustCalls"], backend, counts)
    keys(s, "query missing malformed")
    for name, path, value, counts in (("query", "é[0].雪", 9, [0, 3]), ("missing", "missing", 77, [0, 1])):
        row = s[name]
        keys(row, "path value rustCalls")
        if row["path"] != path or not same(row["value"], value):
            raise ValueError("JSON-path actual Lua helper/default result differs")
        calls(row["rustCalls"], backend, counts)
    row = s["malformed"]
    keys(row, "path accepted nativeErrorMatched rustCalls")
    if row["path"] != "é[0x].雪" or row["accepted"] is not False or row["nativeErrorMatched"] is not True:
        raise ValueError("JSON-path malformed Lua helper did not reject the native syntax error")
    calls(row["rustCalls"], backend, [0, 2])
    if not same(v, {"imagePath": "/behaviorlab/jsonpath-result.png", "color": COLOR, "scale": 4, "label": "JSONPATH"}):
        raise ValueError("JSON-path normal visual is not driven by the observed values")
    return {"version": 1, "assets": {k: (value if k in ("sourceHex", "patchHex") else
                {rk: rv for rk, rv in value.items() if rk != "rustCalls"})
            for k, value in a.items() if k != "backend"},
            "script": {k: {rk: rv for rk, rv in row.items() if rk != "rustCalls"} for k, row in s.items()}, "visual": v}


def visible(frame, receipt):
    if receipt.get("cameraPosition") != [64, 48] or receipt.get("cameraPixelRatio") != 2 or min(frame.size) < 200:
        raise ValueError("invalid JSON-path camera/viewport")
    x, y = frame.width // 2, frame.height // 2
    pixels = list(frame.crop((x - 40, y - 40, x + 40, y + 40)).convert("RGBA").getdata())
    if pixels.count(tuple(COLOR)) < 16:
        raise ValueError("JSON-path patched RGB has no visible result ink")
    label = list(frame.crop((x - 100, y - 100, x + 100, y - 40)).convert("RGBA").getdata())
    if label.count((255, 255, 255, 255)) < 8:
        raise ValueError("JSON-path normal-font label has no visible ink")
