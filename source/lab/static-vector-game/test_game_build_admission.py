"""Pure guards; no tool invocation or actual game admission."""
import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_sv_ad_test', HERE / 'game_build_admission.py')
ad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ad)
G = ad.build_root()


class AdmissionTests(unittest.TestCase):
    def test_current30_profiles_and_source(self):
        ad.config.validate_source()
        self.assertEqual(len(ad.SELECTORS), 30)
        self.assertEqual(sum(v == 'ON' for v in ad.profiles()['candidate'].values()), 29)
        self.assertEqual(set(ad.profiles()['reference'].values()), {'OFF'})
        bad = dict(ad.profiles()['candidate'], STAR_USE_RUST_LINE_QUERY='ON')
        with self.assertRaises(ValueError):
            ad.config.validate_profile('candidate', bad)
        with self.assertRaises(ValueError):
            ad.config.validate_source('option(STAR_USE_RUST_STATIC_VECTOR "bad" ON)')

    def test_original_clock_no_renewal(self):
        now = dt.datetime(2026, 10, 29, tzinfo=dt.timezone.utc)
        plan = dict(createdUTC=now.isoformat(), deadlines=ad.DEADLINES)
        ad.check_deadline(plan, now + dt.timedelta(seconds=2099))
        for delta in (-1, 2100, 9000):
            with self.assertRaises(ValueError):
                ad.check_deadline(plan, now + dt.timedelta(seconds=delta))
        with self.assertRaises(ValueError):
            ad.check_deadline(dict(plan, deadlines={'maxAgeSeconds': 9999}), now)

    def test_explicit_metadata_and_fresh_roles(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            (root / 'observation.json').write_text('{}')
            self.assertEqual(len(ad.metadata_inventory(root)), 1)
            (root / 'candidate').mkdir()
            with self.assertRaises(ValueError):
                ad.metadata_inventory(root)

    def test_alias_and_native_metadata_rejected(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            (root / 'note').write_bytes(b'\xcf\xfa\xed\xfe')
            with self.assertRaises(ValueError):
                ad.metadata_inventory(root)
            (root / 'alias').symlink_to(root / 'note')
            with self.assertRaises(ValueError):
                ad.identity(root / 'alias')

    def test_exact_needed_old_pair_allowed_unexpected_rejected(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            behavior = root / 'build/behavior'
            for role in ad.profiles():
                path = behavior / 'id-map-combined-r2' / role / 'bin/starbound'
                path.parent.mkdir(parents=True)
                path.write_text(role)
            pins = {r: ad.sha(behavior / 'id-map-combined-r2' / r / 'bin/starbound') for r in ad.profiles()}
            with patch.object(ad, 'ROOT', root), patch.object(ad, 'PREDECESSORS', pins):
                self.assertEqual(len(ad.check_binaries()), 2)
                bad = behavior / 'surprise/reference/bin/starbound'
                bad.parent.mkdir(parents=True)
                bad.write_text('unowned')
                with self.assertRaises(ValueError):
                    ad.check_binaries()

    def test_missing_sdk_fails_current_path_selection(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            path = Path(temp) / 'selector.json'
            import json
            tools = {key: '/usr/bin/python3' for key in ('CMAKE_EXECUTABLE', 'CMAKE_C_COMPILER',
                'CMAKE_CXX_COMPILER', 'CMAKE_AR', 'CMAKE_RANLIB', 'CMAKE_LINKER', 'CMAKE_MAKE_PROGRAM',
                'STAR_CARGO_EXECUTABLE', 'STAR_RUSTC_EXECUTABLE', 'APPLE_TOOLCHAIN_SELECTOR')}
            path.write_text(json.dumps(dict(tools=tools, sdk='/missing/SDK')))
            with patch.object(ad.primitives, 'native'):
                with self.assertRaises(ValueError):
                    ad.primitives.selected_paths(path, ad.sha(path))

    def test_configure_candidate_has_separate_cargo(self):
        plan = dict(buildRoot=str(G), sdk='/SDK', tools={'CMAKE_EXECUTABLE': '/cmake'})
        commands = ad.commands(plan, 'candidate')
        self.assertIn('star_rust_engine_ffi_build', commands['cargo'])
        self.assertNotIn('starbound', commands['cargo'])
        self.assertIn('starbound', commands['build'])
        self.assertIsNone(ad.commands(plan, 'reference')['cargo'])

    def test_retention_covers_whole_generation_not_just_four_binaries(self):
        forecast = dict(schema='static-vector-product-retention-forecast-v1',
                        sourceCheckpoint=ad.CHECKPOINT, complete=True,
                        products={key: 1 for key in ad.RETENTION_PRODUCTS})
        budget = dict(archiveBytes=ad.CAPS['archiveBytes'] - len(ad.RETENTION_PRODUCTS))
        self.assertEqual(ad.check_retention(forecast, ad.CHECKPOINT, budget), len(ad.RETENTION_PRODUCTS))
        for missing in ad.RETENTION_PRODUCTS:
            with self.subTest(missing=missing):
                bad = dict(forecast, products={k: v for k, v in forecast['products'].items() if k != missing})
                with self.assertRaises(ValueError):
                    ad.check_retention(bad, ad.CHECKPOINT, budget)
        bad = dict(forecast, products={k: 1 for k in
                   ('predecessor-reference', 'predecessor-candidate', 'new-reference', 'new-candidate')})
        with self.assertRaisesRegex(ValueError, 'binaries alone'):
            ad.check_retention(bad, ad.CHECKPOINT, budget)

    def test_retention_rejects_underfunded_boolean_and_unknown_costs(self):
        forecast = dict(schema='static-vector-product-retention-forecast-v1',
                        sourceCheckpoint=ad.CHECKPOINT, complete=True,
                        products={key: 1 for key in ad.RETENTION_PRODUCTS})
        budget = dict(archiveBytes=ad.CAPS['archiveBytes'] - len(ad.RETENTION_PRODUCTS) + 1)
        with self.assertRaisesRegex(ValueError, 'headroom'):
            ad.check_retention(forecast, ad.CHECKPOINT, budget)
        for value in (True, 0, -1, 1.5):
            with self.subTest(value=value):
                bad = dict(forecast, products=dict(forecast['products'], **{'cargo-products': value}))
                with self.assertRaises(ValueError):
                    ad.check_retention(bad, ad.CHECKPOINT, dict(archiveBytes=0))
        bad = dict(forecast, products=dict(forecast['products'], surprise=1))
        with self.assertRaises(ValueError):
            ad.check_retention(bad, ad.CHECKPOINT, dict(archiveBytes=0))

    def test_wrong_base_rejected_before_inputs(self):
        plan = dict(stage=ad.STAGE, scope=ad.SCOPE, caps=ad.CAPS, sourceCheckpoint='0' * 40,
                    checkpointRole='BASE_ONLY; current working-tree bytes authoritative')
        with self.assertRaises(ValueError):
            ad.static_plan(plan)


if __name__ == '__main__':
    unittest.main()
