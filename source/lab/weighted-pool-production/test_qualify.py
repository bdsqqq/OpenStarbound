"""Pure composition controls; no native execution or certificate creation."""
import copy
import unittest
import qualify as q


class QualificationControlsTests(unittest.TestCase):
    def test_all_seven_process_corruptions_detected(self):
        self.assertEqual(q.controls(), ['abort', 'unreaped', 'wrong PID', 'wrong PGID', 'wrong OS identity', 'wrong binary', 'missing launch binding'])

    def test_all_four_raw_envelope_corruptions_detected(self):
        self.assertEqual(q.schema.controls(), ['metadata', 'file', 'width', 'capture'])

    def test_manifest_binary_cannot_be_rebound(self):
        start = dict(pid=9, pgid=9, status='started', osStart='stable', binary=dict(sha256='original'))
        end = dict(pid=9, pgid=9, status='reaped', exitCode=0, osStart='stable', startReceipt=dict(sha256='launch'))
        manifest = dict(binary=copy.deepcopy(start['binary']), processStart=copy.deepcopy(end['startReceipt']))
        q.process(start, end, manifest)
        manifest['binary']['sha256'] = 'substitute'
        with self.assertRaisesRegex(ValueError, 'process source binding'):
            q.process(start, end, manifest)


if __name__ == '__main__':
    unittest.main()
