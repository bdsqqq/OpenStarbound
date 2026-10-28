"""Allocation observations only; no native build or historical cause attribution."""
import ast
from pathlib import Path
import os
import stat
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import allocation as a


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.build = self.root / 'build'; self.build.mkdir()
        self.active = self.build / 'active'; self.active.mkdir()
        self.archive = self.build / 'migration-evidence-archive'; self.archive.mkdir()

    def file(self, path):
        path.write_bytes(b'x' * 8192)
        return path

    def observation(self, **changes):
        data = dict(archiveBytes=0, activeRootBytes=0, outsideBytes=0, complete=True)
        data.update(changes)
        return data

    def test_three_direct_categories_and_fixed_caps(self):
        paths = [self.file(d / 'data') for d in (self.build, self.active, self.archive)]
        result = a.enforce(self.root, self.active)
        for key in ('archiveBytes', 'activeRootBytes', 'outsideBytes'):
            self.assertGreater(result[key], 0)
        self.assertEqual(result['liveBytes'], result['outsideBytes'] + result['activeRootBytes'])
        self.assertEqual(result['reservedLiveBytes'], result['outsideBytes'] + 1536 * 1024**2)
        self.assertLessEqual(result['startedUTC'], result['finishedUTC'])
        self.assertEqual(a.CAPS, dict(liveBytes=4 * 1024**3, archiveBytes=16 * 1024**3, newRootBytes=1536 * 1024**2))

    def test_same_category_hardlinks_count_once(self):
        source = self.file(self.active / 'one')
        before = a.measure(self.root, self.active)
        os.link(source, self.active / 'two')
        after = a.measure(self.root, self.active)
        self.assertEqual(after['activeRootBytes'], before['activeRootBytes'])
        self.assertEqual(after['observedEntries'], before['observedEntries'] + 1)
        self.assertEqual(after['uniqueInodes'], before['uniqueInodes'])

    def test_cross_category_hardlinks_rejected(self):
        source = self.file(self.active / 'one')
        os.link(source, self.archive / 'alias')
        with self.assertRaisesRegex(a.AllocationError, 'crosses') as caught:
            a.measure(self.root, self.active)
        self.assertFalse(caught.exception.observation['complete'])
        self.assertEqual(len(caught.exception.observation['paths']), 2)

    def test_symlink_targets_not_followed_or_double_charged(self):
        external = self.root / 'external'; external.mkdir()
        self.file(external / 'not-a-build-entry')
        (self.active / 'link').symlink_to(external, target_is_directory=True)
        result = a.measure(self.root, self.active)
        self.assertEqual(result['symbolicLinks'], 1)
        self.assertEqual(result['observedEntries'], 4)

    def test_root_aliases_and_overlapping_categories_rejected(self):
        alias = self.build / 'alias'; alias.symlink_to(self.active, target_is_directory=True)
        for target in (alias, self.build, self.archive, self.archive / 'child', self.root / 'outside'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                a.measure(self.root, target)

    def test_archive_root_alias_rejected(self):
        self.archive.rmdir()
        self.archive.symlink_to(self.active, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'physical'):
            a.measure(self.root, self.active)

    def test_absent_future_active_root(self):
        result = a.enforce(self.root, self.build / 'future')
        self.assertEqual(result['activeRootBytes'], 0)

    def test_fifo_metadata_is_charged_without_opening_or_reading(self):
        os.mkfifo(self.active / 'fifo')
        with patch('builtins.open', side_effect=AssertionError('must never read IPC')):
            result = a.enforce(self.root, self.active)
        self.assertEqual(result['namedPipes'], 1)

    def test_unsupported_socket_fails_closed_with_interval_and_totals(self):
        sock = socket.socket(socket.AF_UNIX)
        self.addCleanup(sock.close)
        sock.bind(str(self.active / 'socket'))
        with self.assertRaisesRegex(a.AllocationError, 'unsupported') as caught:
            a.measure(self.root, self.active)
        detail = caught.exception.observation
        self.assertIn('startedUTC', detail); self.assertIn('finishedUTC', detail)
        self.assertFalse(detail['complete'])

    def test_traversal_failure_is_not_a_partial_success(self):
        with patch.object(a, '_entries', side_effect=FileNotFoundError('synthetic concurrent removal')):
            with self.assertRaises(a.AllocationError) as caught:
                a.measure(self.root, self.active)
        self.assertFalse(caught.exception.observation['complete'])

    def test_boundary_and_actual_outside_growth(self):
        outside = a.CAPS['liveBytes'] - a.CAPS['newRootBytes']
        a.check(self.observation(outsideBytes=outside, activeRootBytes=a.CAPS['newRootBytes']))
        with self.assertRaisesRegex(a.AllocationError, 'reservation') as caught:
            a.check(self.observation(outsideBytes=outside + 1))
        self.assertEqual(caught.exception.observation['outsideBytes'], outside + 1)

    def test_all_caps_stay_strict(self):
        for change, message in ((dict(archiveBytes=a.CAPS['archiveBytes'] + 1), '16 GiB'),
                                (dict(activeRootBytes=a.CAPS['newRootBytes'] + 1), '1536 MiB'),
                                (dict(outsideBytes=a.CAPS['liveBytes'], activeRootBytes=1), '4 GiB')):
            with self.subTest(change=change), self.assertRaisesRegex(a.AllocationError, message):
                a.check(self.observation(**change))
        for change in (dict(complete=False), dict(outsideBytes=-1), dict(archiveBytes=True)):
            with self.assertRaises(a.AllocationError):
                a.check(self.observation(**change))

    def test_known_old_subtractive_race_and_new_disjoint_invariant(self):
        # Execute the actual old function with synthetic observations. This is a
        # demonstrated susceptibility, NOT evidence of the historical incident.
        path = Path(__file__).with_name('game_build_admission.py')
        tree = ast.parse(path.read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'check_budget')
        outside = a.CAPS['liveBytes'] - a.CAPS['newRootBytes'] - 1024**2
        active_before, active_after = 2 * 1024**2, 0
        calls = iter((0, outside + active_before, active_after))
        def need(ok, why):
            if not ok: raise ValueError(why)
        scope = dict(ROOT=self.root, CAPS=a.CAPS, allocated=lambda p: next(calls), need=need)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), scope)
        with self.assertRaisesRegex(ValueError, 'reservation'):
            scope['check_budget'](self.active)
        # Direct category attribution does not subtract the changed active root.
        a.check(self.observation(outsideBytes=outside, activeRootBytes=active_after))
        with self.assertRaisesRegex(a.AllocationError, 'reservation'):
            a.check(self.observation(outsideBytes=outside + 2 * 1024**2, activeRootBytes=active_after))

    def test_single_walk_lstats_once_per_entry(self):
        self.file(self.active / 'one')
        entries = list(a._entries(self.build))
        self.assertEqual(len({p for p, _ in entries}), len(entries))
        synthetic = SimpleNamespace(st_mode=stat.S_IFREG, st_blocks=-1, st_dev=1, st_ino=1)
        with self.assertRaises(a.AllocationError):
            a._partition([(self.active / 'bad', synthetic)], self.active, self.archive)


if __name__ == '__main__':
    unittest.main()
