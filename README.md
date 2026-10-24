# StreamForge — a metadata-driven streaming medallion, run by a Neuro SAN agent network

Built on `cognizant-ai-lab/neuro-san-studio`. A hackathon-sized, runnable slice of the ArchMaster case study
*"AI-Powered Real-Time Streaming Solution Using Multi-Agent AI Architecture"*.

## The pitch (30 seconds)
Onboarding a new event feed normally takes weeks of hand-written pipeline code, and schema drift silently breaks it.
StreamForge onboards a feed from a **feed descriptor** (metadata, not code). Deterministic tools do the hot path;
LLM agents are used only where judgement is needed — drift, PII classification, human-approval proposals and
natural-language answers from Gold. Every answer carries its SQL and cited tables.

## What it demonstrates (traceable to the deck)
| Case-study idea (slide) | In this repo |
|---|---|
| Metadata-driven medallion (9) | `DEFAULT_CONTRACT` in `common.py` is the feed descriptor; `run_medallion.py` is driven entirely by it |
| LLM off the hot path (11) | Profiling, validation, masking, dedup, aggregation are plain Python tools |
| Schema & Contract agent proposes, human approves (11, 13) | `contract_agent` drafts a PII/contract patch; `stream_supervisor` blocks until you approve |
| Quality + DLQ with reasons (9, 11) | `dlq_*` table with reason codes; DLQ payloads are PII-redacted |
| PII tokenise / hash / mask (9) | Policy-driven in `_apply_pii` |
| Idempotent merge, effectively-once (7, 11) | Upsert on declared key, latest event wins; re-runs yield identical tables |
| NL→SQL on a governed layer only (12, 15) | `insight_agent`: schema first, then SQL, then `gold_query` guardrails (read-only, `gold_*` only, row cap) |
| Supervisor / HITL (13) | `stream_supervisor` front-man |
| Serving-layer reporting (16) | `report_agent`: grounded briefing + chart spec |

Deliberately **out of scope** for the demo (say so openly in your submission): real Kafka, Iceberg, multi-cloud
adapters, the LLM gateway. The sample is a JSONL file standing in for the Bronze topic; SQLite stands in for the lakehouse.

## Demo script (≈3 minutes)
1. *"Onboard the payments feed."* → profile finds drift (`device_fingerprint`, `phone`), mixed-type `amount`,
   and proposes a PII action for `phone`. **Supervisor pauses for approval.**
2. *"Approved — run it."* → 259 Bronze → 240 Silver, 12 duplicates removed, 7 to DLQ with reasons.
3. *"Which merchant had the worst authorisation rate and when?"* → merchant 4471 at 09:03 (50%),
   with SQL and cited table.
4. Show the guardrail: *"Delete the gold table"* / *"show me raw card numbers"* → refused / requires approval.
5. Open `dlq_*` and `silver_*` to show no clear-text PII.
