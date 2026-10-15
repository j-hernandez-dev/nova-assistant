"""Authenticate a host-confirmed response on the private Desktop JSONL pipe."""
import hashlib
import hmac
import json


def approval_proof(key: str, command: dict) -> str:
    canonical = json.dumps(command, sort_keys=True, ensure_ascii=False,
                           separators=(',', ':')).encode('utf-8')
    return hmac.new(bytes.fromhex(key), canonical, hashlib.sha256).hexdigest()


def verify_approval_proof(key: str | None, command: dict, proof) -> bool:
    if not key or not isinstance(proof, str) or len(proof) != 64:
        return False
    try:
        return hmac.compare_digest(approval_proof(key, command), proof)
    except (ValueError, TypeError):
        return False
