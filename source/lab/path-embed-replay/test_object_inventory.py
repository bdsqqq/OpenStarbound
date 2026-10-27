"""In-memory semantic controls; no acquisition, subprocesses or cleanup."""
import unittest
from object_inventory import reconcile


def linkmap(entries):
    return (b'# Object files:\n' + b''.join(
        b'[%d] %s\n' % (i, path) for i, path in enumerate(entries))
        + b'# Symbols:\n\xff invalid symbol bytes are outside this table\n')


class ObjectInventoryTests(unittest.TestCase):
    objects = [b'/owned/driver.o', b'/owned/current.o']
    tables = {b'/declared/lib.a': b'__.SYMDEF SORTED\nmember.o\n'}

    def entries(self):
        return [b'linker synthesized', *self.objects,
                b'/declared/lib.a(member.o)', b'/SDK/usr/lib/libSystem.tbd']

    def test_exact_positive_retains_sdk_as_unresolved(self):
        result = reconcile(linkmap(self.entries()), self.objects, self.tables)
        self.assertEqual(result['objects'], self.objects)
        self.assertEqual(result['used_archive_members'], [(b'/declared/lib.a', b'member.o')])
        self.assertEqual(result['unresolved_origins'], [b'/SDK/usr/lib/libSystem.tbd'])

    def test_object_omission_reorder_extra_and_duplicate_rejected(self):
        mutations = [self.objects[:1], self.objects[::-1],
                     self.objects + [b'/foreign.o'], self.objects + self.objects[:1]]
        for objects in mutations:
            with self.subTest(objects=objects), self.assertRaisesRegex(ValueError, 'membership'):
                reconcile(linkmap([b'linker synthesized', *objects]), self.objects, self.tables)

    def test_foreign_missing_and_ambiguous_archive_members_rejected(self):
        for origin, tables in [(b'/foreign/lib.a(member.o)', self.tables),
                               (b'/declared/lib.a(missing.o)', self.tables),
                               (b'/declared/lib.a(member.o)', {b'/declared/lib.a': b'member.o\nmember.o\n'})]:
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                reconcile(linkmap([b'linker synthesized', *self.objects, origin]), self.objects, tables)

    def test_similarly_named_archive_not_credited(self):
        entries = [b'linker synthesized', *self.objects, b'/other/declared/lib.a(member.o)']
        with self.assertRaisesRegex(ValueError, 'undeclared archive'):
            reconcile(linkmap(entries), self.objects, self.tables)

    def test_duplicate_table_index_and_synthesized_origin_rejected(self):
        bad = linkmap(self.entries()).replace(b'[1]', b'[0]')
        with self.assertRaises(ValueError):
            reconcile(bad, self.objects, self.tables)
        with self.assertRaises(ValueError):
            reconcile(linkmap(self.entries() + [b'linker synthesized']), self.objects, self.tables)

    def test_unknown_origin_is_never_silently_accepted(self):
        entries = [b'linker synthesized', *self.objects, b'not-a-known-origin']
        self.assertEqual(reconcile(linkmap(entries), self.objects, {})['unresolved_origins'],
                         [b'not-a-known-origin'])


if __name__ == '__main__':
    unittest.main()
