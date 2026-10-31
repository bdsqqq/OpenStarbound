import json
import tempfile
from pathlib import Path
import unittest
from PIL import Image

import run_current_matrix as matrix


class ComparisonTests(unittest.TestCase):
    def test_pixels_alpha_state_and_frame_set_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            normal = root / 'normal.png'
            changed = root / 'changed.png'
            Image.new('RGBA', (2, 1), (20, 30, 40, 255)).save(normal)
            Image.new('RGBA', (2, 1), (20, 30, 40, 254)).save(changed)
            def frame(path=normal, value=1):
                return {'one': {'png': path, 'receipt': {'worldState': {'value': value}}}}
            self.assertEqual(len(matrix.compare([frame(), frame(), frame()])), 1)
            large = frame(value='x' * (5 * 1024**2))
            summary = matrix.compare([large, large, large])
            self.assertLess(len(json.dumps(summary)), 1024)
            self.assertEqual(len(summary[0]['stateSha256']), 64)
            for candidate in [frame(changed), frame(value=2), {}]:
                with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                    matrix.compare([frame(), frame(), candidate])


if __name__ == '__main__':
    unittest.main()
