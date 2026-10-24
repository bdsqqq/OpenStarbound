"""Source-derived startup/Root/configuration consumers, not a parser round trip."""
from copy import deepcopy
from pathlib import Path

COLOR = [48, 176, 240, 255]
CONFIGURATION = {'color': COLOR, 'label': 'OPTIONS'}
IMAGE = '/behaviorlab/option-parser.png?multiply=30b0f0ff'
# VersionOptionParser registers help/version; RootLoader registers three further
# switches and three parameters. Client startup then calls parseOptions once.
RUST_COUNTS = [[0, 0, 0], [0, 0, 0], [0, 0, 0], [5, 5, 0],
               [3, 3, 0], [0, 0, 0], [1, 1, 0], [0, 0, 0]]


def same(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(right, dict):
        return left.keys() == right.keys() and all(same(left[k], right[k]) for k in right)
    if isinstance(right, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return left == right


def require(condition, message):
    if not condition:
        raise ValueError('option parser: ' + message)


def keys(value, names):
    require(type(value) is dict and set(value) == set(names.split()), 'proof schema')


def validate(receipt):
    proof = receipt.get('optionParserProof')
    keys(proof, 'version backend startup rootConfiguration visual sourceSize displaySize configurationConsumer imageConsumer labelConsumer mainThreadCounters')
    require(type(proof['version']) is int and proof['version'] == 1, 'version')
    require(proof['backend'] in ('cpp', 'rust'), 'backend')
    require(same(proof['rootConfiguration'], CONFIGURATION), 'literal loaded Root configuration')
    require(same(proof['sourceSize'], [16, 16]) and same(proof['displaySize'], [64, 64]), 'image dimensions')
    require(proof['configurationConsumer'] == 'normal-root-lua-getConfiguration'
            and proof['imageConsumer'] == 'normal-Assets-image'
            and proof['labelConsumer'] == 'normal-Font-TextPainter', 'normal consumers')
    visual = {'configuration': CONFIGURATION, 'imagePath': IMAGE, 'color': COLOR, 'label': 'OPTIONS', 'scale': 4}
    require(same(proof['visual'], visual), 'literal Lua-derived image/Font source')
    startup = proof['startup']
    keys(startup, 'nativeParseObservations arguments switches parameters positional errors afterParseCounters root')
    require(type(startup['nativeParseObservations']) is int and startup['nativeParseObservations'] == 1, 'actual parse observation')
    root = startup['root']
    keys(root, 'nativeRootSettingsObservations bootConfigPath sourceJson assetDirectories assetSources storageDirectory defaultConfiguration logLevel quiet afterRootSettingsCounters')
    require(type(root['nativeRootSettingsObservations']) is int and root['nativeRootSettingsObservations'] == 1, 'actual Root settings observation')
    path = root['bootConfigPath']
    require(type(path) is str and Path(path).is_absolute() and Path(path).name == 'sbinit.config', 'explicit boot configuration')
    require(same(startup['arguments'], ['-bootconfig', path]) and same(startup['parameters'], {'bootconfig': [path]}), 'actual argument/parameter consumption')
    require(all(same(startup[k], []) for k in ('switches', 'positional', 'errors')), 'unexpected startup options/errors')
    require(type(root['sourceJson']) is dict and type(root['defaultConfiguration']) is dict, 'native configuration objects')
    boot = root['sourceJson']
    require(type(boot.get('defaultConfiguration')) is dict, 'boot default configuration object')
    require(same(boot['defaultConfiguration'].get('optionParserProof'), CONFIGURATION)
            and same(root['defaultConfiguration'].get('optionParserProof'), CONFIGURATION), 'boot defaults propagated')
    require(same(root['assetDirectories'], boot.get('assetDirectories'))
            and same(root['assetSources'], boot.get('assetSources'))
            and same(root['storageDirectory'], boot.get('storageDirectory')), 'actual Root source fields')
    require(root['logLevel'] == 'Info' and root['quiet'] is False, 'native logging defaults')
    expected = RUST_COUNTS if proof['backend'] == 'rust' else [[0, 0, 0] for _ in range(8)]
    require(all(same(value, expected) for value in (startup['afterParseCounters'], root['afterRootSettingsCounters'], proof['mainThreadCounters'])), 'real startup backend counters')
    # Path projection is only for comparison. bind() additionally checks these
    # bytes against the actual owned launcher file before a capture is accepted.
    normalized = deepcopy(proof)
    normalized.pop('backend')
    normalized.pop('mainThreadCounters')
    state = normalized['startup']
    state.pop('afterParseCounters')
    state['arguments'][1] = '<owned-bootconfig>'
    state['parameters']['bootconfig'][0] = '<owned-bootconfig>'
    state['root'].pop('afterRootSettingsCounters')
    state['root']['bootConfigPath'] = '<owned-bootconfig>'
    state['root']['storageDirectory'] = '<owned-storage>'
    for field in ('storageDirectory', 'logDirectory'):
        require(type(state['root']['sourceJson'].get(field)) is str, 'owned source directory')
        state['root']['sourceJson'][field] = '<owned-storage>'
    return normalized


def bind(receipt, boot_path, boot_json):
    """Bind projected path fields to the actual sentinel-owned launch artifact."""
    validate(receipt)
    root = receipt['optionParserProof']['startup']['root']
    require(root['bootConfigPath'] == str(Path(boot_path).absolute()), 'launcher boot path mismatch')
    require(same(root['sourceJson'], boot_json), 'launcher source JSON mismatch')
    storage = str(Path(boot_path).parent / 'frames' / 'storage')
    require(boot_json.get('storageDirectory') == storage and boot_json.get('logDirectory') == storage,
            'launcher storage escape')


def visible(frame, receipt):
    require(receipt.get('cameraPosition') == [64, 48] and receipt.get('cameraPixelRatio') == 2
            and min(frame.size) >= 200, 'camera/viewport')
    rgba = frame.convert('RGBA')
    x, y = frame.width // 2, frame.height // 2
    ink = [(i % rgba.width, i // rgba.width) for i, pixel in enumerate(rgba.getdata()) if pixel == tuple(COLOR)]
    require(bool(ink), 'configuration-colored image absent')
    bounds = min(a for a, b in ink), min(b for a, b in ink), max(a for a, b in ink) + 1, max(b for a, b in ink) + 1
    require(len(ink) == 4096 and bounds == (x - 32, y - 32, x + 32, y + 32), 'normal image is not64x64')
    label = frame.crop((x - 100, y - 100, x + 100, y - 40)).convert('RGBA')
    require(list(label.getdata()).count((255, 255, 255, 255)) >= 8, 'normal Font label absent')
