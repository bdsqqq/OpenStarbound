"""LRU staged admission machinery. No class execution route is implemented yet.

The shared Plan proves declaration order, not physical truth. This executor adds
file identity, exclusive writes, process supervision and semantic certificates.
Reconstruction calls the same admission function without starting a process.
Static snapshots are not a sandbox, transient-race proof or signed attestation.
"""
import hashlib
import os
import signal
import stat
import subprocess
import sys
import time

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [LAB, os.path.join(LAB, 'path-embed-replay')]
import native_evidence_json as codec
import native_plan as np
import sdk_witness


class Rejected(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Rejected(reason)


def encoded(value):
    raw = codec.dumps(value).encode('ascii')
    require(codec.dumps(codec.loads(raw.decode('ascii'))).encode('ascii') == raw,
            'typed transport failed')
    return raw


def equal(a, b):
    def canonical(value):
        if type(value) is dict:
            return {k:canonical(v) for k, v in
                    sorted(value.items(), key=lambda row: encoded(row[0]))}
        if type(value) is tuple:
            return tuple(canonical(v) for v in value)
        if type(value) is list:
            return [canonical(v) for v in value]
        return value
    return encoded(canonical(a)) == encoded(canonical(b))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'not regular')
        return stream.read()


def load(path):
    return codec.loads(read(path).decode('ascii'))


def write(path, data):
    require(type(path) is bytes and type(data) is bytes, 'exact bytes required')
    require(os.path.realpath(os.path.dirname(path)) == os.path.dirname(path),
            'output parent alias')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)


def emit(path, value):
    write(path, encoded(value))


def identity(path):
    np._path(path)
    require(os.path.realpath(path) == path, 'canonical physical input required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                'regular single-link file required')
        raw = stream.read()
        after = os.fstat(stream.fileno())
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_nlink', 'st_size',
              'st_mtime_ns', 'st_ctime_ns')
    require(tuple(getattr(before, k) for k in fields) ==
            tuple(getattr(after, k) for k in fields), 'input changed during read')
    require(os.lstat(path).st_ino == before.st_ino, 'input replaced during read')
    return {'path': path, 'stat': tuple(getattr(before, k) for k in fields),
            'sha256': digest(raw)}


def ledger(paths):
    return {path: identity(path) for path in paths}


def alias(path):
    np._path(path)
    canonical, hops = sdk_witness._resolve(os.fsdecode(path))
    # These are explicit path fields, not arbitrary helper-object coercion.
    return {'requested': path, 'canonical': os.fsencode(canonical),
            'hops': tuple((os.fsencode(h['path']), os.fsencode(h['target']))
                          for h in hops),
            'payload': identity(os.fsencode(canonical))}


def tree(root):
    require(os.path.realpath(root) == root, 'owned root alias')
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = os.path.join(base, name)
            st = os.lstat(path)
            require(st.st_uid == os.getuid(), 'foreign owned node')
            require(stat.S_ISDIR(st.st_mode) or
                    (stat.S_ISREG(st.st_mode) and st.st_nlink == 1),
                    'owned symlink/hardlink/special node')
            result[path] = 'directory' if stat.S_ISDIR(st.st_mode) else 'file'
    return result


def restore(manifest):
    require(manifest['format'] == 'star-native-plan-v1', 'plan format')
    return np.Plan(manifest['owned_root'], manifest['initial_inputs'],
                   tuple(np.Stage(**row) for row in manifest['stages']))


def meta(stage):
    require(len(stage.outputs) >= 2 and len(stage.logs) == 3,
            'receipt/certificate and stdout/stderr/stdin required')
    return stage.outputs[-2:]


