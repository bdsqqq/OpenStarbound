"""Independent atlas pixels, frame metadata and nonidentity directive anchors."""
from io import BytesIO
from PIL import Image, UnidentifiedImageError

FRAMES = b'{"frameList":{"left":[0,0,16,16],"right":[16,0,32,16]},"aliases":{"alias":"right"}}\n'
ATLAS = "/behaviorlab/assetpath-atlas.png"
COLOR = [32, 128, 96, 255]
RGBA = bytes(COLOR) * 256


def same(a, b):
    if type(a) is not type(b): return False
    if isinstance(b, list): return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(b, dict): return a.keys() == b.keys() and all(same(a[k], b[k]) for k in b)
    return a == b


def keys(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError("invalid asset-path proof schema")


def atlas(value):
    if (not isinstance(value, str) or not 16 <= len(value) <= 16384 or len(value) % 2
            or any(c not in "0123456789abcdef" for c in value)):
        raise ValueError("invalid asset-path source PNG encoding")
    try:
        with Image.open(BytesIO(bytes.fromhex(value))) as image:
            if image.format != "PNG" or image.mode != "RGBA" or image.size != (32, 16):
                raise ValueError("asset-path source atlas dimensions/format differ")
            expected = (bytes([255, 0, 0, 255]) * 16 + bytes([64, 128, 192, 255]) * 16) * 16
            if image.tobytes() != expected:
                raise ValueError("asset-path source atlas differs from independent pixels")
    except (OSError, UnidentifiedImageError) as error:
        raise ValueError("invalid asset-path source PNG") from error


def validate(receipt):
    p = receipt.get("assetPathProof")
    keys(p, "version assets visual")
    if type(p["version"]) is not int or p["version"] != 1:
        raise ValueError("invalid asset-path proof version")
    a, v = p["assets"], p["visual"]
    keys(a, "backend atlasHex framesHex named alias")
    backend = a["backend"]
    if backend not in ("cpp", "rust"):
        raise ValueError("invalid asset-path backend")
    atlas(a["atlasHex"])
    if a["framesHex"] != FRAMES.hex():
        raise ValueError("asset-path source frame table differs from independent literal")
    for name, frame, counts in (("named", "right", [1, 2]), ("alias", "alias", [1, 0])):
        row = a[name]
        keys(row, "path size rgbaHex rustCalls")
        if row["path"] != ATLAS + ":" + frame + "?multiply=80ff80" or not same(row["size"], [16, 16]) or row["rgbaHex"] != RGBA.hex():
            raise ValueError("asset-path actual named/alias crop/directive result differs")
        if not same(row["rustCalls"], counts if backend == "rust" else [0, 0]):
            raise ValueError("asset-path scoped split/range receipts differ")
    expected = {"imagePath": "/behaviorlab/assetpath-result.png", "color": COLOR, "size": [16, 16], "label": "ASSETPATH"}
    if not same(v, expected):
        raise ValueError("asset-path normal image/Font differs from actual returned frame")
    return {"version": 1, "assets": {k: (value if k in ("atlasHex", "framesHex") else
                {rk: rv for rk, rv in value.items() if rk != "rustCalls"})
            for k, value in a.items() if k != "backend"}, "visual": v}


def visible(frame, receipt):
    if receipt.get("cameraPosition") != [64, 48] or receipt.get("cameraPixelRatio") != 2 or min(frame.size) < 200:
        raise ValueError("invalid asset-path camera/viewport")
    x, y = frame.width // 2, frame.height // 2
    pixels = list(frame.crop((x - 40, y - 40, x + 40, y + 40)).convert("RGBA").getdata())
    if pixels.count(tuple(COLOR)) < 16:
        raise ValueError("asset-path processed crop has no visible ink")
    label = list(frame.crop((x - 100, y - 100, x + 100, y - 40)).convert("RGBA").getdata())
    if label.count((255, 255, 255, 255)) < 8:
        raise ValueError("asset-path normal-font label has no visible ink")
