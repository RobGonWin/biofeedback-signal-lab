# Ethics Memo: Biofeedback Signal Lab

## Purpose

This project is an analytics exercise built on public PhysioNet data. Its purpose is to demonstrate careful ingestion, normalization, feature extraction, validation, and reviewability. It is not a medical device, clinical workflow, stress classifier, or treatment-support system.

## Safe Interpretation Boundary

The outputs are designed to support cautious operational interpretation.

They may help surface:
- relative variability differences across windows and channels
- capture consistency differences across subjects or sessions
- motion-heavy periods from accelerometer-derived variability
- records or windows that deserve closer data-quality review

They do not establish:
- clinical diagnosis
- definitive stress state
- cognitive performance level
- treatment need
- medically valid conclusions from summary metrics alone

## Why The Framing Is Conservative

Physiological signals are easy to over-interpret when context is limited. This repo deliberately avoids that failure mode.

What matters here is:
- bounded and documented ingestion
- reproducible transformation logic
- explicit validation before interpretation
- clear explanation of what the outputs do and do not support

What this is not:
- a claim that summary features can diagnose people
- a claim that session-level variability proves cognitive or emotional state

## Data Handling Principles

- use bounded pulls rather than bulk export
- persist manifests before downstream transforms
- keep raw, staging, curated, and warehouse layers separate
- validate completeness and feature sanity before review
- keep the canonical phase-1 workflow local-first with DuckDB
- treat optional Snowflake scaffolding as separate from the main demo path

## Known Limits

- window-level features summarize variability and signal quality, not full physiological context
- sparse `IBI.csv`, `tags.csv`, and `info.txt` inputs are treated as annotations, not definitive labels
- the default slice is intentionally narrow to preserve reproducibility and bandwidth discipline
- optional LUDB and MIT-BIH support broadens technical scope, but the repo headline remains the Wearable Exam Stress path

## Reviewer Takeaway

The correct takeaway is:
"This project shows disciplined analytics engineering on biosignal data, with explicit guardrails around interpretation."

The incorrect takeaway is:
"This project claims to measure or diagnose stress."
