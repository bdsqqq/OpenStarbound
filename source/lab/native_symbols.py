"""Read declared live-symbol providers; this does not attest surviving machine code."""
from dataclasses import dataclass
import re

from native_artifacts import link_map_objects


@dataclass(frozen=True)
class LiveSymbol:
    address: int
    size: int
    object_index: int
    object_path: bytes
    name: bytes

    def manifest(self):
        """Hex fields preserve arbitrary names in JSON without lossy decoding."""
        return {"address": self.address, "size": self.size,
                "object_index": self.object_index,
                "object_path_hex": self.object_path.hex(), "name_hex": self.name.hex()}


def live_symbols(data: bytes) -> tuple[LiveSymbol, ...]:
    """Parse only the live table, keeping explicit object IDs rather than list offsets."""
    link_map_objects(data)  # Shared byte-only object-table validation.
    lines = data.splitlines()
    if lines.count(b"# Symbols:") != 1:
        raise ValueError("one live symbol table required")
    objects_start = lines.index(b"# Object files:") + 1
    symbols_start = lines.index(b"# Symbols:") + 1
    if symbols_start <= objects_start:
        raise ValueError("object table must precede live symbols")
    objects = {}
    for line in lines[objects_start:]:
        if line.startswith(b"#"):
            break
        if line.strip():
            match = re.fullmatch(rb"\[\s*([0-9]+)\]\s+(.+)", line)
            # link_map_objects already rejects malformed rows and duplicate IDs.
            if match is None:
                raise ValueError("malformed object entry")
            objects[int(match[1])] = match[2]
    result = []
    for line in lines[symbols_start:]:
        if line.startswith(b"# Address") or not line.strip():
            continue
        if line == b"# Dead Stripped Symbols:":
            break  # Dead-stripped symbols are NOT live providers.
        if line.startswith(b"#"):
            raise ValueError("unexpected section inside live symbol table")
        match = re.fullmatch(rb"0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)\s+\[\s*([0-9]+)\]\s+(.+)", line)
        if match is None:
            raise ValueError("malformed live symbol row")
        address, size, owner = (int(match[1], 16), int(match[2], 16), int(match[3]))
        if owner not in objects:
            raise ValueError("live symbol references undeclared object")
        result.append(LiveSymbol(address, size, owner, objects[owner], match[4]))
    return tuple(result)


def unique_symbol(symbols: tuple[LiveSymbol, ...], name: bytes) -> LiveSymbol:
    """Exact names only: a substring match can silently select a different overload."""
    if type(name) is not bytes or not name:
        raise TypeError("nonempty byte symbol name required")
    if any(type(symbol) is not LiveSymbol for symbol in symbols):
        raise TypeError("parsed live symbols required")
    matches = [symbol for symbol in symbols if symbol.name == name]
    if len(matches) != 1:
        raise ValueError("one exact live symbol required")
    return matches[0]
