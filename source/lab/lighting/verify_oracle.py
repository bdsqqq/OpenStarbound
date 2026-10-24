#!/usr/bin/env python3
"""Reject oracle drift even when Python assertion checks are disabled."""
import argparse
import hashlib
from pathlib import Path
import subprocess

HEAD = "f5c4da285ba4bbb8eaf21211b8ff9d27654fed55"
HASHES = {
    "StarCellularLightArray.hpp": "f5eea98486ab72adc3ecb37f5e123cff37b49f9c6e9716da8053d87cde6c3ca9",
    "StarCellularLightArray.cpp": "a0f3bab0bebb3839be8e30da4f56f73088ee27f976a03a72b090a2b2ff5dd7e4",
}


def expected_oracles():
    root = Path(__file__).resolve().parents[3]
    expected = {}
    for filename, expected_hash in HASHES.items():
        original = subprocess.check_output(
            ["git", "show", f"{HEAD}:source/base/{filename}"], cwd=root)
        if hashlib.sha256(original).hexdigest() != expected_hash:
            raise ValueError(f"reference hash differs: {filename}")
        if original.count(b"namespace Star {") != 1:
            raise ValueError(f"unexpected reference namespace: {filename}")
        isolated = original.replace(b"namespace Star {", b"namespace Star { namespace LightingOracle {")
        closing = isolated.rfind(b"}")
        if closing < 0 or isolated[closing + 1:].strip():
            raise ValueError(f"unexpected reference namespace ending: {filename}")
        expected[filename] = isolated[:closing] + b"}}" + isolated[closing + 1:]
    return expected


def verify(expected, actual):
    for filename, content in expected.items():
        if actual[filename] != content:
            raise ValueError(f"oracle algorithm drift: {filename}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    expected = expected_oracles()
    actual = {name: (Path(__file__).parent / "oracle" / name).read_bytes() for name in HASHES}
    verify(expected, actual)
    for name, digest in HASHES.items():
        print(f"verified {name}: original sha256={digest}, namespace-only delta")
    if args.self_test:
        mutated = dict(actual)
        old = b"std::max(source - drop, dest)"
        if old not in mutated["StarCellularLightArray.hpp"]:
            raise ValueError("self-test mutation site disappeared")
        mutated["StarCellularLightArray.hpp"] = mutated["StarCellularLightArray.hpp"].replace(
            old, b"std::min(source - drop, dest)", 1)
        try:
            verify(expected, mutated)
        except ValueError:
            print("oracle verifier self-test: deliberate max-to-min mutation rejected")
        else:
            raise ValueError("oracle verifier accepted a deliberate algorithm mutation")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
