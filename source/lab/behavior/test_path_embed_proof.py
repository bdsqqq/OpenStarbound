"""Synthetic sensitivity corpus only: no native game, frames, or qualification."""
import base64
import copy
import io
import json
import unittest
from PIL import Image, ImageDraw
import path_embed_proof as p

RAW = '{"frameList":{"reserved%:?;/":[16,0,32,16],"wrong":[0,0,16,16]},"aliases":{"crop":"reserved%:?;/"}}'
ESCAPED = '{"frameList"%c{"reserved%%%c%q%s%b"%c[16,0,32,16],"wrong"%c[0,0,16,16]},"aliases"%c{"crop"%c"reserved%%%c%q%s%b"}}'


def fixture(backend='rust'):
    image = Image.frombytes('RGBA', (32, 16), p.pixels())
    output = io.BytesIO()
    image.save(output, format='PNG')
    encoded = base64.urlsafe_b64encode(output.getvalue()).decode().rstrip('=')
    path = '/opensb_data;image;' + encoded + ';frames;text;' + ESCAPED
    wanted = int(backend == 'rust')
    measurement = {'version': 1, 'backend': backend, 'scopeThread': 'lua-calling-thread', 'completed': True,
        'operationCount': 1, 'before': {'selector': 0, 'escape': 0},
        'after': {'selector': wanted, 'escape': wanted}, 'delta': {'selector': wanted, 'escape': wanted},
        'method': 'None', 'framesMode': 'text', 'path': path, 'rawFrames': RAW, 'escapedFrames': ESCAPED}
    source = {'version': 1, 'measurement': measurement, 'basePath': path, 'cropPath': path + ':crop',
        'selectedAlias': 'crop', 'reservedFrameName': 'reserved%:?;/', 'seedSize': [32, 16],
        'selectedRect': [16, 0, 32, 16], 'wrongRect': [0, 0, 16, 16]}
    proof = {'version': 1, 'backend': backend, 'source': source, 'parsedFrames': copy.deepcopy(p.PARSED_FRAMES),
        'images': {name: {'size': [16 if crop else 32, 16], 'layout': 'native-bottom-up-rgba8',
            'rgbaHex': p.pixels(crop=crop, native=True).hex()} for name, crop in (('base', False), ('crop', True))},
        'ownership': {'baseHeld': True, 'cropHeld': True, 'baseIdentityUnchanged': True,
            'cropIdentityUnchanged': True, 'distinctImages': True, 'baseAcquisitions': 1, 'cropAcquisitions': 1},
        'network': {'transport': 'tcp', 'address': '127.0.0.1', 'rulesVersion': 5, 'streamEnabled': False,
            'universeHandshake': False, 'ownedBindSucceeded': True,
            'rounds': [{'direction': 'a-to-b', 'sentText': text, 'receivedText': text, 'sendMode': 0,
                       'receivedData': {}} for text in (path, path + ':crop', 'PATHEMBED')]},
        'visual': {'imagePath': path + ':crop', 'basePath': path, 'scale': 4, 'displaySize': [64, 64],
            'center': [64, 48], 'fullbright': True, 'consumer': 'WorldPainter.foregroundOverlays', 'label': 'PATHEMBED'}}
    return {'pathEmbedProof': proof, 'cameraPosition': [64, 48], 'cameraPixelRatio': 2}


def frame():
    """Synthetic negative-control framebuffer, NEVER a captured game frame."""
    image = Image.new('RGBA', (400, 240), (21, 20, 19, 255))
    crop = Image.frombytes('RGBA', (16, 16), p.pixels(crop=True)).resize((64, 64), Image.Resampling.NEAREST)
    image.paste(crop, (168, 88))
    ImageDraw.Draw(image).rectangle((165, 40, 234, 43), fill=(255, 255, 255, 255))
    return image


def nodes(value, path=()):
    yield path, value
    if type(value) is dict:
        for key, child in value.items():
            yield from nodes(child, path + (key,))
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from nodes(child, path + (index,))


def at(value, path):
    for part in path:
        value = value[part]
    return value


