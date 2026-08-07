"""
Brightpeak Academy - Memory System Extension
==============================================
Context-Window Management -- Strategy Evaluation Framework
-----------------------------------------------------------------

Runs all four context-management strategies in this folder
(`sliding_window.py`, `observation_masking.py`, `recursive_summary.py`,
`zone_pruning.py`) against the same long-context test suite
(`test_cases.json`) and produces an evidence-backed comparison, instead
of picking a strategy on intuition.

## What each metric means and how it's computed

- **Task accuracy**: for each test case, `expected_facts` is a list of
  lowercase substrings that MUST appear somewhere in the pruned/
  compressed context for the original query to still be answerable
  from it. An optional `unexpected_facts` list holds substrings that
  must NOT appear -- this catches the specific failure mode where a
  strategy resurfaces a *superseded* fact (e.g. an old track
  preference) as if it were still current. A test case counts as a
  pass (1.0) only if every expected substring is present AND no
  unexpected substring is present; otherwise it's a fail (0.0).
  Per-strategy accuracy is the mean pass rate across all test cases.
  This is a lexical, deterministic check -- it doesn't call an LLM to
  judge answerability, so it's fast and reproducible, at the cost of
  being stricter/dumber than an actual downstream agent might be
  (e.g. it can't handle paraphrase). That tradeoff is intentional for
  a repeatable evaluation harness; see "Known limitations" below.

- **Token consumption**: approximated as `len(content) // 4` per
  message (the same cheap, dependency-free heuristic used inside
  `sliding_window.py`), summed over all messages in the resulting
  context (plus the running summary text, for `recursive_summary`).
  This is an approximation, not a real tokenizer count -- good enough
  for *relative* comparison between strategies on the same text, not
  meant as an exact API billing figure.

- **Execution latency**: wall-clock time (`time.perf_counter`) to run
  the strategy's transform on one test case's messages, in
  milliseconds. Since none of the four strategies call an LLM by
  default (all use dependency-free deterministic stubs for their
  "smart" step -- see each module's docstring), this measures the
  strategy's own bookkeeping/algorithm cost, not summarization
  latency. If a real LLM-backed `summarizer_fn` / `relevance_scorer`
  is injected in production, re-run this harness with that callable
  wired in to get a representative number.

## Known limitations

- Six test cases is enough to *differentiate* the four strategies'
  failure modes (that's what they were designed for -- see
  `_generate_test_cases.py`), not to be a statistically powerful
  benchmark. Treat the accuracy numbers as diagnostic, not as
  four-significant-figures ground truth.
- The lexical accuracy check and the lexical relevance scorer inside
  `zone_pruning.py`'s default configuration share the same blind spot
  (no paraphrase understanding) -- so `zone_pruning`'s accuracy score
  here is optimistic relative to what it'd score against a paraphrased
  query. Swapping in an embedding-based `relevance_scorer` would be a
  fairer real-world comparison.
- `recursive_summary`'s default `_default_summarizer` is extractive
  (keeps short excerpts), not a real abstractive LLM summary -- so its
  accuracy score here is a floor, not a ceiling; a real LLM summarizer
  would likely score at least as well.

## Usage

    cd context_eval
    python evaluate.py

Writes `results/eval_results.json` (full per-test-case, per-strategy
detail) and `results/comparison_table.md` (the aggregate table), and
prints the same table to stdout.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sliding_window import SlidingWindow
from observation_masking import ObservationMasker
from recursive_summary import RecursiveSummarizer
from zone_pruning import ZonePruner

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_CASES_PATH = os.path.join(HERE, "test_cases.json")
RESULTS_DIR = os.path.join(HERE, "results")


def _approx_token_count(text: str) -> int:
    """Same cheap heuristic used in sliding_window.py (~4 chars/token).
    See module docstring's "Token consumption" note for what this is
    and isn't good for.
    """
    return max(0, len(text) // 4)


def _context_text(context_messages: list[dict], extra_text: str = "") -> str:
    """Flattens a resulting context into one lowercase string for the
    substring-based accuracy check and for token counting.
    """
    parts = [str(m.get("content", "")) for m in context_messages]
    if extra_text:
        parts.append(extra_text)
    return " ".join(parts).lower()


# ---------------------------------------------------------------------
# Strategy adapters -- each takes (messages, query) and returns
# (context_messages, extra_text_for_accuracy_check). `extra_text` exists
# because recursive_summary's running summary is a synthetic message
# already included in as_context(), but keeping the adapter shape
# uniform (context_messages, extra_text) makes it trivial to add a
# fifth strategy later without changing the harness below.
# ---------------------------------------------------------------------

def _run_sliding_window(messages: list[dict], query: str) -> tuple[list[dict], str]:
    sw = SlidingWindow(window_size=8)
    result = sw.select(messages)
    return result.included, ""


def _run_observation_masking(messages: list[dict], query: str) -> tuple[list[dict], str]:
    om = ObservationMasker(keep_recent=2)
    result = om.mask(messages)
    return result.messages, ""


def _run_recursive_summary(messages: list[dict], query: str) -> tuple[list[dict], str]:
    # Fresh instance per test case -- RecursiveSummarizer is stateful
    # (tracks _folded_count across calls) and each test case is an
    # independent conversation, not a continuation of the previous one.
    rs = RecursiveSummarizer(trigger_at=10, chunk_size=4, keep_recent=6)
    result = rs.process(messages)
    return result.as_context(), ""


def _run_zone_pruning(messages: list[dict], query: str) -> tuple[list[dict], str]:
    zp = ZonePruner(threshold=0.15)
    result = zp.prune(messages, query)
    return result.messages, ""


STRATEGIES: dict[str, Callable[[list[dict], str], tuple[list[dict], str]]] = {
    "sliding_window": _run_sliding_window,
    "observation_masking": _run_observation_masking,
    "recursive_summary": _run_recursive_summary,
    "zone_pruning": _run_zone_pruning,
}


@dataclass
class TestCaseResult:
    test_case_id: str
    strategy: str
    passed: bool
    missing_expected: list[str]
    leaked_unexpected: list[str]
    tokens_before: int
    tokens_after: int
    token_reduction_pct: float
    latency_ms: float
    messages_before: int
    messages_after: int


@dataclass
class StrategySummary:
    strategy: str
    accuracy: float
    avg_token_reduction_pct: float
    avg_tokens_after: float
    avg_latency_ms: float
    passed_count: int
    total_count: int


def load_test_cases() -> list[dict]:
    with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["test_cases"]


def evaluate_one(test_case: dict, strategy_name: str, strategy_fn) -> TestCaseResult:
    messages = test_case["messages"]
    query = test_case["query"]
    expected = [s.lower() for s in test_case.get("expected_facts", [])]
    unexpected = [s.lower() for s in test_case.get("unexpected_facts", [])]

    tokens_before = sum(_approx_token_count(str(m.get("content", ""))) for m in messages)

    start = time.perf_counter()
    context_messages, extra_text = strategy_fn(messages, query)
    latency_ms = (time.perf_counter() - start) * 1000.0

    text = _context_text(context_messages, extra_text)
    tokens_after = _approx_token_count(text)

    missing_expected = [fact for fact in expected if fact not in text]
    leaked_unexpected = [fact for fact in unexpected if fact in text]
    passed = not missing_expected and not leaked_unexpected

    token_reduction_pct = (
        100.0 * (1 - tokens_after / tokens_before) if tokens_before > 0 else 0.0
    )

    return TestCaseResult(
        test_case_id=test_case["id"],
        strategy=strategy_name,
        passed=passed,
        missing_expected=missing_expected,
        leaked_unexpected=leaked_unexpected,
        tokens_before=tokens_before,
        tokens_after=tokens_after,
        token_reduction_pct=round(token_reduction_pct, 1),
        latency_ms=round(latency_ms, 4),
        messages_before=len(messages),
        messages_after=len(context_messages),
    )


def summarize(results: list[TestCaseResult], strategy_name: str) -> StrategySummary:
    subset = [r for r in results if r.strategy == strategy_name]
    total = len(subset)
    passed = sum(1 for r in subset if r.passed)
    return StrategySummary(
        strategy=strategy_name,
        accuracy=round(passed / total, 3) if total else 0.0,
        avg_token_reduction_pct=round(statistics.mean(r.token_reduction_pct for r in subset), 1) if subset else 0.0,
        avg_tokens_after=round(statistics.mean(r.tokens_after for r in subset), 1) if subset else 0.0,
        avg_latency_ms=round(statistics.mean(r.latency_ms for r in subset), 4) if subset else 0.0,
        passed_count=passed,
        total_count=total,
    )


def render_comparison_table(summaries: list[StrategySummary]) -> str:
    headers = [
        "Strategy", "Accuracy", "Passed", "Avg Token Reduction", "Avg Tokens After", "Avg Latency (ms)",
    ]
    rows = []
    for s in summaries:
        rows.append([
            s.strategy,
            f"{s.accuracy * 100:.1f}%",
            f"{s.passed_count}/{s.total_count}",
            f"{s.avg_token_reduction_pct:.1f}%",
            f"{s.avg_tokens_after:.1f}",
            f"{s.avg_latency_ms:.4f}",
        ])

    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def run() -> tuple[list[TestCaseResult], list[StrategySummary]]:
    test_cases = load_test_cases()
    all_results: list[TestCaseResult] = []

    for test_case in test_cases:
        for strategy_name, strategy_fn in STRATEGIES.items():
            result = evaluate_one(test_case, strategy_name, strategy_fn)
            all_results.append(result)

    summaries = [summarize(all_results, name) for name in STRATEGIES]
    return all_results, summaries


def export_results(all_results: list[TestCaseResult], summaries: list[StrategySummary]) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)

    json_path = os.path.join(RESULTS_DIR, "eval_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "per_test_case_results": [r.__dict__ for r in all_results],
                "strategy_summaries": [s.__dict__ for s in summaries],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    table_md = render_comparison_table(summaries)
    md_path = os.path.join(RESULTS_DIR, "comparison_table.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Context Management Strategy Comparison\n\n")
        f.write(f"Generated from `test_cases.json` ({len(all_results) // len(STRATEGIES)} test cases x "
                f"{len(STRATEGIES)} strategies).\n\n")
        f.write(table_md)
        f.write("\n\n## Per-test-case detail\n\n")
        f.write("| Test Case | Strategy | Passed | Missing Facts | Leaked Stale Facts | Tokens Before -> After | Latency (ms) |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in all_results:
            f.write(
                f"| {r.test_case_id} | {r.strategy} | {'yes' if r.passed else 'no'} | "
                f"{', '.join(r.missing_expected) or '-'} | {', '.join(r.leaked_unexpected) or '-'} | "
                f"{r.tokens_before} -> {r.tokens_after} | {r.latency_ms} |\n"
            )

    print(f"\nExported: {json_path}")
    print(f"Exported: {md_path}")


if __name__ == "__main__":
    all_results, summaries = run()

    print("=" * 100)
    print("CONTEXT MANAGEMENT STRATEGY COMPARISON")
    print("=" * 100)
    print(render_comparison_table(summaries))

    print("\nFailures (if any):")
    failures = [r for r in all_results if not r.passed]
    if not failures:
        print("  none -- every strategy passed every test case.")
    else:
        for r in failures:
            reason = []
            if r.missing_expected:
                reason.append(f"missing: {r.missing_expected}")
            if r.leaked_unexpected:
                reason.append(f"leaked stale fact: {r.leaked_unexpected}")
            print(f"  [{r.strategy}] {r.test_case_id}: {'; '.join(reason)}")

    export_results(all_results, summaries)

    best_accuracy = max(summaries, key=lambda s: s.accuracy)
    best_compression = max(summaries, key=lambda s: s.avg_token_reduction_pct)
    print(f"\nHighest accuracy: {best_accuracy.strategy} ({best_accuracy.accuracy * 100:.1f}%)")
    print(f"Highest token reduction: {best_compression.strategy} ({best_compression.avg_token_reduction_pct:.1f}%)")
    print(
        "\nNote: pick the deployed strategy by weighing accuracy against token reduction for "
        "Brightpeak's actual usage pattern -- see module docstring's 'Known limitations' before "
        "treating either number as the final word."
    )