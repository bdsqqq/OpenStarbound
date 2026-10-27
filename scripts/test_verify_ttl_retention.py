"""Hermetic byte-retention controls; fixtures remain in the owned output tree.

No native processes, canonical source edits, archive restores or fixture cleanup.
Each negative changes only an isolated fixture, never accepted evidence.
"""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class RetentionTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('ttl_retention_fixture', ROOT / 'scripts/verify-ttl-retention.py')
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        fixtures = ROOT / 'build/ttl-retention-r1/fixtures'
        fixtures.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='case-', dir=fixtures)).resolve()
        self.m.ROOT = self.root
        self.codec = self.put('source/lab/native_evidence_json.py',
                              (ROOT / 'source/lab/native_evidence_json.py').read_bytes())
        spec = importlib.util.spec_from_file_location('fixture_codec', self.codec)
        self.t = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.t)
        self.current = self.put('build/current/product', b'current product\x00\xff')
        self.old = self.root / 'build/retired/product'
        self.old_raw = b'archived native output\x00\xff'
        self.historical = self.put('source/core/fixture.hpp', b'current source revision')
        self.old_source = b'original source revision'
        self.older_source = b'another original source revision'
        self.manifest = self.root / 'build/migration-evidence-archive/runs/successor/manifest.json'
        h = sha(self.old_raw)
        self.blob = self.put('build/migration-evidence-archive/blobs/' + h[:2] + '/' + h + '.gz',
                             gzip.compress(self.old_raw, mtime=0))
        self.write_json(self.manifest, dict(status='ARCHIVED_VERIFIED_PRUNED', entries=[
            dict(path=str(self.old.relative_to(self.root)), sha256=h, size=len(self.old_raw))]))
        self.cert = dict(bindings={str(self.current): sha(self.current.read_bytes()),
                                  str(self.old): h,
                                  str(self.historical): sha(self.old_source)}, sourceBindings={})
        self.write_json(self.root / self.m.CERT, self.cert)
        self.m.CERT_SHA = sha((self.root / self.m.CERT).read_bytes())
        self.runtime = {}
        for n in self.m.ADMISSIONS:
            self.runtime_put(n, dict(witness=dict(files={str(self.historical): sha(self.older_source)}, aliases={})))
        for n in ['production-scripted.hpp', 'native-derived.cpp', 'driver.cpp', 'clear-case.tsv',
                  'clear-expected.tsv', 'original-1964-catalog.json', 'reference.d', 'candidate.d',
                  'strict-canonical.d', 'reference', 'candidate', 'reference.o', 'candidate.o',
                  'strict-canonical.cpp', 'strict-canonical.o', 'strict-canonical']:
            self.runtime_put(n, {'fixture': n})
        self.report_pins = {}
        for name in self.m.REPORTS:
            report = (dict(successfulLeaves=[], failedLeavesRetained=[]) if name.startswith(self.m.RUNTIME)
                      else dict(inputs={}, products={}, source={}))
            raw = (self.t.dumps(report).encode('ascii') if name.endswith('.typed')
                   else json.dumps(report).encode())
            self.put(name, raw)
            self.report_pins[name] = sha(raw)
        self.m.REPORTS = self.report_pins
        self.closure = self.root / self.m.OUT / 'closure.json'
        self.write_json(self.closure, dict(certificateSha256=self.m.CERT_SHA,
            reportPins=self.report_pins, runtimeFiles=self.runtime))
        self.versions = self.root / self.m.OUT / 'source-versions.json'
        entries = []
        for raw in [self.old_source, self.older_source]:
            copy = self.put(self.m.OUT + '/bytes/' + sha(raw) + '/fixture.hpp', raw)
            entries.append(dict(path=str(self.historical), sha256=sha(raw), size=len(raw), copy=str(copy)))
        self.write_json(self.versions, dict(certificateSha256=self.m.CERT_SHA, entries=entries))

    def put(self, relative, raw):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        return p

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def runtime_put(self, name, value):
        p = self.root / self.m.RUNTIME / name
        self.write_json(p, value)
        self.runtime[str(p.relative_to(self.root))] = dict(sha256=sha(p.read_bytes()), size=p.stat().st_size)

    def pin(self, path):
        return [str(path), sha(path.read_bytes())]

    def run_verify(self, manifests=None, versions=True, closure=None):
        return self.m.verify([self.pin(self.manifest)] if manifests is None else manifests,
                             self.pin(self.versions) if versions else None,
                             self.pin(self.closure) if closure is None else closure)

    def test_positive_current_archive_and_two_versions_same_requested_path(self):
        report = self.run_verify()
        self.assertEqual(report['status'], 'ACCEPTED_TTL_EXACT_BYTES_RETAINED')
        self.assertEqual(report['archivedBindings'], 1)
        self.assertEqual(report['distinctReconstructedBlobs'], 1)
        self.assertEqual(report['versionedSourceBindings'], 2)
        self.assertGreater(report['currentBindings'], 0)
        self.assertFalse(report['originalCurrentOriginReplayAvailable'])

    def test_cached_archive_blob_can_be_resolved_and_read_repeatedly(self):
        resolver = self.m.Resolver([self.pin(self.manifest)])
        for _ in range(3):
            self.assertEqual(resolver.read(str(self.old), sha(self.old_raw)), self.old_raw)
        self.assertEqual(len(resolver.blobs), 1)

    def test_corrupt_blob_rejected_even_with_valid_gzip(self):
        self.blob.write_bytes(gzip.compress(b'wrong but decodable bytes', mtime=0))
        with self.assertRaisesRegex(ValueError, 'archive reconstructed byte integrity'):
            self.run_verify()

    def test_wrong_manifest_pin_rejected(self):
        with self.assertRaisesRegex(ValueError, 'manifest physical pin'):
            self.run_verify(manifests=[[str(self.manifest), '0' * 64]])

    def test_missing_exact_member_rejected_not_hash_search(self):
        value = json.loads(self.manifest.read_bytes())
        value['entries'][0]['path'] += '.other'
        self.write_json(self.manifest, value)
        with self.assertRaisesRegex(ValueError, 'missing exact archive membership'):
            self.run_verify()

    def test_duplicate_membership_rejected(self):
        value = json.loads(self.manifest.read_bytes())
        value['entries'].append(value['entries'][0])
        self.write_json(self.manifest, value)
        with self.assertRaisesRegex(ValueError, 'duplicate archive membership'):
            self.run_verify()

    def test_duplicate_membership_across_successors_rejected(self):
        other = self.root / 'build/migration-evidence-archive/runs/other/manifest.json'
        self.write_json(other, json.loads(self.manifest.read_bytes()))
        with self.assertRaisesRegex(ValueError, 'duplicate archive membership'):
            self.run_verify(manifests=[self.pin(self.manifest), self.pin(other)])

    def test_wrong_source_copy_rejected(self):
        row = json.loads(self.versions.read_bytes())['entries'][0]
        Path(row['copy']).write_bytes(b'changed original source copy')
        with self.assertRaisesRegex(ValueError, 'source-version exact retained bytes'):
            self.run_verify()

    def test_source_versions_required_wrong_pin_and_coherent_replacement_rejected(self):
        with self.assertRaisesRegex(ValueError, 'current byte integrity'):
            self.run_verify(versions=False)
        with self.assertRaisesRegex(ValueError, 'manifest physical pin'):
            self.m.verify([self.pin(self.manifest)], [str(self.versions), '0' * 64], self.pin(self.closure))
        data = json.loads(self.versions.read_bytes())
        row = data['entries'][0]
        raw = b'coherently changed source-copy and manifest is not original'
        Path(row['copy']).write_bytes(raw)
        row.update(sha256=sha(raw), size=len(raw))
        self.write_json(self.versions, data)
        with self.assertRaisesRegex(ValueError, 'current byte integrity'):
            self.run_verify()

    def test_tool_and_product_source_version_substitution_rejected(self):
        resolver = self.m.Resolver([self.pin(self.manifest)], self.pin(self.versions))
        for role in ('tool', 'product'):
            with self.subTest(role=role):
                with self.assertRaisesRegex(ValueError, 'tool/product source-version substitution'):
                    resolver.resolve(str(self.historical), sha(self.old_source), role)

    def update_native_report(self, products):
        name = 'build/ttl-cache-native-r1/report.json'
        self.write_json(self.root / name, dict(inputs={}, source={}, products=products))
        self.report_pins[name] = sha((self.root / name).read_bytes())
        data = json.loads(self.closure.read_bytes())
        data['reportPins'] = self.report_pins
        self.write_json(self.closure, data)

    def test_full_verifier_rejects_source_version_for_original_product_contract(self):
        self.update_native_report({str(self.historical): sha(self.old_source)})
        with self.assertRaisesRegex(ValueError, 'tool/product source-version substitution'):
            self.run_verify()

    def test_full_verifier_rejects_source_version_for_original_tool_contract(self):
        plan = self.root / 'build/native/tool.plan.json'
        self.write_json(plan, dict(tool=dict(requested=str(self.historical),
            sha256=sha(self.old_source), size=len(self.old_source))))
        self.update_native_report({str(plan): sha(plan.read_bytes())})
        with self.assertRaisesRegex(ValueError, 'tool/product source-version substitution'):
            self.run_verify()

    def test_product_path_cannot_be_declared_historical_source(self):
        data = json.loads(self.versions.read_bytes())
        data['entries'][0]['path'] = str(self.current)
        self.write_json(self.versions, data)
        with self.assertRaisesRegex(ValueError, 'first-party source'):
            self.run_verify()

    def test_closure_pin_and_missing_required_member_rejected(self):
        with self.assertRaisesRegex(ValueError, 'manifest physical pin'):
            self.run_verify(closure=[str(self.closure), '0' * 64])
        data = json.loads(self.closure.read_bytes())
        del data['runtimeFiles'][self.m.RUNTIME + '/reference.o']
        self.write_json(self.closure, data)
        with self.assertRaisesRegex(ValueError, 'missing required runtime closure member'):
            self.run_verify()

    def test_current_product_and_typed_decoder_corruption_rejected(self):
        self.current.write_bytes(b'changed current bytes')
        with self.assertRaisesRegex(ValueError, 'current byte integrity'):
            self.run_verify()
        self.codec.write_bytes(b'raise RuntimeError("must not execute")')
        with self.assertRaisesRegex(ValueError, 'typed decoder source pin'):
            self.run_verify()

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            self.m.decode('{"same":1,"same":2}')


if __name__ == '__main__':
    unittest.main()
