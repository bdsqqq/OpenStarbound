"""A Python-advertised scene must survive the native startup safety gate."""
import re
import unittest
import behavior_lab as lab


def check_native_scenarios(source, scenarios):
    function = source.split("void ClientApplication::validateBehaviorStorage()", 1)[1]
    gate = function.split('throw StarException("BehaviorLab: unsupported scenario")', 1)[0]
    allowed = re.findall(r'scenario != "([a-z0-9-]+)"', gate)
    if not allowed or set(allowed) != set(scenarios):
        raise ValueError("native startup scenario allowlist differs from advertised scenes")


class NativeScenarioContractTests(unittest.TestCase):
    def test_every_advertised_scenario_is_accepted(self):
        source = (lab.ROOT / "source/client/StarClientApplication.cpp").read_text()
        check_native_scenarios(source, lab.SCENARIOS)

    def test_known_missing_scene_is_detected_without_mutating_native_source(self):
        source = (lab.ROOT / "source/client/StarClientApplication.cpp").read_text()
        # Exactly the omitted-clause failure observed in assetpath-actual-r1.
        clause = ' && scenario != "assetpath-room"'
        self.assertEqual(source.count(clause), 1)
        with self.assertRaisesRegex(ValueError, "startup scenario allowlist"):
            check_native_scenarios(source.replace(clause, "", 1), lab.SCENARIOS)


if __name__ == "__main__": unittest.main()
