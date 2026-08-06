# Retrieval Architecture Comparison

| Architecture | Accuracy (12 questions) | Avg tokens/query | Avg latency/query |
|---|---|---|---|
| naive_rag | 86% | 469 | 0.002s |
| hybrid_rag | 89% | 492 | 0.003s |
| agentic_rag | 89% | 404 | 0.005s |
| graph_rag | 40% | 435 | 0.067s |

## Decision

Based on the numbers and Brightpeak's real query patterns
(live advisory calls dominated by quick citation and general
policy questions, with occasional multi-part eligibility questions):

- **Default: Hybrid Search** — best accuracy/latency trade-off for citation and general questions.
- **Route multi-part questions to Agentic RAG** when the query needs decomposition.
- Graph RAG is retained as a bonus path for relationship-heavy questions.
