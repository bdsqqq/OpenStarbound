import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def sha(data):
    return hashlib.sha256(data).hexdigest()


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        spec = importlib.util.spec_from_file_location('retention', Path(__file__).with_name('verify-lru-retention.py'))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.m.ROOT = self.root
        self.m.ARCHIVE = self.root / 'build/migration-evidence-archive'
        self.m.CERTIFICATE = self.root / 'build/final/certificate.json'
        self.verifier = self.root / 'source/lab/lru-qualification/verify.py'
        self.verifier.parent.mkdir(parents=True)
        self.verifier.write_bytes(b'fixture semantic verifier')
        self.m.VERIFIER_SHA = sha(self.verifier.read_bytes())
        self.old = self.root / 'build/old/native-output'
        self.old.parent.mkdir(parents=True)
        self.old.write_bytes(b'original failed or accepted output\x00\xff')
        self.product = self.root / 'build/current/frame.json'
        self.product.parent.mkdir(parents=True)
        self.product.write_bytes(b'{"actual":true}')
        rows = {}
        for p in (self.old, self.verifier, self.product):
            rows[str(p)] = dict(kind='current-regular', canonical=str(p), size=p.stat().st_size, sha256=sha(p.read_bytes()))
        certificate = dict(physicalBindings=rows, archiveManifestPins={}, productTrees=[str(self.product.parent)], products={str(self.product):sha(self.product.read_bytes())})
        self.m.CERTIFICATE.parent.mkdir(parents=True)
        self.m.CERTIFICATE.write_text(json.dumps(certificate))
        self.m.CERT_SHA = sha(self.m.CERTIFICATE.read_bytes())
        self.manifest = self.m.ARCHIVE / 'runs/successor/manifest.json'

    def archive(self):
        raw = self.old.read_bytes()
        h = sha(raw)
        blob = self.m.ARCHIVE / 'blobs' / h[:2] / (h + '.gz')
        blob.parent.mkdir(parents=True)
        with gzip.open(blob, 'wb') as stream:
            stream.write(raw)
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text(json.dumps(dict(status='ARCHIVED_VERIFIED_PRUNED', entries=[dict(path=str(self.old.relative_to(self.root)), sha256=h, size=len(raw))])))
        self.old.unlink()
        return [(str(self.manifest), sha(self.manifest.read_bytes()))], blob

    def test_live_positive_then_exact_successor(self):
        self.assertTrue(self.m.verify([])['originalCurrentOriginReplayAvailable'])
        manifests, _ = self.archive()
        with self.assertRaisesRegex(ValueError, 'missing exact archive membership'):
            self.m.verify([])
        report = self.m.verify(manifests)
        self.assertFalse(report['originalCurrentOriginReplayAvailable'])
        self.assertEqual(report['totalBindings'], 3)
        self.assertEqual(len(report['archivedBindings']), 1)
        self.assertEqual(report['selectedLiveProducts'], 1)

    def test_wrong_manifest_pin_and_corrupt_reconstruction_reject(self):
        manifests, blob = self.archive()
        with self.assertRaisesRegex(ValueError, 'manifest physical pin'):
            self.m.verify([(str(self.manifest), '0' * 64)])
        with gzip.open(blob, 'wb') as stream:
            stream.write(b'wrong but internally valid gzip bytes')
        with self.assertRaisesRegex(ValueError, 'archive reconstructed byte integrity'):
            self.m.verify(manifests)

    def test_manifest_cannot_substitute_another_path_or_hash(self):
        manifests, _ = self.archive()
        m = json.loads(self.manifest.read_bytes())
        m['entries'][0]['path'] += '.other'
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'missing exact archive membership'):
            self.m.verify([(str(self.manifest), sha(self.manifest.read_bytes()))])

    def test_changed_current_source_and_extra_product_reject(self):
        raw = self.verifier.read_bytes()
        self.verifier.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'original semantic verifier pin'):
            self.m.verify([])
        self.verifier.write_bytes(raw)
        (self.product.parent / 'unexpected').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'exact selected product membership'):
            self.m.verify([])

    def test_current_alias_cannot_replace_original_origin(self):
        target = self.root / 'another'
        target.write_bytes(self.old.read_bytes())
        self.old.unlink()
        self.old.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'canonical origin changed'):
            self.m.verify([])


if __name__ == '__main__':
    unittest.main()
