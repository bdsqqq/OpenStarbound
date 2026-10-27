#!/usr/bin/env python3
"""Exact-byte TTL retention, NOT semantic replay or old live-origin renewal.

Normal verification is read-only and subprocess-free. --collect explicitly
prepares historical first-party copies and a runtime closure snapshot ONLY in
build/ttl-retention-r1. Both resulting manifests need independent external pins.
The snapshot supplements the runtime report (which does not itself enumerate
its files); it does not retroactively add producer bindings to that report.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CERT = 'build/ttl-final-qualification-r2/certificate.json'
CERT_SHA = '79d91cc33412c429a496cde890e5254c31bdce65b71445410a2ea467d63aa417'
OUT = 'build/ttl-retention-r1'
RUNTIME = 'build/ttl-production-runtime-r2'
REPORTS = {
    'build/ttl-cache-native-r1/report.json': 'cba3b3c84acc2128bd043400cabd6ed2ebf35fcdde37e6d36e2a870bc7926674',
    'build/ttl-boundary-r1/report.json': 'ce0a8e4ff977edd41e2be59a5ec2edd2800138d9b6b113f070198b915c8d76a0',
    'build/ttl-rust-parity-r1/report.typed': '4c2e0cae5d61e41141915887b76826e1ad2ee4d916a053740e832894f7b92199',
    RUNTIME + '/independent-report-v3.json': 'b7ed52bfe1451465956ff69f5b167a8d75f8f9f754152924322b975e25efaddc',
}
FIRST_PARTY = ('source', 'scripts', 'lib', 'attic', 'cmake', 'nix', 'toolchains', 'triplets')
CODEC_SHA = '973ee8989a9ef1b07a1b62c54bc2906006a9a0cf7b993743f8a57885a7382048'
ADMISSIONS = ('admission.json', 'supplemental-acquisition-admission.json',
              'strict-canonical-admission.json', 'clear-case-admission.json')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def digest(stream):
    h = hashlib.sha256()
    size = 0
    while block := stream.read(1024 * 1024):
        h.update(block)
        size += len(block)
    return h.hexdigest(), size


def file_digest(path):
    with path.open('rb') as stream:
        return digest(stream)


def unique(pairs):
    result = {}
    for k, v in pairs:
        need(k not in result, 'duplicate JSON key: ' + k)
        result[k] = v
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique)


def absolute(name):
    # Retain requested spelling in contracts; lexical normalization is ONLY for
    # safe physical lookup and archive membership, never a new origin claim.
    p = Path(name)
    return Path(os.path.abspath(str(p if p.is_absolute() else ROOT / p)))


def first_party(name):
    p = absolute(name)
    return p.is_relative_to(ROOT) and p.relative_to(ROOT).parts[0] in FIRST_PARTY


def regular(path):
    return stat.S_ISREG(path.lstat().st_mode)


def pinned(path, pin):
    p = absolute(path)
    need(p.resolve() == p and regular(p) and file_digest(p)[0] == pin,
         'manifest physical pin: ' + str(p))
    return decode(p.read_bytes())


class Resolver:
    def __init__(self, manifests, versions=None):
        self.index = {}
        self.pins = {}
        self.cache = {}
        self.blobs = {}
        self.used = {'current': set(), 'archive': set(), 'source-version': set()}
        self.versions = {}
        archive = ROOT / 'build/migration-evidence-archive'
        for name, pin in manifests:
            p = absolute(name)
            need(p.is_relative_to(archive / 'runs'), 'manifest outside archive runs')
            need(str(p) not in self.pins, 'duplicate manifest')
            m = pinned(p, pin)
            need(m['status'] == 'ARCHIVED_VERIFIED_PRUNED', 'manifest not pruned/verified')
            self.pins[str(p)] = pin
            for row in m['entries']:
                rp = Path(row['path'])
                need(not rp.is_absolute() and '..' not in rp.parts and rp.parts[0] == 'build',
                     'archive member outside build')
                key = str(ROOT / rp)
                need(key not in self.index, 'duplicate archive membership: ' + key)
                need(re.fullmatch('[0-9a-f]{64}', row['sha256']) and
                     type(row['size']) is int and row['size'] >= 0, 'archive byte contract')
                self.index[key] = (row, str(p))
        if versions:
            p, pin = versions
            p = absolute(p)
            need(p.is_relative_to(ROOT / OUT), 'source versions outside owned output')
            m = pinned(p, pin)
            need(m['certificateSha256'] == CERT_SHA, 'source-version certificate pin')
            for row in m['entries']:
                key = (row['path'], row['sha256'])
                need(key not in self.versions, 'duplicate source version')
                need(first_party(row['path']), 'source-version must be first-party source')
                copy = absolute(row['copy'])
                need(copy.is_relative_to(p.parent / 'bytes') and copy.resolve() == copy and
                     regular(copy) and copy.stat().st_nlink == 1 and copy.stat().st_uid == os.getuid(),
                     'source-version owned regular copy')
                need(file_digest(copy) == (row['sha256'], row['size']),
                     'source-version exact retained bytes')
                self.versions[key] = row

    def live_hash(self, p):
        canonical = p.resolve(strict=True)
        need(regular(canonical), 'current input not regular: ' + str(p))
        before = canonical.stat()
        stamp = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        if str(canonical) not in self.cache:
            value = file_digest(canonical)
            after = canonical.stat()
            need(stamp == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                 'input changed during hashing')
            self.cache[str(canonical)] = (stamp, value)
        old_stamp, value = self.cache[str(canonical)]
        need(stamp == old_stamp, 'input changed after hashing')
        return value

    def resolve(self, name, sha, role='input', size=None):
        need(isinstance(name, str) and re.fullmatch('[0-9a-f]{64}', sha), 'binding schema')
        key = (name, sha)
        p = absolute(name)
        if key in self.versions:
            need(role not in ('product', 'tool') and first_party(name),
                 'tool/product source-version substitution')
            row = self.versions[key]
            need(size is None or row['size'] == size, 'source-version original byte contract')
            self.used['source-version'].add(key)
            return absolute(row['copy']), row['size'], 'source-version'
        if p.exists():
            actual = self.live_hash(p)
            need(actual[0] == sha and (size is None or actual[1] == size),
                 'current byte integrity: ' + name + ' expected ' + sha)
            self.used['current'].add(key)
            return p, actual[1], 'current'
        need(not p.is_symlink(), 'dangling alias: ' + name)
        need(str(p) in self.index, 'missing exact archive membership: ' + name)
        row, manifest = self.index[str(p)]
        need(row['sha256'] == sha and (size is None or row['size'] == size),
             'archive member hash/size: ' + name)
        blob = ROOT / 'build/migration-evidence-archive/blobs' / sha[:2] / (sha + '.gz')
        if sha not in self.blobs:
            need(blob.resolve() == blob and regular(blob), 'archive blob regular physical path')
            with gzip.open(blob, 'rb') as stream:
                need(digest(stream) == (sha, row['size']), 'archive reconstructed byte integrity')
            self.blobs[sha] = row['size']
        need(self.blobs[sha] == row['size'], 'inconsistent blob size')
        self.used['archive'].add(key)
        return blob, row['size'], 'archive'

    def read(self, name, sha, role='input'):
        path, _, kind = self.resolve(name, sha, role)
        if kind == 'archive':
            with gzip.open(path, 'rb') as stream:
                return stream.read()
        return path.read_bytes()


def typed(raw):
    path = ROOT / 'source/lab/native_evidence_json.py'
    need(file_digest(path)[0] == CODEC_SHA, 'typed decoder source pin')
    spec = importlib.util.spec_from_file_location('ttl_retention_codec', path)
    codec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(codec)
    # This is a typed envelope, not JSON with an object decoder applied later.
    return codec.loads(raw.decode('ascii'))


def contracts(resolver, closure):
    result = {}

    def add(name, sha, role='input', size=None):
        key = (name, sha)
        if key in result:
            old = result[key]
            if role in ('tool', 'product'):
                old['role'] = role
            if size is not None:
                need(old['size'] is None or old['size'] == size, 'conflicting size contract')
                old['size'] = size
        else:
            result[key] = dict(path=name, sha256=sha, role=role, size=size)

    def mapping(values, role='input'):
        for name, sha in values.items():
            add(name, sha, role)

    certificate = decode(resolver.read(CERT, CERT_SHA, 'product'))
    add(CERT, CERT_SHA, 'product')
    mapping(certificate['bindings'])
    mapping(certificate['sourceBindings'], 'source')
    reports = {}
    for name, sha in REPORTS.items():
        raw = resolver.read(name, sha, 'product')
        add(name, sha, 'product')
        reports[name] = typed(raw) if name.endswith('.typed') else decode(raw)
    for name, report in reports.items():
        if name.startswith(RUNTIME):
            continue
        mapping(report['products'], 'product')
        mapping(report.get('source', {}), 'source')
        if isinstance(report['inputs'], dict):
            mapping(report['inputs'])
        else:
            inputs = str(absolute(name).parent / 'inputs.json')
            need(inputs in report['products'], 'original inputs.json not pinned')
            values = decode(resolver.read(inputs, report['products'][inputs], 'product'))
            need(len(values) == report['inputs'], 'original input count')
            mapping(values)
        if 'binary' in report:
            b = report['binary']
            add(b['requested'], b['sha256'], 'product', b['size'])

    need(closure['certificateSha256'] == CERT_SHA and closure['reportPins'] == REPORTS,
         'closure original pins')
    runtime = closure['runtimeFiles']
    for name, row in runtime.items():
        need(absolute(name).is_relative_to(ROOT / RUNTIME), 'closure runtime scope')
        add(name, row['sha256'], 'product', row['size'])
    runtime_report = reports[RUNTIME + '/independent-report-v3.json']
    leaves = runtime_report['successfulLeaves'] + runtime_report['failedLeavesRetained']
    required = set(ADMISSIONS) | {'production-scripted.hpp', 'native-derived.cpp', 'driver.cpp',
        'clear-case.tsv', 'clear-expected.tsv', 'original-1964-catalog.json',
        'reference.d', 'candidate.d', 'strict-canonical.d', 'reference', 'candidate',
        'reference.o', 'candidate.o', 'strict-canonical.cpp', 'strict-canonical.o', 'strict-canonical'}
    for leaf in leaves:
        required.update(leaf + suffix for suffix in
                        ('.plan.json', '.receipt.json', '.started.json', '.stdin', '.stdout', '.stderr'))
    need({RUNTIME + '/' + p for p in required} <= set(runtime), 'missing required runtime closure member')
    for admission in ADMISSIONS:
        name = RUNTIME + '/' + admission
        witness = decode(resolver.read(name, runtime[name]['sha256'], 'product'))['witness']
        mapping(witness['files'])
        # Alias spelling is retained in the original admission. Retention checks
        # its bytes, not renewed historical symlink/native-origin attestations.
        need(isinstance(witness['aliases'], dict), 'historical aliases schema')
    for leaf in leaves:
        prefix = RUNTIME + '/' + leaf
        plan = decode(resolver.read(prefix + '.plan.json', runtime[prefix + '.plan.json']['sha256'], 'product'))
        receipt = decode(resolver.read(prefix + '.receipt.json', runtime[prefix + '.receipt.json']['sha256'], 'product'))
        for ext in ('stdout', 'stderr'):
            add(prefix + '.' + ext, receipt[ext + 'Sha256'], 'product')
        add(prefix + '.stdin', plan['stdinSha256'], 'product')
        # Executable providers must never use a source-version waiver, even if
        # an executable happens to live under a first-party source directory.
        tool = plan['argv'][0]
        for key, row in list(result.items()):
            if absolute(row['path']) == absolute(tool):
                row['role'] = 'tool'
    # Tool identity records are original byte contracts too. Check both names
    # without claiming that today's aliases renew historical native origins.
    for row in list(result.values()):
        name = row['path']
        if name.endswith(('.plan.json', '.receipt.json', '.plan', '.receipt')):
            raw = resolver.read(name, row['sha256'], 'product')
            document = typed(raw) if name.endswith(('.plan', '.receipt')) else decode(raw)
            for field in ('tool', 'tool_before', 'tool_after'):
                tool = document.get(field)
                if isinstance(tool, dict) and 'sha256' in tool:
                    for key in ('requested', 'canonical', 'resolved'):
                        if key in tool:
                            add(tool[key], tool['sha256'], 'tool', tool.get('size'))
    return result


def verify(manifests, source_versions, closure_pin):
    need(closure_pin is not None, 'explicit closure manifest pin required')
    need(absolute(closure_pin[0]).is_relative_to(ROOT / OUT), 'closure outside owned output')
    closure = pinned(*closure_pin)
    resolver = Resolver(manifests, source_versions)
    rows = contracts(resolver, closure)
    for row in rows.values():
        resolver.resolve(row['path'], row['sha256'], row['role'], row['size'])
    need(set(resolver.versions) <= set(rows), 'unbound source-version entry')
    # A version cannot hide behind a different role on the same contract.
    for key in resolver.versions:
        need(rows[key]['role'] not in ('tool', 'product'), 'tool/product source-version substitution')
    certificate = decode(resolver.read(CERT, CERT_SHA, 'product'))
    return dict(status='ACCEPTED_TTL_EXACT_BYTES_RETAINED', certificateSha256=CERT_SHA,
        retentionVerifierSha256=file_digest(Path(__file__).resolve())[0], typedDecoderSha256=CODEC_SHA,
        applicationBindingEntries=len(certificate['bindings']),
        applicationSourceBindingEntries=len(certificate['sourceBindings']),
        reportPins=REPORTS, archiveManifestPins=resolver.pins,
        sourceVersionsPin=source_versions, closurePin=closure_pin,
        bindingContracts=len(rows), requestedPaths=len({k[0] for k in rows}),
        currentBindings=len(resolver.used['current']), archivedBindings=len(resolver.used['archive']),
        versionedSourceBindings=len(resolver.used['source-version']),
        distinctReconstructedBlobs=len(resolver.blobs), runtimeSnapshotFiles=len(closure['runtimeFiles']),
        historicalSourceVersions=sorted([list(k) for k in resolver.used['source-version']]),
        originalCurrentOriginReplayAvailable=False,
        limits=['retention ONLY; no fresh semantics/native acquisition/inode/ctime/source live-origin renewal',
                'runtime closure is an externally pinned retention snapshot, not retroactive producer binding',
                'original certificate, reports, scopes, flags and finite semantic limitations unchanged'])


def collect(manifests):
    # Git recovery is deliberately confined to explicit preparation; normal
    # verification never imports subprocess or consults Git history.
    import subprocess
    out = ROOT / OUT
    need(not out.exists(), 'collect requires a fresh owned output tree')
    resolver = Resolver(manifests)
    runtime = {}
    for p in sorted((ROOT / RUNTIME).rglob('*')):
        if p.is_file():
            need(not p.is_symlink() and regular(p), 'runtime snapshot regular member')
            sha, size = file_digest(p)
            runtime[str(p.relative_to(ROOT))] = dict(sha256=sha, size=size)
    closure = dict(certificateSha256=CERT_SHA, reportPins=REPORTS, runtimeFiles=runtime)
    rows = contracts(resolver, closure)
    versions = []
    recovered = {}
    for row in rows.values():
        name, sha = row['path'], row['sha256']
        p = absolute(name)
        if not first_party(name) or row['role'] in ('tool', 'product'):
            continue
        if p.exists() and resolver.live_hash(p)[0] == sha:
            continue
        rel = str(p.relative_to(ROOT))
        key = (rel, sha)
        if key not in recovered:
            commits = subprocess.check_output(['git', 'rev-list', '--all', '--', rel], cwd=ROOT, text=True).splitlines()
            raw = None
            for commit in commits:
                candidate = subprocess.run(['git', 'show', commit + ':' + rel], cwd=ROOT,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if candidate.returncode == 0 and hashlib.sha256(candidate.stdout).hexdigest() == sha:
                    raw = candidate.stdout
                    break
            need(raw is not None, 'no exact historical first-party Git version: ' + name + ' ' + sha)
            recovered[key] = (raw, commit)
        raw, commit = recovered[key]
        copy = out / 'bytes' / sha / rel
        if not copy.exists():
            copy.parent.mkdir(parents=True, exist_ok=True)
            with copy.open('xb') as stream:
                stream.write(raw)
        versions.append(dict(path=name, sha256=sha, size=len(raw), copy=str(copy), gitCommit=commit))
    out.mkdir(parents=True, exist_ok=True)
    for name, value in [('closure.json', closure), ('source-versions.json',
            dict(certificateSha256=CERT_SHA, entries=versions))]:
        with (out / name).open('x') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
    need(sum(p.stat().st_size for p in out.rglob('*') if p.is_file()) <= 16 * 1024**2,
         'owned output exceeds 16MiB')
    print(json.dumps({name: file_digest(out / name)[0] for name in
                      ('closure.json', 'source-versions.json')}, sort_keys=True))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', nargs=2, action='append', default=[], metavar=('PATH', 'SHA256'))
    ap.add_argument('--source-versions', nargs=2, metavar=('PATH', 'SHA256'))
    ap.add_argument('--closure', nargs=2, metavar=('PATH', 'SHA256'))
    ap.add_argument('--collect', action='store_true')
    a = ap.parse_args()
    if a.collect:
        need(not a.source_versions and not a.closure, 'collect does not accept preexisting version/closure pins')
        collect(a.manifest)
    else:
        def forbid(event, args):
            if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork',
                         'os.forkpty', 'os.exec', 'pty.spawn'}:
                raise ValueError('retention verification is subprocess-free')
        sys.addaudithook(forbid)
        print(json.dumps(verify(a.manifest, a.source_versions, a.closure), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
