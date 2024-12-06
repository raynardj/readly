from base64 import b64encode, b64decode
import json
import hmac
import hashlib
from typing import Dict, Any, Optional


def serialize_json(data: Dict[str, Any]) -> str:
    data_bytes = json.dumps(data).encode()
    return b64encode(data_bytes).decode()


def deserialize_json(data_b64: str) -> Dict[str, Any]:
    data_bytes = b64decode(data_b64)
    return json.loads(data_bytes)


def load_session(token: Optional[str], secret_key: bytes) -> Dict:
    """Load and verify session from cookie"""
    if not token:
        return {}

    try:
        data_b64, signature = token.split(".")
        expected_signature = create_signature(secret_key, data_b64)
        if not hmac.compare_digest(signature.encode(), expected_signature):
            return {}

        data = deserialize_json(data_b64)

        return data

    except (ValueError, json.JSONDecodeError):
        return {}


def create_signature(secret_key: bytes, data: str) -> bytes:
    """
    Create HMAC signature for data
    The signature contains the data and the secret key
    without the secret key, it is infeasible to tamper with the data
    """
    return (
        hmac.new(
            secret_key,
            data.encode(),
            hashlib.sha256,
        )
        .hexdigest()
        .encode()
    )
