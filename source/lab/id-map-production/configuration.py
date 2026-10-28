"""Source-derived selector fixture; the parent alone runs native configuration.

This checks the selected CMake blocks and actual Rust.cmake graph, not the whole
application, an executed Cargo build, or a produced Rust archive.
"""

from pathlib import Path
import hashlib
import json
import re
import shlex


_FLAG = "STAR_USE_RUST_ID_MAP"
_METADATA = "id-map-configuration.txt"


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _selectors(source):
    options = re.findall(r"^option\(STAR_USE_RUST_[^\n]*\)$", source, re.M)
    names = [re.match(r"option\((STAR_USE_RUST_\w+)\s", line)[1]
             for line in options]
    # The production source currently declares 29 selectors, including IdMap.
    _require(len(options) == 29, f"expected 29 Rust options, observed {len(options)}")
    _require(len(set(names)) == 29 and _FLAG in names, "duplicate/missing Rust selector")
    _require(all(re.fullmatch(r'option\(STAR_USE_RUST_\w+ "[^"\n]*" OFF\)', line)
                 for line in options), "Rust option policy is no longer default OFF")
    gates = re.findall(r"^if\(STAR_USE_RUST_[^\n]*\)\n  include\(Rust\)\nendif\(\)",
                       source, re.M)
    _require(len(gates) == 1 and source.count("include(Rust)") == 1,
             "expected one actual Rust include gate")
    condition = gates[0].splitlines()[0][3:-1]
    _require(set(condition.split(" OR ")) == set(names)
             and len(condition.split(" OR ")) == 29,
             "Rust OR gate does not cover exactly the declared options")
    blocks = re.findall(r"^if\(STAR_USE_RUST_ID_MAP\)\n"
                        r"  add_compile_definitions\(STAR_USE_RUST_ID_MAP\)\nendif\(\)",
                        source, re.M)
    _require(len(blocks) == 1
             and source.count("add_compile_definitions(STAR_USE_RUST_ID_MAP)") == 1,
             "expected one actual IdMap definition block")
    return options, names, gates[0], blocks[0]


def _cmake_path(path):
    # Bracket arguments avoid shell/CMake variable interpolation in repo paths.
    value = str(path)
    _require("]=]" not in value and "\n" not in value, "unsupported CMake path")
    return "[=[" + value + "]=]"


def prepare(outputRoot: Path, repo: Path) -> Path:
    """Write a NEW fixture below outputRoot; never configure or build anything.

    Parent must use fresh OFF/ON Ninja build directories, selecting its admitted
    native compiler/SDK/tools explicitly; ON sets only STAR_USE_RUST_ID_MAP=ON.
    """
    repo = Path(repo).resolve(strict=True)
    outputRoot = Path(outputRoot).resolve()
    source = (repo / "source/CMakeLists.txt").read_text()
    options, names, gate, definition = _selectors(source)
    fixture = outputRoot / "configuration-fixture"
    # Refuse reuse rather than overwrite earlier evidence (including symlinks).
    outputRoot.mkdir(parents=True, exist_ok=True)
    fixture.mkdir()
    rust_recipe = repo / "cmake/Rust.cmake"
    metadata = [
        'get_directory_property(_definitions COMPILE_DEFINITIONS)',
        'get_directory_property(_imports IMPORTED_TARGETS)',
        'get_directory_property(_targets BUILDSYSTEM_TARGETS)',
        'set(_ffi 0)',
        'set(_build 0)',
        'set(_location "")',
        'if(TARGET star_rust_engine_ffi)',
        '  set(_ffi 1)',
        '  get_target_property(_location star_rust_engine_ffi IMPORTED_LOCATION)',
        'endif()',
        'if(TARGET star_rust_engine_ffi_build)',
        '  set(_build 1)',
        'endif()',
        'file(WRITE "${CMAKE_BINARY_DIR}/' + _METADATA + '"',
        '  "definitions=${_definitions}\\n"',
        '  "ffi=${_ffi}\\n"',
        '  "build=${_build}\\n"',
        '  "archive=${STAR_RUST_ARCHIVE}\\n"',
        '  "location=${_location}\\n"',
        '  "imports=${_imports}\\n"',
        '  "targets=${_targets}\\n"',
        '  "rust_source=${STAR_RUST_SOURCE}\\n"',
        '  "rust_host=${STAR_RUST_HOST}\\n"',
        '  "rustc=${STAR_RUSTC_EXECUTABLE}\\n"',
    ]
    metadata += ['  "' + name + '=${' + name + '}\\n"' for name in names]
    metadata += [')']
    cmake = '\n'.join([
        'cmake_minimum_required(VERSION 3.23)',
        'project(IdMapConfiguration LANGUAGES CXX)',
        'set(CMAKE_EXPORT_COMPILE_COMMANDS ON)',
        'set(CMAKE_MODULE_PATH ' + _cmake_path(repo / 'cmake') + ')',
        'set(PROJECT_SOURCE_DIR ' + _cmake_path(repo / 'source') + ')',
        'set(STAR_ARCHITECTURE arm64)',
        *options, gate, definition,
        'add_library(id_map_configuration_dummy STATIC dummy.cpp)',
        *metadata, '',
    ])
    (fixture / "CMakeLists.txt").write_text(cmake)
    (fixture / "dummy.cpp").write_text("int id_map_configuration_dummy() { return 0; }\n")
    (fixture / "derivation.json").write_text(json.dumps({
        "repo": str(repo), "options": names,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "rust_cmake_sha256": hashlib.sha256(rust_recipe.read_bytes()).hexdigest(),
        "gate": gate, "definition": definition, "option_lines": options,
    }, indent=2) + "\n")
    return fixture