def contract(plan, commands, aliases=()):
    """Freeze all execution and validator fields before the first subprocess.

    Discovery is a separate immutable plan. It cannot append bindings to this
    one after observing a compiler, linker or native result.
    """
    manifest = codec.loads(np.preflight(plan))
    require(type(commands) is tuple and len(commands) == len(plan.stages),
            'one command contract per stage')
    expected_keys = {'stage_id', 'env', 'cwd', 'stdin', 'timeout_ms',
                     'failure_action', 'validator', 'rules'}
    for stage, command in zip(plan.stages, commands):
        require(type(command) is dict and set(command) == expected_keys,
                'exact command fields')
        require(command['stage_id'] == stage.stage_id, 'command order')
        require(command['validator'] in ('literal-v1', 'recipe-v1'),
                'unimplemented semantic validator')
        require(command['failure_action'] == 'stop-preserve', 'failure action')
        require(type(command['timeout_ms']) is int and 0 < command['timeout_ms'] <= 600000,
                'bounded exact integer timeout')
        require(type(command['stdin']) is bytes, 'literal byte stdin')
        require(type(command['env']) is dict and all(type(k) is bytes and
                type(v) is bytes and k and b'=' not in k and b'\0' not in k+v
                for k, v in command['env'].items()), 'exact environment')
        np._path(command['cwd'])
        require(command['cwd'].startswith(plan.owned_root+b'/') and
                os.path.realpath(command['cwd']) == command['cwd'] and
                os.path.isdir(command['cwd']), 'owned physical cwd')
        for key in (b'HOME', b'TMPDIR'):
            value = command['env'].get(key, b'')
            require(value.startswith(plan.owned_root+b'/') and
                    os.path.realpath(value) == value and os.path.isdir(value),
                    'owned HOME/TMPDIR')
        meta(stage)
        require(stage.argv[0] in aliases, 'executable alias not bound')
        require(all(not os.path.lexists(p) for p in stage.writes), 'fresh outputs required')
        validate_rules(stage, command)
    result = {'format': 'lru-staged-contract-v1', 'plan': manifest,
              'commands': commands, 'aliases': tuple(alias(p) for p in aliases),
              'initial': ledger(plan.initial_inputs), 'bootstrap_tree': tree(plan.owned_root)}
    require(all(a['canonical'] in plan.initial_inputs for a in result['aliases']),
            'canonical executable must be an initial input')
    encoded(result)
    return result


def validate_rules(stage, command):
    rules = command['rules']
    if command['validator'] == 'literal-v1':
        require(type(rules) is dict and set(rules) == {'stdout', 'stderr', 'products'},
                'literal validator fields')
        require(type(rules['stdout']) is bytes and type(rules['stderr']) is bytes and
                type(rules['products']) is dict and
                tuple(rules['products']) == stage.outputs[:-2] and
                all(type(v) is bytes for v in rules['products'].values()),
                'literal products must cover exact product membership')
    else:
        from recipe import validate_recipe_rules
        validate_recipe_rules(stage, rules)


def semantic(stage, command, record):
    if command['validator'] == 'literal-v1':
        rules = command['rules']
        require(record['stdout'] == rules['stdout'] and
                record['stderr'] == rules['stderr'], 'literal output mismatch')
        for path, raw in rules['products'].items():
            require(read(path) == raw, 'literal product mismatch')
        return {'validator': 'literal-v1', 'products': tuple(rules['products']),
                'stdout_sha256': digest(record['stdout'])}
    from recipe import validate_recipe
    return validate_recipe(stage, command['rules'], record)


def check_frozen(frozen):
    plan = restore(frozen['plan'])
    require(equal(codec.loads(np.preflight(plan)), frozen['plan']), 'plan transport drift')
    require(equal(ledger(plan.initial_inputs), frozen['initial']), 'initial input drift')
    require(equal(tuple(alias(a['requested']) for a in frozen['aliases']),
                  frozen['aliases']), 'tool alias/payload drift')
    return plan


def admit(frozen, stage, command, record, available):
    """The only receipt admission path, shared by live execution and replay."""
    require(type(record) is dict and set(record) == {
        'stage_id', 'completed', 'exit_code', 'argv', 'env', 'cwd', 'stdin',
        'stdout', 'stderr', 'pid', 'pgid', 'reaped', 'group_gone', 'timed_out',
        'started_ns', 'ended_ns', 'elapsed_ns', 'before', 'artifacts', 'outputs'},
        'exact process record fields')
    require(record['completed'] is True and type(record['exit_code']) is int and
            record['exit_code'] == 0 and record['timed_out'] is False and
            record['reaped'] is True and record['group_gone'] is True,
            'normal reaped exact-integer zero required')
    for key, value in {'stage_id':stage.stage_id, 'argv':stage.argv,
                       'env':command['env'], 'cwd':command['cwd'],
                       'stdin':command['stdin'], 'outputs':stage.writes}.items():
        require(equal(record[key], value), 'process declaration mismatch: '+key)
    require(type(record['pid']) is int and record['pid'] > 0 and
            type(record['pgid']) is int and record['pgid'] == record['pid'], 'owned process IDs')
    require(all(type(record[k]) is int for k in ('started_ns', 'ended_ns', 'elapsed_ns')) and
            record['started_ns'] <= record['ended_ns'] and
            0 <= record['elapsed_ns'] <= command['timeout_ms'] * 1000000,
            'invalid process interval')
    require(equal(record['before'], ledger(available)), 'input identity drift')
    products = stage.outputs[:-2]+stage.logs
    require(equal(record['artifacts'], ledger(products)), 'product identity drift')
    for path, raw in zip(stage.logs, (record['stdout'], record['stderr'], record['stdin'])):
        require(type(raw) is bytes and read(path) == raw, 'physical I/O differs')
    verdict = semantic(stage, command, record)
    return {'format': 'lru-stage-certificate-v1', 'stage_id': stage.stage_id,
            'contract_sha256': digest(encoded(frozen)), 'record_sha256': digest(encoded(record)),
            'validator': command['validator'], 'semantic': verdict}


