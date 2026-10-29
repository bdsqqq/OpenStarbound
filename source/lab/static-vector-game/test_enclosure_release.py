"""Hermetic source controls: no hdiutil, subprocess, native tool or acquisition."""
import copy
import importlib.util
from pathlib import Path
import plistlib
from types import SimpleNamespace
import stat
import tempfile
import unittest
from unittest.mock import patch
import hashlib

spec = importlib.util.spec_from_file_location('enclosure_release', Path(__file__).with_name('enclosure_release.py'))
er = importlib.util.module_from_spec(spec)
spec.loader.exec_module(er)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        # All real writes are tiny, private, auto-cleaned, below G.
        self.temp = tempfile.TemporaryDirectory(prefix='release-test-', dir=er.G)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'image.dmg'
        self.image.write_bytes(b'fixture image')
        self.mount = self.root / 'mount'
        self.mount.mkdir()
        self.tool = self.root / 'tool-fixture'
        self.tool.write_bytes(b'fixture tool, never executed')
        image = self.image.stat()
        self.host = self.root.stat().st_dev
        self.volume = self.host + 123
        self.mounted = True
        self.calls = []
        self.t = 1000.0
        self.owner = {
            'root': str(self.root),
            'image': {'path': str(self.image), 'st_dev': image.st_dev,
                      'st_ino': image.st_ino, 'size': image.st_size, 'maxBytes': 1024},
            'mount': {'path': str(self.mount), 'st_dev': self.volume},
            'device': '/dev/disk41', 'volumeDevice': '/dev/disk41s1',
            'tool': {'path': er.TOOL, 'sha256': hashlib.sha256(self.tool.read_bytes()).hexdigest()},
            'originalExperiment': {'result': 'FAIL', 'deadline_monotonic': 9.0}}
        self.record = {'image-path': str(self.image), 'system-entities': [
            {'dev-entry': '/dev/disk41'},
            {'dev-entry': '/dev/disk41s1', 'mount-point': str(self.mount)}]}
        self.raw = None
        self.records = [self.record]
        self.hook = lambda stage: None
        physical = er.physical
        original_stat = Path.stat

        def physical_fixture(value):
            if value == er.TOOL:
                return self.tool
            if value == '/dev/disk41s1':
                return SimpleNamespace(stat=lambda: SimpleNamespace(st_mode=stat.S_IFBLK,
                                                                    st_rdev=self.volume))
            return physical(value)

        def stat_fixture(path, *args, **kwargs):
            actual = original_stat(path, *args, **kwargs)
            if path == self.mount:
                fields = {name: getattr(actual, name) for name in dir(actual) if name.startswith('st_')}
                fields['st_dev'] = self.volume if self.mounted else self.host
                return SimpleNamespace(**fields)
            return actual

        self.addCleanup(patch.stopall)
        patch.object(er, 'physical', side_effect=physical_fixture).start()
        patch.object(Path, 'stat', stat_fixture).start()

    def runner(self, argv, *, deadline_monotonic):
        self.calls.append((list(argv), deadline_monotonic))
        self.hook('info' if argv[1] == 'info' else 'detach')
        if argv == [er.TOOL, 'info', '-plist']:
            raw = self.raw if self.raw is not None else plistlib.dumps({'images': self.records})
            return dict(returncode=0, stdout=raw, stderr=b'', reaped=True)
        self.assertEqual(argv, [er.TOOL, 'detach', '/dev/disk41'])
        self.mounted = False
        return dict(returncode=0, stdout=b'', stderr=b'', reaped=True)

    def release(self, runner=None, now=None):
        return er.release_owned_image(self.owner, runner or self.runner,
                                      now=now or (lambda: self.t))

    def rejected(self, runner=None, now=None, calls=0):
        with self.assertRaises((er.ReleaseError, OSError, TimeoutError)):
            self.release(runner, now)
        self.assertEqual(len(self.calls), calls)

    def test_expired_original_preserved_and_exact_commands_same_deadline(self):
        original = self.owner['originalExperiment']
        receipt = self.release()
        self.assertIs(receipt['originalExperiment'], original)
        self.assertEqual(original, {'result': 'FAIL', 'deadline_monotonic': 9.0})
        self.assertEqual(receipt['scope'], 'RESOURCE_RELEASE_ONLY_NOT_ADMISSION')
        self.assertEqual(self.calls, [([er.TOOL, 'info', '-plist'], 1030.0),
                                      ([er.TOOL, 'detach', '/dev/disk41'], 1030.0)])

    def test_opaque_original_type_retained(self):
        for value in (None, ['FAILED', 1], ('FAIL', 2), b'failed'):
            self.owner['originalExperiment'] = value
            self.mounted = True
            self.assertIs(self.release()['originalExperiment'], value)

    def test_original_clock_unsafe_control(self):
        def old_checker(owner, now):
            er.need(now < owner['originalExperiment']['deadline_monotonic'], 'old expired acquisition')
        with self.assertRaises(er.ReleaseError):
            old_checker(self.owner, self.t)
        self.assertEqual(self.release()['scope'], 'RESOURCE_RELEASE_ONLY_NOT_ADMISSION')

    def test_wrong_device_unsafe_control(self):
        self.owner['mount']['st_dev'] += 1
        # Deliberately unsafe mutant drops physical association, accepts wrong device.
        with patch.object(er, 'mounted_state', return_value=self.host):
            self.release()
        self.calls.clear()
        self.mounted = True
        self.rejected()

    def test_owner_schema_missing_and_unknown(self):
        for name in tuple(self.owner):
            with self.subTest(name=name):
                value = self.owner.pop(name)
                self.rejected()
                self.owner[name] = value
        self.owner['arbitraryCommand'] = 'force detach'
        self.rejected()

    def test_numeric_fields_reject_bool_float_negative(self):
        for section, fields in (('image', ('st_dev', 'st_ino', 'size', 'maxBytes')),
                                ('mount', ('st_dev',))):
            for field in fields:
                original = self.owner[section][field]
                for value in (True, 1.0, -1, '1'):
                    with self.subTest(section=section, field=field, value=value):
                        self.owner[section][field] = value
                        self.rejected()
                self.owner[section][field] = original

    def test_invalid_devices_and_tool(self):
        for key, values in (('device', ('/dev/disk4;echo', '/dev/disk4s1', '/dev/disk4')),
                            ('volumeDevice', ('/dev/disk410s1', '/dev/disk41', '/dev/disk41s1/..'))):
            original = self.owner[key]
            for value in values:
                self.owner[key] = value
                self.rejected()
            self.owner[key] = original
        self.owner['tool']['path'] = '/bin/echo'
        self.rejected()

    def test_image_identity_and_size_bound(self):
        for field in ('st_dev', 'st_ino', 'size'):
            old = self.owner['image'][field]
            self.owner['image'][field] += 1
            self.rejected()
            self.owner['image'][field] = old
        self.owner['image']['maxBytes'] = 1
        self.rejected()

    def test_hardlink(self):
        import os
        os.link(self.image, self.root / 'alias')
        self.rejected()

    def test_symlink_and_dotdot_paths(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.image)
        for value in (str(alias), str(self.root / 'mount/../image.dmg'), 'relative', str(self.image) + '/'):
            self.owner['image']['path'] = value
            self.rejected()

    def test_root_and_paths_escape(self):
        for section in ('image', 'mount'):
            previous = self.owner[section]['path']
            self.owner[section]['path'] = str(er.G)
            self.rejected()
            self.owner[section]['path'] = previous
        self.owner['root'] = str(er.G)
        self.rejected()

    def test_missing_image(self):
        self.owner['image']['path'] = str(self.root / 'absent')
        self.rejected()

    def test_tool_digest(self):
        self.tool.write_bytes(b'changed tool')
        self.rejected()

    def test_malformed_and_huge_plist(self):
        for raw in (b'', b'not plist', b'x' * (er.STDOUT_LIMIT + 1), plistlib.dumps({'images': 'wrong'})):
            self.raw = raw
            self.calls.clear()
            self.rejected(calls=1)

    def test_stale_ambiguous_and_unknown_associations(self):
        valid = copy.deepcopy(self.record)
        cases = [[], [valid, valid], [{'image-path': str(self.image), 'system-entities': []}],
                 [{'image-path': str(self.image), 'system-entities': [{'dev-entry': '/dev/disk99'}]}],
                 [dict(valid, **{'image-path': str(self.root / 'other')})],
                 [valid, dict(valid, **{'image-path': str(self.root / 'other')})],
                 [{'image-path': str(self.image), 'system-entities': ['invalid']}]]
        wrong_mount = copy.deepcopy(valid)
        wrong_mount['system-entities'][1]['mount-point'] = str(self.root)
        cases.append([wrong_mount])
        extra = copy.deepcopy(valid)
        extra['system-entities'].append({'dev-entry': '/dev/disk41s2'})
        cases.append([extra])
        for records in cases:
            self.records = records
            self.calls.clear()
            self.rejected(calls=1)

    def test_runner_payload_contract_every_operation(self):
        changes = ({'returncode': 1}, {'returncode': True}, {'returncode': 0.0},
                   {'reaped': False}, {'reaped': 1}, {'stdout': 'not bytes'},
                   {'stderr': b'x' * (er.STDERR_LIMIT + 1)}, {'extra': None})
        for operation in ('info', 'detach'):
            for change in changes:
                self.calls.clear()
                self.mounted = True
                def run(argv, *, deadline_monotonic):
                    result = self.runner(argv, deadline_monotonic=deadline_monotonic)
                    if argv[1] == operation:
                        result.update(change)
                    return result
                self.rejected(run, calls=1 if operation == 'info' else 2)

    def test_busy_and_timeout_no_force(self):
        for operation in ('info', 'detach'):
            self.calls.clear()
            def run(argv, *, deadline_monotonic):
                if argv[1] == operation:
                    self.calls.append((argv, deadline_monotonic))
                    raise TimeoutError('bounded runner reaped on timeout')
                return self.runner(argv, deadline_monotonic=deadline_monotonic)
            self.rejected(run, calls=1 if operation == 'info' else 2)
        self.calls.clear()
        def busy(argv, *, deadline_monotonic):
            if argv[1] == 'detach':
                self.calls.append((argv, deadline_monotonic))
                return dict(returncode=16, stdout=b'', stderr=b'busy', reaped=True)
            return self.runner(argv, deadline_monotonic=deadline_monotonic)
        self.rejected(busy, calls=2)
        self.assertTrue(self.mounted)

    def test_post_detach_still_mounted(self):
        def run(argv, *, deadline_monotonic):
            result = self.runner(argv, deadline_monotonic=deadline_monotonic)
            self.mounted = True
            return result
        self.rejected(run, calls=2)

    def test_image_tool_changes_at_each_operation(self):
        for operation in ('info', 'detach'):
            for target in (self.image, self.tool):
                original = target.read_bytes()
                self.calls.clear()
                self.mounted = True
                def hook(stage):
                    if stage == operation:
                        target.write_bytes(b'altered physical state')
                self.hook = hook
                self.rejected(calls=1 if operation == 'info' else 2)
                target.write_bytes(original)

    def test_expiry_every_clock_boundary(self):
        count = 0
        def count_clock():
            nonlocal count
            count += 1
            return self.t
        self.release(now=count_clock)
        for boundary in range(2, count + 1):
            self.calls.clear()
            self.mounted = True
            reads = 0
            def clock():
                nonlocal reads
                reads += 1
                return self.t if reads < boundary else self.t + 30
            with self.subTest(boundary=boundary):
                with self.assertRaises(er.ReleaseError):
                    self.release(now=clock)
                self.assertLessEqual(len(self.calls), 2)

    def test_same_bytes_replaced_inode_after_query(self):
        def hook(stage):
            if stage == 'info':
                replacement = self.root / 'replacement'
                replacement.write_bytes(self.image.read_bytes())
                replacement.replace(self.image)
        self.hook = hook
        self.rejected(calls=1)

    def test_volume_device_recheck_after_info(self):
        def hook(stage):
            if stage == 'info':
                self.volume += 1
        self.hook = hook
        self.rejected(calls=1)

    def test_host_device_mount_rejected(self):
        self.volume = self.host
        self.owner['mount']['st_dev'] = self.host
        self.rejected()

    def test_symlink_parent(self):
        link = self.root / 'linked'
        link.symlink_to(self.root, target_is_directory=True)
        self.owner['image']['path'] = str(link / 'image.dmg')
        self.rejected()

    def test_missing_runner_keys_every_operation(self):
        for operation in ('info', 'detach'):
            for key in ('returncode', 'stdout', 'stderr', 'reaped'):
                self.calls.clear()
                self.mounted = True
                def run(argv, *, deadline_monotonic):
                    result = self.runner(argv, deadline_monotonic=deadline_monotonic)
                    if argv[1] == operation:
                        result.pop(key)
                    return result
                self.rejected(run, calls=1 if operation == 'info' else 2)

    def test_duplicate_plist_keys(self):
        valid = plistlib.dumps({'images': self.records})
        self.raw = valid.replace(b'<key>images</key>', b'<key>images</key><array/><key>images</key>')
        self.rejected(calls=1)

    def test_info_noncanonical_image_alias(self):
        alias = copy.deepcopy(self.record)
        alias['image-path'] = str(self.root) + '/./image.dmg'
        alias['system-entities'] = [{'dev-entry': '/dev/disk99'}]
        self.records.append(alias)
        self.rejected(calls=1)

    def test_unrelated_image_not_selected(self):
        self.records.append({'image-path': '/unrelated/image.dmg', 'system-entities': [
            {'dev-entry': '/dev/disk99'}]})
        self.release()
        self.assertEqual(self.calls[1][0], [er.TOOL, 'detach', '/dev/disk41'])

    def test_invalid_or_regressing_clock(self):
        for value in (True, float('nan'), float('inf'), '1000'):
            self.rejected(now=lambda: value)
        values = iter((1000.0, 999.0))
        self.rejected(now=lambda: next(values))


if __name__ == '__main__':
    unittest.main()
