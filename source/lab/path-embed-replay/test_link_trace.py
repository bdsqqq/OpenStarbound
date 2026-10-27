import unittest
from link_trace import parse


class LinkTraceTests(unittest.TestCase):
    objects = [b'/owned/a.o', b'/owned/b.o']
    tables = {b'/declared/lib.a': b'member.o\nduplicate.o\nduplicate.o\n'}

    def trace(self):
        return (b'/owned/b.o\n/declared/lib.a(member.o)\n/owned/a.o\n'
                b'/SDK/usr/lib/libSystem.tbd\n'
                b"indirect library '/usr/lib/libSystem.B.dylib' from file '/SDK/usr/lib/libSystem.tbd'\n")

    def test_concurrent_order_and_indirect_source_retained(self):
        result = parse(self.trace(), self.objects, self.tables)
        self.assertEqual(result['objects'], self.objects[::-1])
        self.assertEqual(result['sdk_paths'], [b'/SDK/usr/lib/libSystem.tbd'])
        self.assertEqual(result['indirect_declarations'][0]['source'], b'/SDK/usr/lib/libSystem.tbd')

    def test_missing_extra_duplicate_objects_rejected(self):
        for data in [self.trace().replace(b'/owned/a.o\n', b''),
                     self.trace() + b'/extra.o\n', self.trace() + b'/owned/a.o\n']:
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, 'membership'):
                parse(data, self.objects, self.tables)

    def test_foreign_archive_missing_member_and_overcount_rejected(self):
        for data in [self.trace().replace(b'/declared/lib.a', b'/foreign/lib.a'),
                     self.trace().replace(b'(member.o)', b'(missing.o)'),
                     self.trace() + b'/declared/lib.a(member.o)\n']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse(data, self.objects, self.tables)

    def test_full_duplicate_multiplicity_retained_not_physical_identity(self):
        data = self.trace() + b'/declared/lib.a(duplicate.o)\n' * 2
        result = parse(data, self.objects, self.tables)
        self.assertEqual(result['archive_members'].count((b'/declared/lib.a', b'duplicate.o')), 2)
        with self.assertRaisesRegex(ValueError, 'overcounted'):
            parse(data + b'/declared/lib.a(duplicate.o)\n', self.objects, self.tables)

    def test_unknown_records_and_nonabsolute_sources_rejected(self):
        for extra in [b'ignored warning\n', b'/unknown.dylib\n', b'\n',
                      b"indirect library '/x' from file 'relative.tbd'\n"]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse(self.trace() + extra, self.objects, self.tables)


if __name__ == '__main__':
    unittest.main()
