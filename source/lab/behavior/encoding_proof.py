"""Exact embedded-image evidence; no synthetic pixels count as gameplay proof."""
import base64
import io
import re
from PIL import Image

PALETTE = ((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 255, 255))
SCOPES = {"directives": {1, 2}, "embed": {3}, "decode": {4}, "standard": {3}}


def validate(receipt):
    proof = receipt.get("encodingProof")
    keys = {"version", "patternSize", "embeddedPath", "dataUri", "receipts", "backend", "drawDirective", "drawReceipts"}
    if not isinstance(proof, dict) or set(proof) != keys:
        raise ValueError("invalid encoding proof schema")
    if type(proof["version"]) is not int or proof["version"] != 1 or proof["patternSize"] != [16, 16]:
        raise ValueError("invalid encoding pattern/version")
    if proof["backend"] not in ("cpp", "rust") or proof["drawDirective"] != "multiply=ffffff":
        raise ValueError("invalid encoding backend/draw directive")
    if not isinstance(proof["receipts"], dict) or set(proof["receipts"]) != set(SCOPES):
        raise ValueError("invalid encoding operation scopes")
    for scope, active in {**SCOPES, "draw": {0}}.items():
        calls = proof["drawReceipts"] if scope == "draw" else proof["receipts"][scope]
        if not isinstance(calls, list) or len(calls) != 5:
            raise ValueError("invalid encoding scoped receipt")
        for op, count in enumerate(calls):
            if type(count) is not int or not 0 <= count <= 1_000_000:
                raise ValueError("invalid encoding call count")
            positive = proof["backend"] == "rust" and op in active
            if (count > 0) != positive:
                raise ValueError(f"encoding {scope} operation {op} receipt mismatch")
    prefix = "/opensb_data;bin;"
    embedded, uri = proof["embeddedPath"], proof["dataUri"]
    if (not isinstance(embedded, str) or not embedded.startswith(prefix) or len(embedded) > 100_000
            or not isinstance(uri, str) or len(uri) > 150_000):
        raise ValueError("invalid encoding embedded image strings")
    encoded = embedded[len(prefix):]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
        raise ValueError("embedded image is not unpadded URL base64")
    try:
        png = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        if base64.urlsafe_b64encode(png).decode().rstrip("=") != encoded:
            raise ValueError("noncanonical embedded image encoding")
        if uri != "data:image/png;base64," + base64.b64encode(png).decode():
            raise ValueError("standard/URL encoding bytes differ")
        with Image.open(io.BytesIO(png)) as source:
            if source.format != "PNG" or source.size != (16, 16):
                raise ValueError("encoding image is not the bounded pattern PNG")
            actual = source.convert("RGBA")
            expected = [PALETTE[((x // 4 + y // 4) % 4 + 1) % 4] for y in range(16) for x in range(16)]
            if list(actual.getdata()) != expected:
                raise ValueError("encoding image differs from independent rotated pattern")
    except (OSError, SyntaxError, base64.binascii.Error) as error:
        raise ValueError("invalid encoding PNG/base64") from error
    return {key: proof[key] for key in keys - {"backend", "receipts", "drawReceipts"}}


def visible(frame, receipt):
    """Ink complements byte identity and exact frames; it never masks pixels."""
    if receipt.get("cameraPosition") != [64, 48] or receipt.get("cameraPixelRatio") != 2:
        raise ValueError("encoding image camera differs from fixed native scene")
    if frame.width < 96 or frame.height < 96:
        raise ValueError("encoding viewport too small for pattern visibility")
    cx, cy = frame.width // 2, frame.height // 2
    pixels = list(frame.crop((cx - 40, cy - 40, cx + 40, cy + 40)).convert("RGBA").getdata())
    if any(pixels.count(color) < 4 for color in PALETTE):
        raise ValueError("encoding pattern missing visible palette ink")
