import unittest
from map_bytes import sdk_paths


class MapBytesTests(unittest.TestCase):
    def test_opaque_non_utf8_symbols_do_not_change_sdk_records(self):
        raw=b'# Symbols\n0x1000 0x10 [1] opaque\x93symbol\n[ 114] /sdk/usr/lib/libSystem.tbd\n'
        self.assertEqual(sdk_paths(raw), ['/sdk/usr/lib/libSystem.tbd'])

    def test_invalid_consumed_path_is_rejected_not_replaced(self):
        with self.assertRaises(UnicodeDecodeError):
            sdk_paths(b'[ 114] /sdk/invalid\xff.tbd\n')

    def test_no_interface_records_rejected(self):
        with self.assertRaises(ValueError):
            sdk_paths(b'opaque\x93symbol\n')


if __name__=='__main__':unittest.main()
