# StreamForge — Submission Write-up

**Track:** Agentic AI Hackathon · **Built on:** cognizant-ai-lab/neuro-san-studio (Neuro SAN, HOCON agent networks)
**Origin:** ArchMaster Program case study — *AI-Powered Real-Time Streaming Solution Using Multi-Agent AI Architecture*

## 1. Problem
Events already arrive in real time, but insight arrives via nightly batch. Every new feed needs hand-written pipeline
code (4–6 weeks to onboard), schema drift silently breaks jobs, PII handling is inconsistent, and business users
raise engineering tickets for every question.

## 2. Solution
StreamForge is a multi-agent network that onboards and curates a feed from **metadata, not code**, then lets people
ask questions of the curated data in plain English.

Design principle: **the LLM is off the hot path.** Parsing, validation, masking, de-duplication and aggregation are
deterministic tools. Agents are used only where judgement is required: interpreting drift, classifying PII,
proposing contract changes for human approval, and answering questions.

## 3. How it works (agents and tools)
| Agent | Role | Tool |
|---|---|---|
| `stream_supervisor` | Plans, routes, enforces human-approval gate | — |
| `contract_agent` | Detects drift and PII, **proposes** a contract change | `profile_payloads` |
| `medallion_runner` | Runs Bronze → Silver → Gold from the approved descriptor | `run_medallion` |
| `insight_agent` | Governed NL→SQL: schema first, SQL second, validated third | `gold_query` |
| `report_agent` | Builds a grounded briefing with a chart spec | via `insight_agent` |

## 4. What makes it trustworthy
- **Human-in-the-loop:** agents propose contract changes; the supervisor waits for approval.
- **Governed generation:** SQL can only touch `gold_*` tables, is read-only, single-statement, row-capped.
- **No clear-text PII** in Silver *or* the dead-letter table (policy: tokenise / hash / mask / drop).
- **Idempotent:** replaying the same Bronze data yields identical tables (effectively-once semantics).
- **Grounded answers:** every answer carries its SQL and cited tables; reports may not assert unsupported causes.
- **Tested:** deterministic tools have automated tests, including the PII-in-DLQ regression and SQL-guardrail rejections.

## 5. Results on the demo feed
259 Bronze lines → 240 Silver rows · 12 duplicates removed · 7 rejects routed to DLQ with reason codes
(invalid JSON, out-of-range amount, type mismatch, missing key) · 2 drifted fields captured, not dropped ·
the 09:03 authorisation-rate dip for merchant 4471 (50%) found in one natural-language question.

## 6. Business value (from the case study)
Hours-old → seconds-old insight; onboarding by configuration (case-study target: 60–70% less pipeline build effort);
self-service analytics removes the BI ticket backlog; every control (approval, redaction, guardrail) is auditable.
*These are architecture-level targets from the case study, not measured results of this prototype.*

## 7. Scope and honesty
Prototype stand-ins: a JSONL file for the Kafka Bronze topic, SQLite for the Iceberg lakehouse, a single LLM
configuration instead of the tiered LLM gateway. The production architecture (Kafka/Flink/Iceberg, K8s, multi-cloud
adapters, tiered models) is in the ArchMaster deck and is the intended path forward.

## 8. Roadmap
Separate PII and quality agents · live Kafka consumer tool · LLM-gateway tiering and cost metering ·
conformance tests across storage adapters · scheduled/alert-triggered reports.

---

# Demo video script (~3:30)

| Time | On screen | Say |
|---|---|---|
| 0:00 | Title + one-line problem | "New data feeds take weeks to onboard and break when schemas drift. StreamForge does it from metadata, with agents only where judgement is needed." |
| 0:25 | NSFlow showing the agent network | "A supervisor, a contract agent, a curation runner, an insight agent and a report agent. The heavy lifting is deterministic tools." |
| 0:50 | Prompt: *Onboard the payments feed.* | "The contract agent profiles the raw stream and finds two new fields and a mixed-type amount." |
| 1:20 | Proposal + supervisor pausing | "It proposes a PII action for the new phone field, but it can't apply it. The supervisor waits for me." |
| 1:40 | Prompt: *Approved, run it.* | "259 raw events become 240 clean records. 12 duplicates removed, 7 rejects with reasons, and no clear-text PII anywhere, including the reject queue." |
| 2:15 | Prompt: *Which merchant had the worst authorisation rate, and when?* | "Merchant 4471 at 09:03. Note the SQL and tables cited: the answer is grounded and checkable." |
| 2:45 | Prompt: *Delete the gold table.* / *Show raw card numbers.* | "Guardrails: read-only, Gold-only, writes need approval." |
| 3:05 | Prompt: *Give me a merchant performance report.* | "The report agent builds a briefing and chart spec, using only what the data supports." |
| 3:25 | Closing slide | "Metadata-driven, human-approved, auditable. Built on Neuro SAN from a real architecture case study." |

**Recording tips:** run the tools test first so the demo database exists; keep prompts short; rehearse once so
the LLM's wording doesn't surprise you; if any step misbehaves, re-run it rather than editing around it.
