"""Hermetic producer controls: sparse images, fake block devices, NO processes."""
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('setup_subject', Path(__file__).with_name('enclosure_setup.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
SIZE = 16 * 1024**2
REAL_CORE = s.builder._supervise_command


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='enclosure-setup-test-', dir=s.ad.allocation_root())
        self.addCleanup(self.temp.cleanup)
        self.g = Path(self.temp.name)
        self.root = self.g / 'current30-enclosure'
        self.mount = self.root / 'products'
        self.tool = self.g / 'hdiutil'
        self.tool.write_bytes(b'fixture only, never executed')
        self.host = self.g.stat().st_dev
        self.volume = self.host + 123
        self.mounted = False
        self.t = 1000.0
        self.calls = []
        self.hook = lambda stem, kwargs: None
        self.info_hook = lambda records: None
        self.attach_hook = lambda record: None
        self.receipt_hook = lambda receipt: None
        self.image_hook = lambda image: None
        self.budget_hook = lambda: None
        self.raw_attach = None
        self.raw_info = None
        self.addCleanup(patch.stopall)
        patch.object(s.ad, 'allocation_root', return_value=self.g).start()
        patch.object(s.ad, 'enclosure_root', side_effect=lambda: self.g / 'current30-enclosure').start()
        patch.object(s.ad, 'build_root', side_effect=lambda: self.g / 'current30-enclosure/products').start()
        patch.object(s.ad, 'check_budget', side_effect=lambda: self.budget_hook()).start()
        patch.object(s.ad, 'er', s.er).start()
        patch.object(s.er, 'G', self.g).start()
        patch.object(s.er, 'TOOL', str(self.tool)).start()
        patch.object(s.time, 'monotonic', side_effect=lambda: self.t).start()
        original_release = s.er.release_owned_image
        patch.object(s.er, 'release_owned_image', side_effect=lambda owner, run:
                     original_release(owner, run, now=lambda: self.t)).start()
        self.launch = patch.object(s.builder.subprocess, 'Popen',
                                  side_effect=AssertionError('actual process forbidden')).start()
        patch.object(s.builder, '_supervise_command', side_effect=self.core).start()
        original_physical = s.er.physical
        original_stat = Path.stat

        def physical(value):
            if value == '/dev/disk41s1':
                return SimpleNamespace(stat=lambda: SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=self.volume))
            return original_physical(value)

        def physical_stat(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if path == self.mount and self.mounted:
                fields = {key: getattr(result, key) for key in dir(result) if key.startswith('st_')}
                fields['st_dev'] = self.volume
                return SimpleNamespace(**fields)
            return result

        patch.object(s.er, 'physical', side_effect=physical).start()
        patch.object(Path, 'stat', physical_stat).start()
        self.addCleanup(self.launch.assert_not_called)

    def record(self):
        return {'image-path': str(self.root / 'image.dmg'), 'system-entities': [
            {'dev-entry': '/dev/disk41'},
            {'dev-entry': '/dev/disk41s1', 'mount-point': str(self.mount)}]}

    def core(self, argv, cwd, env, output, **kwargs):
        self.calls.append(list(argv))
        stem = output.name
        self.assertEqual(cwd, s.ad.ROOT / 'source')
        self.assertEqual(set(env), {'PATH', 'HOME'})
        self.assertEqual(env['PATH'], '/usr/bin:/bin')
        self.assertEqual(kwargs['limits'], s.LIMITS)
        self.assertIn(kwargs['scope'], (s.SCOPE, s.runner.SCOPE))
        kwargs['validate']()
        self.assertGreater(kwargs['remaining_seconds'](), 0)
        kwargs['write_record'](output.with_suffix('.command.json'),
                               dict(argv=argv, scope=kwargs['scope'], witness=kwargs['witness']))
        if stem == 'create':
            self.assertEqual(argv, [str(self.tool), 'create', '-sectors', str(SIZE // 512),
                '-fs', 'HFS+', '-type', 'UDIF', '-volname', 'openstarbound-current30',
                str(self.root / 'image.dmg')])
            with (self.root / 'image.dmg').open('xb') as file:
                file.truncate(SIZE)  # sparse; no native image contents are produced
            self.image_hook(self.root / 'image.dmg')
            raw = b'created\r\n'
        elif stem == 'attach':
            self.assertEqual(argv, [str(self.tool), 'attach', '-nobrowse', '-noautoopen',
                '-owners', 'off', '-mountpoint', str(self.mount), '-plist', str(self.root / 'image.dmg')])
            self.mounted = True
            record = self.record()
            self.attach_hook(record)
            raw = self.raw_attach if self.raw_attach is not None else plistlib.dumps({'system-entities': record['system-entities']})
        elif stem in ('info', 'recovery-info'):
            self.assertEqual(argv, [str(self.tool), 'info', '-plist'])
            records = [self.record()]
            self.info_hook(records)
            raw = self.raw_info if self.raw_info is not None else plistlib.dumps({'images': records})
        elif stem == 'detach':
            self.assertEqual(argv, [str(self.tool), 'detach', '/dev/disk41'])
            self.mounted = False
            raw = b'detached'
        else:
            self.fail('unexpected command')
        streams = {}
        for name, data in (('stdout', raw), ('stderr', b'')):
            path = output.with_suffix('.' + name)
            kwargs['check_output'](path)
            with path.open('xb') as file:
                file.write(data)
            streams[name] = dict(eof=True, overflow=None, bytesWritten=len(data), bytesRead=len(data))
        receipt = dict(scope=kwargs['scope'], streams=streams, outputComplete=True,
            commandReaped=True, guardianReaped=True, reaped=True, returncode=0,
            failure=None, cleanupFailure=None)
        self.receipt_hook(receipt)
        kwargs['write_record'](output.with_suffix('.receipt.json'), receipt)
        self.hook(stem, kwargs)
        kwargs['validate']()
        return receipt

    def acquire(self, **kwargs):
        return s.acquire(SIZE, **kwargs)

    def rejected(self):
        with self.assertRaises(Exception) as caught:
            self.acquire()
        self.assertFalse((self.root / 'owner.json').exists())
        return caught.exception

    def test_positive_public_producer_consumed_by_real_admission(self):
        owner = self.acquire()
        self.assertEqual(s.ad.enclosure_state()['owner'], owner)
        self.assertTrue(self.mounted)
        self.assertEqual(owner['image']['size'], SIZE)
        self.assertEqual(owner['originalExperiment']['scope'], s.SCOPE)
        self.assertEqual(owner['originalExperiment']['type'], 'SourceSetupOnly')
        self.assertEqual(owner['originalExperiment']['status'], 'ACQUIRED')
        self.assertEqual(len(self.calls), 3)
        command = json.loads((self.root / 'attach.command.json').read_text())
        self.assertIn(str(Path(s.__file__).resolve()), command['witness']['inputs'])
        for path in self.root.glob('*.json'):
            self.assertLessEqual(path.stat().st_size, s.RECORD_BYTES)
        s.runner.release(owner)  # REAL public release and primitive, mocked owned command core
        self.assertFalse(self.mounted)
        self.assertEqual([a[1] for a in self.calls], ['create', 'attach', 'info', 'info', 'detach'])

    def test_postpublication_failure_stays_uncommitted_even_if_cleanup_and_record_fail(self):
        write = s.bounded.write_json
        def unavailable():
            raise OSError('allocation unavailable after publication')
        def publish(path, value, cap, **kwargs):
            if Path(path).name == 'setup-failure.json':
                raise OSError('failure record unavailable')
            result = write(path, value, cap, **kwargs)
            if Path(path).name == 'owner.json':
                self.budget_hook = unavailable
            return result
        with patch.object(s.bounded, 'write_json', side_effect=publish), \
             patch.object(s.runner, 'release', side_effect=OSError('release unavailable')):
            with self.assertRaisesRegex(OSError, 'allocation unavailable') as caught:
                self.acquire()
        self.assertTrue(self.mounted)
        self.assertTrue((self.root / 'owner.json').exists())
        self.assertTrue((self.root / '.setup-in-progress').exists())
        self.assertFalse((self.root / 'setup-failure.json').exists())
        self.assertEqual(caught.exception.setup_cleanup['status'], 'UNAVAILABLE')
        with self.assertRaisesRegex(ValueError, 'setup.*committed'):
            s.ad.enclosure_state()

    def test_fixture_cannot_pass_default_native_namespace(self):
        self.root = self.g / 'enclosure-setup-host-r1'
        self.mount = self.root / 'products'
        owner = self.acquire(host_fixture=True)
        self.assertEqual(owner['originalExperiment']['evidence'], 'HOST_ONLY')
        with self.assertRaises(FileNotFoundError):
            s.ad.enclosure_state()
        self.assertFalse((self.g / 'current30-enclosure').exists())

    def test_required_strict_sizes_and_boolean(self):
        with self.assertRaises(TypeError):
            s.acquire()
        for value in (True, False, 1.0, '16777216', None, 0, SIZE - 512, SIZE + 1,
                      s.ad.CAPS['newRootBytes']):
            with self.subTest(value=value), self.assertRaises(ValueError):
                s.acquire(value)
        for fixture in (1, 'yes', None):
            with self.assertRaises(ValueError):
                s.acquire(SIZE, host_fixture=fixture)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.root.exists())

    def test_existing_root_even_empty_or_alias_is_not_reused(self):
        self.root.mkdir()
        self.rejected()
        self.assertEqual(self.calls, [])

    def test_dangling_root_alias_rejected(self):
        self.root.symlink_to(self.g / 'absent')
        self.rejected()
        self.assertEqual(self.calls, [])

    def test_noncanonical_or_historical_root_rejected(self):
        for root in (self.g / 'old-root', self.g / 'x/../current30-enclosure'):
            with patch.object(s.ad, 'enclosure_root', return_value=root):
                self.rejected()
        self.assertEqual(self.calls, [])

    def test_symlink_allocation_parent_rejected(self):
        alias = self.g / 'alias'
        alias.symlink_to(self.g, target_is_directory=True)
        with patch.object(s.ad, 'allocation_root', return_value=alias):
            self.rejected()
        self.assertEqual(self.calls, [])

    def test_wrong_actual_size_fails_before_attach(self):
        self.image_hook = lambda image: image.open('wb').close()
        self.rejected()
        self.assertEqual([a[1] for a in self.calls], ['create'])

    def test_image_hardlink_rejected(self):
        self.image_hook = lambda image: os.link(image, self.g / 'image-alias')
        self.rejected()
        self.assertEqual(len(self.calls), 1)

    def test_mount_replacement_before_attach_rejected(self):
        def change(stem, kwargs):
            if stem == 'create':
                self.mount.rename(self.root / 'original-products')
                self.mount.mkdir()
        self.hook = change
        self.rejected()
        self.assertEqual(len(self.calls), 1)

    def test_wrong_returned_device_not_guessed_and_no_force(self):
        self.attach_hook = lambda record: record['system-entities'][1].update({'dev-entry': '/dev/disk42s1'})
        self.info_hook = lambda records: records[0]['system-entities'][1].update({'dev-entry': '/dev/disk42s1'})
        error = self.rejected()
        self.assertEqual(error.setup_cleanup['status'], 'UNAVAILABLE')
        self.assertNotIn('detach', [a[1] for a in self.calls])
        self.assertNotIn('-force', sum(self.calls, []))

    def test_wrong_physical_mount_relation_cannot_release(self):
        self.hook = lambda stem, kwargs: setattr(self, 'mounted', False) if stem == 'attach' else None
        error = self.rejected()
        self.assertEqual(error.setup_cleanup['status'], 'UNAVAILABLE')
        self.assertNotIn('detach', [a[1] for a in self.calls])

    def test_malformed_attach_recovers_only_through_current_info(self):
        self.raw_attach = b'not plist'
        error = self.rejected()
        self.assertEqual(error.setup_cleanup['status'], 'RELEASED')
        self.assertFalse(self.mounted)
        self.assertTrue((self.root / 'recovery-info.stdout').exists())

    def test_duplicate_plist_keys_rejected(self):
        self.raw_attach = b'''<?xml version="1.0"?><plist version="1.0"><dict>
        <key>system-entities</key><array/><key>system-entities</key><array/></dict></plist>'''
        self.rejected()
        self.assertTrue((self.root / 'recovery-info.stdout').exists())

    def test_failed_clock_not_renewed_and_public_release_has_independent_clock(self):
        original = TimeoutError('original setup deadline')
        def expire(stem, kwargs):
            if stem == 'info' and kwargs['scope'] == s.SCOPE:
                self.t += s.SETUP_SECONDS + 1
                raise original
        self.hook = expire
        error = self.rejected()
        self.assertIs(error, original)
        self.assertEqual(error.setup_cleanup['status'], 'RELEASED')
        failure = json.loads((self.root / 'setup-failure.json').read_text())
        record = failure['originalExperiment']
        self.assertEqual(record['status'], 'FAILED')
        from datetime import datetime
        self.assertEqual((datetime.fromisoformat(record['deadlineUTC']) -
                          datetime.fromisoformat(record['createdUTC'])).total_seconds(), s.SETUP_SECONDS)

    def test_expired_after_attach_recovers_with_independent_reserve(self):
        def expire(stem, kwargs):
            if stem == 'attach':
                self.t += s.SETUP_SECONDS + 1
        self.hook = expire
        error = self.rejected()
        self.assertEqual(error.setup_cleanup['status'], 'RELEASED')
        self.assertFalse(self.mounted)

    def test_budget_walk_failure_does_not_block_owned_cleanup(self):
        def break_walk(stem, kwargs):
            if stem == 'info' and kwargs['scope'] == s.SCOPE:
                self.budget_hook = lambda: (_ for _ in ()).throw(PermissionError('unreadable G'))
        self.hook = break_walk
        error = self.rejected()
        self.assertIsInstance(error, PermissionError)
        self.assertEqual(error.setup_cleanup['status'], 'RELEASED')

    def test_source_drift_leaves_resource_unavailable_not_arbitrary_release(self):
        fingerprint = s.runner._fingerprint
        drift = [False]
        def changed(path):
            value = fingerprint(path)
            return (*value[:-1], value[-1] + 1) if drift[0] and path == Path(s.__file__).resolve() else value
        self.hook = lambda stem, kwargs: drift.__setitem__(0, True) if stem == 'attach' else None
        with patch.object(s.runner, '_fingerprint', side_effect=changed):
            error = self.rejected()
        self.assertEqual(error.setup_cleanup['status'], 'UNAVAILABLE')
        self.assertNotIn('detach', [a[1] for a in self.calls])

    def test_info_overlap_fails_before_publication_unsafe_control_falsified(self):
        def overlap(records):
            records.append({'image-path': 'ram://2048', 'system-entities': [{'dev-entry': '/dev/disk41'}]})
        self.info_hook = overlap
        self.rejected()
        self.assertFalse((self.root / 'ownership-info.plist').exists())

    def test_unsafe_skip_association_mutant_falsified_by_rejection_oracle(self):
        def overlap(records):
            records.append({'image-path': 'ram://2048', 'system-entities': [{'dev-entry': '/dev/disk41'}]})
        self.info_hook = overlap
        # Removing the association barrier makes the real producer publish a
        # valid-looking owner. The rejection oracle MUST detect this mutant.
        with patch.object(s.er, 'association'), self.assertRaises(AssertionError):
            self.rejected()
        self.assertTrue((self.root / 'owner.json').exists())
        with self.assertRaises(ValueError):
            s.ad.enclosure_state()

    def test_stale_info_partial_retained_and_no_owner_publication(self):
        def stale(stem, kwargs):
            if stem == 'info' and kwargs['scope'] == s.SCOPE:
                (self.root / '.ownership-info.plist.partial').write_bytes(b'old')
        self.hook = stale
        self.rejected()
        self.assertEqual((self.root / '.ownership-info.plist.partial').read_bytes(), b'old')
        self.assertFalse((self.root / 'ownership-info.plist').exists())

    def test_stale_owner_partial_blocks_last_publication(self):
        def stale(stem, kwargs):
            if stem == 'info' and kwargs['scope'] == s.SCOPE:
                (self.root / '.owner.json.partial').write_bytes(b'old')
        self.hook = stale
        self.rejected()
        self.assertTrue((self.root / 'ownership-info.plist').exists())

    def test_receipt_scope_and_capture_counters_fail_closed(self):
        self.receipt_hook = lambda receipt: receipt.update(scope='NATIVE_ADMISSION')
        self.rejected()
        self.assertEqual(len(self.calls), 1)

    def test_unreadable_budget_prevents_any_creation(self):
        self.budget_hook = lambda: (_ for _ in ()).throw(PermissionError('budget unavailable'))
        self.rejected()
        self.assertFalse(self.root.exists())
        self.assertEqual(self.calls, [])

    def test_real_generic_core_connected_but_process_launch_is_mocked(self):
        denied = RuntimeError('mock denies process launch')
        with patch.object(s.builder, '_supervise_command', side_effect=REAL_CORE), \
             patch.object(s.builder.subprocess, 'Popen', side_effect=denied) as mocked_launch:
            error = self.rejected()
        self.assertIs(error, denied)
        mocked_launch.assert_called_once()
        receipt = json.loads((self.root / 'create.receipt.json').read_text())
        self.assertEqual(receipt['scope'], s.SCOPE)
        self.assertFalse(receipt['commandReaped'])
        self.assertIn('mock denies process launch', receipt['failure'])
        self.assertEqual(self.calls, [])

    def test_exact_callback_paths_and_record_bound(self):
        def check(stem, kwargs):
            if stem != 'create':
                return
            for path in (self.root / 'arbitrary.stdout', self.mount / 'create.stdout',
                         self.root / 'x/../create.stdout'):
                with self.assertRaises(ValueError):
                    kwargs['check_output'](path)
            with self.assertRaises(ValueError):
                kwargs['write_record'](self.root / 'info.command.json', {'large': 'x' * s.RECORD_BYTES})
            self.assertLessEqual((self.root / '.info.command.json.partial').stat().st_size, s.RECORD_BYTES)
            raise RuntimeError('stop after bound control')
        self.hook = check
        self.rejected()

    def test_info_byte_publication_rejects_oversize_and_stale_partial(self):
        self.root.mkdir()
        path = self.root / 'ownership-info.plist'
        with self.assertRaises(ValueError):
            s._publish_bytes(path, b'x' * (1024**2 + 1))
        self.assertEqual(list(self.root.iterdir()), [])
        partial = self.root / '.ownership-info.plist.partial'
        partial.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            s._publish_bytes(path, b'bounded')
        self.assertEqual(partial.read_bytes(), b'preserve')
        self.assertFalse(path.exists())

    def test_capture_counter_type_cannot_be_float_or_bool(self):
        self.receipt_hook = lambda receipt: receipt['streams']['stdout'].update(bytesRead=1.0)
        self.rejected()
        self.assertEqual(len(self.calls), 1)

    def test_image_symlink_fails_before_attach(self):
        target = self.g / 'alias-target'
        with target.open('xb') as file:
            file.truncate(SIZE)
        def alias(image):
            image.rename(self.g / 'original-image')
            image.symlink_to(target)
        self.image_hook = alias
        self.rejected()
        self.assertEqual(len(self.calls), 1)

    def test_unrelated_opaque_info_is_supported(self):
        self.info_hook = lambda records: records.append({'image-path': 'ram://2048',
            'system-entities': [{'dev-entry': '/dev/disk99'}]})
        self.acquire()
        self.assertTrue((self.root / 'owner.json').exists())

    def test_original_failure_survives_secondary_release_failure(self):
        original = RuntimeError('original failure')
        self.hook = lambda stem, kwargs: (_ for _ in ()).throw(original) if stem == 'info' else None
        with patch.object(s.runner, 'release', side_effect=OSError('secondary release failure')):
            error = self.rejected()
        self.assertIs(error, original)
        self.assertEqual(error.setup_cleanup['status'], 'UNAVAILABLE')
        self.assertIn('secondary release failure', error.setup_cleanup['secondary'][0])


if __name__ == '__main__':
    unittest.main()
