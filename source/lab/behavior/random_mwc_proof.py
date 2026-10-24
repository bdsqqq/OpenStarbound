"""Literal seeded MWC sequence and separately observed unsigned/native + signed/Lua values."""
EVENTS = [
    {"op": "construct", "seed": "31415926", "calls": [1, 0, 0]},
    {"op": "randu32", "native": "2950892229", "calls": [0, 0, 1]},
    {"op": "randu64", "native": "6090466678391964828", "calls": [0, 0, 2]},
    {"op": "randu32", "native": "445970691", "calls": [0, 0, 1]},
    {"op": "addEntropy", "seed": "27182818", "calls": [0, 1, 0]},
    {"op": "randu32", "native": "2992900064", "calls": [0, 0, 1]},
    {"op": "randu64", "native": "15329329036541151364", "calls": [0, 0, 2]},
    {"op": "randb", "native": True, "calls": [0, 0, 1]},
    {"op": "init", "seed": "31415926", "calls": [1, 0, 0]},
]
RESET = {"native": "2950892229", "calls": [0, 0, 1]}
LUA = {"b": "6090466678391964828", "e": "-3117415037168400252", "f": True,
       "bInteger": True, "eInteger": True}
COLOR = [197, 10, 227, 255]
VISUAL = {"rgb": COLOR[:3], "width": 44, "height": 16, "label": "RANDOM", "imagePath": "/behaviorlab/random-result.png"}


def same(a, b):
    if type(a) is not type(b): return False
    if isinstance(b, list): return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(b, dict): return a.keys() == b.keys() and all(same(a[k], b[k]) for k in b)
    return a == b


def keys(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError("invalid random MWC proof schema")


def validate(receipt):
    p = receipt.get("randomMwcProof")
    keys(p, "version fixture backend complete sameUserdata events resetDraw lua visual")
    if (type(p["version"]) is not int or p["version"] != 1 or p["fixture"] != "random-mwc-v1"
            or p["backend"] not in ("cpp", "rust") or p["complete"] is not True or p["sameUserdata"] is not True):
        raise ValueError("invalid random MWC identity/completion")
    if not isinstance(p["events"], list) or len(p["events"]) != 9:
        raise ValueError("random MWC native operation sequence incomplete")
    expected = [dict(row, calls=row["calls"] if p["backend"] == "rust" else [0, 0, 0]) for row in EVENTS]
    reset = dict(RESET, calls=RESET["calls"] if p["backend"] == "rust" else [0, 0, 0])
    if not same(p["events"], expected) or not same(p["resetDraw"], reset):
        raise ValueError("random MWC native seed/draw/entropy/reset/receipt sequence differs")
    if not same(p["lua"], LUA):
        raise ValueError("random MWC Lua signed integer/value observation differs")
    if not same(p["visual"], VISUAL):
        raise ValueError("random MWC actual bytes/width do not drive the normal visual")
    return {k: value for k, value in p.items() if k not in ("backend", "events", "resetDraw")} | {
        "events": [{k: value for k, value in row.items() if k != "calls"} for row in p["events"]],
        "resetDraw": {k: value for k, value in p["resetDraw"].items() if k != "calls"}}


def visible(frame, receipt):
    if receipt.get("cameraPosition") != [64, 48] or receipt.get("cameraPixelRatio") != 2 or min(frame.size) < 220:
        raise ValueError("invalid random MWC camera/viewport")
    x, y = frame.width // 2, frame.height // 2
    pixels = list(frame.crop((x - 100, y - 48, x + 100, y + 48)).convert("RGBA").getdata())
    matches = [(i % 200, i // 200) for i, pixel in enumerate(pixels) if pixel == tuple(COLOR)]
    if not matches or len(matches) != 176 * 64:
        raise ValueError("random MWC result has no exact 176x64 visible area")
    xs, ys = zip(*matches)
    if (min(xs), min(ys), max(xs) + 1, max(ys) + 1) != (12, 16, 188, 80):
        raise ValueError("random MWC actual-derived width or position differs")
    label = list(frame.crop((x - 100, y - 100, x + 100, y - 40)).convert("RGBA").getdata())
    if label.count((255, 255, 255, 255)) < 8:
        raise ValueError("random MWC normal-font label has no visible ink")
