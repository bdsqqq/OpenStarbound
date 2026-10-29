#!/usr/bin/env python3
"""Hermetic admission controls: fake bytes and metadata, NEVER native execution."""
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('weighted_game_admission', Path(__file__).with_name('game_build_admission.py'))
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return path


class HermeticCase(unittest.TestCase):
    # unittest.enterContext is only available starting with Python 3.11.
    def enterContext(self, context):
        value = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        return value


class Admission(HermeticCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.enterContext(patch.object(a, 'ROOT', self.root))
        self.seed = put(self.root / a.SEED, 'seed')
        self.sdk = self.root / 'sdk'
        self.sdk.mkdir()
        self.ninja = put(self.seed.parent / 'build.ninja', f'  FLAGS = -O3 -isysroot {self.sdk}\n')
        self.src = put(self.root / 'source/CMakeLists.txt', '\n'.join(f'option({s} "fixture" OFF)' for s in a.SELECTORS))
        binary = put(self.root / 'native-tool', b'\xcf\xfa\xed\xfe fixture bytes')
        binary.chmod(0o755)
        names = ('CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_AR', 'CMAKE_RANLIB',
                 'CMAKE_LINKER', 'CMAKE_MAKE_PROGRAM', 'CMAKE_EXECUTABLE',
                 'APPLE_TOOLCHAIN_SELECTOR', 'STAR_CARGO_EXECUTABLE', 'STAR_RUSTC_EXECUTABLE')
        self.tools = dict(sorted((k, str(binary)) for k in names))
        self.enterContext(patch.object(a, 'auxiliary_tools', return_value=[binary]))
        self.enterContext(patch.object(a, 'selection', return_value=self.tools))
        self.enterContext(patch.object(a, 'check_retirement', return_value={'exact': 'fixture'}))
        self.enterContext(patch.object(a, 'check_budget', return_value={'small': True}))
        self.enterContext(patch.object(a, 'admission_roots', return_value=[str(self.root / 'source')]))
        # Each immutable plan expires within its own bounded execution unit.
        arg = put(self.root / 'admission/tool-args.txt', '\n'.join('-D' + k + '=' + v for k, v in self.tools.items() if k not in a.EXCLUDED) + '\n')
        launch = put(arg.parent / 'launcher-paths.txt', f'{binary}\n{binary}\n{self.sdk}\n')
        witness = a.closure([self.root / 'source'])
        for path in (binary, self.seed, self.ninja, arg, launch):
            witness['aliases'][str(path)] = a.physical(path)
            witness['files'][a.physical(path)] = a.sha(path)
        self.plan = dict(stage='WEIGHTED_POOL_PREEXECUTION_COMPLETE_CACHE_TOOLS', tools=self.tools,
            caps=a.CAPS, scope=a.SCOPE, deadlines=a.DEADLINES,
            createdUTC=a.dt.datetime.now(a.dt.timezone.utc).isoformat(), sourceCheckpoint='a' * 40,
            checkpointRole='BASE_ONLY; current working-tree bytes authoritative', generation=1,
            buildRoot=str(self.root / 'build/behavior/weighted-pool-combined-r1'), profiles=a.profiles(),
            seedCache=str(self.seed), seedPhysical=a.physical(self.seed), seedCacheSha256=a.sha(self.seed),
            seedNinjaSha256=a.sha(self.ninja), sdk=str(self.sdk), sdkPhysical=str(self.sdk), witness=witness,
            argumentFile=str(arg), argumentSha256=a.sha(arg), launcherFile=str(launch), launcherSha256=a.sha(launch),
            retirement={'exact': 'fixture'}, sourceRoots=[str(self.root / 'source')],
            treeMembers=a.tree_members([self.root / 'source']))

    def configured_fixture(self, role='candidate'):
        build = Path(self.plan['buildRoot']) / role / 'cmake'
        cache = '\n'.join(k + ':BOOL=' + v for k, v in a.profiles()[role].items())
        put(build / 'CMakeCache.txt', cache + '\n')
        put(build / 'build.ninja', self.ninja.read_bytes())
        words = [self.tools['CMAKE_CXX_COMPILER'], '-isysroot', str(self.sdk)]
        words += ['-D' + k for k, v in a.profiles()[role].items() if v == 'ON']
        row = dict(file=str(self.root / 'source/client/StarClientApplication.cpp'), arguments=words)
        put(build / 'compile_commands.json', json.dumps([row]))
        return build, row

    def test_complete_plan_and_both_profiles(self):
        a.validate(self.plan)
        for role in ('reference', 'candidate'):
            build, _ = self.configured_fixture(role)
            a.check_configured(self.plan, build)

    def test_missing_archiver_before_configure(self):
        bad = copy.deepcopy(self.plan)
        del bad['witness']['files'][a.physical(self.tools['CMAKE_AR'])]
        with self.assertRaisesRegex(ValueError, 'pre-execution tool'):
            a.validate(bad)
        self.assertFalse(Path(self.plan['buildRoot']).exists())

    def test_every_tool_argument_required(self):
        path = Path(self.plan['argumentFile'])
        original = path.read_text().splitlines()
        for index in range(len(original)):
            with self.subTest(index=index):
                path.write_text('\n'.join(original[:index] + original[index+1:]) + '\n')
                with self.assertRaisesRegex(ValueError, 'future argv'):
                    a.validate(self.plan)
        path.write_text('\n'.join(original) + '\n')

    def test_wrong_launcher_before_configure(self):
        Path(self.plan['launcherFile']).write_text('/unadmitted/cmake\n')
        with self.assertRaisesRegex(ValueError, 'launcher bytes'):
            a.validate(self.plan)

    def test_native_wrapper_rejected(self):
        path = Path(self.tools['CMAKE_AR'])
        path.write_text('#!/bin/sh\nexit 0\n')
        with self.assertRaisesRegex(ValueError, 'non-native tool'):
            a.validate(self.plan)

    def test_tool_symlink_retarget_rejected(self):
        original = Path(self.tools['CMAKE_AR'])
        other = put(self.root / 'other-native', original.read_bytes())
        other.chmod(0o755)
        original.unlink()
        original.symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'pre-execution tool'):
            a.validate(self.plan)

    def test_source_bytes_addition_and_seed_drift(self):
        self.src.write_text(self.src.read_text() + '\n# uncommitted drift')
        with self.assertRaisesRegex(AssertionError, 'input drift'):
            a.validate(self.plan)
        self.plan['witness']['files'][str(self.src)] = a.sha(self.src)
        put(self.src.parent / 'new.cpp', 'new input')
        with self.assertRaisesRegex(ValueError, 'membership'):
            a.validate(self.plan)
        self.seed.write_text('other seed')
        with self.assertRaisesRegex(ValueError, 'seed physical/byte'):
            a.validate(self.plan)

    def test_unhashed_source_rejected_before_configure(self):
        bad = copy.deepcopy(self.plan)
        del bad['witness']['files'][str(self.src)]
        with self.assertRaisesRegex(ValueError, 'unhashed source/tool'):
            a.validate(bad)
        self.assertFalse(Path(self.plan['buildRoot']).exists())

    def test_cli_requires_external_plan_pin(self):
        plan = put(self.root / 'admission/plan.json', json.dumps(self.plan))
        with patch('sys.argv', ['admission', 'before', '--plan', str(plan), '--sha', '0' * 64]):
            with self.assertRaisesRegex(ValueError, 'externally pinned'):
                a.main()
        with patch('sys.argv', ['admission', 'before', '--plan', str(plan), '--sha', a.sha(plan)]):
            a.main()

    def test_deadline_expiry(self):
        self.plan['createdUTC'] = '2000-01-01T00:00:00+00:00'
        with self.assertRaisesRegex(ValueError, 'deadline reached'):
            a.validate(self.plan)

    def test_root_scope_cannot_shrink(self):
        bad = copy.deepcopy(self.plan)
        bad['sourceRoots'] = []
        bad['treeMembers'] = {}
        with self.assertRaisesRegex(ValueError, 'root scope'):
            a.validate(bad)

    def test_all_56_cache_selector_flips(self):
        for role in ('reference', 'candidate'):
            build, _ = self.configured_fixture(role)
            cache = build / 'CMakeCache.txt'
            original = cache.read_text()
            for key, value in a.profiles()[role].items():
                with self.subTest(role=role, key=key):
                    cache.write_text(original.replace(key + ':BOOL=' + value, key + ':BOOL=' + ('OFF' if value == 'ON' else 'ON')))
                    with self.assertRaisesRegex(ValueError, '28-selector cache vector'):
                        a.check_configured(self.plan, build)
            cache.write_text(original)

    def test_all_56_compile_selector_flips(self):
        for role in ('reference', 'candidate'):
            build, row = self.configured_fixture(role)
            for key, value in a.profiles()[role].items():
                bad = copy.deepcopy(row)
                if value == 'ON':
                    bad['arguments'].remove('-D' + key)
                else:
                    bad['arguments'].append('-D' + key)
                put(build / 'compile_commands.json', json.dumps([bad]))
                with self.subTest(role=role, key=key), self.assertRaisesRegex(ValueError, 'client macro vector'):
                    a.check_configured(self.plan, build)

    def test_configured_path_sdk_tools_and_receipt(self):
        build, row = self.configured_fixture()
        with self.assertRaisesRegex(ValueError, 'exact admitted'):
            a.check_configured(self.plan, build.parent)
        with patch.object(a, 'selection', return_value={}):
            with self.assertRaisesRegex(ValueError, 'unadmitted configured'):
                a.check_configured(self.plan, build)
        a.configured(self.plan, 'a' * 64, build)
        receipt = build.parent / 'complete-tool-admission.json'
        original = receipt.read_bytes()
        a.configured(self.plan, 'a' * 64, build)
        self.assertEqual(original, receipt.read_bytes())
        with self.assertRaisesRegex(ValueError, 'nonidentical'):
            a.configured(self.plan, 'b' * 64, build)
        row['arguments'][2] = '/foreign-sdk'
        put(build / 'compile_commands.json', json.dumps([row]))
        with self.assertRaisesRegex(ValueError, 'client SDK'):
            a.check_configured(self.plan, build)

    def test_lock_old_bin_and_fresh_prepare(self):
        lock = put(self.root / 'build/.migration-cleanup.lock', '')
        with self.assertRaisesRegex(ValueError, 'cleanup lock'):
            a.validate(self.plan)
        lock.unlink()
        old = self.root / 'build/behavior/old/reference/bin/starbound'
        old.parent.mkdir(parents=True)
        old.symlink_to('/missing-old-bin')
        with self.assertRaisesRegex(ValueError, 'old game binary'):
            a.validate(self.plan)
        old.unlink()
        with patch.dict(os.environ, {'STAR_WEIGHTED_POOL_SOURCE_CHECKPOINT': 'a' * 40}):
            with self.assertRaisesRegex(ValueError, 'fresh admission'):
                a.prepare(Path(self.plan['argumentFile']).parent)

    def test_caps_deadline_generation_fail_closed(self):
        for field, value, message in [('caps', {}, 'budget/scope'), ('deadlines', {}, 'deadlines'),
                                      ('generation', 0, 'positive'), ('sourceCheckpoint', 'abc', 'checkpoint')]:
            bad = copy.deepcopy(self.plan)
            bad[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                a.validate(bad)

    def test_actual_sdk_never_empty_cache(self):
        self.ninja.write_text('  FLAGS = -O3\n')
        with self.assertRaisesRegex(ValueError, 'actual -isysroot'):
            a.sdk_from_ninja(self.ninja)

    def test_fixed_cap_reservation_without_native_budget_tool(self):
        # Exercise real budget arithmetic independently of the fixture mock.
        with patch.object(a, 'allocated', side_effect=[a.CAPS['archiveBytes'], 4 * a.GIB + a.CAPS['archiveBytes'] - a.CAPS['newRootBytes'], 0]):
            Admission.real_budget(Path(self.plan['buildRoot']))
        with patch.object(a, 'allocated', side_effect=[a.CAPS['archiveBytes'] + 1, a.CAPS['archiveBytes'] + 1, 0]):
            with self.assertRaisesRegex(ValueError, 'archive cap'):
                Admission.real_budget(Path(self.plan['buildRoot']))
        with patch.object(a, 'allocated', side_effect=[0, 4 * a.GIB, 0]):
            with self.assertRaisesRegex(ValueError, 'reservation'):
                Admission.real_budget(Path(self.plan['buildRoot']))


Admission.real_budget = staticmethod(a.check_budget)


class Retirement(HermeticCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.enterContext(patch.object(a, 'ROOT', self.root))
        self.entries = []
        for index, name in enumerate(sorted(a.expected_retired())):
            data = ('retired bytes ' + str(index)).encode()
            digest = hashlib.sha256(data).hexdigest()
            blob = self.root / 'build/migration-evidence-archive/blobs' / digest[:2] / (digest + '.gz')
            put(blob, gzip.compress(data))
            self.entries.append(dict(path=name, sha256=digest, size=len(data)))
        self.manifest = dict(status='ARCHIVED_VERIFIED_PRUNED', entries=self.entries,
            roots=[f'build/behavior/ttl-cache-combined-r2/{role}/bin' for role in ('reference', 'candidate')])
        self.path = put(self.root / a.RETIREMENT, json.dumps(self.manifest))
        protected = {}
        for role in ('reference', 'candidate'):
            for i in range(113):
                p = put(self.root / f'build/behavior/ttl-cache-combined-r2/{role}/cmake/core/{i}.o', 'object fixture')
                protected[str(p)] = a.sha(p)
        for i in range(1032 - 226):
            p = put(self.root / f'protected/{i}', 'other protected fixture')
            protected[str(p)] = a.sha(p)
        self.protection = put(self.root / a.PRESERVED, json.dumps(dict(protected=protected, protectedSymlinks={})))
        self.enterContext(patch.object(a, 'RETIREMENT_SHA', a.sha(self.path)))
        self.enterContext(patch.object(a, 'PRESERVED_SHA', a.sha(self.protection)))

    def repin(self):
        self.path.write_text(json.dumps(self.manifest))
        self.enterContext(patch.object(a, 'RETIREMENT_SHA', a.sha(self.path)))

    def test_exact_retirement_reconstruction_and_preservation(self):
        a.check_retirement()

    def test_xz_retirement_reconstruction_and_raw_tamper(self):
        import lzma
        for entry in self.entries:
            sha = entry['sha256']
            blob = self.root / 'build/migration-evidence-archive/blobs' / sha[:2] / (sha + '.gz')
            blob.with_suffix('.xz').write_bytes(lzma.compress(gzip.decompress(blob.read_bytes())))
            blob.unlink()
        a.check_retirement()
        sha = self.entries[0]['sha256']
        blob = self.root / 'build/migration-evidence-archive/blobs' / sha[:2] / (sha + '.xz')
        blob.write_bytes(lzma.compress(b'wrong identity'))
        with self.assertRaisesRegex(ValueError, 'reconstruction hash'):
            a.check_retirement()

    def test_manifest_status_membership_and_physical_pin(self):
        original = self.path.read_bytes()
        self.path.write_text('unrelated')
        with self.assertRaisesRegex(ValueError, 'physical pin'):
            a.check_retirement()
        self.path.write_bytes(original)
        self.manifest['entries'] = self.entries[:-1]
        self.repin()
        with self.assertRaisesRegex(ValueError, 'exact six'):
            a.check_retirement()
        self.manifest['entries'] = self.entries
        self.manifest['status'] = 'NOT_PRUNED'
        self.repin()
        with self.assertRaisesRegex(ValueError, 'status'):
            a.check_retirement()

    def test_reappeared_live_symlink_and_corrupt_blob(self):
        live = self.root / self.entries[0]['path']
        live.parent.mkdir(parents=True)
        live.symlink_to('/nonexistent')
        with self.assertRaisesRegex(ValueError, 'live member'):
            a.check_retirement()
        live.unlink()
        digest = self.entries[0]['sha256']
        blob = self.root / 'build/migration-evidence-archive/blobs' / digest[:2] / (digest + '.gz')
        blob.write_bytes(gzip.compress(b'wrong bytes'))
        with self.assertRaisesRegex(ValueError, 'reconstruction hash'):
            a.check_retirement()

    def test_preserved_complement_must_not_drift(self):
        put(self.root / 'protected/0', 'changed')
        with self.assertRaisesRegex(ValueError, 'preserved complement'):
            a.check_retirement()


if __name__ == '__main__':
    unittest.main()
