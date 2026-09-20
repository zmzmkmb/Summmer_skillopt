# Phase 1F Payload Preflight

Date: 2026-08-10

## Status

Payload materialization and local integrity checks passed. No network calls were made during the audit, and no model or paid API calls were made.

## OfficeQA

The public ModelScope mirror was materialized at `data/officeqa_verified`. `officeqa_full.csv` contains 246 rows and 246 unique UIDs with fields `uid`, `question`, `answer`, `source_docs`, `source_files`, and `difficulty`. The repository split is exact: train 50, val 24, test 172; all split UIDs are present exactly once in the CSV. The materialized tree contains 2,104 files and 5,429,451,383 bytes, including 697 parsed document JSONs. CSV SHA-256: `b5eb1ce0cb343842bccb2f5b067793b4ed90e03e8bf64cb0d40d759bb768ff77`. Split manifest SHA-256: `a9ef22cfd14cbeb4c792ec42d0f9969bb31449c463279e0bf6cd6cdccf042b45`

## SpreadsheetBench

`dataset.json` contains 400 unique rows and exactly matches train 80, val 40, test 280. All 400 task directories resolve a prompt and workbook pair. Split manifest SHA-256: `5d9c40cbd9cc539449a538fcd3aacbb7571b224bbc87c8bdeeb823349210978a`. Dataset SHA-256: `bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7`.

## Decision

The payload gate is passed. Phase 1F is now ready for a new immutable pilot config and provider preflight. The next execution boundary is one bounded Token Plan smoke; formal scaling remains disabled.

## Provenance

- Audit script: `scripts/audit_acl2027_phase1f_payloads.py`
- Test: `tests/test_acl2027_phase1f_payloads.py`
- Network calls during audit: 0
- Paid API calls: 0
- Model calls: 0
