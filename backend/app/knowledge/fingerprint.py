import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_default)


def fingerprint_state(value: dict) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
