"""Offline fixtures; no compiler, native execution, or local build tree required."""
import json
import unittest

from native_symbols import live_symbols, unique_symbol


MAP = (b"# Object files:\n[ 0] linker synthesized\n[ 7] /native/core.o\n"
       b"[ 19] /native/fixture.o\n# Sections:\n# Symbols:\n"
       b"# Address Size File Name\n"
       b"0x1000 0x10 [ 7] _parse\n"
       b"0x1010 0x04 [ 19] _opaque_\x93\xff with spaces\n"
       b"# Dead Stripped Symbols:\n# Address Size File Name\n"
       b"<<dead>> 0x04 [ 19] _not_live\n")


class NativeSymbolTests(unittest.TestCase):
    def test_noncontiguous_object_ids_and_opaque_names(self):
        symbols = live_symbols(MAP)
        self.assertEqual(len(symbols), 2)
        self.assertEqual(unique_symbol(symbols, b"_parse").object_path, b"/native/core.o")
        opaque = unique_symbol(symbols, b"_opaque_\x93\xff with spaces")
        self.assertEqual((opaque.object_index, opaque.address, opaque.size), (19, 0x1010, 4))
        manifest = json.loads(json.dumps(opaque.manifest()))
        self.assertEqual(bytes.fromhex(manifest["name_hex"]), opaque.name)
        with self.assertRaises(UnicodeDecodeError):
            MAP.decode("utf8")

    def test_dead_symbols_and_substrings_cannot_select(self):
        for name in (b"_not_live", b"_par", b"parse"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                unique_symbol(live_symbols(MAP), name)

    def test_ambiguous_exact_symbol_rejected(self):
        duplicate = MAP.replace(b"# Dead Stripped Symbols:", b"0x2000 0x10 [ 19] _parse\n# Dead Stripped Symbols:")
        with self.assertRaises(ValueError):
            unique_symbol(live_symbols(duplicate), b"_parse")

    def test_unknown_owner_rejected(self):
        with self.assertRaises(ValueError):
            live_symbols(MAP.replace(b"[ 7] _parse", b"[ 8] _parse"))

    def test_bad_live_rows_rejected(self):
        for row in (b"broken", b"0x1000 0x10 [ 7]", b"0xGG 0x10 [ 7] _parse"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                live_symbols(MAP.replace(b"0x1000 0x10 [ 7] _parse", row))

    def test_unknown_section_cannot_hide_live_rows(self):
        with self.assertRaises(ValueError):
            live_symbols(MAP.replace(b"0x1010", b"# Unexpected:\n0x1010"))

    def test_missing_or_duplicate_live_tables_rejected(self):
        for data in (MAP.replace(b"# Symbols:", b"# Missing:"), MAP + b"# Symbols:\n"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                live_symbols(data)

    def test_bad_object_table_rejected(self):
        with self.assertRaises(ValueError):
            live_symbols(MAP.replace(b"[ 19] /native/fixture.o", b"[ 7] /native/fixture.o"))

    def test_text_and_empty_selectors_rejected(self):
        with self.assertRaises(TypeError):
            live_symbols("not byte data")
        for name in ("_parse", b"", None):
            with self.subTest(name=name), self.assertRaises(TypeError):
                unique_symbol(live_symbols(MAP), name)

    def test_live_table_must_follow_objects(self):
        with self.assertRaises(ValueError):
            live_symbols(b"# Symbols:\n" + MAP.replace(b"# Symbols:\n", b""))


if __name__ == "__main__":
    unittest.main()
