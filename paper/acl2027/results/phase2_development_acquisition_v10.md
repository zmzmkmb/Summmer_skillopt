# Phase 2 Development Acquisition v10

## Decision

The development-acquisition authorization is closed. No later Phase 2 stage ran.

## Scope

This stage contains exactly 10 qwen3.7-plus Token Plan calls: two development tasks
for each of five skill families. It uses zero retries, omits max_tokens, and does
not authorize formal history, probe, held-out execution, or formal scaling.
Development responses are diagnostic and cannot be reused as formal history.

## Scientific Interpretation

The acquisition interface is viable at the stage level: all 10 responses are
exact-contract valid and 8 are verifier-correct. Four families
(`fact_retrieval`, `attribute_comparison`, `bridge_attribute_comparison`, and
`relation_inference`) scored 2/2. `entity_bridge` scored 0/2, with answers that
resolved an intermediate attribute or entity instead of the requested final
bridge answer.

The frozen Phase 2 design treats these calls as a diagnostic rather than a
formal-history eligibility gate, so 0/2 does not by itself cancel the design.
It does indicate elevated coverage risk: the formal-history plan would need 8
independent verified supports for `entity_bridge` within its frozen 32-attempt
cap. No development response is eligible to count toward that target. This
result is capability/acquisition evidence only and is not typed-prior, probe,
triage, held-out, or method-effect evidence.

## Audit Summary

