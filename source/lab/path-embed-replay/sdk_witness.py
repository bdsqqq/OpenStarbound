"""Current SDK interface byte witness; NOT a TAPI resolver or native acceptance.

Paths use Python's filesystem encoding with surrogateescape. Serialize with
json.dumps(..., ensure_ascii=True) to preserve non-UTF8 filesystem bytes. The
caller must retain an independently frozen manifest; replacing both baseline
and current bytes defeats any hash comparison. No transient edit/revert or
adversarial concurrent filesystem mutation guarantee is made.
"""
import hashlib
import os
import stat


class WitnessError(ValueError):
    pass


def _path(value, absolute=False):
    if type(value) is not str or not value or '\0' in value:
        raise WitnessError('filesystem path string required')
    try:
        if os.fsdecode(os.fsencode(value)) != value:
            raise WitnessError('filesystem path does not round trip')
    except UnicodeError as exc:
        raise WitnessError('unsupported filesystem encoding') from exc
    if absolute and (not value.startswith('/') or os.path.normpath(value) != value):
        raise WitnessError('normalized absolute path required')
    return value


def _within(path, root):
    return os.path.commonpath([path, root]) == root


def _resolve(path, root=None):
    """Resolve each component, including directory aliases, without reading files.

    Only the configured root anchor may resolve outside the SDK. Inside it,
    reject a hop that leaves the root even if later hops could return. Unused
    symlinks are inventoried without resolving, so legitimate external metadata
    links do not disqualify an otherwise usable SDK.
    """
    _path(path)
    if not os.path.isabs(path):
        raise WitnessError('absolute consumed path required')
    if root is None:
        current, pending = '/', path.split('/')[1:]
    else:
        if not _within(path, root):
            raise WitnessError('foreign SDK path')
        current, pending = root, path[len(root):].lstrip('/').split('/')
    hops, seen = [], set()
    while pending:
        part = pending.pop(0)
        if part in ('', '.'):
            continue
        if part == '..':
            current = os.path.dirname(current)
            if root is not None and not _within(current, root):
                raise WitnessError('symlink/path escape')
            continue
        candidate = os.path.join(current, part)
        try:
            mode = os.lstat(candidate).st_mode
        except OSError as exc:
            raise WitnessError('missing/dangling path: ' + candidate) from exc
        if stat.S_ISLNK(mode):
            state = (candidate, tuple(pending))
            if state in seen or len(hops) >= 256:
                raise WitnessError('symlink cycle or unsupported >256 hops')
            seen.add(state)
            target = os.readlink(candidate)
            hops.append({'path': candidate, 'target': target})
            if os.path.isabs(target):
                if root is None:
                    current, target_parts = '/', target.split('/')[1:]
                else:
                    # Check the literal anchor, then evaluate .. componentwise.
                    if not _within(target, root):
                        raise WitnessError('symlink escape')
                    current = root
                    target_parts = target[len(root):].lstrip('/').split('/')
            else:
                target_parts = target.split('/')
            pending = target_parts + pending
        else:
            if pending and not stat.S_ISDIR(mode):
                raise WitnessError('non-directory intermediate component')
            current = candidate
    return current, hops


def _anchors(requested_root, expected_canonical_root):
    requested = _path(requested_root, True)
    expected = _path(expected_canonical_root, True)
    if expected == '/':
        raise WitnessError('SDK root cannot be filesystem root')
    canonical, hops = _resolve(requested)
    expected_resolved, expected_hops = _resolve(expected)
    if canonical != expected or expected_resolved != expected or expected_hops:
        raise WitnessError('independently configured canonical root mismatch')
    if not stat.S_ISDIR(os.lstat(expected).st_mode):
        raise WitnessError('SDK root is not a directory')
    return requested, expected, hops


def _digest(path):
    # O_NONBLOCK prevents a replaced FIFO from hanging before fstat rejects it.
    # O_NOFOLLOW rejects a final-component swap; parent directory races remain
    # outside this static witness contract. No SDK writes occur here.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise WitnessError('interface/settings input is not regular')
        digest = hashlib.sha256()
        size = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(chunk)
            digest.update(chunk)
    return {'size': size, 'sha256': digest.hexdigest()}


def capture(requested_root, expected_canonical_root):
    """Bind ALL physical regular .tbd files, settings, and ALL SDK symlinks.

    Membership is independent of any observed linker map. File bytes are opaque;
    extensions select interface candidates but do not establish TAPI validity.
    """
    requested, root, root_hops = _anchors(requested_root, expected_canonical_root)
    interfaces, symlinks = [], []
    def visit(directory):
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda e: os.fsencode(e.name))
        for entry in ordered:
            relative = os.path.relpath(entry.path, root)
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode):
                symlinks.append({'path': relative, 'target': os.readlink(entry.path)})
            elif stat.S_ISDIR(mode):
                visit(entry.path)
            elif entry.name.endswith('.tbd'):
                if not stat.S_ISREG(mode):
                    raise WitnessError('unsupported nonregular interface input')
                interfaces.append({'path': relative, **_digest(entry.path)})
    visit(root)
    settings = []
    for name in ('SDKSettings.json', 'SDKSettings.plist'):
        path = os.path.join(root, name)
        if os.path.lexists(path):
            resolved, hops = _resolve(path, root)
            settings.append({'path': name, 'canonical': os.path.relpath(resolved, root),
                             'hops': hops, **_digest(resolved)})
    return {'version': 1, 'requested_root': requested, 'canonical_root': root,
            'root_hops': root_hops,
            'interfaces': sorted(interfaces, key=lambda r: os.fsencode(r['path'])),
            'symlinks': sorted(symlinks, key=lambda r: os.fsencode(r['path'])),
            'settings': settings}


