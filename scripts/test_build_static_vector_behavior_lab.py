"""Builder pure contracts only; no subprocess/compiler/version/server tests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('_sv_builder_test', Path(__file__).with_name('build-static-vector-behavior-lab.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
G = builder.ad.build_root()
TOOL = str(Path(sys.executable).resolve())
TOOLS = {'CMAKE_C_COMPILER': TOOL, 'CMAKE_CXX_COMPILER': TOOL}


class BuilderTests(unittest.TestCase):
    def test_candidate_cargo_barrier_and_no_reference_cargo(self):
        self.assertEqual(len(builder.phases('candidate')), 7)
        self.assertEqual(len(builder.phases('reference')), 6)
        self.assertLess(builder.phases('candidate').index('cargo'), builder.phases('candidate').index('compile'))
        plan = dict(buildRoot=str(G), sdk='/SDK', python='/python', tools={'CMAKE_EXECUTABLE': '/cmake'})
        with self.assertRaises(ValueError):
            builder.phase_command(plan, 'reference', 'cargo')
        self.assertNotIn('RUSTFLAGS', builder.environment(plan, 'candidate'))

    def test_supervision_owned_group_is_mocked_and_reaped(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory(dir=G) as temp:
            output = Path(temp) / 'mock-phase'
            proc = Mock(pid=4242, returncode=0)
            proc.wait.return_value = 0
            with patch.object(builder.ad, 'validate'), patch.object(builder, 'remaining', return_value=1), \
                 patch.object(builder.subprocess, 'Popen', return_value=proc) as launch, patch.object(builder.os, 'killpg') as kill:
                builder.supervise(['/never-executed'], builder.ROOT / 'source', {}, output, {'witness': {}})
                self.assertTrue(launch.call_args.kwargs['start_new_session'])
                kill.assert_called_once_with(4242, builder.signal.SIGKILL)
                self.assertGreaterEqual(proc.wait.call_count, 2)
            receipt = json.loads(output.with_suffix('.receipt.json').read_text())
            self.assertIs(receipt['reaped'], True)
            self.assertEqual(receipt['pgid'], 4242)

    def test_make_dependency_grammar(self):
        self.assertEqual(builder.make_rule('a.o: source\\ file.hpp path$$name\n'), ('a.o', ['source file.hpp', 'path$name']))
        with self.assertRaises(ValueError):
            builder.make_rule('a.o: first\nb.o: second\n')

    def test_wrong_expanded_cargo_argv_blocks_before_execution(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            build = Path(temp)
            (build / 'build.ninja').write_text('  COMMAND = cd ' + str(build) + ' && /cargo build --package star-engine-ffi --release\n')
            plan = dict(tools={'CMAKE_EXECUTABLE': '/cmake', 'STAR_CARGO_EXECUTABLE': '/cargo', 'STAR_RUSTC_EXECUTABLE': '/rustc'}, witness={'files': {}})
            with self.assertRaises(ValueError):
                builder.cargo_command(plan, build)

    def test_missing_compile_dependencies_rejected(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            root = Path(temp)
            build = root / 'candidate/cmake'
            build.mkdir(parents=True)
            obj = build / 'StarWorldClient.cpp.o'
            obj.write_text('object')
            source = builder.ROOT / 'source/game/StarWorldClient.cpp'
            (build / 'compile_commands.json').write_text(json.dumps([dict(arguments=[TOOL, '-c', str(source), '-o', str(obj)], file=str(source), directory=str(build))]))
            plan = dict(buildRoot=str(root), witness={'files': {str(source): builder.ad.sha(source)}}, sdk='/SDK', tools=TOOLS)
            configured = dict(role='candidate', objects={})
            with self.assertRaises(FileNotFoundError):
                builder.dependency_witness(plan, configured, {'compile_source_files': {}})
            Path(str(obj) + '.d').write_text(str(obj) + ': /unavailable/header.hpp\n')
            with self.assertRaises(FileNotFoundError):
                builder.dependency_witness(plan, configured, {'compile_source_files': {}})

    def test_synthetic_current_consumer_dependency_closure(self):
        for role in ('reference', 'candidate'):
            with self.subTest(role=role), tempfile.TemporaryDirectory(dir=G) as temp:
                root = Path(temp)
                build = root / role / 'cmake'
                build.mkdir(parents=True)
                sdk = root / 'SDK'
                sdk.mkdir()
                sdk_header = sdk / 'mock.h'
                sdk_header.write_text('synthetic SDK observation fixture')
                shared = [builder.ROOT / 'source/game/StarTileSectorArray.hpp',
                          builder.ROOT / 'source/core/StarTileSectorArrayObserver.hpp',
                          builder.ROOT / 'source/core/StarStaticVector.hpp', sdk_header]
                if role == 'candidate':
                    shared += [builder.ROOT / 'source/core/StarRustStaticVector.h',
                               builder.ROOT / 'source/core/StarStaticVectorHost.hpp']
                rows, objects, files = [], {}, {}
                for label, source, extra in [
                    ('world', builder.ROOT / 'source/game/StarWorldClient.cpp', shared),
                    ('client', builder.ROOT / 'source/client/StarClientApplication.cpp', [builder.ROOT / builder.ad.HEADER])]:
                    obj = build / (source.name + '.o')
                    obj.write_text('synthetic object ' + label)
                    deps = [source] + extra
                    dep = Path(str(obj) + '.d')
                    dep.write_text(str(obj) + ': ' + ' '.join(map(str, deps)) + '\n')
                    rows.append(dict(arguments=[TOOL, '-c', str(source), '-o', str(obj)], file=str(source), directory=str(build)))
                    objects[label] = dict(object=str(obj))
                    files.update({str(path): builder.ad.sha(path) for path in deps})
                (build / 'compile_commands.json').write_text(json.dumps(rows))
                plan = dict(buildRoot=str(root), witness={'files': files}, sdk=str(sdk), tools=TOOLS)
                configured = dict(role=role, objects=objects)
                witness = builder.dependency_witness(plan, configured, {'compile_source_files': {}})
                self.assertEqual(len(witness['objects']), 2)
                files[str(sdk_header)] = '0' * 64
                with self.assertRaises(ValueError):
                    builder.dependency_witness(plan, configured, {'compile_source_files': {}})

    def test_archive_file_state_detects_replacement(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            path = Path(temp) / 'archive.a'
            path.write_bytes(b'unchanged')
            before = builder.ad.file_state(path)
            other = Path(temp) / 'other'
            other.write_bytes(b'unchanged')
            other.replace(path)
            self.assertNotEqual(before, builder.ad.file_state(path))


if __name__ == '__main__':
    unittest.main()
