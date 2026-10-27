#!/usr/bin/env python3
"""Bind behavior binaries to build-time source content, not just executable bytes.

This is a local stale-build guard, not an attestation or reproducible-build proof.
External vcpkg packages and system SDK transitive inputs are NOT fully verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


class ProvenanceError(ValueError):
    """A build receipt is missing, malformed, or no longer matches its inputs."""


SOURCE_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = 1
LIMITATIONS = (
    "Local content receipt, not a reproducible-build proof or signed attestation; "
    "external vcpkg packages and system SDK transitive dependencies are not fully verified. "
    "Before/after snapshots cannot detect edits reverted between snapshots."
)
EXCLUDED = {"build", "storage", "logs", "dist", ".git", "__pycache__", "target"}
SOURCE_SUFFIXES = {".cpp", ".hpp", ".cc", ".hh", ".c", ".h", ".mm", ".rs", ".toml", ".lock", ".cmake", ".in", ".inc", ".S"}
ROOT_FILES = {"CMakeLists.txt", "CMakePresets.json", "CMakeUserPresets.json", "vcpkg.json", "vcpkg-configuration.json", "flake.nix", "flake.lock"}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_snapshot(source_root: Path = SOURCE_ROOT) -> dict[str, str]:
    """Return the deterministic input set; additions/deletions change this map too.

    Repository cmake/toolchains/triplets/lib are included in full. source/lab is
    excluded because it is diagnostic code, not compiled game input; runtime
    fixture assets have their own overlay receipt in the behavior runner.
    """
    root = Path(source_root).resolve()
    if not (root / "source").is_dir():
        raise ProvenanceError(f"missing source tree: {root / 'source'}")
    result = {}

    def walk_error(error):
        raise ProvenanceError(f"cannot enumerate build inputs: {error}") from error

    for directory, dirs, files in os.walk(root, onerror=walk_error):
        parent = Path(directory).relative_to(root)
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not (parent == Path("source") and d == "lab"))
        # Only traverse the explicitly supported build input trees.
        if parent == Path("."):
            dirs[:] = [d for d in dirs if d in {"source", "cmake", "toolchains", "triplets", "lib", "scripts"}]
        if parent.parts and parent.parts[0] == "scripts":
            dirs[:] = []
        for name in dirs:
            if (root / parent / name).is_symlink():
                # Do not silently omit compiler inputs behind directory links.
                raise ProvenanceError(f"unsupported symlink input directory: {parent / name}")
        for name in sorted(files):
            rel = parent / name
            parts = rel.parts
            include = (
                (len(parts) == 1 and (name in ROOT_FILES or Path(name).suffix in {".cmake", ".toml", ".lock", ".rs"}))
                or (parts[0] == "source" and (Path(name).suffix in SOURCE_SUFFIXES or name in ROOT_FILES))
                or parts[0] in {"cmake", "toolchains", "triplets", "lib"}
                or rel.as_posix() == "scripts/build-behavior-lab.sh"
            )
            if include:
                result[rel.as_posix()] = _hash(root / rel)
    return dict(sorted(result.items()))


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("expected object")
        return value
    except (OSError, ValueError) as exc:
        raise ProvenanceError(f"cannot read provenance {path}: {exc}") from exc


def _write(path: Path, value: dict) -> None:
    # Atomic publication prevents a partial receipt from looking successful.
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=path.name + ".", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def sidecar(binary: Path) -> Path:
    return Path(str(binary) + ".behavior-build.json")


def begin(source_root: Path = SOURCE_ROOT, build_dir: Path | None = None) -> dict:
    """Snapshot BEFORE configure/build. Pass this result to seal after success."""
    root = Path(source_root).resolve()
    return {"schema": SCHEMA, "source_root": str(root), "source_files": source_snapshot(root),
            "build_dir": str(Path(build_dir).resolve()) if build_dir is not None else None}


def _build_identity(build_dir: Path | None) -> dict:
    if build_dir is None:
        return {"kind": "no-cmake-cache", "files": {}, "cache": {}, "tools": {}}
    cache_path = build_dir / "CMakeCache.txt"
    if not cache_path.is_file():
        raise ProvenanceError(f"missing CMake cache: {cache_path}")
    cache = {}
    for line in cache_path.read_text().splitlines():
        if not line or line.startswith(("#", "//")) or "=" not in line or ":" not in line.split("=", 1)[0]:
            continue
        key_type, value = line.split("=", 1)
        key = key_type.split(":", 1)[0]
        if key.startswith(("CMAKE_", "VCPKG_", "STAR_")):
            cache[key] = value
    files = {str(cache_path): _hash(cache_path)}
    for name in ("build.ninja", "compile_commands.json"):
        path = build_dir / name
        if path.is_file():
            files[str(path)] = _hash(path)
    tools = {}
    for key in ("CMAKE_COMMAND", "CMAKE_C_COMPILER", "CMAKE_CXX_COMPILER", "CMAKE_MAKE_PROGRAM", "CMAKE_AR", "CMAKE_RANLIB", "CMAKE_TOOLCHAIN_FILE", "STAR_CARGO_EXECUTABLE", "STAR_RUSTC_EXECUTABLE"):
        value = cache.get(key)
        if not value:
            continue
        path = Path(value)
        if not path.is_file():
            raise ProvenanceError(f"missing build tool: {key}={value}")
        tool = {"path": str(path), "sha256": _hash(path)}
        if key != "CMAKE_TOOLCHAIN_FILE":
            try:
                process = subprocess.run([str(path), "--version"], capture_output=True, text=True, timeout=10, check=False)
                tool["version_exit_code"] = process.returncode
                tool["version"] = (process.stdout + process.stderr).strip()
            except (OSError, subprocess.TimeoutExpired) as exc:
                tool["version_unavailable"] = type(exc).__name__
        tools[key] = tool
    return {"kind": "cmake", "files": files, "cache": cache, "tools": tools}


def _compile_source_inputs(build_dir: Path) -> dict[str, str]:
    """Include configure-generated TUs that source-tree walks cannot observe."""
    database = build_dir / "compile_commands.json"
    try:
        entries = json.loads(database.read_text())
        if not isinstance(entries, list) or not entries:
            raise ValueError("expected nonempty command database")
        result = {}
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("file"), str) or not isinstance(entry.get("directory"), str):
                raise ValueError("invalid compilation source/directory")
            path = Path(entry["file"])
            if not path.is_absolute():
                path = Path(entry["directory"]) / path
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"missing or symlink compilation source: {path}")
            result[str(path)] = _hash(path)
        return dict(sorted(result.items()))
    except (OSError, ValueError, TypeError) as exc:
        raise ProvenanceError(f"cannot bind configured compilation sources: {exc}") from exc


def configured(snapshot: dict, source_root: Path | None = None) -> dict:
    """Freeze generated sources and evaluated recipes before compilation.

    A post-build digest cannot establish which generated bytes the compiler
    read. Keep this separate from begin(), since CMake creates those inputs.
    """
    root = Path(source_root or SOURCE_ROOT).resolve()
    if snapshot.get("schema") != SCHEMA or snapshot.get("source_root") != str(root) or not snapshot.get("build_dir"):
        raise ProvenanceError("configured phase requires a source snapshot with a CMake directory")
    _check_sources(snapshot["source_files"], root)
    build_dir = Path(snapshot["build_dir"])
    identity = _build_identity(build_dir)
    sources = _compile_source_inputs(build_dir)
    _check_sources(snapshot["source_files"], root)
    if _build_identity(build_dir) != identity or _compile_source_inputs(build_dir) != sources:
        raise ProvenanceError("configuration inputs changed while being frozen")
    return {**snapshot, "build_identity": identity, "compile_source_files": sources}


def _check_configured(snapshot: dict, build_dir: Path, identity: dict) -> None:
    if "compile_source_files" not in snapshot or "build_identity" not in snapshot:
        raise ProvenanceError("configuration inputs were not frozen before compilation")
    if identity != snapshot["build_identity"]:
        raise ProvenanceError("CMake/compiler/toolchain identity differs from configured inputs")
    if _compile_source_inputs(build_dir) != snapshot["compile_source_files"]:
        raise ProvenanceError("configured compilation source inputs differ")


def _check_sources(recorded: dict, root: Path) -> None:
    actual = source_snapshot(root)
    if actual != recorded:
        added = sorted(actual.keys() - recorded.keys())
        deleted = sorted(recorded.keys() - actual.keys())
        changed = sorted(k for k in actual.keys() & recorded.keys() if actual[k] != recorded[k])
        raise ProvenanceError(f"build inputs differ: added={added}, deleted={deleted}, changed={changed}")


def seal(binary: Path, snapshot: dict, source_root: Path | None = None) -> dict:
    """Seal only AFTER a successful build; seal itself does not run the builder.

    build_dir=None supports isolated fake-client tests and is labeled in the
    receipt. Production builder always supplies its actual CMake directory.
    """
    binary = Path(binary).resolve()
    root = Path(source_root or SOURCE_ROOT).resolve()
    if snapshot.get("schema") != SCHEMA or snapshot.get("source_root") != str(root):
        raise ProvenanceError("snapshot schema/source root mismatch")
    try:
        _check_sources(snapshot["source_files"], root)
        build_dir = Path(snapshot["build_dir"]) if snapshot.get("build_dir") else None
        identity = _build_identity(build_dir)
        if build_dir is not None:
            _check_configured(snapshot, build_dir, identity)
        binary_hash = _hash(binary)
        _check_sources(snapshot["source_files"], root)
        if build_dir is not None:
            _check_configured(snapshot, build_dir, _build_identity(build_dir))
        proof = {**snapshot, "binary": str(binary), "binary_sha256": binary_hash,
                 "build_identity": identity, "limitations": LIMITATIONS}
        _write(sidecar(binary), proof)
        return proof
    except (OSError, KeyError, TypeError) as exc:
        raise ProvenanceError(f"cannot seal build: {exc}") from exc


def verify(binary: Path, source_root: Path | None = None) -> dict:
    """Return recorded proof, or fail closed before capture outputs or launch.

    Call again after the run. Tests should supply an isolated source_root.
    """
    binary = Path(binary).resolve()
    root = Path(source_root or SOURCE_ROOT).resolve()
    proof = _read(sidecar(binary))
    try:
        if proof["schema"] != SCHEMA or proof["source_root"] != str(root) or proof["binary"] != str(binary):
            raise ProvenanceError("provenance schema/path mismatch")
        if _hash(binary) != proof["binary_sha256"]:
            raise ProvenanceError("executable differs from sealed build")
        _check_sources(proof["source_files"], root)
        build_dir = Path(proof["build_dir"]) if proof.get("build_dir") else None
        identity = _build_identity(build_dir)
        if identity != proof["build_identity"]:
            raise ProvenanceError("CMake/compiler/toolchain identity differs from sealed build")
        if build_dir is not None:
            _check_configured(proof, build_dir, identity)
        return proof
    except (OSError, KeyError, TypeError, AttributeError) as exc:
        raise ProvenanceError(f"invalid build provenance: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("begin", "configured", "seal", "verify"))
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--binary", type=Path)
    args = parser.parse_args()
    try:
        if args.phase == "begin":
            if args.snapshot is None:
                parser.error("begin requires --snapshot")
            _write(args.snapshot, begin(args.source_root, args.build_dir))
        elif args.phase == "configured":
            if args.snapshot is None:
                parser.error("configured requires --snapshot")
            _write(args.snapshot, configured(_read(args.snapshot), args.source_root))
        else:
            if args.binary is None or (args.phase == "seal" and args.snapshot is None):
                parser.error("seal/verify require --binary; seal requires --snapshot")
            proof = seal(args.binary, _read(args.snapshot), args.source_root) if args.phase == "seal" else verify(args.binary, args.source_root)
            print(json.dumps(proof, sort_keys=True))
    except (ProvenanceError, OSError) as exc:
        parser.exit(1, f"build provenance: {exc}\n")


if __name__ == "__main__":
    main()
