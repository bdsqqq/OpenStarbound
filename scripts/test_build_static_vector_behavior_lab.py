"""Builder pure contracts only; no subprocess/compiler/version/server tests."""
from contextlib import contextmanager
import importlib.util
import inspect
import json
import os
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
fixture = builder.load('_physical_builder_fixture', builder.ROOT / 'source/lab/static-vector-game/test_physical_link_map.py')


@contextmanager
def dependency_fixture(role='candidate', extra_tus=0, shared_headers=0):
    """Real tiny inputs and raw .d files; no mocked dependency verifier."""
    with tempfile.TemporaryDirectory(dir=G) as temp:
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
        for index in range(shared_headers):
            header = sdk / ('shared-%03d.h' % index)
            header.write_text('/* shared %d */\n' % index)
            shared.append(header)
        inputs = [
            ('world', builder.ROOT / 'source/game/StarWorldClient.cpp', shared),
            ('client', builder.ROOT / 'source/client/StarClientApplication.cpp',
             [builder.ROOT / builder.ad.HEADER] + shared)]
        for index in range(extra_tus):
            source = root / ('extra-%03d.cpp' % index)
            source.write_text('/* synthetic TU %d */\n' % index)
            inputs.append(('extra-%03d' % index, source, shared))
        rows, objects, files, closures = [], {}, {}, {}
        for label, source, extra in inputs:
            obj = build / (source.name + '.o')
            obj.write_text('synthetic object ' + label)
            deps = [source] + extra
            dep = Path(str(obj) + '.d')
            dep.write_text(str(obj) + ': ' + ' '.join(map(str, deps)) + '\n')
            rows.append(dict(arguments=[TOOL, '-c', str(source), '-o', str(obj)],
                             file=str(source), directory=str(build)))
            objects[label] = dict(object=str(obj))
            files.update({str(path): builder.ad.sha(path) for path in deps})
            closures[str(obj)] = set(map(str, deps))
            newest = max(path.stat().st_mtime_ns for path in deps)
            os.utime(obj, ns=(newest + 1000000, newest + 1000000))
        (build / 'compile_commands.json').write_text(json.dumps(rows))
        plan = dict(buildRoot=str(root), witness={'files': files}, sdk=str(sdk), tools=TOOLS)
        configured = dict(role=role, objects=objects)
        yield plan, configured, {'compile_source_files': {}}, closures


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
            with self.subTest(role=role), dependency_fixture(role=role) as args:
                plan, configured, snapshot, _ = args
                witness = builder.dependency_witness(plan, configured, snapshot)
                self.assertEqual(len(witness['objects']), 2)
                plan['witness']['files'][str(Path(plan['sdk']) / 'mock.h')] = '0' * 64
                with self.assertRaisesRegex(ValueError, 'unadmitted dependency'):
                    builder.dependency_witness(plan, configured, snapshot)

    def test_interned_shared_dependencies_capture_once_and_stable_ids(self):
        with dependency_fixture(extra_tus=6, shared_headers=64) as args:
            plan, configured, snapshot, closures = args
            with patch.object(builder.ad, 'sha', wraps=builder.ad.sha) as hashes:
                witness = builder.dependency_witness(plan, configured, snapshot)
            self.assertEqual(witness['schema'], 'static-vector-compile-dependencies-v2')
            paths = [record['path'] for record in witness['files']]
            self.assertEqual(paths, sorted(set().union(*closures.values())))
            self.assertEqual(len(paths), 79)
            calls = [str(call.args[0]) for call in hashes.call_args_list]
            self.assertTrue(all(calls.count(path) == 1 for path in paths))
            self.assertEqual(calls.count(TOOL), 1)
            self.assertEqual(len(calls), 97)  # 79 dependencies + 8 objects + 8 .d + compiler + database.
            self.assertEqual(len(calls), len(set(calls)))
            self.assertNotIn(TOOL, paths)
            old = dict(schema='static-vector-compile-dependencies-v1', objects={})
            for obj, row in witness['objects'].items():
                ids = row['dependency_ids']
                self.assertEqual(ids, sorted(set(ids)))
                self.assertTrue(all(type(index) is int for index in ids))
                self.assertEqual({paths[index] for index in ids}, closures[obj])
                old['objects'][obj] = dict({key: value for key, value in row.items() if key != 'dependency_ids'},
                    dependencies={paths[index]: witness['files'][index] for index in ids})
            compact_size = len(json.dumps(witness, sort_keys=True).encode())
            repeated_size = len(json.dumps(old, sort_keys=True).encode())
            self.assertLess(compact_size * 3, repeated_size)
            # Reorder rows and repeat an equivalent lexical spelling in a raw
            # depfile: table IDs stay canonical, raw .d identity remains distinct.
            build = Path(plan['buildRoot']) / configured['role'] / 'cmake'
            database = build / 'compile_commands.json'
            database.write_text(json.dumps(list(reversed(json.loads(database.read_text())))))
            obj = configured['objects']['world']['object']
            dep = Path(obj + '.d')
            header = Path(plan['sdk']) / 'mock.h'
            dep.write_text(dep.read_text().rstrip() + ' ' + str(header.parent / 'present/../mock.h') + '\n')
            (header.parent / 'present').mkdir()
            with patch.object(builder.ad, 'sha', wraps=builder.ad.sha) as fresh_hashes:
                again = builder.dependency_witness(plan, configured, snapshot)
            self.assertEqual(len(fresh_hashes.call_args_list), 97)
            self.assertEqual(witness['files'], again['files'])
            self.assertEqual({obj: row['dependency_ids'] for obj, row in witness['objects'].items()},
                             {obj: row['dependency_ids'] for obj, row in again['objects'].items()})
            self.assertNotEqual(witness['objects'][obj]['depfile'], again['objects'][obj]['depfile'])

    def test_dependency_admission_consumer_sdk_and_mtime_negatives(self):
        errors = {'hash': 'unadmitted dependency', 'wrong-sdk': 'actual consumed SDK',
                  'missing-consumer': 'missing required compiled consumer', 'newer': 'dependency newer',
                  'unadmitted': 'unadmitted dependency', 'alias': 'duplicate compiled object',
                  'missing-source': 'source missing', 'on-only': 'ON-only'}
        for case, error in errors.items():
            with self.subTest(case=case), dependency_fixture() as args:
                plan, configured, snapshot, _ = args
                header = Path(plan['sdk']) / 'mock.h'
                obj = Path(configured['objects']['world']['object'])
                if case == 'hash':
                    header.write_text('actual header drift')
                elif case == 'wrong-sdk':
                    plan['sdk'] = str(header.parent / 'other-SDK')
                elif case == 'missing-consumer':
                    Path(configured['objects']['client']['object']).unlink()
                elif case == 'newer':
                    newer = obj.stat().st_mtime_ns + 1
                    os.utime(header, ns=(newer, newer))
                elif case == 'unadmitted':
                    del plan['witness']['files'][str(header)]
                elif case == 'alias':
                    database = obj.parent / 'compile_commands.json'
                    rows = json.loads(database.read_text())
                    alias = dict(rows[0], arguments=list(rows[0]['arguments']))
                    alias['arguments'][-1] = str(obj.parent) + '/./' + obj.name
                    rows.append(alias)
                    database.write_text(json.dumps(rows))
                elif case == 'missing-source':
                    dep = Path(str(obj) + '.d')
                    dep.write_text(dep.read_text().replace(str(builder.ROOT / 'source/game/StarWorldClient.cpp'), ''))
                elif case == 'on-only':
                    configured['role'] = 'reference'
                    # Keep the fixture at its original location while changing
                    # role semantics: the reference must not consume ON headers.
                    original = Path(plan['buildRoot']) / 'candidate'
                    original.rename(original.with_name('reference'))
                    for path in original.with_name('reference').rglob('*'):
                        if path.suffix == '.d' or path.name == 'compile_commands.json':
                            path.write_text(path.read_text().replace('/candidate/', '/reference/'))
                    for row in configured['objects'].values():
                        row['object'] = row['object'].replace('/candidate/', '/reference/')
                with self.assertRaisesRegex(ValueError, error):
                    builder.dependency_witness(plan, configured, snapshot)

    def test_dependency_aliases_require_strict_physical_resolution(self):
        for kind in ('missing-parent', 'symlink-parent'):
            with self.subTest(kind=kind), dependency_fixture() as args:
                plan, configured, snapshot, _ = args
                sdk = Path(plan['sdk'])
                alias = sdk / 'alias'
                obj = configured['objects']['world']['object']
                dep = Path(obj + '.d')
                dep.write_text(dep.read_text().rstrip() + ' ' + str(alias) + '/../mock.h\n')
                if kind == 'missing-parent':
                    with self.assertRaises(FileNotFoundError):
                        builder.dependency_witness(plan, configured, snapshot)
                else:
                    physical = sdk.parent / 'redirect'
                    (physical / 'inner').mkdir(parents=True)
                    (physical / 'mock.h').write_text('not the admitted SDK header')
                    alias.symlink_to(physical / 'inner', target_is_directory=True)
                    with self.assertRaisesRegex(ValueError, 'unadmitted dependency'):
                        builder.dependency_witness(plan, configured, snapshot)

    def test_capture_detects_change_during_hash(self):
        with dependency_fixture() as args:
            plan, configured, snapshot, _ = args
            header = Path(plan['sdk']) / 'mock.h'
            real_sha = builder.ad.sha

            def changing_sha(path):
                digest = real_sha(path)
                if path == header:
                    path.write_text('changed after content read')
                return digest

            with patch.object(builder.ad, 'sha', side_effect=changing_sha), \
                 self.assertRaisesRegex(ValueError, 'changed during capture'):
                builder.dependency_witness(plan, configured, snapshot)

    def test_final_stability_barrier_and_known_unguarded_mutant(self):
        source = inspect.getsource(builder.dependency_witness)
        guard = "ad.need(before == fingerprint(path), 'compile input changed before return: ' + str(path))"
        self.assertEqual(source.count(guard), 1)
        namespace = dict(vars(builder))
        exec(compile(source.replace(guard, 'pass'), '<isolated-no-final-stability-mutant>', 'exec'), namespace)
        for implementation, rejects in [(builder.dependency_witness, True), (namespace['dependency_witness'], False)]:
            with self.subTest(rejects=rejects), dependency_fixture(extra_tus=1) as args:
                plan, configured, snapshot, _ = args
                header = Path(plan['sdk']) / 'mock.h'
                last_obj = Path(configured['objects']['extra-000']['object'])
                real_identity = builder.identity

                def late_change(path):
                    record = real_identity(path)
                    if path == last_obj:
                        header.write_text('late change after shared header capture')
                    return record

                # Mutant has isolated globals; only the capture observer differs.
                if rejects:
                    with patch.object(builder, 'identity', side_effect=late_change), \
                         self.assertRaisesRegex(ValueError, 'changed before return'):
                        implementation(plan, configured, snapshot)
                else:
                    namespace['identity'] = late_change
                    self.assertEqual(implementation(plan, configured, snapshot)['schema'],
                                     'static-vector-compile-dependencies-v2')

    def test_physical_map_closure_and_selected_bytes(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            side = Path(temp)
            (side / 'cmake').mkdir()
            library = side / 'lib.a'
            bodies = [fixture.macho(), fixture.macho((b'_right',))]
            library.write_bytes(fixture.ar(bodies))
            direct = side / 'cmake/direct.o'
            direct.write_bytes(fixture.macho((b'_direct',)))
            data = fixture.linkmap([(4096, 8, 7, b'_right'), (4104, 8, 91, b'_left')],
                                   path=bytes(library))
            data = data.replace(b'# Symbols:', b'[150] ' + bytes(direct) + b'\n# Symbols:')
            (side / 'link.map').write_bytes(data)
            plan = dict(witness={'files': {str(library): builder.ad.sha(library)}})
            deps = {'objects': {str(direct): {}}}
            origins = builder.link_map_closure(plan, side, deps, None)
            self.assertEqual([r['object_index'] for r in origins['objects']], [0, 7, 91, 150])
            link = {'actualOrigins': origins}
            self.assertEqual(builder.link_object_bytes(link), {7: bodies[1], 91: bodies[0], 150: direct.read_bytes()})
            # Wrong recorded offset must reject even when a first-member shortcut is tempting.
            first = origins['objects'][1]
            old = first['member_header_offset']
            first['member_header_offset'] = origins['objects'][2]['member_header_offset']
            with self.assertRaises(ValueError):
                builder.link_object_bytes(link)
            first['member_header_offset'] = old
            original_direct = direct.read_bytes()
            direct.write_bytes(fixture.macho((b'_changed',)))
            with self.assertRaises(ValueError):
                builder.link_object_bytes(link)
            direct.write_bytes(original_direct)
            library.write_bytes(fixture.ar(list(reversed(bodies))))
            with self.assertRaises(ValueError):
                builder.link_object_bytes(link)

    def test_map_aliases_cannot_assign_one_physical_input_twice(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            side = Path(temp); (side / 'cmake').mkdir()
            library = side / 'lib.a'
            library.write_bytes(fixture.ar([fixture.macho()]))
            direct = side / 'cmake/direct.o'
            direct.write_bytes(fixture.macho((b'_direct',)))
            plan = dict(witness={'files': {str(library): builder.ad.sha(library)}})
            deps = {'objects': {str(direct): {}}}
            for first, second in [
                    (bytes(library) + b'(dup\xff.o)', bytes(library.parent) + b'/./lib.a(dup\xff.o)'),
                    (bytes(direct), bytes(direct.parent) + b'/./direct.o')]:
                data = (b'# Object files:\n[0] linker synthesized\n[7] ' + first +
                        b'\n[19] ' + second + b'\n# Symbols:\n')
                (side / 'link.map').write_bytes(data)
                with self.subTest(first=first), self.assertRaisesRegex(ValueError, 'map aliases'):
                    builder.link_map_closure(plan, side, deps, None)

    def test_physical_member_name_sha_and_kind_guards(self):
        with tempfile.TemporaryDirectory(dir=G) as temp:
            path = Path(temp) / 'lib.a'
            path.write_bytes(fixture.ar([fixture.macho()]))
            member = builder.physical.archive.arm64_archive_members(path.read_bytes())[0]
            row = dict(kind='ARCHIVE_MEMBER', object_index=7, archive=builder.identity(path),
                       member_header_offset=member['offset'], member_name_hex=member['name'].hex(),
                       member_sha256=member['sha256'])
            for field, value in [('member_name_hex', b'wrong.o'.hex()), ('member_sha256', '0' * 64),
                                 ('member_header_offset', member['offset'] + 1)]:
                with self.subTest(field=field), self.assertRaises(ValueError):
                    builder.link_object_bytes({'actualOrigins': {'objects': [dict(row, **{field: value})]}})
            obj = Path(temp) / 'bad.o'
            obj.write_bytes(b'not Mach-O')
            with self.assertRaises(ValueError):
                builder.link_object_bytes({'actualOrigins': {'objects': [dict(kind='COMPILED_OBJECT', object_index=9, object=builder.identity(obj))]}})

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
