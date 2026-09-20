# Phase 4C repaired held-out live v2 analysis

This analysis is descriptive and coverage-incomplete. The run has 395 completed responses out of 400 scheduled rows; five rows are missing because the CNY 3.00 stage ceiling triggered a terminal hard stop. No new provider calls were made.

{
  "schema_version": 2,
  "status": "coverage_incomplete",
  "scheduled_rows": 400,
  "completed_rows": 395,
  "missing_rows": 5,
  "gold_tasks": 80,
  "conditions": {
    "cold": {
      "scheduled": 80,
      "completed": 79,
      "contract_valid": 79,
      "evidence_ids_resolve": 79,
      "answer_scored": 79,
      "answer_correct": 73,
      "contract_valid_rate": 1.0,
      "evidence_resolve_rate": 1.0,
      "answer_accuracy_over_scored": 0.924051
    },
    "global_only": {
      "scheduled": 80,
      "completed": 79,
      "contract_valid": 79,
      "evidence_ids_resolve": 79,
      "answer_scored": 79,
      "answer_correct": 78,
      "contract_valid_rate": 1.0,
      "evidence_resolve_rate": 1.0,
      "answer_accuracy_over_scored": 0.987342
    },
    "contextual_typed": {
      "scheduled": 80,
      "completed": 79,
      "contract_valid": 79,
      "evidence_ids_resolve": 79,
      "answer_scored": 79,
      "answer_correct": 78,
      "contract_valid_rate": 1.0,
      "evidence_resolve_rate": 1.0,
      "answer_accuracy_over_scored": 0.987342
    },
    "shuffled_typed": {
      "scheduled": 80,
      "completed": 79,
      "contract_valid": 79,
      "evidence_ids_resolve": 79,
      "answer_scored": 79,
      "answer_correct": 78,
      "contract_valid_rate": 1.0,
      "evidence_resolve_rate": 1.0,
      "answer_accuracy_over_scored": 0.987342
    },
    "incompatible_control": {
      "scheduled": 80,
      "completed": 79,
      "contract_valid": 79,
      "evidence_ids_resolve": 79,
      "answer_scored": 79,
      "answer_correct": 76,
      "contract_valid_rate": 1.0,
      "evidence_resolve_rate": 1.0,
      "answer_accuracy_over_scored": 0.962025
    }
  },
  "task_grids_observed": 79,
  "provider_calls": 0,
  "new_calls_made": 0,
  "interpretation": "Descriptive analysis only; the 400-row frozen gate is not evaluable because five rows are missing and cumulative-cost accounting requires review."
}
