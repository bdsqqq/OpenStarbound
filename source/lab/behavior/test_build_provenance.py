"""Isolated stale-build negative controls; no native game build or launch."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import build_provenance as provenance


class BuildProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cpp = self.put("source/game/example.cpp", "int game = 1;\n")
        self.binary = self.put("build/behavior/reference/bin/starbound", "fake binary")

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def seal(self, build_dir=None):
        snapshot = provenance.begin(self.root, build_dir)
        return provenance.seal(self.binary, snapshot, self.root)

    def verify(self):
        return provenance.verify(self.binary, self.root)

    def test_success_returns_exact_recorded_proof(self):
        proof = self.seal()
        self.assertEqual(proof, self.verify())
        self.assertEqual(proof, json.loads(provenance.sidecar(self.binary).read_text()))
        self.assertIn("not a reproducible-build proof", proof["limitations"])

    def test_missing_proof_fails(self):
        with self.assertRaises(provenance.ProvenanceError):
            self.verify()

    def test_source_modification_fails_even_when_mtime_preserved(self):
        import os
        self.seal()
        stat = self.cpp.stat()
        self.cpp.write_text("int game = 2;\n")
        os.utime(self.cpp, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        with self.assertRaisesRegex(provenance.ProvenanceError, "changed=.*example.cpp"):
            self.verify()

    def test_added_source_fails(self):
        self.seal()
        self.put("source/game/added.hpp", "// added")
        with self.assertRaisesRegex(provenance.ProvenanceError, "added=.*added.hpp"):
            self.verify()

    def test_deleted_source_fails(self):
        self.seal()
        self.cpp.unlink()
        with self.assertRaisesRegex(provenance.ProvenanceError, "deleted=.*example.cpp"):
            self.verify()

    def test_modified_binary_fails(self):
        self.seal()
        self.binary.write_text("different binary")
        with self.assertRaisesRegex(provenance.ProvenanceError, "executable differs"):
            self.verify()

    def test_ignored_changes_do_not_invalidate(self):
        self.put("doc/notes.md", "before")
        self.seal()
        for path in ("doc/notes.md", "source/lab/behavior/behavior_lab.py", "source/lab/behavior/assets/test.object", "storage/save.cpp", "build/generated.hpp", "dist/file.cpp", "logs/a.cpp"):
            self.put(path, "after")
        self.verify()

    def test_input_rules_cover_build_contract(self):
        included = ["source/foo.mm", "source/foo.c", "source/foo.h", "source/foo.rs", "source/extern/fmt/format.cc", "source/foo.inc", "source/rust/a/Cargo.toml", "source/rust/a/Cargo.lock", "source/rust/a/build.rs", "source/CMakeLists.txt", "source/CMakePresets.json", "source/vcpkg.json", "source/core/version.cpp.in", "cmake/a.cmake", "toolchains/a.cmake", "triplets/a.cmake", "lib/include/a.h", "lib/a.a", "scripts/build-behavior-lab.sh", "CMakeLists.txt"]
        for path in included:
            self.put(path, "input")
        snapshot = provenance.source_snapshot(self.root)
        self.assertTrue(set(included).issubset(snapshot))
        self.assertEqual(list(snapshot), sorted(snapshot))
        self.assertEqual(snapshot, provenance.source_snapshot(self.root))

    def test_changes_during_build_cannot_be_sealed(self):
        snapshot = provenance.begin(self.root)
        self.cpp.write_text("changed during build")
        with self.assertRaises(provenance.ProvenanceError):
            provenance.seal(self.binary, snapshot, self.root)
        self.assertFalse(provenance.sidecar(self.binary).exists())

    def test_cache_and_external_tool_changes_fail(self):
        compiler = self.put("external/compiler", "#!/bin/sh\necho fixture-compiler-1\n")
        compiler.chmod(0o755)
        cache = self.put("build/cmake/CMakeCache.txt", f"CMAKE_CXX_COMPILER:FILEPATH={compiler}\nSTAR_USE_RUST_LIGHTING:BOOL=ON\n")
        proof = self.seal(cache.parent)
        self.assertEqual(proof["build_identity"]["tools"]["CMAKE_CXX_COMPILER"]["version"], "fixture-compiler-1")
        compiler.write_text("#!/bin/sh\necho fixture-compiler-2\n")
        with self.assertRaisesRegex(provenance.ProvenanceError, "identity differs"):
            self.verify()
        compiler.write_text("#!/bin/sh\necho fixture-compiler-1\n")
        self.verify()
        cache.write_text(cache.read_text() + "CMAKE_CXX_FLAGS:STRING=-ffast-math\n")
        with self.assertRaisesRegex(provenance.ProvenanceError, "identity differs"):
            self.verify()

    def test_added_symlink_directory_fails_closed(self):
        self.seal()
        external = self.root / "external-inputs"
        external.mkdir()
        (external / "hidden.cpp").write_text("new input")
        (self.root / "source/linked").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(provenance.ProvenanceError, "symlink input directory"):
            self.verify()

    def test_missing_cmake_cache_cannot_seal(self):
        with self.assertRaisesRegex(provenance.ProvenanceError, "missing CMake cache"):
            self.seal(self.root / "build/cmake")

    def test_malformed_receipt_fails(self):
        self.seal()
        provenance.sidecar(self.binary).write_text('{"schema":1}')
        with self.assertRaises(provenance.ProvenanceError):
            self.verify()

    def test_cli_phases_and_failure_status(self):
        script = Path(provenance.__file__).resolve()
        snapshot = self.root / "build/inputs.json"
        base = [sys.executable, str(script)]
        common = ["--source-root", str(self.root)]
        subprocess.run(base + ["begin", "--snapshot", str(snapshot)] + common, check=True, capture_output=True)
        subprocess.run(base + ["seal", "--snapshot", str(snapshot), "--binary", str(self.binary)] + common, check=True, capture_output=True)
        subprocess.run(base + ["verify", "--binary", str(self.binary)] + common, check=True, capture_output=True)
        self.cpp.write_text("stale")
        failed = subprocess.run(base + ["verify", "--binary", str(self.binary)] + common, capture_output=True, text=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("build inputs differ", failed.stderr)


if __name__ == "__main__":
    unittest.main()
