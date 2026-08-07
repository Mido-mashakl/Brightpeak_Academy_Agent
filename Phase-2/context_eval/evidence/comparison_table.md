# Context Management Strategy Comparison

Generated from `test_cases.json` (6 test cases x 4 strategies).

| Strategy | Accuracy | Passed | Avg Token Reduction | Avg Tokens After | Avg Latency (ms) |
|---|---|---|---|---|---|
| sliding_window | 66.7% | 4/6 | 22.9% | 116.0 | 0.0062 |
| observation_masking | 66.7% | 4/6 | -4.6% | 166.3 | 0.0143 |
| recursive_summary | 66.7% | 4/6 | -3.1% | 164.0 | 0.0195 |
| zone_pruning | 83.3% | 5/6 | 11.2% | 133.0 | 0.0853 |

## Per-test-case detail

| Test Case | Strategy | Passed | Missing Facts | Leaked Stale Facts | Tokens Before -> After | Latency (ms) |
|---|---|---|---|---|---|---|
| case1_recency_loss | sliding_window | no | 92% | - | 222 -> 139 | 0.0139 |
| case1_recency_loss | observation_masking | yes | - | - | 222 -> 228 | 0.0221 |
| case1_recency_loss | recursive_summary | yes | - | - | 222 -> 224 | 0.044 |
| case1_recency_loss | zone_pruning | yes | - | - | 222 -> 80 | 0.1717 |
| case2_stale_supersession | sliding_window | yes | - | - | 186 -> 113 | 0.0076 |
| case2_stale_supersession | observation_masking | no | - | web development | 186 -> 202 | 0.0206 |
| case2_stale_supersession | recursive_summary | no | - | web development | 186 -> 200 | 0.0214 |
| case2_stale_supersession | zone_pruning | no | - | web development | 186 -> 150 | 0.0989 |
| case3_masking_loss | sliding_window | yes | - | - | 177 -> 139 | 0.0045 |
| case3_masking_loss | observation_masking | no | 97% | - | 177 -> 184 | 0.021 |
| case3_masking_loss | recursive_summary | yes | - | - | 177 -> 191 | 0.0157 |
| case3_masking_loss | zone_pruning | yes | - | - | 177 -> 184 | 0.0727 |
| case4_zone_relevance | sliding_window | no | 88% | - | 155 -> 111 | 0.0039 |
| case4_zone_relevance | observation_masking | yes | - | - | 155 -> 161 | 0.0079 |
| case4_zone_relevance | recursive_summary | yes | - | - | 155 -> 164 | 0.0162 |
| case4_zone_relevance | zone_pruning | yes | - | - | 155 -> 161 | 0.0752 |
| case5_summary_truncation | sliding_window | yes | - | - | 149 -> 126 | 0.0034 |
| case5_summary_truncation | observation_masking | yes | - | - | 149 -> 155 | 0.0075 |
| case5_summary_truncation | recursive_summary | no | scheduling conflict | - | 149 -> 137 | 0.0151 |
| case5_summary_truncation | zone_pruning | yes | - | - | 149 -> 155 | 0.0586 |
| case6_baseline_sanity | sliding_window | yes | - | - | 65 -> 68 | 0.0037 |
| case6_baseline_sanity | observation_masking | yes | - | - | 65 -> 68 | 0.0066 |
| case6_baseline_sanity | recursive_summary | yes | - | - | 65 -> 68 | 0.0048 |
| case6_baseline_sanity | zone_pruning | yes | - | - | 65 -> 68 | 0.0348 |
