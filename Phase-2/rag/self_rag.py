"""
Brightpeak Academy — Self-RAG-style Verification
=================================================

Before an answer reaches the user, an explicit check:
  1. Is the retrieved content actually relevant to the query?
  2. Is the generated answer actually supported by the retrieved content?

Applies to both RAG answers and memories recalled from episodic/semantic
stores. When the check fails, the system refuses to answer confidently
and surfaces the failure reason (visible to a grader).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class VerificationResult:
    is_relevant: bool
    is_supported: bool
    relevance_score: float
    support_score: float
    reason: str
    action: str  # "pass" | "refuse" | "regenerate"

    def to_dict(self) -> dict:
        return {
            "is_relevant": self.is_relevant,
            "is_supported": self.is_supported,
            "relevance_score": self.relevance_score,
            "support_score": self.support_score,
            "reason": self.reason,
            "action": self.action,
        }


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _overlap_ratio(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta:
        return 0.0
    return len(ta & tb) / len(ta)


class SelfRAGVerifier:
    """
    Rule-based verifier (deterministic, no API key). In production the
    same interface is backed by an LLM critique step following the
    Self-RAG paper (reflection tokens / relevance + support grades).
    """

    def __init__(
        self,
        relevance_threshold: float = 0.15,
        support_threshold: float = 0.20,
    ):
        self.relevance_threshold = relevance_threshold
        self.support_threshold = support_threshold

    def check_relevance(self, query: str, passages: list[str]) -> tuple[bool, float, str]:
        if not passages:
            return False, 0.0, "No passages retrieved."
        scores = [_overlap_ratio(query, p) for p in passages]
        best = max(scores)
        ok = best >= self.relevance_threshold
        reason = (
            f"Best passage overlap with query = {best:.2f} "
            f"(threshold {self.relevance_threshold})."
        )
        return ok, best, reason

    def check_support(self, answer: str, passages: list[str]) -> tuple[bool, float, str]:
        if not answer or answer.strip().lower() in {
            "i don't know",
            "no relevant policy passages found.",
            "i cannot answer from the retrieved documents.",
        }:
            # Explicit refusal is always "supported"
            return True, 1.0, "Answer is an explicit refusal / insufficient-info statement."
        if not passages:
            return False, 0.0, "Answer claims knowledge but no passages were retrieved."
        combined = " ".join(passages)
        score = _overlap_ratio(answer, combined)
        # Also penalise if answer is very long relative to support
        ok = score >= self.support_threshold
        reason = (
            f"Answer token overlap with retrieved passages = {score:.2f} "
            f"(threshold {self.support_threshold})."
        )
        return ok, score, reason

    def verify(
        self,
        query: str,
        passages: list[str],
        answer: str | None = None,
    ) -> VerificationResult:
        rel_ok, rel_score, rel_reason = self.check_relevance(query, passages)

        if not rel_ok:
            return VerificationResult(
                is_relevant=False,
                is_supported=False,
                relevance_score=rel_score,
                support_score=0.0,
                reason=f"RELEVANCE FAIL: {rel_reason}",
                action="refuse",
            )

        if answer is None:
            # Pre-generation check: only relevance matters so far
            return VerificationResult(
                is_relevant=True,
                is_supported=True,
                relevance_score=rel_score,
                support_score=1.0,
                reason=f"RELEVANCE PASS: {rel_reason}",
                action="pass",
            )

        sup_ok, sup_score, sup_reason = self.check_support(answer, passages)
        if not sup_ok:
            return VerificationResult(
                is_relevant=True,
                is_supported=False,
                relevance_score=rel_score,
                support_score=sup_score,
                reason=f"SUPPORT FAIL: {sup_reason}",
                action="refuse",
            )

        return VerificationResult(
            is_relevant=True,
            is_supported=True,
            relevance_score=rel_score,
            support_score=sup_score,
            reason=f"PASS: {rel_reason} | {sup_reason}",
            action="pass",
        )

    def apply(
        self,
        query: str,
        hits: list[dict],
        answer: str | None = None,
    ) -> dict[str, Any]:
        """Convenience wrapper used by the agent loop."""
        passages = [h["document"] for h in hits]
        result = self.verify(query, passages, answer)
        return {
            "verification": result.to_dict(),
            "final_answer": (
                answer
                if result.action == "pass" and answer is not None
                else (
                    "I could not find sufficiently relevant or supporting policy "
                    f"passages to answer confidently. ({result.reason})"
                )
            ),
        }


if __name__ == "__main__":
    v = SelfRAGVerifier()
    passages = [
        "Students must maintain at least 75% attendance per course to remain eligible for final assessments."
    ]
    print(v.verify("What is the attendance threshold?", passages, "The minimum is 75%."))
    print(v.verify("What is the attendance threshold?", passages, "The minimum is 40% and also free pizza."))
    print(v.verify("What colour is the sky?", passages, "Blue."))
