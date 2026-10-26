"""Isolated artifact tables only; no native execution or module qualification."""
import unittest
from native_artifacts import link_map_objects, has_archive_member, check_archive_members

MAP = (b'# Path: fixture\n# Arch: arm64\n# Object files:\n'
       b'[  0] linker synthesized\n[  1] /fixture/native-core.a(StarIODevice.cpp.o)\n'
       b'[  2] /fixture/\xff/source.o\n# Sections:\n# Symbols:\n\xff\xfe invalid UTF-8 symbol bytes\n')


class NativeArtifactTests(unittest.TestCase):
    def test_object_table_ignores_non_utf8_symbols_and_preserves_path_bytes(self):
        with self.assertRaises(UnicodeDecodeError):MAP.decode('utf-8')
        self.assertEqual(link_map_objects(MAP)[2], b'/fixture/\xff/source.o')
        self.assertTrue(has_archive_member(MAP,b'native-core.a',b'StarIODevice.cpp.o'))

    def test_matching_is_not_a_loose_substring(self):
        self.assertFalse(has_archive_member(MAP,b'core.a',b'StarIODevice.cpp.o'))
        self.assertFalse(has_archive_member(MAP,b'native-core.a',b'IODevice.cpp.o'))
        self.assertFalse(has_archive_member(MAP,b'native-core.a',b'StarBuffer.cpp.o'))
        near=MAP.replace(b'/native-core.a(',b'/other-native-core.a(')
        self.assertFalse(has_archive_member(near,b'native-core.a',b'StarIODevice.cpp.o'))

    def test_malformed_tables_fail_closed(self):
        for data in (b'',MAP.replace(b'# Object files:',b'# No objects:'),
                     MAP.replace(b'[  2]',b'[  1]'),MAP.replace(b'[  2]',b'[ -2]'),
                     b'# Object files:\n[0] foo.o\n',b'# Object files:\n# Sections:\n',
                     MAP+b'# Object files:\n'):
            with self.subTest(data=data),self.assertRaises(ValueError):link_map_objects(data)

    def test_symbol_index_is_not_an_object(self):
        expected=[b'one.o',b'two.o']
        for index in (b'',b'__.SYMDEF\n',b'__.SYMDEF SORTED\n',b'__.SYMDEF_64\n'):
            check_archive_members(index+b'one.o\ntwo.o\n',expected)

    def test_missing_extra_reordered_and_wrong_count_reject(self):
        for data in (b'one.o\n',b'two.o\none.o\n',b'one.o\ntwo.o\nextra.o\n',
                     b'__.SYMDEF\none.o\none.o\n'):
            with self.subTest(data=data),self.assertRaises(ValueError):
                check_archive_members(data,[b'one.o',b'two.o'])
        with self.assertRaises(ValueError):check_archive_members(b'one.o\n',[])

    def test_basename_contract(self):
        for archive,member in ((b'/native-core.a',b'foo.o'),(b'native-core.a',b''),('native-core.a',b'foo.o')):
            with self.subTest(archive=archive,member=member),self.assertRaises(ValueError):
                has_archive_member(MAP,archive,member)


if __name__=='__main__':unittest.main()
