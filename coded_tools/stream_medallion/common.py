"""Shared helpers for the StreamForge medallion tools (stdlib only)."""
import json
import os
import re
import sqlite3
from typing import Any

WORK_DIR = os.environ.get("STREAMFORGE_DIR", "data/stream_medallion")
DEFAULT_SAMPLE = os.path.join(WORK_DIR, "payments_auth_sample.jsonl")
DB_PATH = os.path.join(WORK_DIR, "medallion.db")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Heuristic PII detectors used when a field has no declared policy yet.
PII_PATTERNS = {
    "card_number": re.compile(r"^\d{13,19}$"),
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "phone": re.compile(r"^\+?\d[\d\s\-]{8,14}\d$"),
}
PII_NAME_HINTS = ("card", "email", "holder", "name", "phone", "ssn", "address")

DEFAULT_CONTRACT = {
    "feed": "payments_auth_v3",
    "key": ["txn_id"],
    "fields": {
        "txn_id": {"type": "string", "required": True},
        "merchant_id": {"type": "string", "required": True},
        "amount": {"type": "number", "required": True, "min": 0, "max": 1000000},
        "currency": {"type": "string", "required": True},
        "status": {"type": "string", "required": True},
        "decline_reason": {"type": "string", "required": False},
        "card_no": {"type": "string", "required": False},
        "email": {"type": "string", "required": False},
        "holder": {"type": "string", "required": False},
        "event_ts": {"type": "string", "required": True},
    },
    "pii": {"card_no": "tokenise", "email": "hash", "holder": "mask"},
    "gold": {
        "group_by": ["merchant_id"],
        "time_field": "event_ts",
        "bucket": "minute",
        "status_field": "status",
        "success_value": "APPROVED",
        "amount_field": "amount",
    },
}


def parse_json_arg(value: Any, default: Any = None) -> Any:
    """Accept a dict or a JSON string from the LLM; fall back to default."""
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def read_jsonl(path: str):
    """Yield (line_no, raw_line, parsed_or_None). Bad JSON yields None."""
    with open(path, "r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            raw = raw.rstrip("\n")
            if not raw.strip():
                continue
            try:
                parsed = json.loads(raw)
                parsed = parsed if isinstance(parsed, dict) else None
            except ValueError:
                parsed = None
            yield line_no, raw, parsed


def python_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if value is None:
        return "null"
    return "string"


def safe_ident(name: str) -> str:
    if not IDENT.match(name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return name


def connect(read_only: bool = False) -> sqlite3.Connection:
    os.makedirs(WORK_DIR, exist_ok=True)
    if read_only:
        return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return sqlite3.connect(DB_PATH)