class PathEmbedProofTests(unittest.TestCase):
    def test_native_rust_normalization_and_visible_literal(self):
        self.assertEqual(p.validate(fixture('native')), p.validate(fixture('rust')))
        for backend in ('native', 'rust'):
            receipt = fixture(backend)
            p.visible(frame(), receipt)
            p.validate_snapshots([copy.deepcopy(receipt) for _ in range(3)])
        self.assertEqual(p.escape(RAW), ESCAPED)

    def test_model_matches_frozen_input_not_candidate(self):
        from pathlib import Path
        seed = Path(__file__).parent / 'path-embed-assets/behaviorlab/path-embed-seed.png'
        with Image.open(seed) as image:
            self.assertEqual(image.size, (32, 16))
            self.assertEqual(image.tobytes(), p.pixels())
        self.assertEqual(p.pixels(crop=True)[(1 * 16 + 1) * 4: (1 * 16 + 1) * 4 + 4], bytes([255]*4))
        self.assertNotEqual(p.pixels(crop=True), p.pixels(crop=True, native=True))

    def test_every_required_member_missing_or_extra_rejected(self):
        original = fixture()
        for path, value in nodes(original['pathEmbedProof'], ('pathEmbedProof',)):
            if type(value) is not dict:
                continue
            for key in value:
                receipt = copy.deepcopy(original)
                del at(receipt, path)[key]
                with self.subTest(path=path, missing=key), self.assertRaises(ValueError):
                    p.validate(receipt)
            receipt = copy.deepcopy(original)
            at(receipt, path)['unexpected'] = 0
            with self.subTest(path=path, extra=True), self.assertRaises(ValueError):
                p.validate(receipt)
        with self.assertRaises(ValueError):
            p.validate({})

    def test_every_integer_rejects_bool_float_negative(self):
        original = fixture()
        for path, value in nodes(original['pathEmbedProof'], ('pathEmbedProof',)):
            if type(value) is not int:
                continue
            for bad in (bool(value), float(value), -1):
                receipt = copy.deepcopy(original)
                at(receipt, path[:-1])[path[-1]] = bad
                with self.subTest(path=path, bad=bad), self.assertRaises(ValueError):
                    p.validate(receipt)

    def test_each_boolean_requires_exact_value_and_type(self):
        original = fixture()
        for path, value in nodes(original['pathEmbedProof'], ('pathEmbedProof',)):
            if type(value) is not bool:
                continue
            for bad in (not value, int(value), None):
                receipt = copy.deepcopy(original)
                at(receipt, path[:-1])[path[-1]] = bad
                with self.subTest(path=path, bad=bad), self.assertRaises(ValueError):
                    p.validate(receipt)

    def test_counter_zero_bypass_stale_alias_and_wrong_backend_rejected(self):
        for backend in ('native', 'rust'):
            for name in ('selector', 'escape'):
                for field, value in (('before', 1), ('after', 0 if backend == 'rust' else 1),
                                     ('delta', 0 if backend == 'rust' else 1)):
                    receipt = fixture(backend)
                    receipt['pathEmbedProof']['source']['measurement'][field][name] = value
                    with self.subTest(backend=backend, name=name, field=field), self.assertRaises(ValueError):
                        p.validate(receipt)
        for bad in ('cpp', 'Rust', '', None, True, 1, []):
            receipt = fixture()
            receipt['pathEmbedProof']['backend'] = bad
            with self.subTest(backend=bad), self.assertRaises(ValueError):
                p.validate(receipt)
        receipt = fixture()
        receipt['pathEmbedProof']['source']['measurement']['backend'] = 'native'
        with self.assertRaises(ValueError):
            p.validate(receipt)

    def test_wrong_alias_rect_frame_raw_escape_and_parser_rejected(self):
        mutations = [
            lambda q: q['source'].update(cropPath=q['source']['basePath'] + ':wrong'),
            lambda q: q['source'].update(selectedRect=[0, 0, 16, 16]),
            lambda q: q['source']['measurement'].update(rawFrames=RAW.replace('16,0,32,16', '0,0,16,16')),
            lambda q: q['source']['measurement'].update(rawFrames=RAW.replace('[16,0,32,16]', '[16.0,0,32,16]')),
            lambda q: q['source']['measurement'].update(rawFrames=RAW[:-1]+',"aliases":{"crop":"wrong"}}'),
            lambda q: q['source']['measurement'].update(escapedFrames=ESCAPED.replace('%%%c', '%%c')),
            lambda q: q['parsedFrames']['aliases'].update(crop='wrong'),
            lambda q: q['parsedFrames']['frames'].update({'reserved%:?;/': [0, 0, 16, 16]}),
            lambda q: q['parsedFrames'].update(file='/behaviorlab/proxy.frames'),
            lambda q: q['visual'].update(imagePath='/behaviorlab/path-embed-seed.png'),
            lambda q: q['visual'].update(imagePath=q['source']['basePath']),
            lambda q: q['network']['rounds'][0].update(receivedText='/behaviorlab/proxy.png'),
            lambda q: q['network']['rounds'].reverse(),
            lambda q: q['network']['rounds'].pop(),
        ]
        for number, mutate in enumerate(mutations):
            receipt = fixture()
            mutate(receipt['pathEmbedProof'])
            with self.subTest(mutation=number), self.assertRaises(ValueError):
                p.validate(receipt)

    def test_rebound_bad_producer_png_and_escape_paths_rejected(self):
        def rebind(receipt, path):
            old = receipt['pathEmbedProof']['source']['basePath']
            def visit(value):
                if type(value) is dict:
                    return {k: visit(v) for k, v in value.items()}
                if type(value) is list:
                    return [visit(v) for v in value]
                return value.replace(old, path) if type(value) is str else value
            return visit(receipt)

        for fault in ('wrong-half', 'orientation', 'marker', 'rgb', 'bad-base64', 'padded-base64', 'compressed-selector'):
            receipt = fixture()
            parts = receipt['pathEmbedProof']['source']['basePath'].split(';')
            seed = Image.frombytes('RGBA', (32, 16), p.pixels())
            if fault == 'wrong-half':
                seed.paste((224, 32, 176, 255), (16, 0, 32, 16))
            elif fault == 'orientation':
                seed = seed.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            elif fault == 'marker':
                seed.putpixel((17, 1), (240, 80, 40, 255))
            elif fault == 'rgb':
                seed = seed.convert('RGB')
            output = io.BytesIO()
            seed.save(output, format='PNG')
            parts[2] = base64.urlsafe_b64encode(output.getvalue()).decode().rstrip('=')
            if fault == 'bad-base64':
                parts[2] = '!!!'
            elif fault == 'padded-base64':
                parts[2] += '='
            elif fault == 'compressed-selector':
                parts.insert(2, 'zlib')
            bad = rebind(receipt, ';'.join(parts))
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, 'PNG|base64|None/text'):
                p.validate(bad)
        receipt = fixture()
        old = receipt['pathEmbedProof']['source']['basePath']
        bad = rebind(receipt, old.replace('reserved%%%c%q%s%b', 'reserved%%%q%q%s%b'))
        bad['pathEmbedProof']['source']['measurement']['escapedFrames'] = ESCAPED.replace('reserved%%%c%q%s%b', 'reserved%%%q%q%s%b')
        with self.assertRaisesRegex(ValueError, 'escaped text'):
            p.validate(bad)

    def test_decoded_pixels_layout_orientation_ownership_rejected(self):
        for name in ('base', 'crop'):
            for field, value in (('rgbaHex', p.pixels(crop=name == 'crop').hex()),
                                 ('layout', 'top-down-rgba8'), ('size', [32, 16] if name == 'crop' else [16, 16])):
                receipt = fixture()
                receipt['pathEmbedProof']['images'][name][field] = value
                with self.subTest(name=name, field=field), self.assertRaises(ValueError):
                    p.validate(receipt)
        for key in fixture()['pathEmbedProof']['ownership']:
            receipt = fixture()
            receipt['pathEmbedProof']['ownership'][key] = False if type(receipt['pathEmbedProof']['ownership'][key]) is bool else 2
            with self.subTest(ownership=key), self.assertRaises(ValueError):
                p.validate(receipt)

    def test_every_decoded_pixel_channel_change_rejected(self):
        # Probe every RGBA byte, including the wrong half and both asymmetric
        # orientation markers, without trusting an image digest alone.
        original = fixture()
        for name in ('base', 'crop'):
            raw = bytes.fromhex(original['pathEmbedProof']['images'][name]['rgbaHex'])
            for offset in range(len(raw)):
                receipt = copy.deepcopy(original)
                bad = raw[:offset] + bytes([raw[offset] ^ 1]) + raw[offset + 1:]
                receipt['pathEmbedProof']['images'][name]['rgbaHex'] = bad.hex()
                with self.subTest(image=name, offset=offset), self.assertRaises(ValueError):
                    p.validate(receipt)

    def test_stage_snapshots_reject_missing_backend_switch_and_stale_counter(self):
        receipt = fixture()
        for snapshots in ([], [receipt], [receipt]*2, [receipt]*4,
                          [fixture('native'), fixture('rust'), fixture('rust')]):
            with self.assertRaises(ValueError):
                p.validate_snapshots(snapshots)
        snapshots = [fixture() for _ in range(3)]
        m = snapshots[1]['pathEmbedProof']['source']['measurement']
        m['before'] = {'selector': 3, 'escape': 4}
        m['after'] = {'selector': 4, 'escape': 5}
        p.validate(snapshots[1])
        with self.assertRaisesRegex(ValueError, 'changed across stages'):
            p.validate_snapshots(snapshots)

    def test_visible_rejects_proxy_wrong_half_flip_scale_and_label(self):
        receipt = fixture()
        for fault in ('missing', 'wrong-half', 'flipped', 'scaled', 'label'):
            image = frame()
            crop = Image.frombytes('RGBA', (16, 16), p.pixels(crop=True))
            if fault == 'missing':
                image.paste((0, 0, 0, 255), (168, 88, 232, 152))
            elif fault == 'wrong-half':
                image.paste((224, 32, 176, 255), (168, 88, 232, 152))
            elif fault == 'flipped':
                image.paste(crop.transpose(Image.Transpose.FLIP_TOP_BOTTOM).resize((64, 64), Image.Resampling.NEAREST), (168, 88))
            elif fault == 'scaled':
                image.paste(crop.resize((60, 60), Image.Resampling.NEAREST), (168, 88))
            else:
                image.paste((0, 0, 0, 255), (100, 20, 300, 80))
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                p.visible(image, receipt)
        for field, value in (('cameraPosition', [True, 48]), ('cameraPosition', [64, 49]),
                             ('cameraPixelRatio', True), ('cameraPixelRatio', float('nan'))):
            bad = fixture()
            bad[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                p.visible(frame(), bad)


if __name__ == '__main__':
    unittest.main()
