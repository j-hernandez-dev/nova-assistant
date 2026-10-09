"""Full frozen campaign coordinator; default CLI is read-only offline preflight."""
import argparse
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DOCS = ROOT / "docs/knowledge_inputs_v2/revision_04"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
from scorer import score
sys.modules.setdefault('runner',sys.modules[__name__])

class FrozenAbort(RuntimeError):
    fatal=True

@contextmanager
def isolated_environment(output):
    changed={}
    values={key:str(output/'private'/key.lower()) for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP')}
    values.update(NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
    removals=[key for key in os.environ if key.startswith('LOCAL_CLI_') or key.casefold() in ('http_proxy','https_proxy','all_proxy')]
    for key in set(values)|set(removals):changed[key]=os.environ.get(key)
    try:
        for key in removals:os.environ.pop(key,None)
        for key,value in values.items():
            os.environ[key]=value
            if key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP'):Path(value).mkdir(parents=True,exist_ok=True)
        yield
    finally:
        for key,value in changed.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value

def file_sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding="utf-8"))
def write(path, value):
    # Execution evidence only, always in a verified external directory.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def pin_errors(freeze, root=ROOT):
    errors = []
    for row in freeze["pins"]:
        path = (root / row["path"]).resolve()
        if not path.is_relative_to(root.resolve()): errors.append("PIN_OUTSIDE_ROOT"); continue
        if not path.is_file() or file_sha(path) != row["sha256"]: errors.append("DRIFT:" + row["path"])
    if not freeze["pins"]: errors.append("EMPTY_PINS")
    for row in freeze.get('external_pins',[]):
        path=Path(row['path'])
        if not path.is_file() or file_sha(path)!=row['sha256']:errors.append('EXTERNAL_DRIFT:'+row['path'])
    return errors

def authorization_errors(auth, freeze_sha):
    if not isinstance(auth, dict): return ["JOINT_AUTHORIZATION_ABSENT"]
    errors = []
    if auth.get("freeze_sha256") != freeze_sha: errors.append("AUTHORIZATION_FREEZE_MISMATCH")
    if auth.get("status") != "AUTHORIZED" or auth.get("profiles") != ["4K", "8K"]: errors.append("JOINT_AUTHORIZATION_ABSENT")
    if auth.get("no_tuning_between") is not True or auth.get("one_campaign_each") is not True: errors.append("AUTHORIZATION_POLICY")
    for field in ("human_identity", "human_message_reference", "authorized_at", "execution_id"):
        if not isinstance(auth.get(field), str) or not auth[field].strip(): errors.append("MISSING_AUTH_" + field)
    return errors

def preflight(authorization=None):
    freeze_path = DOCS / "freeze_final_v2_r4.json"
    freeze = read(freeze_path); errors = pin_errors(freeze)
    profile = read(DOCS / "execution_profile_v2_r3.json")
    runtime=read(DOCS/'runtime.json')
    if str(Path(sys.executable).resolve()).casefold()!=str(Path(runtime['python_executable']).resolve()).casefold(): errors.append('PYTHON_EXECUTABLE_DRIFT')
    if '.'.join(str(x) for x in sys.version_info[:3])!=runtime['python_version']:errors.append('PYTHON_VERSION_DRIFT')
    prior = read(ROOT / "docs/knowledge_inputs_v2/revision_02/execution_profile_v2_r2.json")
    if profile["llm"] != prior["llm"] or profile["profiles"] != prior["profiles"]: errors.append("EXECUTION_PROFILE_DRIFT_FROM_R2")
    if freeze.get("status") != "FROZEN_PENDING_HUMAN_REVIEW": errors.append("FREEZE_STATUS")
    return dict(integrity_errors=errors, execution_errors=errors + authorization_errors(authorization, file_sha(freeze_path)),
                freeze_sha256=file_sha(freeze_path), campaigns_consumed=0, inference=0, retrieval=0, admission=0)

def pipeline(adapter, case, corpus, gold, directory, audit):
    """Tests inject only a synthetic adapter. Actual execution uses NovaAdapter."""
    directory.mkdir(parents=True, exist_ok=False)
    observed = None
    try:
        adapter.prepare(case, directory, audit)
        observed = adapter.turn(case, audit)
        result = score(case, corpus, gold, observed)
        write(directory / "observation.json", observed)
        write(directory / "score.json", result)
        return result
    except Exception as exc:
        write(directory / "incident.json", dict(type=type(exc).__name__, message=str(exc),
              phase=getattr(adapter, "phase", "UNKNOWN"), counters=deepcopy(audit.counters), retry_permitted=False))
        raise
    finally:
        adapter.close(directory)

