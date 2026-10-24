"""Tool 2 - metadata-driven Bronze -> Silver -> Gold run, no LLM on the hot path."""
import hashlib
import json
import re
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.stream_medallion import common as c

_DIGITS = re.compile(r"\d{13,19}")
_EMAIL = re.compile(r"[^@\s\"]+@[^@\s\"]+")
BUCKET_CHARS = {"minute": 16, "hour": 13, "day": 10}  # ISO-8601 prefix length


def _check(rec: dict, fields: dict) -> str | None:
    """Return a rejection reason, or None when the record satisfies the contract."""
    for name, rule in fields.items():
        value = rec.get(name)
        if value in (None, ""):
            if rule.get("required"):
                return f"missing_required:{name}"
            continue
        if rule["type"] == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return f"type_mismatch:{name}"
            if "min" in rule and value < rule["min"]:
                return f"out_of_range:{name}"
            if "max" in rule and value > rule["max"]:
                return f"out_of_range:{name}"
        elif rule["type"] == "string" and not isinstance(value, str):
            return f"type_mismatch:{name}"
    return None


def _apply_pii(rec: dict, policy: dict) -> dict:
    out = dict(rec)
    for field, action in policy.items():
        value = out.get(field)
        if value in (None, ""):
            continue
        digest = hashlib.sha256(str(value).encode()).hexdigest()
        if action == "tokenise":
            out[field] = f"tok_{digest[:12]}"
        elif action == "hash":
            out[field] = digest[:16]
        elif action == "mask":
            out[field] = str(value)[0] + "***"
        elif action == "drop":
            out[field] = None
    return out


def _safe_payload(rec: dict | None, raw: str, policy: dict) -> str:
    """DLQ must never hold clear-text PII (NFR5): apply policy, or regex-redact unparseable lines."""
    if rec is not None:
        return json.dumps(_apply_pii(rec, policy))[:300]
    return _EMAIL.sub("[email]", _DIGITS.sub("[digits]", raw))[:300]


class RunMedallion(CodedTool):
    """Applies a feed descriptor to a Bronze file and materialises Silver and Gold."""

    def invoke(self, args: dict[str, Any], sys_data: dict[str, Any]) -> Any:
        path = args.get("sample_path") or c.DEFAULT_SAMPLE
        contract = c.parse_json_arg(args.get("contract"), c.DEFAULT_CONTRACT)
        try:
            feed = c.safe_ident(contract["feed"])
            fields = {c.safe_ident(k): v for k, v in contract["fields"].items()}
            key = [c.safe_ident(k) for k in contract["key"]]
            gold = contract["gold"]
            group_by = [c.safe_ident(g) for g in gold["group_by"]]
            time_f = c.safe_ident(gold["time_field"])
            status_f = c.safe_ident(gold["status_field"])
            amount_f = c.safe_ident(gold["amount_field"])
            width = BUCKET_CHARS[gold.get("bucket", "minute")]
        except (KeyError, ValueError) as err:
            return f"Error: invalid feed descriptor ({err})"

        silver: dict = {}
        dlq: list[dict] = []
        reasons: dict[str, int] = {}
        drift_fields: set[str] = set()
        bronze_count = 0

        try:
            for line_no, raw, rec in c.read_jsonl(path):
                bronze_count += 1
                reason = "invalid_json" if rec is None else _check(rec, fields)
                if reason:
                    dlq.append({"line": line_no, "reason": reason,
                                "payload": _safe_payload(rec, raw, contract.get("pii", {}))})
                    reasons[reason] = reasons.get(reason, 0) + 1
                    continue
                drift_fields |= set(rec) - set(fields)  # captured, never rejected
                clean = _apply_pii({k: rec.get(k) for k in fields}, contract.get("pii", {}))
                k = tuple(clean[x] for x in key)
                # idempotent upsert: latest event wins, so replays converge
                if k not in silver or str(clean[time_f]) >= str(silver[k][time_f]):
                    silver[k] = clean
        except FileNotFoundError:
            return f"Error: sample file not found: {path}"

        silver_t, dlq_t, gold_t = f"silver_{feed}", f"dlq_{feed}", f"gold_{feed}_kpi"
        conn = c.connect()
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        group_sql = ", ".join(group_by)
        success = gold["success_value"]
        with conn:
            for table in (silver_t, dlq_t, gold_t):
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute(f"CREATE TABLE {silver_t} ({cols})")
            conn.executemany(
                f"INSERT INTO {silver_t} ({cols}) VALUES ({marks})",
                [tuple(r[f] for f in fields) for r in silver.values()],
            )
            conn.execute(f"CREATE TABLE {dlq_t} (line, reason, payload)")
            conn.executemany(
                f"INSERT INTO {dlq_t} VALUES (?,?,?)",
                [(d["line"], d["reason"], d["payload"]) for d in dlq],
            )
            conn.execute(
                f"""CREATE TABLE {gold_t} AS
                    SELECT {group_sql},
                           substr({time_f}, 1, {width}) AS time_bucket,
                           COUNT(*) AS txn_count,
                           SUM({status_f} = ?) AS approved,
                           SUM({status_f} <> ?) AS declined,
                           ROUND(1.0 * SUM({status_f} = ?) / COUNT(*), 4) AS auth_rate,
                           ROUND(SUM({amount_f}), 2) AS total_amount
                    FROM {silver_t}
                    GROUP BY {group_sql}, time_bucket""",
                (success, success, success),
            )
            gold_rows = conn.execute(f"SELECT COUNT(*) FROM {gold_t}").fetchone()[0]
        conn.close()

        return {
            "feed": feed,
            "bronze_records": bronze_count,
            "silver_rows": len(silver),
            "deduplicated": bronze_count - len(dlq) - len(silver),
            "dlq_rows": len(dlq),
            "dlq_reasons": reasons,
            "drift_fields_captured": sorted(drift_fields),
            "pii_policy_applied": contract.get("pii", {}),
            "tables_created": {"silver": silver_t, "dlq": dlq_t, "gold": gold_t},
            "gold_rows": gold_rows,
            "dlq_sample": json.loads(json.dumps(dlq[:3])),
        }
