"""Independent all-handler JSON patch/rollback result and semantic receipt vectors."""
import json
SOURCE = "{\"a/b\":{\"~é\":[64,128]},\"items\":[{\"id\":\"a\",\"n\":1},{\"id\":\"b\",\"n\":2}],\"visual\":{\"rgb\":[],\"scale\":1,\"label\":\"BEFORE\"},\"trash\":7}\n".encode("utf-8")
PATCHES = ["[{\"op\":\"test\",\"path\":\"/a~1b/~0é/0\",\"value\":64},{\"op\":\"copy\",\"from\":\"/a~1b/~0é/0\",\"path\":\"/visual/rgb/-\"},{\"op\":\"add\",\"path\":\"/visual/rgb/-\",\"value\":128},{\"op\":\"replace\",\"path\":\"/visual/scale\",\"value\":4},{\"op\":\"move\",\"from\":\"/trash\",\"path\":\"/moved\"},{\"op\":\"remove\",\"path\":\"/moved\"},{\"op\":\"merge\",\"path\":\"/visual\",\"value\":{\"rgb\":[64,128,192],\"label\":\"PATCH\",\"scale\":null}},{\"op\":\"test\",\"path\":\"/items\",\"search\":{\"id\":\"a\"}},{\"op\":\"add\",\"path\":\"/items\",\"search\":{\"id\":\"b\"},\"value\":{\"id\":\"x\",\"n\":9}},{\"op\":\"replace\",\"path\":\"/items\",\"search\":{\"id\":\"x\"},\"value\":{\"id\":\"x\",\"n\":10}},{\"op\":\"merge\",\"path\":\"/items\",\"search\":{\"id\":\"x\"},\"value\":{\"extra\":true,\"n\":null}},{\"op\":\"copy\",\"from\":\"/items\",\"path\":\"/selected\",\"search\":{\"id\":\"x\"}},{\"op\":\"move\",\"from\":\"/items\",\"path\":\"/picked\",\"search\":{\"id\":\"b\"}},{\"op\":\"remove\",\"path\":\"/items\",\"search\":{\"id\":\"a\"}},{\"op\":\"test\",\"path\":\"/absent\",\"inverse\":true},[{\"op\":\"add\",\"path\":\"/visual/scale\",\"value\":99},{\"op\":\"test\",\"path\":\"/visual/scale\",\"value\":-1}],{\"op\":\"add\",\"path\":\"/after\",\"value\":true}]\n".encode("utf-8"), "[{\"op\":\"replace\",\"path\":\"/visual/label\",\"value\":\"BAD\"},{\"op\":\"test\",\"path\":\"/visual/scale\",\"value\":-1}]\n".encode("utf-8")]
VALUE = json.loads("{\"a/b\":{\"~é\":[64,128]},\"items\":[{\"id\":\"x\",\"n\":10,\"extra\":true}],\"visual\":{\"rgb\":[64,128,192],\"scale\":4,\"label\":\"PATCH\"},\"selected\":{\"id\":\"x\",\"n\":10,\"extra\":true},\"picked\":{\"id\":\"b\",\"n\":2},\"after\":true}")
CALLS = {"attempt": [0,20,7,5,2,4,3,2,2,2], "success": [0,18,7,3,2,4,3,2,2,2], "exception": [0,2,0,2,0,0,0,0,0,0]}
COLOR = [64,128,192,255]

def same(a, b):
    if type(a) is not type(b): return False
    if isinstance(b, list): return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(b, dict): return a.keys() == b.keys() and all(same(a[k], b[k]) for k in b)
    return a == b


def keys(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError("invalid JSON patch proof schema")


def validate(receipt):
    p = receipt.get("jsonPatchProof")
    keys(p, "version assets visual")
    if type(p["version"]) is not int or p["version"] != 1:
        raise ValueError("invalid JSON patch proof version")
    a, v = p["assets"], p["visual"]
    keys(a, "backend sourceHex patchesHex value calls")
    backend = a["backend"]
    if backend not in ("cpp", "rust"):
        raise ValueError("invalid JSON patch backend")
    if a["sourceHex"] != SOURCE.hex() or a["patchesHex"] != [value.hex() for value in PATCHES]:
        raise ValueError("JSON patch inputs differ from independent literal bytes")
    if not same(a["value"], VALUE):
        raise ValueError("JSON patch full typed result/search/rollback differs")
    expected = CALLS if backend == "rust" else {name: [0] * 10 for name in CALLS}
    if not same(a["calls"], expected):
        raise ValueError("JSON patch attempted/successful/exception semantic receipts differ")
    visual = {"color": COLOR, "scale": 4, "label": "PATCH", "imagePath": "/behaviorlab/jsonpatch-result.png"}
    if not same(v, visual):
        raise ValueError("JSON patch actual data does not drive the normal image/Font")
    return {"version": 1, "assets": {k: value for k, value in a.items() if k not in ("backend", "calls")}, "visual": v}


def visible(frame, receipt):
    if receipt.get("cameraPosition") != [64,48] or receipt.get("cameraPixelRatio") != 2 or min(frame.size) < 200:
        raise ValueError("invalid JSON patch camera/viewport")
    x, y = frame.width // 2, frame.height // 2
    pixels = list(frame.crop((x-40,y-40,x+40,y+40)).convert("RGBA").getdata())
    if pixels.count(tuple(COLOR)) < 16:
        raise ValueError("JSON patch actual result has no visible pixel ink")
    label = list(frame.crop((x-100,y-100,x+100,y-40)).convert("RGBA").getdata())
    if label.count((255,255,255,255)) < 8:
        raise ValueError("JSON patch normal-font label has no visible ink")
