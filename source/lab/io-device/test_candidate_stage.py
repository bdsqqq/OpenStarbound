"""Selected counter/route verifier failures in isolated synthetic receipts."""
import json
import unittest
import candidate_stage as candidate


class CandidateReceiptTests(unittest.TestCase):
    def encode(self,rows):return ('IO_DEVICE_COUNTS '+json.dumps(rows)+'\n').encode()

    def test_balanced_attempts_bind_actual_returned_routes(self):
        rows=[[2,1,1,1,1,0,0] for _ in range(22)]
        self.assertEqual(candidate.counts(self.encode(rows)),rows)
        rows[2]=[3,0,3,0,3,0,0]  # Always-pending definitions need no success.
        self.assertEqual(candidate.counts(self.encode(rows)),rows)

    def test_native_bypass_and_unknown_return_are_rejected(self):
        for rows in ([[0]*7 for _ in range(22)],[[2,1,1,1,0,1,0] for _ in range(22)]):
            with self.assertRaises(ValueError):candidate.counts(self.encode(rows))

    def test_boolean_cannot_substitute_for_numeric_attempt(self):
        rows=[[True,1,0,1,0,0,0] for _ in range(22)]
        with self.assertRaises(ValueError):candidate.counts(self.encode(rows))

    def test_missing_or_duplicate_observation_is_not_credit(self):
        row=self.encode([[1,1,0,1,0,0,0] for _ in range(22)])
        for data in (b'',row+row,self.encode([])):
            with self.assertRaises(ValueError):candidate.counts(data)


if __name__=='__main__':unittest.main()