def _metadata(build):
    rows = (build / _METADATA).read_text().splitlines()
    pairs = [line.split("=", 1) for line in rows]
    _require(all(len(pair) == 2 for pair in pairs), "malformed configure metadata")
    values = dict(pairs)
    _require(len(values) == len(pairs), "duplicate metadata key")
    return values


def _list(value):
    return value.split(";") if value else []


def check(offBuild: Path, onBuild: Path, selectedRustc: str):
    """Read configure artifacts only. Does not invoke CMake, Cargo, or a compiler."""
    offBuild, onBuild = Path(offBuild).resolve(), Path(onBuild).resolve()
    _require(offBuild != onBuild, "OFF and ON builds must be distinct")
    _require(bool(selectedRustc), "selected rustc is required")
    provenance = None
    on_meta = None
    for build, enabled in ((offBuild, False), (onBuild, True)):
        cache = (build / "CMakeCache.txt").read_text()
        roots = re.findall(r"^CMAKE_HOME_DIRECTORY:INTERNAL=(.+)$", cache, re.M)
        _require(len(roots) == 1, "missing unique fixture source directory")
        fixture = Path(roots[0])
        derivation = json.loads((fixture / "derivation.json").read_text())
        if provenance is None:
            provenance = derivation
        _require(derivation == provenance, "OFF/ON fixture derivations differ")
        repo = Path(derivation["repo"])
        source = (repo / "source/CMakeLists.txt").read_text()
        options, names, gate, definition = _selectors(source)
        _require(hashlib.sha256(source.encode()).hexdigest() == derivation["source_sha256"]
                 and hashlib.sha256((repo / "cmake/Rust.cmake").read_bytes()).hexdigest()
                 == derivation["rust_cmake_sha256"], "source changed after preparation")
        _require(options == derivation["option_lines"] and names == derivation["options"]
                 and gate == derivation["gate"] and definition == derivation["definition"],
                 "selector derivation mismatch")
        meta = _metadata(build)
        for name in names:
            expected = "ON" if enabled and name == _FLAG else "OFF"
            _require(meta[name] == expected, f"{build}: unexpected {name}={meta[name]}")
            _require(f"{name}:BOOL={expected}" in cache.splitlines(),
                     f"{build}: selector cache mismatch for {name}")
        _require(_list(meta["definitions"]) == ([_FLAG] if enabled else []),
                 f"{build}: unexpected directory definitions")
        _require(meta["ffi"] == meta["build"] == ("1" if enabled else "0"),
                 f"{build}: aggregate target presence mismatch")
        _require(_list(meta["imports"]) == (["star_rust_engine_ffi"] if enabled else []),
                 "expected only the single existing Rust imported aggregate")
        targets = _list(meta["targets"])
        _require(sorted(targets) == sorted(["id_map_configuration_dummy"]
                 + (["star_rust_engine_ffi_build"] if enabled else [])),
                 "unexpected build targets")
        commands = json.loads((build / "compile_commands.json").read_text())
        _require(len(commands) == 1, "expected exactly one dummy compile command")
        entry = commands[0]
        _require(Path(entry["file"]).resolve() == (fixture / "dummy.cpp").resolve(),
                 "compile command is not the dummy translation unit")
        args = entry.get("arguments") or shlex.split(entry["command"])
        defines = [arg for arg in args if arg.startswith("-DSTAR_USE_RUST_")]
        _require(defines == (["-D" + _FLAG] if enabled else []),
                 "actual compile command selector mismatch")
        if enabled:
            on_meta = meta
            expected_archive = build / "rust-engine-ffi" / meta["rust_host"] / "release/libstar_engine_ffi.a"
            _require(bool(meta["rust_host"]), "missing Rust host")
            _require(meta["archive"] == meta["location"] == str(expected_archive),
                     "aggregate archive location mismatch")
            _require(meta["rust_source"] == str(repo / "source/rust"), "wrong Rust source")
            _require(meta["rustc"] == selectedRustc, "wrong selected rustc")
        else:
            _require(meta["archive"] == meta["location"] == meta["rust_source"] == "",
                     "OFF unexpectedly configured Rust")
    ninja = (onBuild / "build.ninja").read_text()
    commands = [shlex.split(line.strip()[len("COMMAND = "):].replace("$$", "$"))
                for line in ninja.splitlines() if line.strip().startswith("COMMAND = ")]
    rust_commands = [args for args in commands if "--package" in args
                     and "star-engine-ffi" in args]
    _require(len(rust_commands) == 1, "expected exactly one aggregate Cargo custom command")
    args = rust_commands[0]
    _require("RUSTC=" + selectedRustc in args, "custom command omitted selected RUSTC")
    _require("--manifest-path" in args and args[args.index("--manifest-path") + 1]
             == str(Path(provenance["repo"]) / "source/rust/Cargo.toml"),
             "custom command does not use actual aggregate manifest")
    _require(args[args.index("--package") + 1] == "star-engine-ffi",
             "wrong aggregate Cargo package")
    _require(all(arg in args for arg in ("build", "--release", "--locked", "--offline")),
             "missing existing aggregate Cargo recipe flags")
    return {"off": str(offBuild), "on": str(onBuild),
            "archive": on_meta["archive"], "rustc": selectedRustc,
            "source_sha256": provenance["source_sha256"],
            "rust_cmake_sha256": provenance["rust_cmake_sha256"],
            "scope": "selector blocks and configure graph only; Cargo not executed"}
