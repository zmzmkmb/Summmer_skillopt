# Phase 3D v3.1 contract-shape diagnostic

The strict v3 gate remains **negative** because 240/240 responses used a candidate-ID-keyed assessment object instead of the frozen ordered assessment array. The non-gating diagnostic reconstructs that order only to describe the already spent responses; it cannot reverse the strict result.

Tolerant parse: `240/240`. Metrics: `{"alias_contextual_vs_cold": {"both": 32, "left_only": 0, "neither": 6, "net_wins": -2, "right_only": 2}, "alias_contextual_vs_irrelevant": {"both": 30, "left_only": 2, "neither": 6, "net_wins": 0, "right_only": 2}, "contextual_alias_net_loss_vs_cold": 2, "contextual_alias_net_wins_over_irrelevant": 0, "contextual_single_correct_selection_rate": 1.0, "contextual_single_selected_non_none_rate": 1.0, "contextual_vs_irrelevant_normalized_answer_change_rate": 0.1, "contextual_vs_irrelevant_operation_change_rate": 0.55, "dual_correct_selection_rate": 1.0, "dual_order_effect_absolute_difference": 0.0, "dual_wrong_selection_rate": 0.0, "irrelevant_single_rejection_rate": 0.675}`.

Fingerprint: `b90e0659a9936da215e0d47c34a418a91267070d9e0f28573d008d46d6846ddb`.