class ExecutionAudit:
    def __init__(self, output, freeze, freeze_sha, reservation, authorization, authorization_path):
        self.output, self.freeze, self.freeze_sha = output, freeze, freeze_sha
        self.reservation, self.authorization = reservation, authorization
        self.authorization_path,self.authorization_sha=authorization_path,file_sha(authorization_path)
        self.counters = dict(campaigns_consumed=0, inference=0, retrieval=0, admission=0)
        self.reserved = False
    def checkpoint(self): write(self.output / "execution_counters.json", self.counters)
    def observe(self, layer):
        self.counters[layer] += 1; self.checkpoint()
    def before_model(self):
        errors = pin_errors(self.freeze)
        errors += authorization_errors(self.authorization, self.freeze_sha)
        if file_sha(self.authorization_path)!=self.authorization_sha:errors.append('AUTHORIZATION_DRIFT_OR_REVOCATION')
        if errors: raise FrozenAbort("PREFLIGHT_REJECTED:" + repr(errors))
        if not self.reserved:
            # O_EXCL reserves both campaigns before even a failed inference transport.
            self.reservation.parent.mkdir(parents=True, exist_ok=True)
            with self.reservation.open("x", encoding="utf-8") as stream:
                json.dump(dict(freeze_sha256=self.freeze_sha, profiles=["4K", "8K"],
                    campaigns_consumed=2, execution_id=self.authorization["execution_id"]), stream)
            self.reserved = True
            self.counters["campaigns_consumed"] = 2
        self.observe("inference")

def execute(output, authorization_path, ledger):
    auth = read(authorization_path); check = preflight(auth)
    if check["execution_errors"]: raise RuntimeError(repr(check["execution_errors"]))
    output, ledger = output.resolve(), ledger.resolve()
    if output.exists() or output.is_relative_to(ROOT) or output == Path(output.anchor):
        raise ValueError("fresh private output outside checkout required")
    if ledger.is_relative_to(ROOT) or ledger == Path(ledger.anchor): raise ValueError("private ledger outside checkout required")
    reservation = ledger / (check["freeze_sha256"] + ".json")
    if reservation.exists(): raise RuntimeError("CAMPAIGNS_ALREADY_RESERVED")
    # Lazy import: offline preflight/tests never import Nova, Ollama or model code.
    sys.path.insert(0,read(DOCS/'runtime.json')['offline_dependencies'])
    from nova_adapter import NovaAdapter, verify_backend
    profile = read(DOCS / "execution_profile_v2_r3.json")
    freeze = read(DOCS / "freeze_final_v2_r4.json")
    corpus, gold = read(HERE / "corpus_v2_r3.json"), read(HERE / "gold_v2_r3.json")
    profiles = read(DOCS / "profiles.json")
    output.mkdir(parents=True, exist_ok=False)
    write(output / "authorization.json", auth); write(output/'preflight.json',check)
    audit = ExecutionAudit(output, freeze, check["freeze_sha256"], reservation, auth,authorization_path); audit.checkpoint()
    try: identity=verify_backend(profile)
    except Exception as exc:
        write(output/'initialization_incident.json',dict(type=type(exc).__name__,message=str(exc),counters=audit.counters,retry_permitted=False));raise
    write(output / "identity_before.json", identity)
    results = {}
    for name in profiles["campaign_order"]:
        if pin_errors(freeze): raise RuntimeError("DRIFT_BETWEEN_PROFILES")
        rows = []
        for case_id in profiles["profiles"][name]["case_ids"]:
            case = next(c for c in corpus["cases"] if c["id"] == case_id)
            adapter = NovaAdapter(profile, profiles["profiles"][name], corpus)
            attempt = output / name / case_id / "attempt-01"
            try:
                with isolated_environment(output):
                    row = pipeline(adapter, case, corpus, gold, attempt, audit)
            except Exception as exc:
                row = dict(status="INCIDENT", first_failure="HARNESS_OR_ENVIRONMENT", error=repr(exc), quality_eligible=False)
                if getattr(exc,'fatal',False):
                    write(output/'abort.json',dict(error=repr(exc),counters=audit.counters,results=results));raise
            rows.append(dict(case_id=case_id, score=row))
            write(output / name / "progress.json", rows)
        denominator = profiles["profiles"][name]["denominator"]
        results[name] = dict(rows=rows, denominator=denominator,
            passed=sum(r["score"]["status"] == "PASS" and r["score"]["quality_eligible"] for r in rows),
            status="PASS" if len(rows)==denominator and all(r["score"]["status"]=="PASS" and r["score"]["quality_eligible"] for r in rows) else "FAIL")
        write(output / "results.json", results)
    try:write(output / "identity_after.json", verify_backend(profile))
    except Exception as exc:
        write(output/'final_identity_incident.json',dict(error=repr(exc),counters=audit.counters))
        for result in results.values():result['status']='FAIL'
        write(output/'results.json',results);raise
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps(preflight(read(args.authorization) if args.authorization else None), indent=2)); return 0
    if any(x is None for x in (args.authorization,args.output,args.ledger)): parser.error("execute requires authorization, fresh output and ledger")
    results=execute(args.output,args.authorization,args.ledger)
    return 0 if all(result['status']=='PASS' for result in results.values()) else 1

if __name__ == "__main__": raise SystemExit(main())
