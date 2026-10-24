"""Literal shell arguments plus actual local command responses and world state."""
import math

COMMANDS = ["2f7365746772617669747920225c75303033302e323522", "2f736574677261766974792022302e323522"]
COLOR = [224, 160, 32, 255]
RESPONSE = ["Gravity set to 0.25 (This is client-side!)"]


def keys(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError("invalid shell proof schema")


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def calls(value, expected):
    if type(value) is not int or value != expected:
        raise ValueError("shell scoped receipt mismatch")


def validate(receipt):
    p = receipt.get("shellProof")
    keys(p, "version backend admin queryPosition originalGravity commands query restore visual")
    if type(p["version"]) is not int or p["version"] != 1 or p["backend"] not in ("cpp", "rust") or p["admin"] is not True:
        raise ValueError("invalid shell version/backend/admin")
    if (p["queryPosition"] != [64, 48] or any(type(x) is not int for x in p["queryPosition"])
            or not number(p["originalGravity"]) or p["originalGravity"] == 0.25):
        raise ValueError("invalid shell original gravity/query position")
    if not isinstance(p["commands"], list) or len(p["commands"]) != 2:
        raise ValueError("invalid shell command sequence")
    expected_calls = int(p["backend"] == "rust")
    commands = []
    for command, literal in zip(p["commands"], COMMANDS):
        keys(command, "commandHex tokenHex tokenCalls responses gravity gravityBits rustCalls")
        if (command["commandHex"] != literal or command["tokenHex"] != ["302e3235"]
                or command["responses"] != RESPONSE or not number(command["gravity"])
                or command["gravity"] != 0.25 or command["gravityBits"] != "3e800000"):
            raise ValueError("shell literal tokens/response/observed gravity differ")
        calls(command["tokenCalls"], expected_calls)
        calls(command["rustCalls"], expected_calls)
        commands.append({key: value for key, value in command.items() if not key.endswith("Calls")})
    for key, response, gravity in (("query", ["0.25"], 0.25), ("restore", ["Gravity reset"], p["originalGravity"])):
        value = p[key]
        keys(value, "responses gravity rustCalls")
        if value["responses"] != response or not number(value["gravity"]) or value["gravity"] != gravity:
            raise ValueError("shell world gravity query/restoration failed")
        calls(value["rustCalls"], 0)
    v = p["visual"]
    keys(v, "gravity imagePath label color")
    if (not number(v["gravity"]) or v["gravity"] != 0.25 or v["imagePath"] != "/behaviorlab/shell-result.png"
            or v["label"] != "SHELL" or v["color"] != COLOR or any(type(x) is not int for x in v["color"])):
        raise ValueError("shell actual-state visual contract differs")
    return {"version": 1, "admin": True, "queryPosition": p["queryPosition"], "originalGravity": p["originalGravity"],
            "commands": commands, "visual": v,
            **{key: {k: value for k, value in p[key].items() if k != "rustCalls"} for key in ("query", "restore")}}


def visible(frame, receipt):
    if receipt.get("cameraPosition") != [64, 48] or receipt.get("cameraPixelRatio") != 2 or min(frame.size) < 200:
        raise ValueError("invalid shell visual camera/viewport")
    x, y = frame.width // 2, frame.height // 2
    image = list(frame.crop((x - 40, y - 40, x + 40, y + 40)).convert("RGBA").getdata())
    if image.count(tuple(COLOR)) < 16:
        raise ValueError("shell observed gravity has no visible image result")
    label = list(frame.crop((x - 100, y - 100, x + 100, y - 40)).convert("RGBA").getdata())
    if label.count((255, 255, 255, 255)) < 8:
        raise ValueError("shell normal-font label has no visible ink")
