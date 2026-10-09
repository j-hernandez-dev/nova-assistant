"""Frozen IO/identity/preflight helpers. No inference in default preflight."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / 'docs/knowledge_inputs_v1/source_conflict_focal/revision_02'
OUTPUT = ROOT.parent / 'k8-certification-evidence/source-conflict-focal'


class StopExecution(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    """Only fresh execution artifacts or append-only event snapshots, not freezes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def append(path, value):
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')


def file_tree(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(Path(path).rglob('*')) if p.is_file()}


@contextmanager
def private_environment(directory):
    """Normal host audit storage setting, not a product monkeypatch or sandbox."""
    values = dict(LOCALAPPDATA=str(directory / 'host-audit'), NO_PROXY='127.0.0.1,localhost',
                  no_proxy='127.0.0.1,localhost')
    removed = [k for k in os.environ if k.startswith('LOCAL_CLI_') or k.casefold() in
               ('http_proxy', 'https_proxy', 'all_proxy')]
    before = {k: os.environ.get(k) for k in set(values) | set(removed)}
    try:
        for k in removed:
            os.environ.pop(k, None)
        os.environ.update(values)
        yield
    finally:
        for k, v in before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def api(profile, path, data=None):
    if path not in ('tags', 'ps', 'show', 'version'):
        raise StopExecution('IDENTITY_API_NOT_ALLOWLISTED')
    request = urllib.request.Request(profile['endpoint'] + '/api/' + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=15) as response:
        return json.load(response)


def backend(profile, *, strict=True):
    tags, ps, show, version = api(profile, 'tags'), api(profile, 'ps'), api(profile, 'show', {'model': profile['model']}), api(profile, 'version')
    exact = [[m for m in rows.get('models', []) if m.get('name') == profile['model'] and
              m.get('digest') == profile['digest']] for rows in (tags, ps)]
    errors = []
    if not exact[0] or not exact[1]:
        errors.append('EXACT_MODEL_NOT_INSTALLED_AND_RESIDENT')
    for m in exact[0] + exact[1]:
        declared = m.get('details', {}).get('runner')
        if declared is not None and declared != profile['runner']:
            errors.append('BACKEND_RUNNER_MISMATCH')
    if 'completion' not in show.get('capabilities', []):
        errors.append('COMPLETION_UNAVAILABLE')
    result = dict(timestamp=now(), tags=tags, ps=ps, show=show, version=version,
                  exact_installed=exact[0], exact_resident=exact[1], selected_by='NAME_AND_FULL_DIGEST', errors=errors)
    if strict and errors:
        error = StopExecution(errors[0])
        error.identity = result
        raise error
    return result


def verify_pins(freeze, *, check_workspace=True):
    errors = []
    for entry in freeze['pins']:
        path = Path(entry['path'])
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file() or sha(path) != entry['sha256']:
            errors.append(str(path))
    seed = Path(freeze['seed_state'])
    if file_tree(seed) != freeze['seed_tree']:
        errors.append('SEED_TREE_DRIFT')
    if check_workspace and file_tree(Path(freeze['workspace'])) != freeze['workspace_tree']:
        errors.append('WORKSPACE_TREE_DRIFT')
    return errors


def runtime_identity(profile):
    import pypdf
    from local_cli.model_presets import get_model_preset
    options = dict(get_model_preset(profile['model']), temperature=profile['temperature'], num_ctx=profile['context'])
    return dict(python_executable=str(Path(sys.executable).resolve()), python_version=platform.python_version(),
        python_sha256=sha(sys.executable), bytecode_disabled=bool(sys.dont_write_bytecode),
        pypdf_version=pypdf.__version__, platform=platform.platform(), effective_options=options,
        think=profile['think'], maxIterations=profile['maxIterations'], seed=profile['seed'])


def authorization_errors(auth, freeze_sha, case_id):
    exact = dict(status='AUTHORIZED', profile='8K', case_id=case_id,
                 one_quality_attempt=True, no_tuning=True, freeze_sha256=freeze_sha)
    errors = ['AUTHORIZATION_MISMATCH:' + k for k, v in exact.items()
              if auth.get(k) != v or type(auth.get(k)) is not type(v)]
    for key in ('human_instruction_reference', 'execution_id', 'timestamp'):
        if not isinstance(auth.get(key), str) or not auth[key].strip():
            errors.append('AUTHORIZATION_REQUIRED:' + key)
    return errors


def preflight(auth=None, real_backend=True, *, check_workspace=True):
    freeze = read(DOCS / 'freeze.json')
    profile = read(DOCS / 'execution_profile.json')
    errors = verify_pins(freeze, check_workspace=check_workspace)
    runtime = runtime_identity(profile)
    if runtime != freeze['runtime_identity']:
        errors.append('RUNTIME_OR_EFFECTIVE_PARAMETERS_DRIFT')
    identity = backend(profile, strict=False) if real_backend else None
    if identity:
        errors += identity['errors']
    if identity and identity['version'] != freeze['backend_version']:
        errors.append('OLLAMA_VERSION_DRIFT')
    if auth is not None:
        errors += authorization_errors(auth, sha(DOCS / 'freeze.json'), read(DOCS / 'corpus.json')['case_id'])
    return dict(timestamp=now(), status='PASS' if not errors else 'BLOCKED', errors=errors,
        pins_checked=len(freeze['pins']), freeze_sha256=sha(DOCS / 'freeze.json'),
        runtime=runtime, identity=identity, authorization='NOT_CREATED' if auth is None else 'CHECKED',
        model_inference=0, retrieval=0, admission=0, quality_attempts=0)


class NetworkAudit:
    """Process-lifetime audit gate; blocks chat/generate/embed until authorized."""
    def __init__(self, directory):
        self.directory = directory
        self.allow_chat = False
        self.chat_requests = 0
        self.blocked = 0
        self.requests = []
        sys.addaudithook(self.event)

    def event(self, event, args):
        if event == 'http.client.connect':
            host, port = args[1:3]
            if host != '127.0.0.1' or port != 11434:
                self.blocked += 1
                raise StopExecution('ONLY_LOOPBACK_OLLAMA_ALLOWED')
        if event != 'http.client.send':
            return
        packet = args[1]
        if not isinstance(packet, bytes):
            return
        first = packet.split(b'\r\n', 1)[0].decode('ascii', errors='ignore')
        if not first.startswith(('GET /', 'POST /')):
            return
        method, path, _ = first.split(' ', 2)
        allowed = path in ('/api/tags', '/api/ps', '/api/show', '/api/version')
        if path == '/api/chat':
            allowed = self.allow_chat
        if not allowed:
            self.blocked += 1
            append(self.directory / 'network.jsonl', dict(timestamp=now(), method=method, path=path, blocked=True))
            raise StopExecution('MODEL_NOT_AUTHORIZED_OR_ENDPOINT_FORBIDDEN')
        if path == '/api/chat':
            self.chat_requests += 1
        self.requests.append(dict(method=method, path=path))
        append(self.directory / 'network.jsonl', dict(timestamp=now(), method=method, path=path, blocked=False))

    def receipt(self):
        return dict(chat_requests=self.chat_requests, blocked=self.blocked, requests=self.requests,
                    generation=0, embeddings=0, cloud=0)
