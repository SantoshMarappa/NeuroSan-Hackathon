"""Tool 3 - guarded read-only SQL over Gold (the NL->SQL safety net)."""
import re
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.stream_medallion import common as c

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|attach|detach|pragma|create|replace|vacuum|load_extension)\b",
    re.IGNORECASE,
)
TABLE_REF = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
ROW_CAP = 100


class GoldQuery(CodedTool):
    """With no sql argument, returns the Gold schema; otherwise validates and runs the query."""

    def invoke(self, args: dict[str, Any], sys_data: dict[str, Any]) -> Any:
        sql = (args.get("sql") or "").strip().rstrip(";")
        try:
            conn = c.connect(read_only=True)
        except Exception:  # pylint: disable=broad-except
            return "Error: no medallion database yet - run the medallion first."

        try:
            if not sql:
                tables = [r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'gold_%'")]
                return {t: [col[1] for col in conn.execute(f"PRAGMA table_info({t})")]
                        for t in tables}

            # Guardrails: single read-only SELECT against gold_* tables only
            if ";" in sql or not sql.lower().startswith("select"):
                return "Rejected: exactly one SELECT statement is allowed."
            if FORBIDDEN.search(sql):
                return "Rejected: read-only queries only."
            tables = TABLE_REF.findall(sql)
            if not tables or any(not t.lower().startswith("gold_") for t in tables):
                return "Rejected: query Gold tables only (names start with gold_)."
            if not re.search(r"\blimit\b", sql, re.IGNORECASE):
                sql += f" LIMIT {ROW_CAP}"

            cursor = conn.execute(sql)
            names = [d[0] for d in cursor.description]
            rows = cursor.fetchmany(ROW_CAP)
            return {"sql_executed": sql, "tables_cited": sorted(set(tables)),
                    "columns": names, "rows": [list(r) for r in rows]}
        except Exception as err:  # pylint: disable=broad-except
            return f"Query error: {err}"
        finally:
            conn.close()

