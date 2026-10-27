"""isolated declaration/receipt controls; no files, compilers or processes."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import native_evidence_json as evidence
from native_plan import Plan, Receipt, Stage, check_completion, check_ready, preflight


ROOT = b"/owned/native-plan"
RECIPE = b"/readonly/recipe\xff"
TOOL = b"/readonly/tool"
SOURCE = ROOT + b"/fixture\x93.cpp"
OBJECT = ROOT + b"/fixture\xff.o"
DRIVER = ROOT + b"/driver.json"
EXE = ROOT + b"/fixture"
INSPECTION = ROOT + b"/inspection"
RESULT = ROOT + b"/result"


def fixture():
    return Plan(ROOT, (RECIPE, TOOL), (
        Stage("source", (b"python", RECIPE, SOURCE), (RECIPE, TOOL), (SOURCE,),
              (ROOT + b"/source.stdout", ROOT + b"/source.stderr")),
        Stage("compile", (b"clang", b"-c", SOURCE, b"-o", OBJECT),
              (TOOL, SOURCE), (OBJECT,), (ROOT + b"/compile.log",), ("source",)),
        Stage("driverexpand", (b"clang", b"-###", OBJECT), (TOOL, OBJECT),
              (DRIVER,), (ROOT + b"/driver.log",), ("compile",)),
        Stage("link", (b"clang", OBJECT, b"-o", EXE), (TOOL, OBJECT, DRIVER),
              (EXE,), (ROOT + b"/link.log",), ("driverexpand",)),
        Stage("inspect", (b"objdump", EXE), (TOOL, EXE), (INSPECTION,),
              (ROOT + b"/inspect.log",), ("link",)),
        Stage("run", (EXE,), (EXE, INSPECTION), (RESULT,),
              (ROOT + b"/run.stdout", ROOT + b"/run.stderr"), ("inspect",)),
    ))


def changed(plan, index, **fields):
    stages = list(plan.stages)
    stages[index] = replace(stages[index], **fields)
    return replace(plan, stages=tuple(stages))


def simulated(plan, count):
    stages = plan.stages[:count]
    receipts = tuple(Receipt(s.stage_id, True, 0, s.writes) for s in stages)
    available = plan.initial_inputs + tuple(p for s in stages for p in s.writes)
    return receipts, available


class NativePlanTests(unittest.TestCase):
    def test_positive_graph_each_stage_then_full_completion(self):
        plan = fixture()
        for index, stage in enumerate(plan.stages):
            with self.subTest(stage=stage.stage_id):
                check_ready(plan, stage.stage_id, *simulated(plan, index))
        check_completion(plan, *simulated(plan, len(plan.stages)))

    def test_whole_manifest_byte_paths_nested_tuples_and_readonly_alias(self):
        plan = fixture()
        with patch.object(evidence, "dumps", wraps=evidence.dumps) as dumps, \
                patch.object(evidence, "loads", wraps=evidence.loads) as loads:
            encoded = preflight(plan)
            self.assertEqual((dumps.call_count, loads.call_count), (1, 1))
        manifest = evidence.loads(encoded)
        self.assertEqual(manifest["owned_root"], ROOT)
        self.assertEqual(manifest["initial_inputs"], plan.initial_inputs)
        self.assertIs(type(manifest["stages"]), tuple)
        self.assertEqual(manifest["stages"][1]["argv"], plan.stages[1].argv)
        self.assertEqual(manifest["stages"][1]["outputs"], (OBJECT,))
        self.assertEqual(manifest["stages"][0]["inputs"][0], RECIPE)
        self.assertTrue(TOOL not in tuple(p for s in plan.stages for p in s.writes))
        with self.assertRaises(TypeError):
            json.dumps(manifest)  # the old failure shape, without importing a run.
        self.assertEqual(evidence.dumps(manifest), encoded)

    def test_readiness_always_preflights_entire_manifest(self):
        plan = fixture()
        with patch.object(evidence, "dumps", wraps=evidence.dumps) as dumps:
            check_ready(plan, "source", (), plan.initial_inputs)
            self.assertEqual(dumps.call_count, 1)
        # a later scope error blocks even the first would-be execution.
        bad = changed(plan, 5, logs=(b"/outside/launch.log",))
        with self.assertRaises(ValueError):
            check_ready(bad, "source", (), plan.initial_inputs)

    def test_driver_cannot_use_planned_future_or_missing_object(self):
        plan = fixture()
        stages = list(plan.stages)
        stages[1], stages[2] = stages[2], stages[1]
        for bad in (replace(plan, stages=tuple(stages)),
                    changed(plan, 1, outputs=()),
                    changed(plan, 2, inputs=(TOOL, ROOT + b"/unplanned.o")),
                    changed(plan, 2, requires=())):
            with self.subTest(plan=bad), self.assertRaises(ValueError):
                preflight(bad)
        with self.assertRaises(ValueError):
            check_ready(plan, "driverexpand", *simulated(plan, 1))
        receipts, available = simulated(plan, 2)
        with self.assertRaises(ValueError):
            check_ready(plan, "driverexpand", receipts, tuple(p for p in available if p != OBJECT))
        check_ready(plan, "driverexpand", receipts, available)

    def test_no_log_whitelist_or_prefix_escape(self):
        plan = fixture()
        for path in (b"/outside/launch.log", ROOT + b"-other/log", ROOT,
                     ROOT + b"/../launch.log", ROOT + b"//log", ROOT + b"/./log",
                     ROOT + b"/log/", ROOT + b"/nul\0", b"relative/log"):
            for field in ("outputs", "logs"):
                with self.subTest(path=path, field=field), self.assertRaises(ValueError):
                    preflight(changed(plan, 5, **{field: (path,)}))
        with self.assertRaises(ValueError):
            preflight(replace(plan, owned_root=b"/"))

    def test_duplicate_ids_artifacts_and_overwriting_prebound_files(self):
        plan = fixture()
        for bad in (changed(plan, 5, stage_id="source"),
                    changed(plan, 5, outputs=(EXE,)),
                    changed(plan, 5, outputs=(RESULT, RESULT)),
                    changed(plan, 5, logs=(RESULT,)),
                    changed(plan, 5, logs=plan.stages[0].logs),
                    replace(plan, initial_inputs=plan.initial_inputs + (RESULT,)),
                    replace(plan, initial_inputs=(RECIPE, RECIPE))):
            with self.subTest(plan=bad), self.assertRaises(ValueError):
                preflight(bad)

    def test_file_artifacts_cannot_be_each_others_parent(self):
        plan = fixture()
        for first, second in ((ROOT + b"/file", ROOT + b"/file/child"),
                              (ROOT + b"/file/child", ROOT + b"/file")):
            with self.subTest(first=first), self.assertRaises(ValueError):
                preflight(Plan(ROOT, (), (Stage("a", (b"fake",), outputs=(first,)),
                                          Stage("b", (b"fake",), logs=(second,)))))
        for initial in ((TOOL, TOOL + b"/child"), (ROOT,)):
            with self.subTest(initial=initial), self.assertRaises(ValueError):
                preflight(replace(plan, initial_inputs=initial))
        with self.assertRaises(ValueError):
            preflight(changed(plan, 0, outputs=(RECIPE + b"/child",)))

    def test_forward_cycle_unknown_and_duplicate_dependencies(self):
        plan = fixture()
        for deps in (("run",), ("source",), ("unknown",), ("",)):
            with self.subTest(deps=deps), self.assertRaises((ValueError, TypeError)):
                preflight(changed(plan, 0, requires=deps))
        with self.assertRaises(ValueError):
            preflight(changed(plan, 1, requires=("source", "source")))

    def test_failed_partial_bool_exit_and_pass_dict_not_credited(self):
        plan = fixture()
        receipts, available = simulated(plan, 1)
        for receipt in (replace(receipts[0], completed=False),
                        replace(receipts[0], completed=1),
                        replace(receipts[0], exit_code=False),
                        replace(receipts[0], exit_code=True),
                        replace(receipts[0], exit_code=0.0),
                        replace(receipts[0], exit_code=1),
                        replace(receipts[0], outputs=(SOURCE,)),
                        replace(receipts[0], outputs=(SOURCE, SOURCE)),
                        {"stage_id": "source", "status": "PASS", "exit_code": 0}):
            with self.subTest(receipt=receipt), self.assertRaises((TypeError, ValueError)):
                check_ready(plan, "compile", (receipt,), available)
        with self.assertRaises(ValueError):
            check_completion(plan, receipts, available)
        with self.assertRaises(ValueError):
            check_ready(plan, "compile", receipts, tuple(p for p in available if p != SOURCE))
        check_ready(plan, "compile", receipts, available)

    def test_completion_requires_every_output_and_log(self):
        plan = fixture()
        receipts, available = simulated(plan, 6)
        for path in available:
            with self.subTest(missing=path), self.assertRaises(ValueError):
                check_completion(plan, receipts, tuple(p for p in available if p != path))
        with self.assertRaises(ValueError):
            check_completion(plan, receipts[:-1], available)
        with self.assertRaises(ValueError):
            check_completion(plan, receipts[::-1], available)
        check_completion(plan, receipts, available)

    def test_unknown_duplicate_and_already_completed_stage(self):
        plan = fixture()
        receipts, available = simulated(plan, 1)
        for stage_id in ("unknown", "source", False):
            with self.subTest(stage=stage_id), self.assertRaises((ValueError, TypeError)):
                check_ready(plan, stage_id, receipts, available)
        for invalid in ((replace(receipts[0], stage_id="unknown"),),
                        (replace(receipts[0], stage_id=True),), receipts + receipts):
            with self.subTest(receipts=invalid), self.assertRaises((ValueError, TypeError)):
                check_ready(plan, "compile", invalid, available)

    def test_available_cannot_credit_future_or_undeclared_artifact(self):
        plan = fixture()
        for available in (plan.initial_inputs + (OBJECT,),
                          plan.initial_inputs + (b"/unknown",),
                          (TOOL,), plan.initial_inputs + (TOOL,)):
            with self.subTest(available=available), self.assertRaises(ValueError):
                check_ready(plan, "source", (), available)

    def test_exact_immutable_types_no_implicit_path_stringification(self):
        plan = fixture()
        with self.assertRaises(FrozenInstanceError):
            plan.owned_root = b"/other"
        with self.assertRaises(FrozenInstanceError):
            plan.stages[0].outputs = ()
        for bad in (replace(plan, owned_root=Path("/owned")),
                    replace(plan, owned_root="/owned"),
                    replace(plan, stages=list(plan.stages)),
                    changed(plan, 0, argv=("python",)),
                    changed(plan, 0, inputs=[RECIPE]),
                    changed(plan, 0, stage_id=True),
                    changed(plan, 0, requires=(False,))):
            with self.subTest(plan=bad), self.assertRaises(TypeError):
                preflight(bad)
        for argv in ((), (b"",), (b"python", b"nul\0")):
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                preflight(changed(plan, 0, argv=argv))
        for paths in ((b"/readonly/../recipe",), (b"relative",)):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                preflight(replace(plan, initial_inputs=paths))


if __name__ == "__main__":
    unittest.main()
