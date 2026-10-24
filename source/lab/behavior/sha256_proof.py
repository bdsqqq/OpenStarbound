"""Validate same-input Assets hashing and real in-memory hashed-key operations."""
import base64
import binascii
import hashlib
import re

MAX_TRANSCRIPT = 32 * 1024 * 1024
KEY = "behaviorlab-sha256-key"
BEFORE = b"alpha\0one".hex()
UPDATED = b"beta\0two".hex()


def _calls(value, expected, backend):
    if not isinstance(value, list) or len(value) != 4 or any(type(n) is not int or n < 0 for n in value):
        raise ValueError("invalid SHA scoped receipts")
    if value != (expected if backend == "rust" else [0, 0, 0, 0]):
        raise ValueError("SHA scoped receipt mismatch")


def validate(receipt):
    proof = receipt.get("sha256Proof")
    if not isinstance(proof, dict) or set(proof) != {"version", "assets", "database"}:
        raise ValueError("invalid SHA proof schema")
    if type(proof["version"]) is not int or proof["version"] != 1:
        raise ValueError("invalid SHA proof version")
    assets, database = proof["assets"], proof["database"]
    if not isinstance(assets, dict) or set(assets) != {"backend", "digestHex", "transcriptBase64", "chunkSizes", "rustCalls"}:
        raise ValueError("invalid Assets SHA proof schema")
    backend = assets["backend"]
    if backend not in ("cpp", "rust"):
        raise ValueError("invalid SHA backend")
    encoded, chunks, digest = assets["transcriptBase64"], assets["chunkSizes"], assets["digestHex"]
    if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_TRANSCRIPT + 2) // 3):
        raise ValueError("SHA input transcript too large/invalid")
    if (not isinstance(chunks, list) or len(chunks) > 1_000_000
            or any(type(n) is not int or not 0 <= n <= MAX_TRANSCRIPT for n in chunks)):
        raise ValueError("invalid SHA input chunk lengths")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("invalid SHA digest")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("invalid SHA input transcript encoding") from error
    if len(data) > MAX_TRANSCRIPT or base64.b64encode(data).decode() != encoded or sum(chunks) != len(data):
        raise ValueError("SHA transcript bytes/chunks disagree")
    # This fixture is below the legacy 512 MiB length wrap; hashlib is a valid
    # independent digest oracle here, not for all legacy total-length states.
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Assets SHA digest differs from exact input transcript")
    _calls(assets["rustCalls"], [1, len(chunks), 1, 0], backend)
    keys = {"backend", "key", "foundBeforeHex", "foundUpdatedHex", "foundReopenedHex", "removed",
            "containsAfterRemove", "recordCountAfterRemove", "rustCalls"}
    if not isinstance(database, dict) or set(database) != keys or database["backend"] != backend:
        raise ValueError("invalid hashed-key database proof schema/backend")
    if (database["key"] != KEY or database["foundBeforeHex"] != BEFORE
            or database["foundUpdatedHex"] != UPDATED or database["foundReopenedHex"] != UPDATED
            or database["removed"] is not True or database["containsAfterRemove"] is not False
            or type(database["recordCountAfterRemove"]) is not int or database["recordCountAfterRemove"] != 0):
        raise ValueError("hashed-key database observations differ")
    _calls(database["rustCalls"], [0, 0, 0, 7], backend)
    return {"version": 1,
            "assets": {key: value for key, value in assets.items() if key not in ("backend", "rustCalls")},
            "database": {key: value for key, value in database.items() if key not in ("backend", "rustCalls")}}
