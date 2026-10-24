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

## Install into your neuro-san-studio clone
```bash
git clone https://github.com/cognizant-ai-lab/neuro-san-studio && cd neuro-san-studio
# (follow the repo README for the venv + .env with your LLM key)

cp -r <this>/coded_tools/stream_medallion  coded_tools/
cp    <this>/registries/streamforge.hocon  registries/
cp -r <this>/data/stream_medallion         data/
cp    <this>/tests/test_tools.py           tests/test_streamforge.py
# add the manifest line from registries/manifest_entry.txt to registries/manifest.hocon

python tests/test_streamforge.py      # tools only, no LLM needed
python -m run                         # then open http://localhost:4173 and pick "streamforge"
```

## Demo script (≈3 minutes)
1. *"Onboard the payments feed."* → profile finds drift (`device_fingerprint`, `phone`), mixed-type `amount`,
   and proposes a PII action for `phone`. **Supervisor pauses for approval.**
2. *"Approved — run it."* → 259 Bronze → 240 Silver, 12 duplicates removed, 7 to DLQ with reasons.
3. *"Which merchant had the worst authorisation rate and when?"* → merchant 4471 at 09:03 (50%),
   with SQL and cited table.
4. Show the guardrail: *"Delete the gold table"* / *"show me raw card numbers"* → refused / requires approval.
5. Open `dlq_*` and `silver_*` to show no clear-text PII.

## Verify before you submit (I could not run these here)
The tools are tested (`tests/`). The HOCON was written from the documented Neuro SAN conventions but **I could not
load it into a live server or reach the repo page**, so confirm these against an existing network in the repo
(`registries/music_nerd.hocon` and any network that uses `"class"`):
1. **`class` path** — coded-tool classes are referenced relative to `coded_tools/`. If yours fails to resolve, try
   `coded_tools.stream_medallion.<module>.<Class>`.
2. **`llm_config`** — match the model name/provider your `.env` and `config/llm_config.hocon` use.
3. **Parameter schemas** — compare the `function.parameters` block shape with an existing coded-tool network.
Shortcut: run the **Agent Network Designer** on this README's pitch and diff its HOCON against `streamforge.hocon`.

## Extending (if you have time before the deadline)
- Add a `pii_agent` and `quality_agent` as separate agents (the deck's 12-agent catalogue) — the tools already isolate the logic.
- Swap the JSONL for a real Kafka consumer tool (`kafka-python` / Redpanda in Docker).
- Report agent is included; next step is rendering its chart spec (slide 16) in a UI.
