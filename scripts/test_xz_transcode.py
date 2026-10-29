"""Hermetic SOURCE controls: no real archives, game data, or native tools."""
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'cleanup_xz_tests', Path(__file__).with_name('cleanup-migration-artifacts.py'))
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


PAYLOAD = b'hermetic archive fixture: repeated bytes\x00\xff\n' * 40000
REJECT = (ValueError, OSError)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical_gzip(data, level, mtime=0):
    output = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=output, mode='wb',
                       compresslevel=level, mtime=mtime) as stream:
        stream.write(data)
    return output.getvalue()


class XzTranscodeTests(unittest.TestCase):
    def fixture(self, repo, level=1, payload=PAYLOAD):
        """Make a completed legacy manifest without invoking archive/prune."""
        arc = repo / 'build/migration-evidence-archive'
        sha = sha256(payload)
        old = arc / 'blobs' / sha[:2] / (sha + '.gz')
        old.parent.mkdir(parents=True)
        old.write_bytes(canonical_gzip(payload, level))
        manifest = arc / 'runs/xz-hermetic/manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({
            'version': 1, 'roots': ['build/old'],
            'status': 'ARCHIVED_VERIFIED_PRUNED',
            'entries': [{'path': 'build/old/payload', 'sha256': sha,
                         'size': len(payload)}],
        }, indent=2) + '\n')
        row = cleanup.plan_xz_blob(repo, str(manifest.relative_to(repo)), sha)
        return arc, manifest, old, row

    def positive_fixture(self, repo, level=1):
        result = self.fixture(repo, level)
        self.assertIsNotNone(result[3], 'repeated fixture must yield a positive XZ gain')
        return result

    def new_paths(self, old):
        return old.with_suffix('.xz-transcode.tmp'), old.with_suffix('.xz')

    def encoded(self):
        return lzma.compress(PAYLOAD, format=lzma.FORMAT_XZ,
                             check=lzma.CHECK_CRC64, preset=6)

    def assert_original(self, old, original, manifest, manifest_bytes):
        self.assertEqual(old.read_bytes(), original)
        self.assertEqual(manifest.read_bytes(), manifest_bytes)

    def assert_conversion(self, arc, manifest, old, row, original, manifest_bytes):
        temp, dest = self.new_paths(old)
        self.assertFalse(old.exists())
        self.assertFalse(temp.exists())
        self.assertEqual(dest.stat().st_nlink, 1)
        encoded = dest.read_bytes()
        self.assertEqual((sha256(encoded), len(encoded)),
                         (row['newEncodedSha256'], row['newEncodedSize']))
        raw = lzma.decompress(encoded)
        self.assertEqual((sha256(raw), len(raw)), (row['sha256'], row['rawSize']))
        self.assertEqual(canonical_gzip(raw, row['oldGzipLevel']), original)
        self.assertEqual(manifest.read_bytes(), manifest_bytes)
        self.assertEqual(cleanup.resolve_blob(arc, row['sha256']), dest)
        with cleanup.open_blob(arc, row['sha256']) as decoded:
            self.assertEqual(decoded.read(), raw)
        cleanup.verify(arc, manifest)

    def test_gzip_1_and_9_exact_recovery_and_legacy_reader(self):
        for level in (1, 9):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory).resolve()
                arc, manifest, old, row = self.positive_fixture(repo, level)
                original, manifest_bytes = old.read_bytes(), manifest.read_bytes()
                self.assertEqual(row['oldGzipLevel'], level)
                self.assertEqual(row['schema'], 'xz-transcode-plan-v1')
                self.assertEqual(row['codec'], 'XZ-LZMA2-CRC64-preset6-v1')
                self.assertLess(row['newEncodedSize'], row['oldEncodedSize'])
                receipt = cleanup.recode_xz_blob(repo, row)
                self.assertEqual(receipt['status'],
                                 'RAW_AND_OLD_GZIP_RECONSTRUCTED_BEFORE_XZ_CONVERSION')
                self.assert_conversion(arc, manifest, old, row, original, manifest_bytes)

    def test_nonpositive_gain_returns_none_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, manifest, old, row = self.fixture(repo, payload=b'')
            self.assertIsNone(row)
            self.assertEqual(old.read_bytes(), canonical_gzip(b'', 1))
            self.assertEqual(sorted(p.name for p in old.parent.iterdir()), [old.name])
            self.assertEqual(json.loads(manifest.read_bytes())['status'], 'ARCHIVED_VERIFIED_PRUNED')

    def test_plan_field_tampering_retains_original(self):
        # Start from real rows, preserving implementation-specific source identities.
        mutations = {
            'sha256': '0' * 64, 'rawSize': len(PAYLOAD) - 1,
            'oldEncodedSha256': '0' * 64, 'oldEncodedSize': 1,
            'newEncodedSha256': '0' * 64, 'newEncodedSize': 1,
            'manifestSha256': '0' * 64, 'codec': 'wrong', 'schema': 'wrong',
            'python': 'wrong', 'zlib': 'wrong', 'oldGzipLevel': 6,
        }
        for key, value in mutations.items():
            with self.subTest(field=key), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory).resolve()
                _, manifest, old, row = self.positive_fixture(repo)
                original, manifest_bytes = old.read_bytes(), manifest.read_bytes()
                bad = copy.deepcopy(row)
                bad[key] = value
                with self.assertRaises(REJECT):
                    cleanup.recode_xz_blob(repo, bad)
                self.assert_original(old, original, manifest, manifest_bytes)
                self.assertFalse(self.new_paths(old)[1].exists())
                if key == 'newEncodedSize':
                    temp = self.new_paths(old)[0]
                    if temp.exists():
                        self.assertLessEqual(temp.stat().st_size, 1)

    def test_type_exact_counts_fingerprint_and_explicit_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, _, old, row = self.positive_fixture(repo)
            original = old.read_bytes()
            for field in ('rawSize', 'oldEncodedSize', 'newEncodedSize', 'oldGzipLevel'):
                bad = copy.deepcopy(row)
                bad[field] = float(bad[field])
                with self.subTest(field=field), self.assertRaises(ValueError):
                    cleanup.recode_xz_blob(repo, bad)
            bad = copy.deepcopy(row)
            bad['fingerprint'][-1] = True
            with self.assertRaises(ValueError):
                cleanup.recode_xz_blob(repo, bad)
            for resume in (1, 'true', None):
                with self.subTest(resume=resume), self.assertRaises(ValueError):
                    cleanup.recode_xz_blob(repo, row, resume=resume)
            self.assertEqual(old.read_bytes(), original)
            self.assertFalse(self.new_paths(old)[0].exists())

    def test_changed_fingerprint_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, manifest, old, row = self.positive_fixture(repo)
            original, manifest_bytes = old.read_bytes(), manifest.read_bytes()
            row = copy.deepcopy(row)
            row['fingerprint'][3] += 1
            with self.assertRaises(REJECT):
                cleanup.recode_xz_blob(repo, row)
            self.assert_original(old, original, manifest, manifest_bytes)

    def test_changed_manifest_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, manifest, old, row = self.positive_fixture(repo)
            original = old.read_bytes()
            manifest.write_bytes(manifest.read_bytes() + b' ')
            changed = manifest.read_bytes()
            with self.assertRaises(REJECT):
                cleanup.recode_xz_blob(repo, row)
            self.assert_original(old, original, manifest, changed)

    def test_planner_rejects_corrupt_wrong_raw_size_and_unfinished_inputs(self):
        for mode in ('corrupt', 'wrong-raw', 'raw-size', 'unfinished'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory).resolve()
                _, manifest, old, row = self.positive_fixture(repo)
                data = json.loads(manifest.read_bytes())
                if mode == 'corrupt':
                    old.write_bytes(b'not gzip')
                elif mode == 'wrong-raw':
                    old.write_bytes(canonical_gzip(b'wrong payload', 1))
                elif mode == 'raw-size':
                    data['entries'][0]['size'] -= 1
                else:
                    data['status'] = 'PLANNED_NOT_PRUNED'
                manifest.write_text(json.dumps(data))
                original, manifest_bytes = old.read_bytes(), manifest.read_bytes()
                with self.assertRaises(REJECT):
                    cleanup.plan_xz_blob(repo, row['manifest'], row['sha256'])
                self.assert_original(old, original, manifest, manifest_bytes)

    def test_noncanonical_mtime_cannot_be_forged_into_an_execution_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, manifest, old, row = self.positive_fixture(repo)
            old.write_bytes(canonical_gzip(PAYLOAD, 1, mtime=17))
            original, manifest_bytes = old.read_bytes(), manifest.read_bytes()
            with self.assertRaises(REJECT):
                cleanup.plan_xz_blob(repo, row['manifest'], row['sha256'])
            bad = copy.deepcopy(row)
            bad['fingerprint'] = cleanup.fingerprint(old)
            bad['oldEncodedSha256'], bad['oldEncodedSize'] = cleanup.file_digest(old)
            with self.assertRaises(REJECT):
                cleanup.recode_xz_blob(repo, bad)
            self.assert_original(old, original, manifest, manifest_bytes)

    def test_manifest_alias_traversal_and_absolute_paths_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, manifest, old, row = self.positive_fixture(repo)
            alias = manifest.parent / 'alias'
            alias.symlink_to(manifest.parent, target_is_directory=True)
            for name in (str(manifest), '../manifest.json',
                         str((alias / 'manifest.json').relative_to(repo))):
                with self.subTest(path=name), self.assertRaises(REJECT):
                    cleanup.plan_xz_blob(repo, name, row['sha256'])
            original = old.read_bytes()
            os.link(old, repo / 'external-link')
            with self.assertRaises(REJECT):
                cleanup.plan_xz_blob(repo, row['manifest'], row['sha256'])
            with self.assertRaises(REJECT):
                cleanup.recode_xz_blob(repo, row)
            self.assertEqual(old.read_bytes(), original)

    def test_symlinked_old_blob_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, _, old, row = self.positive_fixture(repo)
            target = repo / 'elsewhere.gz'
            old.rename(target)
            old.symlink_to(target)
            with self.assertRaises(REJECT):
                cleanup.plan_xz_blob(repo, row['manifest'], row['sha256'])
            with self.assertRaises(REJECT):
                cleanup.recode_xz_blob(repo, row)
            self.assertEqual(target.read_bytes(), canonical_gzip(PAYLOAD, 1))

    def test_invalid_encoded_limits_reject_before_install(self):
        for value in (0, -1, 20 * 1024**2):
            with self.subTest(size=value), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory).resolve()
                _, _, old, row = self.positive_fixture(repo)
                original = old.read_bytes()
                bad = copy.deepcopy(row)
                bad['newEncodedSize'] = value
                with self.assertRaises(REJECT):
                    cleanup.recode_xz_blob(repo, bad)
                self.assertEqual(old.read_bytes(), original)
                self.assertFalse(self.new_paths(old)[1].exists())

    def test_archive_reservation_is_physical_not_encoded_length(self):
        for used in (16 * 1024**3, 16 * 1024**3 - 1024**2,
                     16 * 1024**3 - 64 * 1024**2):
            with self.subTest(used=used), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory).resolve()
                _, _, old, row = self.positive_fixture(repo)
                original = old.read_bytes()
                with patch.object(cleanup, 'allocated_bytes', return_value=used):
                    with self.assertRaises(REJECT):
                        cleanup.recode_xz_blob(repo, row)
                self.assertEqual(old.read_bytes(), original)
                self.assertFalse(self.new_paths(old)[0].exists())
                self.assertFalse(self.new_paths(old)[1].exists())

    def test_fixed_live_cap_rejects_without_creating_scratch(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            arc, _, old, row = self.positive_fixture(repo)
            original = old.read_bytes()

            def allocation(root):
                return 0 if Path(root) == arc else 4 * 1024**3 + 1

            with patch.object(cleanup, 'allocated_bytes', side_effect=allocation):
                with self.assertRaises(REJECT):
                    cleanup.recode_xz_blob(repo, row)
            self.assertEqual(old.read_bytes(), original)
            self.assertFalse(self.new_paths(old)[0].exists())
            self.assertFalse(self.new_paths(old)[1].exists())

    def test_actual_physical_overrun_retains_old_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, _, old, row = self.positive_fixture(repo)
            original = old.read_bytes()
            real_fstat = os.fstat

            def oversized(fd):
                info = real_fstat(fd)
                if stat.S_ISREG(info.st_mode):
                    values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
                    values['st_blocks'] = (64 * 1024**2 // 512) + 1
                    return SimpleNamespace(**values)
                return info

            with patch.object(cleanup.os, 'fstat', side_effect=oversized):
                with self.assertRaises(REJECT):
                    cleanup.recode_xz_blob(repo, row)
            self.assertEqual(old.read_bytes(), original)
            self.assertFalse(self.new_paths(old)[1].exists())

    def interruption(self, repo, state):
        arc, manifest, old, row = self.positive_fixture(repo)
        temp, dest = self.new_paths(old)
        encoded = self.encoded()
        self.assertEqual((sha256(encoded), len(encoded)),
                         (row['newEncodedSha256'], row['newEncodedSize']))
        if state == 'A':
            temp.write_bytes(encoded)
        elif state == 'B':
            temp.write_bytes(encoded)
            os.link(temp, dest)
        elif state == 'C':
            dest.write_bytes(encoded)
        elif state == 'D':
            dest.write_bytes(encoded)
            old.unlink()
        else:
            raise AssertionError(state)
        return arc, manifest, old, row

    def test_default_rejects_all_interrupted_states_without_modification(self):
        for state in 'ABCD':
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory).resolve()
                _, manifest, old, row = self.interruption(repo, state)
                paths = (manifest, old, *self.new_paths(old))
                before = {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_nlink)
                          for p in paths if p.exists()}
                with self.assertRaises(REJECT):
                    cleanup.recode_xz_blob(repo, row)
                after = {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_nlink)
                         for p in paths if p.exists()}
                self.assertEqual(after, before)

    def test_explicit_resume_verifies_each_admitted_interruption(self):
        for state in 'ABCD':
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory).resolve()
                arc, manifest, old, row = self.interruption(repo, state)
                manifest_bytes = manifest.read_bytes()
                original = canonical_gzip(PAYLOAD, row['oldGzipLevel'])
                cleanup.recode_xz_blob(repo, row, resume=True)
                self.assert_conversion(arc, manifest, old, row, original, manifest_bytes)

    def test_corrupt_interrupted_bytes_never_prune_or_silently_cleanup(self):
        for state in 'ABCD':
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory).resolve()
                _, _, old, row = self.interruption(repo, state)
                temp, dest = self.new_paths(old)
                target = temp if temp.exists() else dest
                target.write_bytes(b'corrupt interrupted target')
                paths = (old, temp, dest)
                before = {p: p.read_bytes() for p in paths if p.exists()}
                with self.assertRaises(REJECT):
                    cleanup.recode_xz_blob(repo, row, resume=True)
                self.assertEqual({p: p.read_bytes() for p in paths if p.exists()}, before)

    def test_resume_rejects_external_new_hardlink(self):
        for state in 'ABCD':
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory).resolve()
                _, _, old, row = self.interruption(repo, state)
                temp, dest = self.new_paths(old)
                target = temp if temp.exists() else dest
                outside = repo / 'external-xz-link'
                os.link(target, outside)
                original = old.read_bytes() if old.exists() else None
                with self.assertRaises(REJECT):
                    cleanup.recode_xz_blob(repo, row, resume=True)
                self.assertEqual(outside.read_bytes(), self.encoded())
                self.assertEqual(old.read_bytes() if old.exists() else None, original)

    def test_resume_rejects_independent_temp_and_dest_even_when_bytes_match(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, _, old, row = self.interruption(repo, 'A')
            temp, dest = self.new_paths(old)
            dest.write_bytes(temp.read_bytes())
            with self.assertRaises(REJECT):
                cleanup.recode_xz_blob(repo, row, resume=True)
            self.assertTrue(old.exists())
            self.assertTrue(temp.exists())
            self.assertTrue(dest.exists())

    def test_resume_revalidates_old_identity_and_manifest(self):
        for mode in ('old-fingerprint', 'manifest', 'codec', 'old-encoding'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory).resolve()
                _, manifest, old, row = self.interruption(repo, 'C')
                if mode == 'old-fingerprint':
                    info = old.stat()
                    os.utime(old, ns=(info.st_atime_ns, info.st_mtime_ns + 1000000))
                elif mode == 'manifest':
                    manifest.write_bytes(manifest.read_bytes() + b' ')
                elif mode == 'codec':
                    row = dict(row, codec='wrong')
                else:
                    row = dict(row, oldEncodedSha256='0' * 64)
                original = old.read_bytes()
                with self.assertRaises(REJECT):
                    cleanup.recode_xz_blob(repo, row, resume=True)
                self.assertEqual(old.read_bytes(), original)

    def test_completed_resume_still_reconstructs_old_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, _, old, row = self.interruption(repo, 'D')
            dest = self.new_paths(old)[1]
            original = dest.read_bytes()
            row = dict(row, oldEncodedSha256='0' * 64)
            with self.assertRaises(REJECT):
                cleanup.recode_xz_blob(repo, row, resume=True)
            self.assertEqual(dest.read_bytes(), original)
            self.assertFalse(old.exists())

    def test_resume_rejects_existing_generated_physical_overallocation(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, manifest, old, row = self.interruption(repo, 'A')
            temp, dest = self.new_paths(old)
            original = old.read_bytes()
            actual_lstat = Path.lstat
            def modeled_lstat(path):
                s = actual_lstat(path)
                if path != temp:
                    return s
                fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns',
                          'st_mode', 'st_nlink')
                return SimpleNamespace(**{k: getattr(s, k) for k in fields},
                                       st_blocks=96 * 1024**2 // 512)
            with patch.object(Path, 'lstat', modeled_lstat):
                with self.assertRaisesRegex(ValueError, 'physical'):
                    cleanup.recode_xz_blob(repo, row, resume=True)
            self.assertEqual(old.read_bytes(), original)
            self.assertTrue(temp.exists())
            self.assertFalse(dest.exists())

    def test_resume_rejects_missing_old_with_two_generated_names(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, _, old, row = self.interruption(repo, 'B')
            temp, dest = self.new_paths(old)
            old.unlink()
            with self.assertRaises(ValueError):
                cleanup.recode_xz_blob(repo, row, resume=True)
            self.assertTrue(temp.exists())
            self.assertTrue(dest.exists())
            self.assertEqual(dest.stat().st_nlink, 2)

    def test_preexisting_destination_is_not_clobbered(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, _, old, row = self.positive_fixture(repo)
            dest = self.new_paths(old)[1]
            dest.write_bytes(b'existing unrelated evidence')
            original = old.read_bytes()
            for resume in (False, True):
                with self.subTest(resume=resume), self.assertRaises(REJECT):
                    cleanup.recode_xz_blob(repo, row, resume=resume)
                self.assertEqual(dest.read_bytes(), b'existing unrelated evidence')
                self.assertEqual(old.read_bytes(), original)

    def test_install_race_cannot_overwrite_new_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            _, _, old, row = self.positive_fixture(repo)
            original = old.read_bytes()
            _, dest = self.new_paths(old)
            real_link = os.link
            reached = []

            def competing_link(source, target, *args, **kwargs):
                if Path(target) == dest:
                    reached.append(True)
                    dest.write_bytes(b'concurrent destination evidence')
                return real_link(source, target, *args, **kwargs)

            with patch.object(cleanup.os, 'link', side_effect=competing_link):
                with self.assertRaises(REJECT):
                    cleanup.recode_xz_blob(repo, row)
            self.assertEqual(reached, [True], 'installation must use exclusive os.link')
            self.assertEqual(dest.read_bytes(), b'concurrent destination evidence')
            self.assertEqual(old.read_bytes(), original)

    def test_fault_before_old_unlink_leaves_verified_single_link_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            arc, manifest, old, row = self.positive_fixture(repo)
            original, manifest_bytes = old.read_bytes(), manifest.read_bytes()
            temp, dest = self.new_paths(old)
            real_unlink, real_fsync = os.unlink, os.fsync
            directory_syncs = []
            reached = []

            def fsync(fd):
                info = os.fstat(fd)
                if stat.S_ISDIR(info.st_mode) and info.st_ino == old.parent.stat().st_ino:
                    directory_syncs.append(True)
                return real_fsync(fd)

            def unlink(path, *args, **kwargs):
                if Path(path) == old:
                    reached.append(True)
                    self.assertTrue(directory_syncs, 'directory must be durable before pruning')
                    self.assertFalse(temp.exists())
                    self.assertEqual(dest.stat().st_nlink, 1)
                    decoded = lzma.decompress(dest.read_bytes())
                    self.assertEqual((sha256(decoded), len(decoded)),
                                     (row['sha256'], row['rawSize']))
                    self.assertEqual(canonical_gzip(decoded, row['oldGzipLevel']), original)
                    raise OSError('injected old-unlink interruption')
                return real_unlink(path, *args, **kwargs)

            with patch.object(cleanup.os, 'fsync', side_effect=fsync), \
                    patch.object(cleanup.os, 'unlink', side_effect=unlink):
                with self.assertRaisesRegex(OSError, 'injected old-unlink interruption'):
                    cleanup.recode_xz_blob(repo, row)
            self.assertEqual(reached, [True])
            self.assert_original(old, original, manifest, manifest_bytes)
            cleanup.recode_xz_blob(repo, row, resume=True)
            self.assert_conversion(arc, manifest, old, row, original, manifest_bytes)


class BoundedEncodingControls(unittest.TestCase):
    def assert_rejects_before_write(self, writer_class):
        output = io.BytesIO()
        writer = writer_class(output, 1)
        with self.assertRaises(ValueError):
            writer.write(b'oversized')
        self.assertEqual(output.getvalue(), b'')

    def test_encoded_guard_and_known_unsafe_mutant(self):
        self.assert_rejects_before_write(cleanup.BoundedEncoding)

        class UnsafeBoundedEncoding:
            def __init__(self, output, limit):
                self.output = output

            def write(self, data):
                return self.output.write(data)

        # The same control MUST fail if the pre-write bound is removed.
        with self.assertRaises(AssertionError):
            self.assert_rejects_before_write(UnsafeBoundedEncoding)

    def test_physical_guard_and_known_unsafe_mutant(self):
        def rejects_overallocation(writer_class):
            with tempfile.TemporaryDirectory() as directory:
                with (Path(directory) / 'bounded-output').open('wb') as output:
                    writer = writer_class(output, 1024)
                    allocation = SimpleNamespace(st_blocks=64 * 1024**2 // 512 + 1)
                    with patch.object(cleanup.os, 'fstat', return_value=allocation):
                        with self.assertRaises(ValueError):
                            writer.write(b'within encoded limit')

        rejects_overallocation(cleanup.BoundedEncoding)

        class EncodedOnlyUnsafeBoundedEncoding:
            def __init__(self, output, limit):
                self.output, self.limit = output, limit

            def write(self, data):
                if len(data) > self.limit:
                    raise ValueError('encoded overrun')
                return self.output.write(data)

        with self.assertRaises(AssertionError):
            rejects_overallocation(EncodedOnlyUnsafeBoundedEncoding)


if __name__ == '__main__':
    unittest.main()
