"""Run from repo root:  python -m pytest tests -q   (or python tests/test_tools.py)
Uses a stub CodedTool when neuro-san is not installed."""
import json, os, sys, tempfile, types

sys.path.insert(0, os.getcwd())
try:
    import neuro_san.interfaces.coded_tool  # noqa: F401
except ImportError:
    ns = types.ModuleType("neuro_san");
    itf = types.ModuleType("neuro_san.interfaces")
    ct = types.ModuleType("neuro_san.interfaces.coded_tool")
    ct.CodedTool = type("CodedTool", (), {})
    sys.modules.update({"neuro_san": ns, "neuro_san.interfaces": itf, "neuro_san.interfaces.coded_tool": ct})

os.environ["STREAMFORGE_DIR"] = tempfile.mkdtemp()
import shutil

shutil.copy("data/stream_medallion/payments_auth_sample.jsonl", os.environ["STREAMFORGE_DIR"])

from coded_tools.stream_medallion.profile_payloads import ProfilePayloads
from coded_tools.stream_medallion.run_medallion import RunMedallion
from coded_tools.stream_medallion.gold_query import GoldQuery


def test_pipeline():
    prof = ProfilePayloads().invoke({}, {})
    assert prof["invalid_json"] == 2
    assert set(prof["drift"]["new_fields_not_in_contract"]) == {"device_fingerprint", "phone"}
    assert "amount" in prof["drift"]["mixed_type_fields"]
    assert "phone" in prof["pii_candidates_without_policy"]

    run = RunMedallion().invoke({}, {})
    assert run["bronze_records"] == 259
    assert run["silver_rows"] + run["deduplicated"] + run["dlq_rows"] == 259
    assert run["dlq_reasons"]["invalid_json"] == 2
    again = RunMedallion().invoke({}, {})  # idempotent replay
    assert again["silver_rows"] == run["silver_rows"]

    q = GoldQuery().invoke(
        {"sql": "SELECT merchant_id, time_bucket, auth_rate FROM gold_payments_auth_v3_kpi ORDER BY auth_rate LIMIT 3"},
        {})
    assert q["rows"][0][0] == "4471"  # the planted incident is found
    for bad in ["DROP TABLE gold_payments_auth_v3_kpi", "SELECT * FROM silver_payments_auth_v3",
                "SELECT 1; DELETE FROM x", "SELECT card_no FROM silver_payments_auth_v3"]:
        assert str(GoldQuery().invoke({"sql": bad}, {})).startswith("Rejected"), bad
    assert "gold_payments_auth_v3_kpi" in GoldQuery().invoke({}, {})


def test_dlq_has_no_clear_pii():
    import sqlite3
    from coded_tools.stream_medallion import common as c
    RunMedallion().invoke({}, {})
    rows = sqlite3.connect(c.DB_PATH).execute("SELECT payload FROM dlq_payments_auth_v3").fetchall()
    blob = " ".join(r[0] for r in rows)
    assert "@example.com" not in blob and "Asha" not in blob


if __name__ == "__main__":
    test_pipeline();
    test_dlq_has_no_clear_pii();
    print("all tests passed")
    print(json.dumps(RunMedallion().invoke({}, {}), indent=1)[:900])
    print(GoldQuery().invoke({
                                 "sql": "SELECT merchant_id,time_bucket,txn_count,auth_rate FROM gold_payments_auth_v3_kpi ORDER BY auth_rate LIMIT 3"},
                             {}))
