"""Tool 1 - profile a Bronze sample: infer schema, spot PII, detect drift."""
from collections import Counter, defaultdict
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.stream_medallion import common as c


class ProfilePayloads(CodedTool):
    """Deterministic profiling. The LLM only sees this summary, never the raw feed."""

    def invoke(self, args: dict[str, Any], sys_data: dict[str, Any]) -> Any:
        path = args.get("sample_path") or c.DEFAULT_SAMPLE
        contract = c.parse_json_arg(args.get("contract"), c.DEFAULT_CONTRACT)
        declared = set(contract["fields"])

        total = bad_json = 0
        types: dict[str, Counter] = defaultdict(Counter)
        nulls: Counter = Counter()
        seen_at: dict[str, int] = {}
        pii_hits: dict[str, set] = defaultdict(set)
        keys = Counter()

        try:
            for line_no, _raw, rec in c.read_jsonl(path):
                total += 1
                if rec is None:
                    bad_json += 1
                    continue
                for field, value in rec.items():
                    types[field][c.python_type(value)] += 1
                    seen_at.setdefault(field, line_no)
                    if value in (None, ""):
                        nulls[field] += 1
                    if isinstance(value, str):
                        for label, pattern in c.PII_PATTERNS.items():
                            if pattern.match(value):
                                pii_hits[field].add(label)
                    if any(h in field.lower() for h in c.PII_NAME_HINTS):
                        pii_hits[field].add("name_hint")
                key = tuple(str(rec.get(k)) for k in contract["key"])
                keys[key] += 1
        except FileNotFoundError:
            return f"Error: sample file not found: {path}"

        parsed = total - bad_json
        profile = {
            f: {
                "types": dict(t),
                "null_rate": round(nulls[f] / parsed, 3) if parsed else 0,
                "first_seen_line": seen_at[f],
            }
            for f, t in types.items()
        }
        return {
            "sample_path": path,
            "records_total": total,
            "invalid_json": bad_json,
            "duplicate_keys": sum(1 for n in keys.values() if n > 1),
            "profile": profile,
            "drift": {
                "new_fields_not_in_contract": sorted(set(types) - declared),
                "contract_fields_never_seen": sorted(declared - set(types)),
                "mixed_type_fields": sorted(
                    f for f, t in types.items() if len([k for k in t if k != "null"]) > 1
                ),
            },
            "pii_candidates_without_policy": {
                f: sorted(v)
                for f, v in pii_hits.items()
                if f not in contract.get("pii", {})
            },
            "contract_in_use": contract["feed"],
        }
