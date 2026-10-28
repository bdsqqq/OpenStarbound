"""Literal, source-derived native-only IdMap edge oracle.

No baseline import, native execution, Rust input, or acquired output files.
The partial-scalar literal requires the admitted little-endian C++ profile;
it is not a portable new serialization or rollback contract.
"""

import sys


BACKENDS = ("ordered", "hash")
# Record order mirrors the fixture's semantic checkpoints, not acquired output.
RECORDS = (
    ("CASE", "outer-argument-copy", "identity-preserved,cursor=10,size=1"),
    ("PASS", "outer-copy-identity-and-conservation", None),
    ("CASE", "duplicate-stream-first-wins", "size=1,value=77,next=10"),
    ("CASE", "loaded-outside-cursor", "99,10"),
    ("CASE", "partial-metadata-little-endian", "00112202015566778811223345,pos=3"),
    ("PASS", "native-partial-scalar-before-conversion", None),
    ("CASE", "printable-uint8-duplicate", "(IdMapException) IdMapWrapper::add(id, value) called with pre-existing id 'A'"),
    ("CASE", "outside-keys-exhaustion", "(IdMapException) No id space left in IdMapWrapper"),
    ("PASS", "unvalidated-load-and-explicit-keys", None),
)
case_names = tuple(
    f"{backend}/{name}" for backend in BACKENDS for kind, name, _ in RECORDS if kind == "CASE"
)
property_names = tuple(
    f"{backend}/{name}" for backend in BACKENDS for kind, name, _ in RECORDS if kind == "PASS"
)


def expected() -> str:
    lines = []
    for backend in BACKENDS:
        for kind, name, value in RECORDS:
            line = f"{kind}\t{backend}/{name}"
            if kind == "CASE":
                line += f"\t{value}"
            lines.append(line + "\n")
    return "".join(lines)


def verify(actual: str) -> None:
    """Reject every difference, including extra rows, order and newline framing."""
    if actual != expected():
        raise ValueError("IdMap edge transcript differs from frozen literal source contract")


if __name__ == "__main__":
    sys.stdout.write(expected())