```json
{
  "answer_correct": 8,
  "authorization_closed": true,
  "authorization_sha256": "51f3715616675c3d802b5e334bdd743232c67111ac5806d314e3861ffdacdfb6",
  "authorized_calls": 10,
  "completed_calls": 10,
  "contract_valid": 10,
  "cost_status": "exact",
  "development_outputs_not_formal_history": true,
  "duplicates": 0,
  "evaluations": [
    {
      "answer_correct": true,
      "contract_valid": true,
      "development_only": true,
      "eligible_for_formal_history": false,
      "logical_call_id": "phase2-v10:development_acquisition:fact_retrieval:2bb294748127473c895738c5addb9336:cold",
      "parsed_answer": "Lima",
      "skill_family": "fact_retrieval",
      "task_id": "2bb294748127473c895738c5addb9336"
    },
    {
      "answer_correct": true,
      "contract_valid": true,
      "development_only": true,
      "eligible_for_formal_history": false,
      "logical_call_id": "phase2-v10:development_acquisition:fact_retrieval:82fd2c61b9a64b5f8971b28a1cfd8c1b:cold",
      "parsed_answer": "Douglas MacArthur",
      "skill_family": "fact_retrieval",
      "task_id": "82fd2c61b9a64b5f8971b28a1cfd8c1b"
    },
    {
      "answer_correct": true,
      "contract_valid": true,
      "development_only": true,
      "eligible_for_formal_history": false,
      "logical_call_id": "phase2-v10:development_acquisition:attribute_comparison:fbac69b4087b11ebbd69ac1f6bf848b6:cold",
      "parsed_answer": "No",
      "skill_family": "attribute_comparison",
      "task_id": "fbac69b4087b11ebbd69ac1f6bf848b6"
    },
    {
      "answer_correct": true,
      "contract_valid": true,
      "development_only": true,
      "eligible_for_formal_history": false,
      "logical_call_id": "phase2-v10:development_acquisition:attribute_comparison:ae623ebe086111ebbd5dac1f6bf848b6:cold",
      "parsed_answer": "Daniel Tauvry",
      "skill_family": "attribute_comparison",
      "task_id": "ae623ebe086111ebbd5dac1f6bf848b6"
    },
    {
      "answer_correct": true,
      "contract_valid": true,
      "development_only": true,
      "eligible_for_formal_history": false,
      "logical_call_id": "phase2-v10:development_acquisition:bridge_attribute_comparison:4cc2866e087f11ebbd6bac1f6bf848b6:cold",
      "parsed_answer": "No. 1 Of The Secret Service",
      "skill_family": "bridge_attribute_comparison",
      "task_id": "4cc2866e087f11ebbd6bac1f6bf848b6"
    },
    {
      "answer_correct": true,
      "contract_valid": true,
      "development_only": true,
      "eligible_for_formal_history": false,
      "logical_call_id": "phase2-v10:development_acquisition:bridge_attribute_comparison:53625784086511ebbd5eac1f6bf848b6:cold",
      "parsed_answer": "Beauty No. 2",
      "skill_family": "bridge_attribute_comparison",
      "task_id": "53625784086511ebbd5eac1f6bf848b6"
    },
    {
      "answer_correct": false,
      "contract_valid": true,
      "development_only": true,
      "eligible_for_formal_history": false,
      "logical_call_id": "phase2-v10:development_acquisition:entity_bridge:5d2b68b60bdd11eba7f7acde48001122:cold",
      "parsed_answer": "Iranian-Kurdish",
      "skill_family": "entity_bridge",
      "task_id": "5d2b68b60bdd11eba7f7acde48001122"
    },
    {
      "answer_correct": false,
      "contract_valid": true,
      "development_only": true,
      "eligible_for_formal_history": false,
      "logical_call_id": "phase2-v10:development_acquisition:entity_bridge:fd9660300bdd11eba7f7acde48001122:cold",
      "parsed_answer": "Hildene",
      "skill_family": "entity_bridge",
      "task_id": "fd9660300bdd11eba7f7acde48001122"
    },
    {
      "answer_correct": true,
      "contract_valid": true,
      "development_only": true,
      "eligible_for_formal_history": false,
      "logical_call_id": "phase2-v10:development_acquisition:relation_inference:46e2b2720baf11ebab90acde48001122:cold",
      "parsed_answer": "Sir Roger Martin, 2nd Baronet",
      "skill_family": "relation_inference",
      "task_id": "46e2b2720baf11ebab90acde48001122"
    },
    {
      "answer_correct": true,
      "contract_valid": true,
      "development_only": true,
      "eligible_for_formal_history": false,
      "logical_call_id": "phase2-v10:development_acquisition:relation_inference:60b814940baf11ebab90acde48001122:cold",
      "parsed_answer": "Birut\u0117",
      "skill_family": "relation_inference",
      "task_id": "60b814940baf11ebab90acde48001122"
    }
  ],
  "exact_local_cost_cny": 0.025526,
  "experiment": "acl2027_phase2_development_acquisition_v10",
  "formal_history_calls": 0,
  "formal_scaling_calls": 0,
  "held_out_calls": 0,
  "ledger_sha256": "3ebad7483a3f280296ef80a04cb783e110f569be313ff3abf092fd5df40517bf",
  "max_tokens_present": false,
  "pacing_ledger_sha256": "55c08dbbfabc515c5619b17fe0dc28c906aa44ceda9ec90d929ad63231961be0",
  "per_family": {
    "attribute_comparison": {
      "answer_correct": 2,
      "calls": 2,
      "contract_valid": 2
    },
    "bridge_attribute_comparison": {
      "answer_correct": 2,
      "calls": 2,
      "contract_valid": 2
    },
    "entity_bridge": {
      "answer_correct": 0,
      "calls": 2,
      "contract_valid": 2
    },
    "fact_retrieval": {
      "answer_correct": 2,
      "calls": 2,
      "contract_valid": 2
    },
    "relation_inference": {
      "answer_correct": 2,
      "calls": 2,
      "contract_valid": 2
    }
  },
  "probe_calls": 0,
  "provider_attempts": 10,
  "request_start_pacing_valid": true,
  "request_start_spacing_minimum_seconds": 1.6265254,
  "retries": 0,
  "schema_version": 10,
  "status": "completed",
  "terminal_rows": 0,
  "total_input_tokens": 12371,
  "total_output_tokens": 98,
  "total_tokens": 12469
}
```
