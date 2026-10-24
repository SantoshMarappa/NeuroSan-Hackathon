"""Generate a reproducible Bronze sample with duplicates, bad rows, drift and PII."""
import json
import random
from datetime import datetime, timedelta

random.seed(42)
out = []
start = datetime(2026, 10, 21, 9, 0, 0)
merchants = ["4471", "2210", "8805"]
for i in range(240):
    ts = start + timedelta(seconds=i * 1.25)
    m = random.choice(merchants)
    minute = i * 1.25 // 60
    # merchant 4471 has an issuer-timeout incident in minute 3
    bad_window = m == "4471" and minute == 3
    declined = random.random() < (0.65 if bad_window else 0.06)
    rec = {
        "txn_id": f"T{i:05d}", "merchant_id": m,
        "amount": round(random.uniform(5, 900), 2), "currency": "EUR",
        "status": "DECLINED" if declined else "APPROVED",
        "decline_reason": ("ISSUER_TIMEOUT" if bad_window else "INSUFFICIENT_FUNDS") if declined else None,
        "card_no": f"4{random.randint(10 ** 14, 10 ** 15 - 1)}",
        "email": f"user{i}@example.com", "holder": random.choice(["Asha Rao", "Liam Chen", "Maria Silva"]),
        "event_ts": ts.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if i >= 170:  # schema drift: new field appears mid-stream
        rec["device_fingerprint"] = f"fp_{random.randint(1000, 9999)}"
        rec["phone"] = f"+4477{random.randint(10000000, 99999999)}"
    out.append(json.dumps(rec))

lines = out[:]
lines += random.sample(out, 12)  # duplicate deliveries
for i in (10, 55, 120):  # out-of-range / negative amounts
    r = json.loads(out[i]);
    r["txn_id"] = f"X{i:05d}";
    r["amount"] = -50 if i % 2 else 5_000_000
    lines.append(json.dumps(r))
r = json.loads(out[7]);
r["txn_id"] = None;
lines.append(json.dumps(r))  # missing key
r = json.loads(out[9]);
r["txn_id"] = "XSTR1";
r["amount"] = "12.50";
lines.append(json.dumps(r))  # type drift
lines += ['{"txn_id": "BROKEN", "amount": ', "not json at all"]
random.shuffle(lines)
open("data/stream_medallion/payments_auth_sample.jsonl", "w").write("\n".join(lines) + "\n")
print(len(lines), "lines written")
