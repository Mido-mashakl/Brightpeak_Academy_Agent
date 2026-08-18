# Retrieval Evaluation — Legacy + Course Material

The benchmark keeps the original 12 policy questions and adds 50 course-material cases: grounded, wrong-course, and out-of-scope refusal tests.

| Architecture | Overall | Policy | Course Hit@5 | Course MRR | Course Isolation | Negative Refusal | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| naive | 86% | 100% | 97% | 0.926 | 100% | 43% | 0.001s |
| hybrid | 84% | 100% | 100% | 0.958 | 100% | 29% | 0.005s |
| agentic | 82% | 92% | 100% | 0.958 | 100% | 29% | 0.007s |
| graph | 66% | 50% | 83% | 0.806 | 83% | 36% | 0.005s |

## Acceptance criteria

- A grounded course question should retrieve at least one expected source.
- Every course result must stay inside the requested `course_id` and `content_type=course_material`.
- Wrong-course and out-of-scope cases should be rejected by Self-RAG; the teaching agent must not answer from general knowledge.
- The original policy benchmark remains part of the same evaluation so regressions are visible.
