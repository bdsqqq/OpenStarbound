"""Pure Python fixtures under G; no subprocess/compiler/game qualification."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_bounded_outputs_test', HERE / 'bounded_outputs.py')
bounded = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bounded)
G = HERE.parents[2] / 'build/behavior/static-vector-combined-r1'


def identity(p):
    raw = p.read_bytes()
    return dict(path=str(p), sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))


def legacy(value, **kwargs):
    stream = io.StringIO()
    json.dump(value, stream, sort_keys=True, ensure_ascii=True, allow_nan=False, **kwargs)
    return stream.getvalue().encode('utf-8')


class BoundedOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bounded-output-test-', dir=G)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve(strict=True)
        self.p = self.root / 'out.json'
        self.partial = self.root / '.out.json.partial'

    def assert_bounded(self, limit):
        self.assertLessEqual(self.partial.stat().st_size, limit)

    def test_exact_legacy_unicode_and_default_newline(self):
        value = {'z': ['é', '\U0001f642', '\udcff', 5, None], 'a': {'b': True}}
        expected = legacy(value, indent=2) + b'\n'
        got = bounded.write_json(self.p, value, len(expected))
        self.assertEqual(self.p.read_bytes(), expected)
        self.assertEqual(got, identity(self.p))
        self.assertFalse(self.partial.exists())
        self.assertEqual(self.p.stat().st_nlink, 1)

    def test_custom_formats_and_newline(self):
        for index, (indent, separators, newline) in enumerate([
            (None, (',', ':'), False), (0, None, True), ('\t', (',', ': '), False),
            (4, (', ', ': '), True), (None, None, True),
            ('é', (',', ': '), True), (None, (',', ':é'), False)]):
            with self.subTest(indent=indent, separators=separators, newline=newline):
                p = self.root / str(index)
                value = {'b': [1, 2], 'a': 'ñ'}
                expected = legacy(value, indent=indent, separators=separators) + (b'\n' if newline else b'')
                self.assertEqual(bounded.write_json(p, value, len(expected), indent=indent,
                                 separators=separators, newline=newline), identity(p))
                self.assertEqual(p.read_bytes(), expected)

    def test_invalid_limits_before_any_write(self):
        for limit in [True, False, 0, -1, 1.0, float('inf'), '10', None]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                bounded.write_json(self.p, {}, limit)
            self.assertFalse(self.partial.exists())
            self.assertFalse(self.p.exists())
        with self.assertRaises(ValueError):
            bounded.write_json(self.p, {}, 100, newline=1)
        self.assertFalse(self.partial.exists())

    def test_one_giant_chunk_checked_before_write(self):
        with patch.object(bounded.os, 'write', wraps=os.write) as write:
            with self.assertRaisesRegex(ValueError, 'byte limit'):
                bounded.write_json(self.p, 'a' * 200000, 16)
            write.assert_not_called()
        self.assertEqual(self.partial.read_bytes(), b'')
        self.assertFalse(self.p.exists())
        with self.assertRaises(FileExistsError):
            bounded.write_json(self.p, 1, 16)
        self.assertEqual(list(self.root.iterdir()), [self.partial])

    def test_many_chunks_overflow_preserves_old_and_bounded_partial(self):
        self.p.write_bytes(b'original')
        pin = identity(self.p)
        with self.assertRaisesRegex(ValueError, 'byte limit'):
            bounded.write_json(self.p, list(range(1000)), 128, replace_expected=pin)
        self.assert_bounded(128)
        self.assertGreater(self.partial.stat().st_size, 0)
        self.assertEqual(identity(self.p), pin)
        self.assertLessEqual(sum(p.stat().st_size for p in self.root.iterdir()), pin['size'] + 128)
        with self.assertRaises(FileExistsError):
            bounded.write_json(self.p, 0, 128, replace_expected=pin)

    def test_newline_is_inside_cap(self):
        with self.assertRaisesRegex(ValueError, 'byte limit'):
            bounded.write_json(self.p, 123, 3)
        self.assertEqual(self.partial.read_bytes(), b'123')
        self.assertFalse(self.p.exists())

    def test_invalid_nan_preserves_partial(self):
        with self.assertRaises(ValueError):
            bounded.write_json(self.p, [0, float('nan')], 100)
        self.assertTrue(self.partial.exists())
        self.assert_bounded(100)
        self.assertFalse(self.p.exists())

    def test_encoder_iteration_failure_retains_prefix(self):
        def chunks(_):
            yield '12'
            raise RuntimeError('injected iterator')
        with patch.object(bounded.json.JSONEncoder, 'iterencode', side_effect=chunks):
            with self.assertRaisesRegex(RuntimeError, 'iterator'):
                bounded.write_json(self.p, {}, 100)
        self.assertEqual(self.partial.read_bytes(), b'12')
        self.assertFalse(self.p.exists())

    def test_unicode_format_bytes_checked_before_chunk_write(self):
        with self.assertRaisesRegex(ValueError, 'byte limit'):
            bounded.write_json(self.p, {'a': 1}, 8, indent='é' * 4)
        self.assert_bounded(8)
        self.assertFalse(self.p.exists())

    def test_circular_reference_failure(self):
        value = []
        value.append(value)
        with self.assertRaisesRegex(ValueError, 'Circular'):
            bounded.write_json(self.p, value, 100)
        self.assert_bounded(100)
        self.assertFalse(self.p.exists())

    def test_non_json_type_failure(self):
        with self.assertRaises(TypeError):
            bounded.write_json(self.p, {'unsupported': object()}, 100)
        self.assert_bounded(100)
        self.assertFalse(self.p.exists())

    def test_short_writes_account_actual_bytes_and_piece_bound(self):
        real_write = os.write
        counts = []
        def short(fd, data):
            self.assertLessEqual(len(data), 64 * 1024)
            count = real_write(fd, data[:1003])
            counts.append(count)
            return count
        value = 'b' * 150000
        expected = legacy(value, indent=2) + b'\n'
        with patch.object(bounded.os, 'write', side_effect=short):
            got = bounded.write_json(self.p, value, len(expected))
        self.assertEqual(sum(counts), len(expected))
        self.assertGreater(len(counts), 100)
        self.assertEqual(got, identity(self.p))
        self.assertEqual(self.p.read_bytes(), expected)

    def test_write_error_retains_actual_prefix_and_blocks_retry(self):
        real_write = os.write
        calls = 0
        def broken(fd, data):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(fd, data[:3])
            raise OSError('injected write')
        with patch.object(bounded.os, 'write', side_effect=broken):
            with self.assertRaisesRegex(OSError, 'write'):
                bounded.write_json(self.p, 'a' * 100, 200)
        self.assertEqual(self.partial.read_bytes(), b'"aa')
        self.assertFalse(self.p.exists())
        with self.assertRaises(FileExistsError):
            bounded.write_json(self.p, 0, 200)

    def test_zero_progress_is_failure(self):
        with patch.object(bounded.os, 'write', return_value=0):
            with self.assertRaisesRegex(OSError, 'progress'):
                bounded.write_json(self.p, 123, 100)
        self.assertEqual(self.partial.read_bytes(), b'')
        self.assertFalse(self.p.exists())

    def test_existing_destination_rejected_before_partial(self):
        self.p.write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            bounded.write_json(self.p, {}, 100)
        self.assertEqual(self.p.read_bytes(), b'foreign')
        self.assertFalse(self.partial.exists())

    def test_destination_directory_and_dangling_symlink_rejected(self):
        for name in ('directory', 'dangling'):
            p = self.root / name
            if name == 'directory':
                p.mkdir()
            else:
                p.symlink_to(self.root / 'missing')
            before = p.lstat()
            with self.assertRaisesRegex(ValueError, 'already exists'):
                bounded.write_json(p, {}, 100)
            self.assertEqual(p.lstat(), before)
            self.assertFalse((self.root / ('.' + name + '.partial')).exists())

    def test_canonical_path_rejects_relative_traversal_and_lexical_alias(self):
        for path in ['/', 'relative.json', str(self.root) + '/../escape.json',
                     str(self.root) + '/./out.json', str(self.root) + '//out.json']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                bounded.write_json(path, {}, 100)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_symlink_parent_rejected(self):
        physical = self.root / 'physical'
        physical.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(physical, target_is_directory=True)
        with self.assertRaises(ValueError):
            bounded.write_json(alias / 'out.json', {}, 100)
        self.assertEqual(list(physical.iterdir()), [])

    def test_destination_symlink_rejected_even_with_pin(self):
        target = self.root / 'target'
        target.write_bytes(b'foreign')
        self.p.symlink_to(target)
        pin = dict(identity(target), path=str(self.p))
        with self.assertRaises(ValueError):
            bounded.write_json(self.p, {}, 100, replace_expected=pin)
        self.assertFalse(self.partial.exists())
        self.assertEqual(target.read_bytes(), b'foreign')

    def test_destination_hardlink_rejected(self):
        self.p.write_bytes(b'foreign')
        os.link(self.p, self.root / 'other')
        with self.assertRaises(ValueError):
            bounded.write_json(self.p, {}, 100, replace_expected=identity(self.p))
        self.assertFalse(self.partial.exists())
        self.assertEqual(self.p.read_bytes(), b'foreign')

    def test_existing_partial_all_kinds_rejected_without_touching(self):
        target = self.root / 'target'
        target.write_bytes(b'foreign')
        cases = ['regular', 'symlink', 'hardlink', 'directory', 'dangling']
        for kind in cases:
            with self.subTest(kind=kind):
                p = self.root / kind
                partial = self.root / ('.' + kind + '.partial')
                if kind == 'regular':
                    partial.write_bytes(b'old' * 100)
                elif kind in ('symlink', 'dangling'):
                    partial.symlink_to(target if kind == 'symlink' else self.root / 'missing')
                elif kind == 'hardlink':
                    os.link(target, partial)
                else:
                    partial.mkdir()
                before = partial.lstat()
                with self.assertRaises(FileExistsError):
                    bounded.write_json(p, {}, 10)
                self.assertEqual(partial.lstat(), before)
                self.assertFalse(p.exists())
                self.assertEqual(target.read_bytes(), b'foreign')

    def test_pin_replacement_positive(self):
        self.p.write_bytes(b'old old old')
        pin = identity(self.p)
        result = bounded.write_json(self.p, {'new': 3}, 100, replace_expected=pin)
        self.assertEqual(result, identity(self.p))
        self.assertEqual(self.p.read_bytes(), legacy({'new': 3}, indent=2) + b'\n')
        self.assertFalse(self.partial.exists())

    def test_wrong_or_malformed_pins_before_partial(self):
        self.p.write_bytes(b'old')
        pin = identity(self.p)
        for bad in [dict(pin, size=4), dict(pin, sha256='0' * 64),
                    dict(pin, path=str(self.root / 'other')), dict(pin, size=True),
                    dict(pin, extra=1), {}, False]:
            with self.subTest(pin=bad), self.assertRaises(ValueError):
                bounded.write_json(self.p, {}, 100, replace_expected=bad)
            self.assertFalse(self.partial.exists())
            self.assertEqual(self.p.read_bytes(), b'old')

    def test_missing_replacement_does_not_become_new_publish(self):
        with self.assertRaises(ValueError):
            bounded.write_json(self.p, {}, 100, replace_expected=dict(
                path=str(self.p), sha256='0' * 64, size=0))
        self.assertFalse(self.partial.exists())

    def test_changed_original_content_or_same_bytes_inode_rejected(self):
        real_iterencode = bounded.json.JSONEncoder.iterencode
        for index, change in enumerate(['content', 'inode', 'rewrite']):
            with self.subTest(change=change):
                p = self.root / str(index)
                p.write_bytes(b'old')
                pin = identity(p)
                def chunks(encoder, value):
                    yield from real_iterencode(encoder, value)
                    if change == 'inode':
                        replacement = self.root / 'replacement'
                        replacement.write_bytes(b'old')
                        os.replace(replacement, p)
                    else:
                        p.write_bytes(b'new' if change == 'content' else b'old')
                with patch.object(bounded.json.JSONEncoder, 'iterencode', chunks):
                    with self.assertRaisesRegex(ValueError, 'changed'):
                        bounded.write_json(p, {}, 100, replace_expected=pin)
                self.assertEqual(p.read_bytes(), b'new' if change == 'content' else b'old')
                self.assertLessEqual((self.root / ('.' + p.name + '.partial')).stat().st_size, 100)

    def test_concurrent_destination_appearance_preserves_foreign(self):
        real_link = os.link
        def raced(src, dst, **kwargs):
            self.p.write_bytes(b'foreign')
            return real_link(src, dst, **kwargs)
        with patch.object(bounded.os, 'link', side_effect=raced):
            with self.assertRaises(FileExistsError):
                bounded.write_json(self.p, {}, 100)
        self.assertEqual(self.p.read_bytes(), b'foreign')
        self.assertEqual(self.partial.read_bytes(), b'{}\n')

    def test_file_fsync_failure_retains_bounded_partial_and_old(self):
        self.p.write_bytes(b'old')
        pin = identity(self.p)
        with patch.object(bounded.os, 'fsync', side_effect=OSError('injected fsync')):
            with self.assertRaisesRegex(OSError, 'fsync'):
                bounded.write_json(self.p, {}, 100, replace_expected=pin)
        self.assertEqual(identity(self.p), pin)
        self.assertEqual(self.partial.read_bytes(), b'{}\n')
        with self.assertRaises(FileExistsError):
            bounded.write_json(self.p, {}, 100, replace_expected=pin)

    def test_link_failure_retains_partial(self):
        with patch.object(bounded.os, 'link', side_effect=OSError('injected link')):
            with self.assertRaisesRegex(OSError, 'link'):
                bounded.write_json(self.p, {}, 100)
        self.assertFalse(self.p.exists())
        self.assertEqual(self.partial.read_bytes(), b'{}\n')
        with self.assertRaises(FileExistsError):
            bounded.write_json(self.p, {}, 100)

    def test_directory_fsync_failure_keeps_bounded_link_coexistence(self):
        real_fsync = os.fsync
        calls = 0
        def fail_dir(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('injected directory fsync')
            return real_fsync(fd)
        with patch.object(bounded.os, 'fsync', side_effect=fail_dir):
            with self.assertRaisesRegex(OSError, 'directory fsync'):
                bounded.write_json(self.p, {}, 3)
        self.assertEqual(self.p.read_bytes(), b'{}\n')
        self.assertEqual(self.partial.read_bytes(), b'{}\n')
        self.assertEqual(self.p.stat().st_ino, self.partial.stat().st_ino)
        self.assertEqual(self.p.stat().st_nlink, 2)
        self.assertLessEqual(self.p.stat().st_size, 3)
        with self.assertRaises(ValueError):
            bounded.write_json(self.p, {}, 3)
        with self.assertRaises(ValueError):
            bounded.write_json(self.p, {}, 3, replace_expected=identity(self.p))

    def test_unlink_failure_retains_both_links_without_success(self):
        with patch.object(bounded.os, 'unlink', side_effect=OSError('injected unlink')):
            with self.assertRaisesRegex(OSError, 'unlink'):
                bounded.write_json(self.p, {}, 3)
        self.assertEqual(self.p.read_bytes(), b'{}\n')
        self.assertEqual(self.partial.read_bytes(), b'{}\n')
        self.assertEqual(self.p.stat().st_nlink, 2)
        with self.assertRaises(ValueError):
            bounded.write_json(self.p, {}, 3, replace_expected=identity(self.p))

    def test_post_unlink_directory_fsync_failure_retains_new_artifact(self):
        real_fsync = os.fsync
        calls = 0
        def fail_final(fd):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError('injected final directory fsync')
            return real_fsync(fd)
        with patch.object(bounded.os, 'fsync', side_effect=fail_final):
            with self.assertRaisesRegex(OSError, 'final directory'):
                bounded.write_json(self.p, {}, 3)
        self.assertEqual(self.p.read_bytes(), b'{}\n')
        self.assertFalse(self.partial.exists())
        with self.assertRaises(ValueError):
            bounded.write_json(self.p, {}, 3)

    def test_replace_failure_preserves_old_and_partial(self):
        self.p.write_bytes(b'old')
        pin = identity(self.p)
        with patch.object(bounded.os, 'replace', side_effect=OSError('injected replace')):
            with self.assertRaisesRegex(OSError, 'replace'):
                bounded.write_json(self.p, {}, 100, replace_expected=pin)
        self.assertEqual(identity(self.p), pin)
        self.assertEqual(self.partial.read_bytes(), b'{}\n')

    def test_post_replace_fsync_failure_is_not_success(self):
        self.p.write_bytes(b'old')
        pin = identity(self.p)
        real_fsync = os.fsync
        calls = 0
        def fail_dir(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('injected post replacement fsync')
            return real_fsync(fd)
        with patch.object(bounded.os, 'fsync', side_effect=fail_dir):
            with self.assertRaisesRegex(OSError, 'post replacement'):
                bounded.write_json(self.p, {}, 100, replace_expected=pin)
        self.assertEqual(self.p.read_bytes(), b'{}\n')
        self.assertFalse(self.partial.exists())
        with self.assertRaises(ValueError):
            bounded.write_json(self.p, {}, 100, replace_expected=pin)

    def test_final_identity_reads_actual_bytes_not_writer_assertion(self):
        real_unlink = os.unlink
        def corrupt(name, **kwargs):
            result = real_unlink(name, **kwargs)
            self.p.write_bytes(b'XXX')
            return result
        with patch.object(bounded.os, 'unlink', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'published bytes differ'):
                bounded.write_json(self.p, {}, 100)
        self.assertEqual(self.p.read_bytes(), b'XXX')

    def test_final_identity_enforces_cap(self):
        real_unlink = os.unlink
        def grow(name, **kwargs):
            result = real_unlink(name, **kwargs)
            self.p.write_bytes(b'X' * 4)
            return result
        with patch.object(bounded.os, 'unlink', side_effect=grow):
            with self.assertRaisesRegex(ValueError, 'byte limit'):
                bounded.write_json(self.p, {}, 3)

    def test_parent_drift_before_publication_fails_closed(self):
        directory = self.root / 'directory'
        directory.mkdir()
        p = directory / 'out'
        real_iterencode = bounded.json.JSONEncoder.iterencode
        moved = self.root / 'moved'
        def chunks(encoder, value):
            yield from real_iterencode(encoder, value)
            directory.rename(moved)
            directory.mkdir()
        with patch.object(bounded.json.JSONEncoder, 'iterencode', chunks):
            with self.assertRaisesRegex(ValueError, 'directory drift'):
                bounded.write_json(p, {}, 100)
        self.assertFalse(p.exists())
        self.assertEqual((moved / '.out.partial').read_bytes(), b'{}\n')

    def test_partial_path_drift_rejected(self):
        real_iterencode = bounded.json.JSONEncoder.iterencode
        def chunks(encoder, value):
            yield from real_iterencode(encoder, value)
            self.partial.rename(self.root / 'owned-moved')
            self.partial.write_bytes(b'foreign')
        with patch.object(bounded.json.JSONEncoder, 'iterencode', chunks):
            with self.assertRaisesRegex(ValueError, 'partial path drift'):
                bounded.write_json(self.p, {}, 100)
        self.assertEqual(self.partial.read_bytes(), b'foreign')
        self.assertFalse(self.p.exists())

    def test_partial_hardlink_during_encoding_fails_closed(self):
        real_iterencode = bounded.json.JSONEncoder.iterencode
        def chunks(encoder, value):
            yield from real_iterencode(encoder, value)
            os.link(self.partial, self.root / 'alias')
        with patch.object(bounded.json.JSONEncoder, 'iterencode', chunks):
            with self.assertRaisesRegex(ValueError, 'unique ordinary'):
                bounded.write_json(self.p, {}, 100)
        self.assertFalse(self.p.exists())
        self.assertEqual(self.partial.stat().st_nlink, 2)
        self.assert_bounded(100)

    def test_known_unsafe_limit_ignore_control_is_detected(self):
        # The control writes excessive bytes on purpose; only this test-owned
        # tiny fixture is affected. A verifier that trusts a claimed size loses.
        def unsafe(path, value, limit):
            path.write_bytes(legacy(value, indent=2) + b'\n')
            return dict(path=str(path), sha256='0' * 64, size=limit)
        def verify(writer):
            result = writer(self.p, 'over cap', 4)
            self.assertLessEqual(self.p.stat().st_size, 4)
            self.assertEqual(result, identity(self.p))
        with self.assertRaises(AssertionError):
            verify(unsafe)
        self.assertGreater(self.p.stat().st_size, 4)


if __name__ == '__main__':
    unittest.main()
