"""Hermetic byte-conservation fixtures; never touch real build/archive trees."""
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location('weighted_retention', Path(__file__).with_name('verify-weighted-pool-retention.py'))
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)


def pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return pin(path)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        self.roots = ['build/weighted-pool-fixture-' + str(i) for i in range(11)]
        self.excluded = 'build/weighted-pool-native-composition-fixture'
        for name in self.roots + [self.excluded]:
            (self.repo / name).mkdir(parents=True)
        self.large = self.repo / self.roots[0] / 'large.bin'
        self.large.write_bytes(b'weighted-pool\x00' * (V.MIN_BYTES // 14 + 1))
        # Ensure the fixture genuinely crosses the fixed threshold.
        with self.large.open('ab') as stream:
            stream.write(b'X' * (V.MIN_BYTES - self.large.stat().st_size + 1))
        self.compact = self.repo / self.roots[0] / 'report.json'
        self.compact.write_bytes(b'{"retained": true}')
        self.excluded_large = self.repo / self.excluded / 'protected-large'
        self.excluded_large.write_bytes(b'P' * V.MIN_BYTES)
        self.alias = self.compact.parent / 'report-link'
        self.alias.symlink_to('report.json')
        self.external = self.repo / 'external-tool'
        self.external.write_bytes(b'original tool bytes')
        self.external_alias = self.repo / 'external-tool-link'
        self.external_alias.symlink_to(self.external.name)
        self.cert = self.repo / 'build/weighted-pool-certificate/certificate.json'
        self.aux = self.repo / 'build/weighted-pool-admission/admission.json'
        cert_pin = write_json(self.cert, {'bindings': {str(self.excluded_large.relative_to(self.repo)): pin(self.excluded_large)}})
        aux_pin = write_json(self.aux, {'witness': {
            'files': {str(self.external): pin(self.external)},
            'aliases': {str(self.external_alias): str(self.external)}}})
        rows = []
        for path in (self.large, self.compact, self.excluded_large):
            rows.append(dict(path=str(path.relative_to(self.repo)), sha256=pin(path),
                             size=path.stat().st_size, fingerprint=V.fingerprint(path)))
        self.selected = str(self.large.relative_to(self.repo))
        self.large_sha = pin(self.large)
        codec = V.codec_size(self.large)
        self.closure = dict(version=1, repoRoot=str(self.repo), archiveRun='fixture-r1', minBytes=V.MIN_BYTES,
            roots=self.roots, observedRoots=self.roots + [self.excluded], entries=rows,
            selected=[self.selected], aliases=[dict(path=str(self.alias.relative_to(self.repo)),
                target=os.readlink(self.alias), fingerprint=V.fingerprint(self.alias))],
            protection=dict(certificatePath=str(self.cert.relative_to(self.repo)), certificateSha256=cert_pin,
                auxiliaryAdmissionPath=str(self.aux.relative_to(self.repo)), auxiliaryAdmissionSha256=aux_pin),
            projection=dict(archiveAllocatedBefore=4096, liveAllocatedBefore=4 * V.MIN_BYTES,
                exactCodecNewBlobBytes={self.large_sha: codec}, verifiedExistingBlobs=[],
                archiveGrowthBound=1024 * 1024, archiveCap=V.ARCHIVE_CAP, liveCap=V.LIVE_CAP),
            limits=['finite fixture only'])
        self.closure_path = self.repo / 'build/weighted-pool-retention-r1/closure.json'
        self.manifest_path = self.repo / 'build/migration-evidence-archive/runs/fixture-r1/manifest.json'
        self.blob = self.repo / 'build/migration-evidence-archive/blobs' / self.large_sha[:2] / (self.large_sha + '.gz')
        self.manifest = None

    def audit(self, archived=False):
        cp = write_json(self.closure_path, self.closure)
        mp = write_json(self.manifest_path, self.manifest) if archived else None
        return V.verify(self.closure_path, cp, self.repo, self.manifest_path if archived else None, mp)

    def archive_fixture(self):
        self.blob.parent.mkdir(parents=True)
        with self.blob.open('wb') as raw:
            with gzip.GzipFile(filename='', fileobj=raw, mode='wb', compresslevel=1, mtime=0) as out:
                out.write(self.large.read_bytes())
        row = copy.deepcopy(self.closure['entries'][0])
        row.update(mode=0o644, mtime_ns=row['fingerprint'][3])
        self.manifest = dict(version=1, status='ARCHIVED_VERIFIED_PRUNED', roots=self.roots,
            min_bytes=V.MIN_BYTES, entries=[row], removed_bytes=row['size'])
        self.large.unlink()

    def test_live_positive(self):
        result = self.audit()
        self.assertEqual(result['mode'], 'LIVE_BEFORE_PRUNE')
        self.assertEqual(result['selectedFiles'], 1)
        self.assertTrue(self.large.exists())
        self.assertFalse(self.blob.exists())

    def test_archived_positive(self):
        self.archive_fixture()
        result = self.audit(True)
        self.assertEqual(result['mode'], 'ARCHIVED_BYTES_RETAINED_NO_LIVE_ORIGIN_RENEWAL')
        self.assertEqual(result['reconstructedBlobs'], 1)
        self.assertTrue(self.compact.exists())
        self.assertFalse(self.large.exists())

    def test_existing_blob_partition(self):
        self.archive_fixture()
        self.large.write_bytes(gzip.decompress(self.blob.read_bytes()))
        self.closure['entries'][0]['fingerprint'] = V.fingerprint(self.large)
        self.closure['projection']['exactCodecNewBlobBytes'] = {}
        self.closure['projection']['verifiedExistingBlobs'] = [self.large_sha]
        self.assertEqual(self.audit()['reconstructedBlobs'], 1)

    def test_missing_complement(self):
        self.compact.unlink()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.audit()

    def test_changed_complement_bytes(self):
        self.compact.write_bytes(b'changed report')
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            self.audit()

    def test_changed_complement_fingerprint(self):
        self.compact.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            self.audit()

    def test_added_inventory_member(self):
        (self.compact.parent / 'unadmitted').write_bytes(b'new')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.audit()

    def test_changed_alias(self):
        self.alias.unlink()
        self.alias.symlink_to('large.bin')
        with self.assertRaisesRegex(ValueError, 'alias changed'):
            self.audit()

    def test_added_directory_symlink_not_followed(self):
        (self.compact.parent / 'escape').symlink_to(self.repo, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'alias inventory'):
            self.audit()

    def test_read_only_success(self):
        cp = write_json(self.closure_path, self.closure)
        before = {str(p): V.fingerprint(p) for p in self.repo.rglob('*')}
        V.verify(self.closure_path, cp, self.repo)
        after = {str(p): V.fingerprint(p) for p in self.repo.rglob('*')}
        self.assertEqual(before, after)

    def test_archived_missing_complement(self):
        self.archive_fixture()
        self.compact.unlink()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.audit(True)

    def test_archived_changed_complement(self):
        self.archive_fixture()
        self.compact.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            self.audit(True)

    def test_excluded_large_member_must_remain(self):
        self.archive_fixture()
        self.excluded_large.unlink()
        with self.assertRaises(FileNotFoundError):
            self.audit(True)

    def test_duplicate_json_keys(self):
        self.closure_path.parent.mkdir(parents=True)
        self.closure_path.write_bytes(b'{"version":1,"version":1}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            V.verify(self.closure_path, pin(self.closure_path), self.repo)

    def test_symlink_archive_blob(self):
        self.archive_fixture()
        raw = self.blob.read_bytes()
        copy_path = self.repo / 'blob-copy'
        copy_path.write_bytes(raw)
        self.blob.unlink()
        self.blob.symlink_to(copy_path)
        with self.assertRaisesRegex(ValueError, 'aliased physical'):
            self.audit(True)

    def test_selected_complement_inode_overlap(self):
        os.link(self.large, self.compact.parent / 'unselected-link')
        other = self.compact.parent / 'unselected-link'
        self.closure['entries'][0]['fingerprint'] = V.fingerprint(self.large)
        # Place this alias in the excluded observed tree: it is large but MUST
        # remain live, and pruning its sibling would change nlink/ctime.
        other.rename(self.repo / self.excluded / 'unselected-link')
        other = self.repo / self.excluded / 'unselected-link'
        self.closure['entries'].append(dict(path=str(other.relative_to(self.repo)),
            sha256=self.large_sha, size=other.stat().st_size, fingerprint=V.fingerprint(other)))
        self.closure['entries'][0]['fingerprint'] = V.fingerprint(self.large)
        with self.assertRaisesRegex(ValueError, 'complement inode overlap'):
            self.audit()

    def test_wrong_external_closure_hash(self):
        write_json(self.closure_path, self.closure)
        with self.assertRaisesRegex(ValueError, 'pin mismatch'):
            V.verify(self.closure_path, '0' * 64, self.repo)

    def test_wrong_archive_hash(self):
        self.archive_fixture()
        cp = write_json(self.closure_path, self.closure)
        write_json(self.manifest_path, self.manifest)
        with self.assertRaisesRegex(ValueError, 'pin mismatch'):
            V.verify(self.closure_path, cp, self.repo, self.manifest_path, '0' * 64)

    def test_missing_archive_entry(self):
        self.archive_fixture()
        self.manifest['entries'] = []
        with self.assertRaisesRegex(ValueError, 'selection membership'):
            self.audit(True)

    def test_archive_fingerprint_mismatch(self):
        self.archive_fixture()
        self.manifest['entries'][0]['fingerprint'][1] += 1
        with self.assertRaisesRegex(ValueError, 'contract mismatch'):
            self.audit(True)

    def test_wrong_blob_bytes(self):
        self.archive_fixture()
        self.blob.write_bytes(gzip.compress(b'wrong bytes'))
        with self.assertRaisesRegex(ValueError, 'bytes mismatch'):
            self.audit(True)

    def test_missing_blob(self):
        self.archive_fixture()
        self.blob.unlink()
        with self.assertRaises(FileNotFoundError):
            self.audit(True)

    def test_leftover_selected(self):
        raw = self.large.read_bytes()
        self.archive_fixture()
        self.large.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.audit(True)

    def test_protected_selection(self):
        self.closure['protection']['certificateSha256'] = write_json(self.cert, {
            'bindings': {self.selected: self.large_sha}})
        with self.assertRaisesRegex(ValueError, 'protected selection'):
            self.audit()

    def test_protected_inode_overlap(self):
        hardlink = self.repo / 'tool-hardlink'
        os.link(self.large, hardlink)
        self.closure['entries'][0]['fingerprint'] = V.fingerprint(self.large)
        self.closure['protection']['auxiliaryAdmissionSha256'] = write_json(self.aux, {
            'witness': {'files': {str(hardlink): self.large_sha}, 'aliases': {}}})
        with self.assertRaisesRegex(ValueError, 'protected selection'):
            self.audit()

    def test_changed_protected_bytes(self):
        self.external.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'protected bytes'):
            self.audit()

    def test_changed_protected_alias(self):
        self.external_alias.unlink()
        self.external_alias.symlink_to(self.compact)
        with self.assertRaisesRegex(ValueError, 'alias resolution'):
            self.audit()

    def test_traversal_escape(self):
        self.closure['entries'][0]['path'] = 'build/../external-tool'
        with self.assertRaisesRegex(ValueError, 'unsafe relative'):
            self.audit()

    def test_aliased_root(self):
        root = self.repo / self.roots[1]
        root.rmdir()
        root.symlink_to(self.repo / self.roots[2], target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'aliased physical'):
            self.audit()

    def test_selection_must_be_complete(self):
        self.closure['selected'] = []
        with self.assertRaisesRegex(ValueError, 'threshold selection'):
            self.audit()

    def test_fixed_caps(self):
        self.closure['projection']['archiveCap'] *= 2
        with self.assertRaisesRegex(ValueError, 'fixed budget'):
            self.audit()

    def test_understated_codec_projection(self):
        self.closure['projection']['exactCodecNewBlobBytes'][self.large_sha] -= 1
        with self.assertRaisesRegex(ValueError, 'codec projection'):
            self.audit()

    def test_audit_hook_rejects_process_events(self):
        for event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork', 'os.exec'):
            with self.subTest(event=event), self.assertRaisesRegex(ValueError, 'process creation'):
                V.forbid_process(event, ())
        V.forbid_process('open', ())


if __name__ == '__main__':
    unittest.main()