def _keys(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise WitnessError('unexpected record fields/type')


def _relative(value):
    _path(value)
    if os.path.isabs(value) or os.path.normpath(value) != value or value in ('.', '..') or value.startswith('../'):
        raise WitnessError('canonical relative path required')


def _hash_record(row):
    if type(row['size']) is not int or row['size'] < 0:
        raise WitnessError('nonnegative integer size required (not bool)')
    digest = row['sha256']
    if type(digest) is not str or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise WitnessError('sha256 required')


def _hops(rows):
    if type(rows) is not list:
        raise WitnessError('hop list required')
    for row in rows:
        _keys(row, ('path', 'target'))
        _path(row['path'], True)
        _path(row['target'])


def _validate(manifest):
    _keys(manifest, ('version', 'requested_root', 'canonical_root', 'root_hops', 'interfaces', 'symlinks', 'settings'))
    if type(manifest['version']) is not int or manifest['version'] != 1:
        raise WitnessError('unsupported manifest version/type')
    _path(manifest['requested_root'], True)
    _path(manifest['canonical_root'], True)
    _hops(manifest['root_hops'])
    for group in ('interfaces', 'symlinks', 'settings'):
        rows = manifest[group]
        if type(rows) is not list:
            raise WitnessError('record list required')
        paths = []
        for row in rows:
            fields = {'interfaces': ('path', 'size', 'sha256'),
                      'symlinks': ('path', 'target'),
                      'settings': ('path', 'canonical', 'hops', 'size', 'sha256')}[group]
            _keys(row, fields)
            _relative(row['path'])
            paths.append(row['path'])
            if group == 'symlinks':
                _path(row['target'])
            else:
                _hash_record(row)
            if group == 'interfaces' and not row['path'].endswith('.tbd'):
                raise WitnessError('noninterface manifest member')
            if group == 'settings':
                if row['path'] not in ('SDKSettings.json', 'SDKSettings.plist'):
                    raise WitnessError('unknown SDK settings')
                _relative(row['canonical'])
                _hops(row['hops'])
        if paths != sorted(set(paths), key=os.fsencode):
            raise WitnessError('duplicate or unordered members')


def verify(manifest, requested_root, expected_canonical_root):
    """Rebuild exact membership and content against an independently held baseline."""
    _validate(manifest)
    current = capture(requested_root, expected_canonical_root)
    if manifest != current:
        raise WitnessError('SDK witness differs from frozen baseline')


def reconcile_consumed(manifest, paths, *, requested_root, expected_canonical_root):
    """Return current consumed interface bindings, preserving order/duplicates.

    Roots are required independently here too: an untrusted manifest cannot
    choose its own trust anchor. This verifies the full snapshot first, then
    requires each consumed resolution hop and physical file to be prebound.
    A future orchestrator must additionally verify the frozen baseline AFTER
    linking and bind actual compiler/linker trace provenance separately.
    """
    verify(manifest, requested_root, expected_canonical_root)
    if type(paths) is not list:
        raise WitnessError('consumed path list required')
    files = {r['path']: r for r in manifest['interfaces']}
    links = {os.path.join(expected_canonical_root, r['path']): r['target'] for r in manifest['symlinks']}
    results = []
    for path in paths:
        _path(path)
        if not os.path.isabs(path):
            raise WitnessError('absolute consumed path required')
        if _within(path, requested_root):
            suffix = path[len(requested_root):].lstrip('/')
            root_hops = manifest['root_hops']
        elif _within(path, expected_canonical_root):
            suffix = path[len(expected_canonical_root):].lstrip('/')
            root_hops = []
        else:
            raise WitnessError('foreign or wrong SDK consumed path')
        canonical, hops = _resolve(os.path.join(expected_canonical_root, suffix), expected_canonical_root)
        for hop in hops:
            if links.get(hop['path']) != hop['target']:
                raise WitnessError('unbound consumed symlink')
        relative = os.path.relpath(canonical, expected_canonical_root)
        if relative not in files:
            raise WitnessError('unbound/noninterface consumed file')
        if _digest(canonical) != {k: files[relative][k] for k in ('size', 'sha256')}:
            raise WitnessError('consumed interface digest changed')
        results.append({'requested': path, 'canonical': canonical,
                        'relative': relative, 'hops': root_hops + hops,
                        'size': files[relative]['size'], 'sha256': files[relative]['sha256']})
    return results
