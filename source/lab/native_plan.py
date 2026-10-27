"""declarative POSIX command preflight; no commands or filesystem queries.

paths and argv are exact built-in bytes, never Path/str/repr conversions. paths
must be absolute and lexically canonical. argv (including read-only tool aliases)
is opaque; declare tool files as inputs when needed, not as writable outputs.
outputs and logs share one owned-root check. logs includes stdout/stderr captures.

receipts and availability are caller assertions, NOT actual exit attestation or
filesystem witnesses. this checks neither argv's real reads/writes nor aliases,
symlinks/hardlinks, tool hashes, implicit driver inputs, SDK/runtime, code origin,
compiler semantics/native behavior, liveness or external-tool side effects.
lexical POSIX checks do not claim Windows safety or provenance/class acceptance.
"""
from dataclasses import dataclass

import native_evidence_json as evidence


@dataclass(frozen=True)
class Stage:
    stage_id: str
    argv: tuple[bytes, ...]
    inputs: tuple[bytes, ...] = ()
    outputs: tuple[bytes, ...] = ()
    logs: tuple[bytes, ...] = ()
    requires: tuple[str, ...] = ()

    @property
    def writes(self):
        return self.outputs + self.logs


@dataclass(frozen=True)
class Plan:
    owned_root: bytes
    initial_inputs: tuple[bytes, ...]
    stages: tuple[Stage, ...]


@dataclass(frozen=True)
class Receipt:
    stage_id: str
    completed: bool
    exit_code: int
    outputs: tuple[bytes, ...]


def _path(path):
    if type(path) is not bytes:
        raise TypeError("exact byte path required")
    if (not path.startswith(b"/") or b"\0" in path
            or any(p in (b"", b".", b"..") for p in path[1:].split(b"/"))):
        raise ValueError("noncanonical absolute POSIX path")


def _tuple(values, item_type):
    if type(values) is not tuple or any(type(v) is not item_type for v in values):
        raise TypeError("exact tuple and item types required")


def _unique(values):
    if len(set(values)) != len(values):
        raise ValueError("duplicate declaration")


def _file_conflict(path, existing):
    # All artifacts are FILE declarations, so a file cannot also be a parent.
    return any(path == p or path.startswith(p + b"/") or p.startswith(path + b"/")
               for p in existing)


def _id(value):
    if type(value) is not str or not value:
        raise TypeError("nonempty exact string stage ID required")


def preflight(plan: Plan) -> str:
    """return the entire typed manifest only after validation and codec roundtrip.

    input producers must already precede their consumer AND be in its explicit
    dependency closure; a future object cannot satisfy driver expansion.
    """
    if type(plan) is not Plan:
        raise TypeError("frozen Plan required")
    _path(plan.owned_root)
    _tuple(plan.initial_inputs, bytes)
    _unique(plan.initial_inputs)
    checked_inputs = set()
    for path in plan.initial_inputs:
        _path(path)
        if _file_conflict(path, checked_inputs):
            raise ValueError("overlapping prebound file paths")
        checked_inputs.add(path)
    _tuple(plan.stages, Stage)
    producers = {p: None for p in plan.initial_inputs}
    ancestors = {}
    manifest_stages = []
    for stage in plan.stages:
        _id(stage.stage_id)
        if stage.stage_id in ancestors:
            raise ValueError("duplicate stage ID")
        _tuple(stage.argv, bytes)
        if not stage.argv or not stage.argv[0] or any(b"\0" in a for a in stage.argv):
            raise ValueError("nonempty executable and NUL-free argv required")
        _tuple(stage.requires, str)
        _unique(stage.requires)
        parents = set()
        for dep in stage.requires:
            _id(dep)
            if dep not in ancestors:
                raise ValueError("unknown, cyclic or forward stage dependency")
            parents.update(ancestors[dep] | {dep})
        for paths in (stage.inputs, stage.outputs, stage.logs):
            _tuple(paths, bytes)
            _unique(paths)
            for path in paths:
                _path(path)
        for path in stage.inputs:
            if path not in producers:
                raise ValueError("undeclared or not-yet-produced input")
            if producers[path] is not None and producers[path] not in parents:
                raise ValueError("input producer missing from dependencies")
        _unique(stage.writes)
        for path in stage.writes:
            if not path.startswith(plan.owned_root + b"/"):
                raise ValueError("output or log escapes owned root")
            if _file_conflict(path, producers):
                raise ValueError("output collision, file-parent conflict or prebound overwrite")
            producers[path] = stage.stage_id
        ancestors[stage.stage_id] = parents
        manifest_stages.append({"stage_id": stage.stage_id, "argv": stage.argv,
                                "inputs": stage.inputs, "outputs": stage.outputs,
                                "logs": stage.logs, "requires": stage.requires})
    manifest = {"format": "star-native-plan-v1", "owned_root": plan.owned_root,
                "initial_inputs": plan.initial_inputs, "stages": tuple(manifest_stages)}
    encoded = evidence.dumps(manifest)
    if evidence.loads(encoded) != manifest:
        raise ValueError("plan manifest transport mismatch")
    return encoded


def _state(plan, receipts, available):
    preflight(plan)  # readiness cannot bypass whole-plan transport preflight.
    _tuple(receipts, Receipt)
    _tuple(available, bytes)
    _unique(available)
    for path in available:
        _path(path)
    available = set(available)
    stages = {s.stage_id: s for s in plan.stages}
    completed = set()
    credited = set(plan.initial_inputs)
    for receipt in receipts:
        _id(receipt.stage_id)
        if receipt.stage_id not in stages or receipt.stage_id in completed:
            raise ValueError("unknown or duplicate receipt stage")
        stage = stages[receipt.stage_id]
        if receipt.completed is not True or type(receipt.exit_code) is not int or receipt.exit_code != 0:
            raise ValueError("only completed exact-integer exit zero can be credited")
        _tuple(receipt.outputs, bytes)
        _unique(receipt.outputs)
        if set(receipt.outputs) != set(stage.writes):
            raise ValueError("partial or undeclared receipt outputs")
        if not set(stage.requires) <= completed:
            raise ValueError("receipt precedes required successful stage")
        if not set(stage.inputs) <= credited & available:
            raise ValueError("receipt input unavailable or uncredited")
        if not set(stage.writes) <= available:
            raise ValueError("completed output not declared available")
        credited.update(stage.writes)
        completed.add(stage.stage_id)
    if not available <= credited:
        raise ValueError("unknown or uncompleted artifact declared available")
    return stages, completed, available


def check_ready(plan: Plan, stage_id: str, receipts: tuple[Receipt, ...],
                available: tuple[bytes, ...]) -> None:
    """validate simulated readiness, not permission or supervision to execute."""
    stages, completed, available = _state(plan, receipts, available)
    _id(stage_id)
    if stage_id not in stages or stage_id in completed:
        raise ValueError("unknown or already completed stage")
    stage = stages[stage_id]
    if not set(stage.requires) <= completed or not set(stage.inputs) <= available:
        raise ValueError("stage dependencies or input artifacts unavailable")


def check_completion(plan: Plan, receipts: tuple[Receipt, ...],
                     available: tuple[bytes, ...]) -> None:
    """require every declared stage, output and log; a PASS dict is not evidence."""
    stages, completed, _ = _state(plan, receipts, available)
    if set(stages) != completed:
        raise ValueError("plan only partially completed")
