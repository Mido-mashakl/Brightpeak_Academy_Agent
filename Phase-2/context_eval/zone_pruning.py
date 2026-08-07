"""
Brightpeak Academy - Memory System Extension
==============================================
Context Window Management -- Zone Pruning Strategy
--------------------------------------------------------

A context-window management strategy that operates on *topical zones*
rather than on raw message count (sliding_window.py), message type
(observation_masking.py), or age (recursive_summary.py).

A "zone" here is a contiguous run of messages that belong to the same
sub-topic -- e.g. everything about Ahmed's attendance, then everything
about a different student's scholarship eligibility, then everything
about registering for the Flutter track. Real conversations with an
academic advisor jump between students and topics; once the
conversation has moved on from a zone, that zone is a strong candidate
to prune *regardless of how many turns ago it was*, even if it's more
recent than some other zone that's still relevant to the current query.

This is the complementary case sliding_window.py can't handle well: a
purely recency-based window keeps the last N messages even if most of
them are about a topic the current query has nothing to do with, and
can drop an older zone that's actually still relevant.

Like the other context_eval/ strategies, this is a read-time view:
- It never mutates the input messages.
- Pruned zones are not deleted from the source of truth -- they are
  simply excluded from *this* prompt. The caller can still find them
  in full history, or in episodic/semantic memory if the
  Promote-or-Drop router (memory/router.py) already promoted the
  relevant facts out of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

# (zone_messages, query) -> relevance score in [0.0, 1.0]
RelevanceScorerFn = Callable[[list[dict], str], float]


def _tokenize(text: str) -> set[str]:
    return {w.strip(".,!?:;\"'()").lower() for w in text.split() if w.strip(".,!?:;\"'()")}


def _default_relevance_scorer(zone_messages: list[dict], query: str) -> float:
    """Dependency-free lexical-overlap scorer: fraction of the query's
    (non-trivial) words that also appear somewhere in the zone. Good
    enough to prove the pruning logic works; swap in a real embedding
    similarity function in production.
    """
    query_words = _tokenize(query)
    if not query_words:
        return 0.0
    zone_text = " ".join(str(m.get("content", "")) for m in zone_messages)
    zone_words = _tokenize(zone_text)
    overlap = query_words & zone_words
    return len(overlap) / len(query_words)


def default_zone_key(message: dict) -> Optional[str]:
    """Default zone boundary: messages are grouped by their
    `metadata["zone"]` tag (e.g. a student id or topic label set by the
    agent/router as it tags messages). Messages with no zone tag each
    form their own single-message zone rather than being silently
    merged into a neighboring zone.
    """
    return message.get("metadata", {}).get("zone")


@dataclass
class Zone:
    key: Optional[str]
    messages: list[dict]
    relevance: float = 0.0
    pruned: bool = False

    def __len__(self) -> int:
        return len(self.messages)


@dataclass
class ZonePruningResult:
    zones: list[Zone]
    messages: list[dict]  # flattened, in original order, pruned zones excluded

    @property
    def kept_zone_count(self) -> int:
        return sum(1 for z in self.zones if not z.pruned)

    @property
    def pruned_zone_count(self) -> int:
        return sum(1 for z in self.zones if z.pruned)


class ZonePruner:
    """Groups messages into contiguous topical zones, scores each zone's
    relevance to the current query, and prunes low-relevance zones --
    except the most recent zone, which always stays (the agent should
    never lose track of what it was just doing, even mid-topic-shift).

    Args:
        threshold: zones scoring below this are pruned, unless they are
            the most recent zone or `always_keep_last` is False.
        always_keep_last: if True (default), the most recent zone is
            never pruned regardless of its score.
        zone_key_fn: `message -> zone key`. Consecutive messages with
            the same (non-None) key are grouped into one zone; a `None`
            key means "start a new single-message zone here" rather
            than merging into a neighbor. Defaults to `default_zone_key`
            (grouping by `metadata["zone"]`).
        relevance_scorer: `(zone_messages, query) -> score in [0, 1]`.
            Defaults to a dependency-free lexical-overlap stub (see
            `_default_relevance_scorer`); inject a real embedding-based
            scorer in production.
    """

    def __init__(
        self,
        threshold: float = 0.15,
        always_keep_last: bool = True,
        zone_key_fn: Optional[Callable[[dict], Optional[str]]] = None,
        relevance_scorer: Optional[RelevanceScorerFn] = None,
    ):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        self.threshold = threshold
        self.always_keep_last = always_keep_last
        self.zone_key_fn = zone_key_fn or default_zone_key
        self.relevance_scorer = relevance_scorer or _default_relevance_scorer

    def _group_into_zones(self, messages: Sequence[dict]) -> list[Zone]:
        zones: list[Zone] = []
        current_key: object = object()  # sentinel guaranteed to differ from any real key
        for msg in messages:
            key = self.zone_key_fn(msg)
            starts_new_zone = key is None or key != current_key or not zones
            if starts_new_zone:
                zones.append(Zone(key=key, messages=[msg]))
            else:
                zones[-1].messages.append(msg)
            current_key = key
        return zones

    def prune(self, messages: Sequence[dict], query: str) -> ZonePruningResult:
        """Scores each topical zone against `query` and prunes the ones
        below `threshold`. Never mutates `messages`.
        """
        zones = self._group_into_zones(messages)

        for zone in zones:
            zone.relevance = self.relevance_scorer(zone.messages, query)
            zone.pruned = zone.relevance < self.threshold

        if self.always_keep_last and zones:
            zones[-1].pruned = False

        flattened = [m for z in zones if not z.pruned for m in z.messages]
        return ZonePruningResult(zones=zones, messages=flattened)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ZonePruner(threshold={self.threshold}, always_keep_last={self.always_keep_last})"


if __name__ == "__main__":
    # Minimal runnable proof, same spirit as the other test_*.py scripts
    # in memory/ (no pytest required).
    sample = [
        {"role": "user", "content": "Is Ahmed eligible for the merit scholarship?",
         "metadata": {"zone": "ahmed_scholarship"}},
        {"role": "assistant", "content": "Checking Ahmed's GPA and attendance now.",
         "metadata": {"zone": "ahmed_scholarship"}},
        {"role": "tool", "content": "Ahmed: GPA 3.6, attendance 90%. Eligible.",
         "metadata": {"zone": "ahmed_scholarship"}},
        {"role": "assistant", "content": "Yes, Ahmed is eligible for the merit scholarship.",
         "metadata": {"zone": "ahmed_scholarship"}},

        {"role": "user", "content": "Can you register Sara for the Flutter track?",
         "metadata": {"zone": "sara_flutter_registration"}},
        {"role": "assistant", "content": "Registering Sara for the Flutter track now.",
         "metadata": {"zone": "sara_flutter_registration"}},
        {"role": "tool", "content": "Sara enrolled in Flutter track, cohort spring-2026.",
         "metadata": {"zone": "sara_flutter_registration"}},
        {"role": "assistant", "content": "Done -- Sara is registered in the spring-2026 Flutter cohort.",
         "metadata": {"zone": "sara_flutter_registration"}},

        {"role": "user", "content": "What was Ahmed's attendance percentage again?",
         "metadata": {"zone": "ahmed_attendance_followup"}},
        {"role": "assistant", "content": "Ahmed's attendance was 90 percent.",
         "metadata": {"zone": "ahmed_attendance_followup"}},
    ]

    pruner = ZonePruner(threshold=0.2)
    query = "remind me about Ahmed's scholarship eligibility"
    result = pruner.prune(sample, query)

    print(f"query: {query!r}")
    print(f"zones found: {len(result.zones)}")
    for z in result.zones:
        status = "PRUNED" if z.pruned else "kept  "
        print(f"  [{status}] zone={z.key!r:30s} relevance={z.relevance:.2f} messages={len(z)}")
    print(f"\nkept zones: {result.kept_zone_count}, pruned zones: {result.pruned_zone_count}")
    print(f"messages in final context: {len(result.messages)} / {len(sample)}")

    # The Sara/Flutter zone has zero lexical overlap with an Ahmed/
    # scholarship query and isn't the most recent zone -> must be pruned.
    sara_zone = next(z for z in result.zones if z.key == "sara_flutter_registration")
    assert sara_zone.pruned, "irrelevant middle zone should be pruned"

    # The Ahmed/scholarship zone is highly relevant -> must be kept.
    scholarship_zone = next(z for z in result.zones if z.key == "ahmed_scholarship")
    assert not scholarship_zone.pruned, "relevant zone should never be pruned"

    # The most recent zone (Ahmed attendance follow-up) is always kept,
    # even though its lexical overlap with THIS query is weaker than the
    # scholarship zone's.
    followup_zone = next(z for z in result.zones if z.key == "ahmed_attendance_followup")
    assert not followup_zone.pruned, "most recent zone must always survive pruning"

    # Original messages must be untouched.
    assert sample[4]["content"] == "Can you register Sara for the Flutter track?"

    print("\nAll zone_pruning.py checks passed.")