"""Synthetic verifier fixtures; these are NOT native startup or Font evidence."""
from copy import deepcopy
from pathlib import Path
import unittest
from PIL import Image, ImageDraw
import option_parser_proof as proof
import option_parser_cli as cli


def fixture(backend='rust', base='/owned/run'):
    path = base + '/sbinit.config'
    storage = base + '/frames/storage'
    boot = {'assetDirectories': [], 'assetSources': ['/immutable/packed.pak'],
            'storageDirectory': storage, 'logDirectory': storage,
            'defaultConfiguration': {'optionParserProof': deepcopy(proof.CONFIGURATION)}}
    counts = deepcopy(proof.RUST_COUNTS if backend == 'rust' else [[0, 0, 0] for _ in range(8)])
    root = {'nativeRootSettingsObservations': 1, 'bootConfigPath': path,
            'sourceJson': boot, 'assetDirectories': [], 'assetSources': ['/immutable/packed.pak'],
            'storageDirectory': storage, 'defaultConfiguration': deepcopy(boot['defaultConfiguration']),
            'logLevel': 'Info', 'quiet': False, 'afterRootSettingsCounters': deepcopy(counts)}
    startup = {'nativeParseObservations': 1, 'arguments': ['-bootconfig', path], 'switches': [],
               'parameters': {'bootconfig': [path]}, 'positional': [], 'errors': [],
               'afterParseCounters': deepcopy(counts), 'root': root}
    return {'cameraPosition': [64, 48], 'cameraPixelRatio': 2, 'optionParserProof': {
        'version': 1, 'backend': backend, 'startup': startup,
        'rootConfiguration': deepcopy(proof.CONFIGURATION),
        'visual': {'configuration': deepcopy(proof.CONFIGURATION), 'imagePath': proof.IMAGE,
                   'color': deepcopy(proof.COLOR), 'label': 'OPTIONS', 'scale': 4},
        'sourceSize': [16, 16], 'displaySize': [64, 64],
        'configurationConsumer': 'normal-root-lua-getConfiguration', 'imageConsumer': 'normal-Assets-image',
        'labelConsumer': 'normal-Font-TextPainter', 'mainThreadCounters': counts}}


class OptionParserProofTests(unittest.TestCase):
    def test_cli_literal_verifier_and_help_error_precedence(self):
        for name in ('help', 'help-with-error'):
            cli.validate(name, 0, cli.PREAMBLE + cli.HELP)
            with self.assertRaises(ValueError):
                cli.validate(name, 1, cli.HELP)
        for name, message in cli.ERRORS.items():
            cli.validate(name, 1, cli.PREAMBLE + ('Error: ' + message + '\n\n').encode() + cli.HELP)
            with self.assertRaises(ValueError):
                cli.validate(name, 1, cli.HELP)
        with self.assertRaises(ValueError):
            cli.validate('help', 0, cli.HELP + b'error')

    def test_cpp_rust_and_owned_path_projection(self):
        self.assertEqual(proof.validate(fixture('cpp', '/owned/reference')),
                         proof.validate(fixture('rust', '/owned/candidate')))

    def test_real_launcher_binding(self):
        receipt = fixture()
        boot = receipt['optionParserProof']['startup']['root']['sourceJson']
        proof.bind(receipt, Path('/owned/run/sbinit.config'), deepcopy(boot))
        with self.assertRaises(ValueError):
            proof.bind(receipt, Path('/owned/other/sbinit.config'), boot)
        changed = deepcopy(boot)
        changed['assetSources'].append('/foreign/source')
        with self.assertRaises(ValueError):
            proof.bind(receipt, Path('/owned/run/sbinit.config'), changed)

    def test_counter_suppression(self):
        receipt = fixture()
        receipt['optionParserProof']['mainThreadCounters'][6] = [0, 0, 0]
        with self.assertRaises(ValueError):
            proof.validate(receipt)

    def test_false_cpp_backend(self):
        receipt = fixture()
        receipt['optionParserProof']['backend'] = 'cpp'
        with self.assertRaises(ValueError):
            proof.validate(receipt)

    def test_changed_consumed_argument(self):
        receipt = fixture()
        receipt['optionParserProof']['startup']['arguments'].append('--')
        with self.assertRaises(ValueError):
            proof.validate(receipt)

    def test_lost_root_value(self):
        receipt = fixture()
        receipt['optionParserProof']['startup']['root']['defaultConfiguration']['optionParserProof']['label'] = 'SHADOW'
        with self.assertRaises(ValueError):
            proof.validate(receipt)

    def test_fake_consumer_and_boolean_counter(self):
        for field, value in [('imageConsumer', 'kernel-loop'), ('version', True)]:
            receipt = fixture()
            receipt['optionParserProof'][field] = value
            with self.assertRaises(ValueError):
                proof.validate(receipt)
        receipt = fixture()
        receipt['optionParserProof']['mainThreadCounters'][6][0] = True
        with self.assertRaises(ValueError):
            proof.validate(receipt)

    def test_malformed_source_defaults_rejected_cleanly(self):
        receipt = fixture()
        receipt['optionParserProof']['startup']['root']['sourceJson']['defaultConfiguration'] = []
        with self.assertRaises(ValueError):
            proof.validate(receipt)

    def test_image_geometry_and_label_requirements(self):
        image = Image.new('RGBA', (1000, 600), (0, 0, 0, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((468, 268, 531, 331), fill=tuple(proof.COLOR))
        with self.assertRaises(ValueError):
            proof.visible(image, fixture())
        draw.rectangle((490, 220, 509, 223), fill=(255, 255, 255, 255))
        proof.visible(image, fixture())
        draw.rectangle((436, 236, 563, 363), fill=tuple(proof.COLOR))
        with self.assertRaises(ValueError):
            proof.visible(image, fixture())


if __name__ == '__main__':
    unittest.main()
