#!/usr/bin/env python3
"""Adversarial tests use isolated fixtures, never rewrite the live catalog."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location('migration_inventory', HERE / 'inventory.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.put('source/lab/migration/modules.json', (HERE / 'modules.json').read_text())
        self.put('source/lab/migration/inventory.py', (HERE / 'inventory.py').read_text())
        self.put('source/core/StarArray.hpp', '// array\n')
        self.put('source/core/StarFile_unix.cpp', '// unix\n')
        self.put('source/core/StarString_windows.cpp', '// windows\n')
        self.put('source/core/CMakeLists.txt', '''# add_library(near_match fake.cpp)
#[[ add_library(bracket_near_match fake.cpp) ]]
set(common [=[StarArray.hpp]=])
set(alias "${common}")
if(UNIX)
  set(platform StarFile_unix.cpp)
else()
  set(platform StarString_windows.cpp)
endif()
add_library(fixture OBJECT ${alias} ${platform})
''')
        self.output = self.root / inventory.OUTPUT

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def run_gate(self, mode):
        # Exercise the very shell entrypoint intended for CI, not an internal approximation.
        return subprocess.run(['sh', str(REPO / 'scripts/migration-inventory.sh'), mode,
                               '--root', str(self.root)], text=True, capture_output=True)

    def write_catalog(self):
        result = self.run_gate('--write')
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.output.read_bytes()

    def test_replay_alias_conditional_and_excluded_near_matches(self):
        self.put('source/core/StarArray.hpp.bak', 'not source')
        self.put('source/rust/example/target/generated.rs', 'not source')
        self.put('source/build/generated.cpp', 'not source')
        self.put('source/lab/migration/generated.cpp', 'not source')
        one = self.write_catalog()
        self.assertEqual(one, self.write_catalog())
        result = self.run_gate('--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        catalog = json.loads(one)
        files = {f['path']: f for f in catalog['files']}
        self.assertEqual(set(files), {'source/core/StarArray.hpp', 'source/core/StarFile_unix.cpp',
                                      'source/core/StarString_windows.cpp'})
        array = files['source/core/StarArray.hpp']
        self.assertEqual(array['module'], 'foundation.collections')
        self.assertEqual(array['cmake_membership'][0]['target'], 'fixture')
        self.assertEqual(array['cmake_membership'][0]['source_line'], 3)
        for path in ('source/core/StarFile_unix.cpp', 'source/core/StarString_windows.cpp'):
            self.assertTrue(files[path]['cmake_membership'][0]['static_context'])
            self.assertEqual(files[path]['membership_status'], 'static-alternative')

    def test_corrupt_output_rejected_without_repair(self):
        self.write_catalog()
        parsed = json.loads(self.output.read_text())
        parsed['summary']['files'] = 999
        self.output.write_text(json.dumps(parsed))
        bad = self.output.read_bytes()
        self.assertNotEqual(self.run_gate('--check').returncode, 0)
        self.assertEqual(self.output.read_bytes(), bad)
        self.write_catalog()
        self.assertEqual(self.run_gate('--check').returncode, 0)

    def test_deleted_output_rejected_without_repair(self):
        self.write_catalog()
        self.output.unlink()
        self.assertNotEqual(self.run_gate('--check').returncode, 0)
        self.assertFalse(self.output.exists())
        self.write_catalog()
        self.assertEqual(self.run_gate('--check').returncode, 0)

    def test_new_source_and_body_drift_rejected_without_repair(self):
        before = self.write_catalog()
        new = self.put('source/core/StarList.hpp', '// new source, known classification\n')
        self.assertNotEqual(self.run_gate('--check').returncode, 0)
        self.assertEqual(self.output.read_bytes(), before)
        self.write_catalog()
        self.assertEqual(self.run_gate('--check').returncode, 0)
        before = self.output.read_bytes()
        new.write_text('// changed body\n')
        self.assertNotEqual(self.run_gate('--check').returncode, 0)
        self.assertEqual(self.output.read_bytes(), before)

    def test_unknown_and_ambiguous_names_fail_even_write(self):
        before = self.write_catalog()
        unknown = self.put('source/core/StarArrayish.hpp', '// near match must not silently classify\n')
        result = self.run_gate('--write')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('expected one classification, got []', result.stderr)
        self.assertEqual(self.output.read_bytes(), before)
        unknown.unlink()
        path = self.root / 'source/lab/migration/modules.json'
        config = json.loads(path.read_text())
        config['rules'].append({'id': 'ambiguous-fixture', 'module': 'foundation.text',
                                'disposition': 'migrate', 'pattern': r'source/core/StarArray\.hpp'})
        path.write_text(json.dumps(config))
        self.assertNotEqual(self.run_gate('--write').returncode, 0)
        self.assertEqual(self.output.read_bytes(), before)

    def test_direct_targets_not_transitive_and_foreach_alternatives(self):
        self.put('source/lab/lighting/LightingLab.cpp', '// harness')
        self.put('source/lab/lighting/CMakeLists.txt', '''foreach(t lighting_lab lighting_lab_cpp)
add_executable(${t} LightingLab.cpp $<TARGET_OBJECTS:star_core>)
endforeach()
''')
        catalog = json.loads(self.write_catalog())
        file = next(f for f in catalog['files'] if f['path'].endswith('LightingLab.cpp'))
        self.assertEqual([e['target'] for e in file['cmake_membership']], ['lighting_lab', 'lighting_lab_cpp'])
        array = next(f for f in catalog['files'] if f['path'].endswith('StarArray.hpp'))
        self.assertEqual([e['target'] for e in array['cmake_membership']], ['fixture'])

    def test_input_and_cmake_drift(self):
        before = self.write_catalog()
        self.put('source/core/CMakeLists.txt', 'add_library(newtarget StarArray.hpp)\n')
        self.assertNotEqual(self.run_gate('--check').returncode, 0)
        self.assertEqual(self.output.read_bytes(), before)

    def test_repository_rules_have_no_unassigned_files(self):
        rules = json.loads((HERE / 'modules.json').read_text())['rules']
        for path in inventory.discover(REPO):
            with self.subTest(path=path):
                inventory.classify(path, rules)


if __name__ == '__main__':
    unittest.main(verbosity=2)
