"""Consume only SDK path records; Mach-O linker-map symbols are arbitrary bytes."""
import re


def sdk_paths(raw):
    # Decoding the entire map would reinterpret unrelated native symbol bytes.
    # SDK interface paths are the only consumed records and must be strict UTF-8.
    records = re.findall(rb'^\[\s*\d+\] (.*\.tbd)$', raw, re.M)
    if not records:
        raise ValueError('no linked SDK interface records')
    return [record.decode('utf-8', errors='strict') for record in records]
