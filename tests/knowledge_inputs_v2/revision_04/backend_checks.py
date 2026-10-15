"""Synthetic regression checks for the sole R4 backend identity correction."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner
from nova_adapter import verify_backend

PROFILE = runner.read(runner.DOCS / "execution_profile_v2_r3.json")
MODEL = PROFILE["llm"]
OTHER_DIGEST = "2e16a80fe3d77d431d295466415848403c8c266667ee5d7d8991ee445b4e1311"

def row(digest=None, name=None, declared_runner="llamacpp"):
    details = {} if declared_runner is None else {"runner": declared_runner}
    return {"name": MODEL["model"] if name is None else name,
            "digest": MODEL["digest"] if digest is None else digest, "details": details}

class BackendIdentityChecks(unittest.TestCase):
    def probe(self, tags, resident, capabilities=None):
        responses = {"tags": {"models": tags}, "ps": {"models": resident},
                     "show": {"capabilities": ["completion"] if capabilities is None else capabilities}}
        requests = []
        class Opener:
            def open(inner, request, timeout):
                path = request.full_url.rsplit("/", 1)[-1]
                requests.append(path)
                if path not in responses:
                    raise AssertionError("NON_METADATA_ENDPOINT:" + path)
                if path == "show":
                    self.assertEqual(json.loads(request.data), {"model": MODEL["model"]})
                return io.BytesIO(json.dumps(deepcopy(responses[path])).encode())
        with patch("nova_adapter.urllib.request.build_opener", return_value=Opener()):
            result = verify_backend(PROFILE)
        self.assertEqual(requests, ["tags", "ps", "show"])
        self.assertEqual(result["model_digest"], MODEL["digest"])
        return result

    def rejection(self, tags, resident, message, capabilities=None):
        with self.assertRaises(runner.FrozenAbort) as caught:
            self.probe(tags, resident, capabilities)
        self.assertEqual(str(caught.exception), message)

    def test_homonym_ggml_does_not_reject_exact_llamacpp_in_either_order(self):
        exact, homonym = row(), row(OTHER_DIGEST, declared_runner="ggml")
        for tags in ([homonym, exact], [exact, homonym]):
            with self.subTest(order=[r["digest"] for r in tags]):
                result = self.probe(tags, [exact])
                self.assertEqual(result["tags"]["models"], tags)
                self.assertEqual(len(result["tags"]["models"]), 2)

    def test_wrong_runner_on_exact_digest_still_rejected(self):
        self.rejection([row(OTHER_DIGEST), row(declared_runner="ggml")], [row()],
                       "BACKEND_RUNNER_MISMATCH")

    def test_name_present_but_exact_installed_digest_absent(self):
        self.rejection([row(OTHER_DIGEST)], [row()], "MODEL_DIGEST_NOT_INSTALLED_AND_RESIDENT")

    def test_ps_must_confirm_exact_resident_digest_not_homonym(self):
        self.rejection([row()], [row(OTHER_DIGEST)], "MODEL_DIGEST_NOT_INSTALLED_AND_RESIDENT")

    def test_installed_digest_under_other_name_is_not_identity(self):
        self.rejection([row(name="other:9b"), row(OTHER_DIGEST)], [row()],
                       "MODEL_DIGEST_NOT_INSTALLED_AND_RESIDENT")

    def test_resident_digest_under_other_name_is_not_identity(self):
        self.rejection([row()], [row(name="other:9b"), row(OTHER_DIGEST)],
                       "MODEL_DIGEST_NOT_INSTALLED_AND_RESIDENT")

    def test_selection_is_not_first_name_match_in_tags_or_ps(self):
        homonym = row(OTHER_DIGEST, declared_runner="ggml")
        wrong_name = row(name="other:9b", declared_runner="ggml")
        result = self.probe([homonym, wrong_name, row()], [homonym, wrong_name, row()])
        self.assertEqual(result["resident"]["models"], [homonym, wrong_name, row()])

    def test_undeclared_runner_keeps_r3_nonblocking_behavior(self):
        self.probe([row(declared_runner=None)], [row()])

    def test_completion_capability_requirement_unchanged(self):
        self.rejection([row()], [row()], "COMPLETION_UNAVAILABLE", capabilities=[])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = args.report.resolve()
    if not report.is_relative_to(runner.ROOT) or report.exists():
        raise ValueError("fresh project preparation evidence required")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BackendIdentityChecks)
    ids = [test.id() for test in suite]
    with patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK_FORBIDDEN_IN_SYNTHETIC_CHECKS")):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    product_modules = [name for name in sys.modules if name.startswith("local_cli")]
    record = dict(status="PASS" if result.wasSuccessful() and not product_modules else "FAIL",
        recorded_at=datetime.now(timezone.utc).isoformat(), tests_run=result.testsRun, test_ids=ids,
        failures=[(test.id(), detail) for test, detail in result.failures],
        errors=[(test.id(), detail) for test, detail in result.errors],
        observations="synthetic HTTP metadata only; socket network trap active",
        product_modules_imported=product_modules, campaigns_consumed=0, inference=0, retrieval=0, admission=0)
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("x", encoding="utf-8") as output:
        json.dump(record, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({k: record[k] for k in ("status", "tests_run", "campaigns_consumed", "inference", "retrieval", "admission")}))
    return 0 if record["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
