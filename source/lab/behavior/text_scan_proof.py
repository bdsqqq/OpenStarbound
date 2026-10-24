"""Normal GUI text callbacks and actual foreground quad colors, not width-only evidence."""
INPUT = b"^red;TEXT^reset;"
RED = [255,73,66,255]
EVENTS = [{"kind": "command", "hex": b"red".hex()}, {"kind": "text", "hex": b"TEXT".hex()}, {"kind": "command", "hex": b"reset".hex()}]
GLYPHS = [{"codepoint": n, "rgba": RED} for n in b"TEXT"]


def same(a, b):
    if type(a) is not type(b): return False
    if isinstance(b, list): return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(b, dict): return a.keys() == b.keys() and all(same(a[k], b[k]) for k in b)
    return a == b


def validate(receipt):
    p = receipt.get("textScanProof")
    if not isinstance(p, dict) or set(p) != set("version backend inputHex calls events glyphs completed".split()):
        raise ValueError("invalid text scanner proof schema")
    if type(p["version"]) is not int or p["version"] != 1 or p["completed"] is not True:
        raise ValueError("incomplete text scanner render scope")
    if p["backend"] not in ("cpp", "rust"):
        raise ValueError("invalid text scanner backend")
    if p["inputHex"] != INPUT.hex() or not same(p["events"], EVENTS):
        raise ValueError("actual normal GUI text/command spans differ")
    if not same(p["glyphs"], GLYPHS):
        raise ValueError("actual foreground glyph codepoints/colors differ")
    wanted = [1,1,2] if p["backend"] == "rust" else [0,0,0]
    if not same(p["calls"], wanted):
        raise ValueError("text scanner render execution/callback receipts differ")
    return {k: value for k, value in p.items() if k not in ("backend", "calls")}


def visible(frame, receipt):
    if receipt.get("cameraPosition") != [64,48] or receipt.get("cameraPixelRatio") != 2 or min(frame.size) < 200:
        raise ValueError("invalid text scanner camera/viewport")
    x, y = frame.width // 2, frame.height // 2
    pixels = list(frame.crop((x-80,y-110,x+80,y-35)).convert("RGBA").getdata())
    # Font coverage can blend the exact native quad color with the room below.
    ink = sum(r > 100 and g < 120 and b < 100 and r > 2*g and a == 255 for r,g,b,a in pixels)
    if ink < 8:
        raise ValueError("normal GUI text has no visible red glyph ink")
