"""Constrain process-requested writes; ownership belongs to admission.

Read access and inherited execution remain unchanged. This profile is not
permission to launch a process or use the network, nor a closure over kernel
or helper I/O. Historical Darwin resource-fork fallback can create shadows
outside the mount before later authorization (xnu-12377.1.9,
bsd/vfs/vfs_xattr.c:getshadowfile). That is a reason to require a separate
filesystem/accounting contract, not evidence of current-provider behavior.
"""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

TOOL = '/usr/bin/sandbox-exec'
VERSION = 2
SCOPE = 'native-writes-only-owned-products'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def physical_path(value):
    need(type(value) is str and value and value.startswith('/'), 'absolute sandbox path')
    need(not any(unicodedata.category(c).startswith('C') for c in value), 'sandbox path control')
    value.encode('utf-8', errors='strict')
    path = Path(value)
    need(str(path) == value and path != Path('/') and
         not any(part in ('.', '..', '') for part in value.split('/')[1:]), 'canonical sandbox path')
    current = path
    while current != current.parent:
        need(not current.is_symlink(), 'sandbox path alias')
        current = current.parent
    need(path.resolve(strict=True) == path and path.is_dir(), 'physical sandbox directory')
    return path


def profile(mount):
    path = str(physical_path(mount))
    # SBPL quoted strings use backslash escapes. Keep UTF-8 literal (not JSON
    # unicode escapes); reject controls rather than relying on parser handling.
    literal = '"' + path.replace('\\', '\\\\').replace('"', '\\"') + '"'
    # Mount operations are separate from file-write*. Helper-mediated device
    # creation is a further boundary, not proved closed by these two denials.
    return ('(version 1)(allow default)(deny file-mount file-unmount)'
            '(deny file-write*)(allow file-write* (subpath ' + literal + '))')


def binding(owner, tool_identity):
    """Derive a typed binding AFTER the caller's current physical owner checks."""
    need(type(owner) is dict and type(tool_identity) is dict, 'sandbox binding objects')
    need(set(tool_identity) == {'path', 'sha256', 'size'} and
         tool_identity['path'] == TOOL and type(tool_identity['sha256']) is str and
         re.fullmatch('[0-9a-f]{64}', tool_identity['sha256']) and
         type(tool_identity['size']) is int and tool_identity['size'] > 0, 'sandbox tool identity')
    mount = owner['mount']
    need(type(mount) is dict and set(mount) == {'path', 'st_dev'} and
         type(mount['st_dev']) is int and mount['st_dev'] > 0, 'sandbox mount binding')
    root = physical_path(owner['root'])
    need(type(mount['path']) is str and Path(mount['path']) != root and
         Path(mount['path']).is_relative_to(root), 'owner products root')
    need(all(type(owner[key]) is str and re.fullmatch('/dev/disk[0-9]+(?:s[0-9]+)?', owner[key])
             for key in ('device', 'volumeDevice')), 'sandbox device binding')
    text = profile(mount['path'])
    return dict(version=VERSION, scope=SCOPE, tool=dict(tool_identity), root=owner['root'],
                mount=dict(mount), device=owner['device'], volumeDevice=owner['volumeDevice'],
                profile=text, profileSha256=hashlib.sha256(text.encode('utf-8')).hexdigest())


def same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def wrap(mount, argv):
    need(type(argv) is list and argv and all(type(word) is str and word and '\x00' not in word for word in argv),
         'nonempty sandbox argv strings')
    need(not any(Path(word).name == 'sandbox-exec' for word in argv), 'double sandbox wrapper')
    return [TOOL, '-p', profile(mount), *argv]


def validate_command(mount, argv):
    need(type(argv) is list and len(argv) > 3 and argv[:3] == [TOOL, '-p', profile(mount)],
         'exact Native sandbox prefix required')
    need(argv == wrap(mount, argv[3:]), 'single exact Native sandbox wrapper')
    return argv