def group_gone(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def execute(frozen):
    """Run only a frozen plan; no arbitrary callback can assert admission."""
    plan = check_frozen(frozen)
    receipts, available = (), plan.initial_inputs
    baseline = dict(frozen['bootstrap_tree'])
    require(equal(tree(plan.owned_root), baseline), 'bootstrap membership drift')
    for stage, command in zip(plan.stages, frozen['commands']):
        check_frozen(frozen)
        np.check_ready(plan, stage.stage_id, receipts, available)
        before = ledger(available)
        require(all(not os.path.lexists(p) for p in stage.writes), 'stale output')
        start, tick = time.time_ns(), time.monotonic_ns()
        process = subprocess.Popen(stage.argv, cwd=command['cwd'], env=command['env'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        timed_out = False
        try:
            out, err = process.communicate(command['stdin'], timeout=command['timeout_ms']/1000)
        except subprocess.TimeoutExpired:
            timed_out = True
            # start_new_session gives this command its own group. Never signal
            # our supervisor's group or discover/signal unrelated processes.
            os.killpg(process.pid, signal.SIGTERM)
            try:
                out, err = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                out, err = process.communicate(timeout=2)
        elapsed = time.monotonic_ns()-tick
        for path, raw in zip(stage.logs, (out, err, command['stdin'])):
            write(path, raw)
        record = {'stage_id': stage.stage_id, 'completed': not timed_out,
                  'exit_code': process.returncode, 'argv': stage.argv,
                  'env': command['env'], 'cwd': command['cwd'], 'stdin':command['stdin'],
                  'stdout':out, 'stderr':err, 'pid':process.pid, 'pgid':process.pid,
                  'reaped':process.poll() is not None, 'group_gone':group_gone(process.pid),
                  'timed_out':timed_out, 'started_ns':start, 'ended_ns':time.time_ns(),
                  'elapsed_ns':elapsed, 'before':before,
                  'artifacts':ledger(stage.outputs[:-2]+stage.logs), 'outputs':stage.writes}
        receipt_path, cert_path = meta(stage)
        emit(receipt_path, record)  # failed records remain, but get no certificate.
        check_frozen(frozen)
        expected = dict(baseline)
        expected.update({p:'file' for p in stage.outputs[:-1]+stage.logs})
        require(equal(tree(plan.owned_root), expected), 'unexpected output membership')
        certificate = admit(frozen, stage, command, record, available)
        emit(cert_path, certificate)
        receipts += (np.Receipt(stage.stage_id, True, process.returncode, stage.writes),)
        available += stage.writes
        baseline.update({p:'file' for p in stage.writes})
    np.check_completion(plan, receipts, available)
    reconstruct(frozen)
    return {'scope':'machinery-only', 'stages':tuple(r.stage_id for r in receipts),
            'class_execution_admitted':False}


def reconstruct(frozen):
    """Read only: no compile, execution, repairs or evidence regeneration."""
    plan = check_frozen(frozen)
    receipts, available = (), plan.initial_inputs
    expected = dict(frozen['bootstrap_tree'])
    for stage, command in zip(plan.stages, frozen['commands']):
        np.check_ready(plan, stage.stage_id, receipts, available)
        receipt_path, cert_path = meta(stage)
        record = load(receipt_path)
        certificate = admit(frozen, stage, command, record, available)
        require(equal(load(cert_path), certificate), 'certificate mismatch')
        receipts += (np.Receipt(stage.stage_id, True, record['exit_code'], stage.writes),)
        available += stage.writes
        expected.update({p:'file' for p in stage.writes})
    np.check_completion(plan, receipts, available)
    require(equal(tree(plan.owned_root), expected), 'reconstructed membership mismatch')
    return {'format':'lru-staged-reconstruction-v1',
            'contract_sha256':digest(encoded(frozen)), 'ledger':ledger(available),
            'stages':tuple(r.stage_id for r in receipts), 'class_execution_admitted':False}
