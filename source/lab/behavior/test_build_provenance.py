"""Isolated stale-build negative controls; no native game build or launch."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

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
        if build_dir is not None:
            snapshot = provenance.configured(snapshot, self.root)
        return provenance.seal(self.binary, snapshot, self.root)

    def verify(self):
        return provenance.verify(self.binary, self.root)

    def test_success_returns_exact_recorded_proof(self):
        proof = self.seal()
        self.assertEqual(proof, self.verify())
        self.assertEqual(proof, json.loads(provenance.sidecar(self.binary).read_text()))
        self.assertIn("not a reproducible-build proof", proof["limitations"])

    def test_default_seal_retains_exact_legacy_bytes(self):
        proof = self.seal()
        expected = (json.dumps(proof, indent=2, sort_keys=True) + '\n').encode()
        self.assertEqual(provenance.sidecar(self.binary).read_bytes(), expected)

    def test_injected_seal_writer_never_calls_legacy_writer(self):
        snapshot = provenance.begin(self.root)
        calls = []
        with patch.object(provenance, '_write', side_effect=AssertionError('legacy writer bypass')):
            proof = provenance.seal(self.binary, snapshot, self.root,
                                    write=lambda path, value: calls.append((path, value)))
        self.assertEqual(calls, [(provenance.sidecar(self.binary.resolve()), proof)])
        self.assertFalse(provenance.sidecar(self.binary).exists())

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
        self.put("build/cmake/compile_commands.json", json.dumps([
            {"file": str(self.cpp), "directory": str(cache.parent)}]))
        # tool execution belongs to host integration, not these source fixtures.
        with patch.object(provenance.subprocess, 'run', return_value=subprocess.CompletedProcess(
                [str(compiler), '--version'], 0, 'fixture-compiler-1\n', '')) as probe:
            proof = self.seal(cache.parent)
            self.assertEqual(proof["build_identity"]["tools"]["CMAKE_CXX_COMPILER"]["version"], "fixture-compiler-1")
            self.assertEqual(probe.call_args.args[0], [str(compiler), '--version'])
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

    def cmake_inputs(self):
        build = self.root / "build/cmake"
        self.put("build/cmake/CMakeCache.txt", "STAR_USE_RUST_PATH_EMBED:BOOL=OFF\n")
        generated = self.put("build/cmake/core/StarVersion.cpp", 'char const* version = "before";\n')
        self.put("build/cmake/compile_commands.json", json.dumps([
            {"file": str(self.cpp), "directory": str(build)},
            {"file": str(generated), "directory": str(build)}]))
        return build, generated

    def test_postbuild_only_generated_source_binding_is_rejected(self):
        build, _ = self.cmake_inputs()
        snapshot = provenance.begin(self.root, build)
        with self.assertRaisesRegex(provenance.ProvenanceError, "not frozen before compilation"):
            provenance.seal(self.binary, snapshot, self.root)
        self.assertFalse(provenance.sidecar(self.binary).exists())

    def test_generated_source_is_bound_before_build_and_during_verify(self):
        build, generated = self.cmake_inputs()
        proof = self.seal(build)
        self.assertIn(str(generated), proof["compile_source_files"])
        self.assertEqual(self.verify(), proof)
        generated.write_text('char const* version = "after";\n')
        with self.assertRaisesRegex(provenance.ProvenanceError, "compilation source inputs differ"):
            self.verify()

    def test_generated_source_change_during_compilation_cannot_be_sealed(self):
        build, generated = self.cmake_inputs()
        snapshot = provenance.configured(provenance.begin(self.root, build), self.root)
        generated.write_text("changed after configuration")
        with self.assertRaisesRegex(provenance.ProvenanceError, "compilation source inputs differ"):
            provenance.seal(self.binary, snapshot, self.root)
        self.assertFalse(provenance.sidecar(self.binary).exists())

    def test_generated_source_change_while_hashing_binary_cannot_be_sealed(self):
        build, generated = self.cmake_inputs()
        snapshot = provenance.configured(provenance.begin(self.root, build), self.root)
        original_hash = provenance._hash
        def mutate_after_binary_hash(path):
            result = original_hash(path)
            if path == self.binary.resolve():
                generated.write_text("changed while sealing")
            return result
        with patch.object(provenance, '_hash', side_effect=mutate_after_binary_hash):
            with self.assertRaisesRegex(provenance.ProvenanceError, "compilation source inputs differ"):
                provenance.seal(self.binary, snapshot, self.root)
        self.assertFalse(provenance.sidecar(self.binary).exists())

    def test_generated_source_omission_is_rejected(self):
        build, generated = self.cmake_inputs()
        snapshot = provenance.configured(provenance.begin(self.root, build), self.root)
        del snapshot["compile_source_files"][str(generated)]
        with self.assertRaisesRegex(provenance.ProvenanceError, "compilation source inputs differ"):
            provenance.seal(self.binary, snapshot, self.root)

    def test_missing_generated_source_cannot_be_frozen(self):
        build, generated = self.cmake_inputs()
        generated.unlink()
        with self.assertRaisesRegex(provenance.ProvenanceError, "compilation sources"):
            provenance.configured(provenance.begin(self.root, build), self.root)

    def test_malformed_receipt_fails(self):
        self.seal()
        provenance.sidecar(self.binary).write_text('{"schema":1}')
        with self.assertRaises(provenance.ProvenanceError):
            self.verify()

    def cli(self, args, *, check=True):
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with patch('sys.argv', ['build_provenance.py', *args]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                provenance.main()
            except SystemExit as exc:
                code = exc.code
        if check:
            self.assertEqual(code, 0, err.getvalue())
        return SimpleNamespace(returncode=code, stdout=out.getvalue(), stderr=err.getvalue())

    def test_cli_configured_phase_binds_generated_sources(self):
        build, generated = self.cmake_inputs()
        snapshot = self.root / "build/inputs.json"
        common = ["--source-root", str(self.root)]
        self.cli(["begin", "--build-dir", str(build), "--snapshot", str(snapshot)] + common)
        self.cli(["configured", "--snapshot", str(snapshot)] + common)
        self.cli(["seal", "--snapshot", str(snapshot), "--binary", str(self.binary)] + common)
        self.cli(["verify", "--binary", str(self.binary)] + common)
        generated.write_text("changed after seal")
        failed = self.cli(["verify", "--binary", str(self.binary)] + common, check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("compilation source inputs differ", failed.stderr)

    def test_cli_phases_and_failure_status(self):
        snapshot = self.root / "build/inputs.json"
        common = ["--source-root", str(self.root)]
        self.cli(["begin", "--snapshot", str(snapshot)] + common)
        self.cli(["seal", "--snapshot", str(snapshot), "--binary", str(self.binary)] + common)
        self.cli(["verify", "--binary", str(self.binary)] + common)
        self.cpp.write_text("stale")
        failed = self.cli(["verify", "--binary", str(self.binary)] + common, check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("build inputs differ", failed.stderr)


if __name__ == "__main__":
    unittest.main()
