#!/usr/bin/env python3
"""Replay the phase-1 native host boundary; no production/Rust/game build."""
import argparse
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = args.output.absolute()
    if any(p.is_symlink() for p in (raw, *raw.parents)):
        parser.error("symlink output refused")
    out = raw.resolve()
    base = ROOT / "build/json-patch-lab/host-prototype"
    if not out.is_relative_to(base) or out == base or out.exists():
        parser.error("new nested host-prototype output required")
    out.mkdir(parents=True)
    cm = ROOT / "build/behavior/reference/cmake"
    entry = next(e for e in json.loads((cm / "compile_commands.json").read_text()) if e["file"].endswith("/StarJsonPatch.cpp"))
    recipe = shlex.split(entry["command"])
    flags, skip = [], False
    for flag in recipe[1:]:
        if skip: skip = False; continue
        if flag == "-o": skip = True
        elif flag not in ("-c", entry["file"]): flags.append(flag)
    if any("STAR_USE_RUST_" in flag for flag in flags): raise ValueError("not an all-C++ reference recipe")
    lines = (cm / "build.ninja").read_text().splitlines()
    index = next(i for i, s in enumerate(lines) if s.startswith("build ") and "/bin/starbound:" in s)
    objects = [cm / p for p in shlex.split(lines[index].split(": ", 1)[1])[1:] if p.endswith(".o") and p.startswith(("core/", "extern/")) and not p.endswith("/StarJsonPatch.cpp.o")]
    if not objects or any(not p.is_file() for p in objects): raise ValueError("reference objects missing")
    libs = shlex.split(next(s.split(" = ", 1)[1] for s in lines[index + 1:index + 15] if s.startswith("  LINK_LIBRARIES = ")))
    libs = [str(cm / p) if p.endswith(".a") and not Path(p).is_absolute() else p for p in libs]
    commands = []

    def run(command, name):
        command = list(map(str, command)); commands.append(shlex.join(command))
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=100)
        (out / (name + ".log")).write_text(commands[-1] + "\n" + result.stdout + result.stderr)
        return result

    tracked = [Path(__file__), *[HERE / name for name in ("host_contract.hpp", "host_contract.cpp", "host_contract_test.cpp", "StarJsonPatch.reference.cpp", "StarJsonPatch.reference.hpp")], cm / "compile_commands.json", cm / "build.ninja", Path(recipe[0]).resolve(), *objects, *[Path(p) for p in libs if p.endswith(".a")]]
    dep = out / "deps.d"
    result = run([recipe[0], *flags, "-I" + str(HERE), "-M", "-MF", dep, HERE / "host_contract_test.cpp"], "dependencies")
    if result.returncode: raise RuntimeError("dependency scan failed")
    tracked += [Path(p) if Path(p).is_absolute() else ROOT / p for p in shlex.split(dep.read_text().replace("\\\n", " ").split(":", 1)[1])]
    tracked = list(dict.fromkeys(p.resolve() for p in tracked if p.is_file()))
    before = {str(p): sha(p) for p in tracked}; (out / "before.json").write_text(json.dumps(before, indent=2))
    archive = out / "native-core.a"
    if run(["/usr/bin/ar", "rcs", archive, *objects], "archive").returncode: raise RuntimeError("archive failed")
    binary = out / "host-test"
    if run([recipe[0], *flags, "-I" + str(HERE), HERE / "host_contract_test.cpp", HERE / "StarJsonPatch.reference.cpp", archive, *libs, "-Wl,-dead_strip", "-o", binary], "compile").returncode: raise RuntimeError("compile failed")
    result = run([binary], "baseline"); repeat = run([binary], "repeat")
    if result.returncode or repeat.returncode or result.stdout != repeat.stdout: raise RuntimeError("host boundary comparison/repeat failed")
    report = json.loads(result.stdout)
    if len(report["coverage"]) != 42 or any(n <= 0 for n in report["coverage"]): raise RuntimeError("opcode coverage incomplete")
    failure = run([binary, "known-fault"], "known-fault")
    if failure.returncode != 1 or "COMPARISON deliberate wrong typed handler" not in failure.stderr: raise RuntimeError("known verifier failure escaped")
    for language, assertion, standard in (("c", "_Static_assert", "c11"), ("c++", "static_assert", "c++17")):
        source = out / ("abi-" + standard + ".txt")
        source.write_text('#include "host_contract.hpp"\n' + assertion + '(sizeof(uint32_t)==4,"u32");\n' + assertion + '(sizeof(uint64_t)==8,"u64");\nint main(void){return JP_APPLY_RELEASE!=41;}\n')
        if run([recipe[0], "-x", language, "-std=" + standard, "-Wall", "-Wextra", "-Werror", "-pedantic", "-I" + str(HERE), source, "-o", out / ("abi-" + standard)], "abi-" + standard).returncode: raise RuntimeError("strict ABI probe failed")
        if run([out / ("abi-" + standard)], "abi-run-" + standard).returncode: raise RuntimeError("ABI runtime probe failed")
    after = {str(p): sha(p) for p in tracked}; (out / "after.json").write_text(json.dumps(after, indent=2))
    if before != after: raise RuntimeError("source/compiler/native-object/checker drift")
    report.update(commands=commands, bindings=before, binary_sha256=sha(binary), negative_controls=["known-wrong-typed-handler"], limits=["phase-1 C++ prototype only; no Rust or game qualification", "compiler-bound evaluation; no actual OOM injection", "semantic values remain native; opaque-context allocation validity is a caller precondition"])
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("commands", "bindings")}))


if __name__ == "__main__": main()
