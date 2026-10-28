"""Independent, finite source-contract oracle; no native/Rust/output-file inputs.

The transcript literals follow StarIdMap.hpp, StarMap.hpp, and DataStream's
big-endian uint32 plus VLQ-size contracts. They are not learned observations.
ReferenceMap is deliberately limited to the defined uint32 cases in this gate;
it does not repair or model every C++ integral instantiation.
"""

from __future__ import annotations

import sys


class IdFailure(Exception):
    """Model identity for the native IdMapException (not MapException)."""


class ReferenceMap:
    def __init__(self, minimum: int = 0, maximum: int = 0xFFFFFFFF):
        if not 0 <= minimum < maximum <= 0xFFFFFFFF:
            raise ValueError("finite defined uint32 range required")
        self.minimum = minimum
        self.maximum = maximum
        self.cursor = minimum
        self.contents: dict[int, int] = {}

    def _increment(self, value: int) -> int:
        return self.minimum if value < self.minimum or value >= self.maximum else value + 1

    def next_id(self) -> int:
        # These finite model cases never truncate len(contents) to uint32.
        if len(self.contents) > self.maximum - self.minimum:
            raise IdFailure("No id space left in IdMapWrapper")
        result = self.cursor
        while result in self.contents:
            result = self._increment(result)
        self.cursor = self._increment(result)
        return result

    def explicit_add(self, key: int, value: int) -> None:
        if key in self.contents:
            raise IdFailure(f"IdMapWrapper::add(id, value) called with pre-existing id '{key}'")
        self.contents[key] = value

    def auto_add(self, value: int) -> int:
        key = self.next_id()
        self.contents[key] = value
        return key

    def clear(self) -> None:
        self.contents.clear()
        self.cursor = self.minimum

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ReferenceMap):
            return NotImplemented
        return (self.minimum, self.maximum, self.contents) == (
            other.minimum, other.maximum, other.contents
        )


# Single-entry bytes: count=1, key=11, value=77, min=10, max=12, cursor=10.
# Keeping one entry avoids imposing an order on the hash container.
ONE_ENTRY_HEX = "010000000b0000004d0000000a0000000c0000000a"

# Literal expectations are intentionally separate from ReferenceMap execution.
# A broken simulator cannot silently update these goldens.
CASE_ROWS = (
    ("default-unsigned", "0,1"),
    ("uint32-high-wrap", "4294967293,4294967294,4294967295,4294967293"),
    ("explicit-outside-range", "5"),
    ("next-unreserved-inclusive", "10,11,12,10,11"),
    ("explicit-no-cursor-advance", "10"),
    ("collision-skip", "12"),
    ("auto-first", "10"),
    ("auto-second", "11"),
    ("fill-last-slot", "12"),
    ("exhaustion", "(IdMapException) No id space left in IdMapWrapper"),
    ("duplicate", "(IdMapException) IdMapWrapper::add(id, value) called with pre-existing id '11'"),
    ("duplicate-preserves-value", "200"),
    ("hole-reused", "11"),
    ("clear-resets", "10,1"),
    ("equality", "cursor-excluded,range-and-contents-included"),
    ("inherited-16", "keys,values,pairs,contains,size,empty,get,ptr,maybe,take,maybeTake,remove,value,begin,end,erase"),
    ("stream-one-entry", ONE_ENTRY_HEX),
    ("stream-roundtrip-cursor", "10,12"),
    # readMapContainer clears before reading count; incomplete pairs never insert.
    ("partial-count", "00000000280000002c00000029"),
    ("partial-entry", "00000000280000002c00000029"),
    # A complete entry survives; only successfully read scalar fields change.
    ("partial-min", "010000000b0000004d000000280000002c00000029"),
    ("partial-max", "010000000b0000004d0000000a0000002c00000029"),
)
PROPERTY_SUFFIXES = (
    "stream-order-and-partial-mutation",
    "auto-add-copy",
    "explicit-add-move",
    "throw-identity-and-advanced-cursor",
    "lifetime-conservation",
    "lazy-no-default-and-native-base-constraints" ,
)
BACKENDS = ("ordered", "hash")
case_names = tuple(f"{backend}/{name}" for backend in BACKENDS for name, _ in CASE_ROWS)
property_names = tuple(f"{backend}/{name}" for backend in BACKENDS for name in PROPERTY_SUFFIXES)


def expected() -> str:
    lines = []
    for backend in BACKENDS:
        lines.extend(f"CASE\t{backend}/{name}\t{value}\n" for name, value in CASE_ROWS)
        lines.extend(f"PASS\t{backend}/{name}\n" for name in PROPERTY_SUFFIXES)
    return "".join(lines)


def verify(actual: str) -> None:
    """Require byte-for-byte transcript identity, including row order/newline."""
    if actual != expected():
        raise ValueError("IdMap native transcript differs from independent literal contract")


if __name__ == "__main__":
    sys.stdout.write(expected())
