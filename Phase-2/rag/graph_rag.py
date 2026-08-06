"""
Brightpeak Academy — Graph RAG (Bonus)
=======================================

Builds a lightweight knowledge graph from the policy corpus:

  Nodes: Policy, Threshold, Sanction, Process, Track, Role
  Edges: DEFINES, REQUIRES, TRIGGERS, APPLIES_TO, REFERENCES

Retrieval:
  1. Match query entities / keywords to nodes.
  2. Expand 1-hop neighbourhood.
  3. Collect the original passages attached to those nodes.
  4. Rank by a simple graph+text score.

This is genuinely applicable: Brightpeak policies have real entity
relationships (Attendance threshold → triggers warning → affects
Scholarship eligibility → recorded by Registrar). A flat vector search
does not model those links.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

RAG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(RAG_DIR))

from vector_db import VectorStore  # noqa: E402
from hybrid_rag import HybridRAG  # noqa: E402


@dataclass
class Node:
    node_id: str
    label: str
    node_type: str
    properties: dict = field(default_factory=dict)
    passage_ids: list[str] = field(default_factory=list)


@dataclass
class Edge:
    source: str
    target: str
    relation: str


class PolicyGraph:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.adj: dict[str, list[tuple[str, str]]] = defaultdict(list)  # node -> [(rel, neighbour)]

    def add_node(self, node_id: str, label: str, node_type: str, **props):
        if node_id not in self.nodes:
            self.nodes[node_id] = Node(node_id, label, node_type, props)
        else:
            self.nodes[node_id].properties.update(props)

    def add_edge(self, source: str, target: str, relation: str):
        self.edges.append(Edge(source, target, relation))
        self.adj[source].append((relation, target))
        self.adj[target].append((f"rev_{relation}", source))

    def attach_passage(self, node_id: str, passage_id: str):
        if node_id in self.nodes and passage_id not in self.nodes[node_id].passage_ids:
            self.nodes[node_id].passage_ids.append(passage_id)

    def neighbours(self, node_id: str, max_hops: int = 1) -> set[str]:
        seen = {node_id}
        frontier = {node_id}
        for _ in range(max_hops):
            nxt = set()
            for n in frontier:
                for _, nb in self.adj.get(n, []):
                    if nb not in seen:
                        seen.add(nb)
                        nxt.add(nb)
            frontier = nxt
        return seen


def build_brightpeak_graph(store: VectorStore) -> PolicyGraph:
    """Hand-crafted + heuristic graph over the known Brightpeak entities."""
    g = PolicyGraph()

    # Core threshold / policy nodes
    entities = [
        ("thr_attendance_75", "75% attendance floor", "Threshold"),
        ("thr_scholarship_90", ">90% grade average for scholarship entry", "Threshold"),
        ("thr_scholarship_88", "≥88% maintenance average", "Threshold"),
        ("thr_withdrawal_14", "14-day early withdrawal window", "Threshold"),
        ("thr_late_3days", "3-day late submission limit", "Threshold"),
        ("pol_attendance", "Attendance Policy", "Policy"),
        ("pol_scholarship", "Scholarship Policy", "Policy"),
        ("pol_integrity", "Academic Integrity Rules", "Policy"),
        ("pol_late", "Late Submission Policy", "Policy"),
        ("pol_withdrawal", "Course Withdrawal Policy", "Policy"),
        ("pol_exam", "Examination and Assessment Policy", "Policy"),
        ("proc_warning", "Attendance warning process", "Process"),
        ("proc_integrity_invest", "Integrity investigation process", "Process"),
        ("sanc_zero", "Zero on assignment", "Sanction"),
        ("sanc_probation", "Academic probation", "Sanction"),
        ("proto_4_2b", "Protocol 4.2b special exam arrangements", "Process"),
        ("role_registrar", "Registrar", "Role"),
        ("role_instructor", "Instructor", "Role"),
        ("role_committee", "Academic Integrity Committee", "Role"),
        ("track_ai", "AI & Machine Learning Track", "Track"),
        ("track_web", "Full-Stack Web Development Track", "Track"),
        ("track_data", "Data Engineering Track", "Track"),
    ]
    for nid, label, ntype in entities:
        g.add_node(nid, label, ntype)

    # Relationships
    relations = [
        ("pol_attendance", "thr_attendance_75", "DEFINES"),
        ("pol_attendance", "proc_warning", "TRIGGERS"),
        ("thr_attendance_75", "pol_exam", "REQUIRES"),
        ("pol_scholarship", "thr_scholarship_90", "DEFINES"),
        ("pol_scholarship", "thr_scholarship_88", "DEFINES"),
        ("thr_attendance_75", "pol_scholarship", "REFERENCES"),
        ("pol_integrity", "sanc_zero", "TRIGGERS"),
        ("pol_integrity", "sanc_probation", "TRIGGERS"),
        ("pol_integrity", "proc_integrity_invest", "DEFINES"),
        ("sanc_probation", "pol_scholarship", "REFERENCES"),
        ("pol_late", "thr_late_3days", "DEFINES"),
        ("pol_withdrawal", "thr_withdrawal_14", "DEFINES"),
        ("pol_exam", "proto_4_2b", "DEFINES"),
        ("proto_4_2b", "role_registrar", "APPLIES_TO"),
        ("proc_warning", "role_instructor", "APPLIES_TO"),
        ("proc_integrity_invest", "role_committee", "APPLIES_TO"),
    ]
    for s, t, r in relations:
        g.add_edge(s, t, r)

    # Attach passages by keyword matching
    keyword_map = {
        "thr_attendance_75": ["75%", "attendance"],
        "thr_scholarship_90": ["90%", "scholarship"],
        "thr_scholarship_88": ["88%"],
        "thr_withdrawal_14": ["14", "withdraw"],
        "thr_late_3days": ["3 days", "late submission"],
        "pol_attendance": ["attendance policy"],
        "pol_scholarship": ["scholarship"],
        "pol_integrity": ["plagiarism", "integrity", "cheating"],
        "pol_late": ["late submission", "10%"],
        "pol_withdrawal": ["withdrawal", "dropped"],
        "pol_exam": ["examination", "final assessment", "resit"],
        "proto_4_2b": ["4.2b", "special arrangement", "extra time"],
        "proc_warning": ["warning", "flag"],
        "sanc_zero": ["zero score", "zero on"],
        "sanc_probation": ["probation"],
        "track_ai": ["ai & machine", "machine learning track"],
        "track_web": ["full-stack", "web development"],
        "track_data": ["data engineering"],
    }

    for i, doc in enumerate(store.documents):
        doc_lower = doc.lower()
        pid = store.ids[i]
        for node_id, kws in keyword_map.items():
            if any(kw in doc_lower for kw in kws):
                g.attach_passage(node_id, pid)

    return g


class GraphRAG:
    def __init__(self, store: VectorStore | None = None, top_k: int = 4):
        self.store = store or VectorStore()
        self.top_k = top_k
        self.graph = build_brightpeak_graph(self.store)
        self.fallback = HybridRAG(store=self.store, top_k=top_k)

    def _match_nodes(self, query: str) -> list[str]:
        q = query.lower()
        matched = []
        for nid, node in self.graph.nodes.items():
            label_tokens = set(re.findall(r"[a-z0-9]+", node.label.lower()))
            query_tokens = set(re.findall(r"[a-z0-9]+", q))
            overlap = label_tokens & query_tokens - {"the", "a", "an", "of", "and", "for", "to", "in", "on"}
            if overlap:
                matched.append(nid)
        if "4.2b" in q or "special arrangement" in q or "extra time" in q or "documented need" in q:
            matched.extend(["proto_4_2b", "pol_exam"])
        if "attendance" in q:
            matched.extend(["thr_attendance_75", "pol_attendance"])
        if "scholarship" in q:
            matched.extend(["thr_scholarship_90", "thr_scholarship_88", "pol_scholarship"])
        if "integrity" in q or "plagiarism" in q or "cheating" in q:
            matched.extend(["pol_integrity", "sanc_zero", "sanc_probation"])
        if "withdraw" in q or "drop" in q:
            matched.extend(["pol_withdrawal", "thr_withdrawal_14"])
        if "late" in q and ("submit" in q or "assignment" in q or "penalty" in q):
            matched.extend(["pol_late", "thr_late_3days"])
        if "track" in q or "machine learning" in q:
            matched.extend(["track_ai", "track_web", "track_data"])
        return list(dict.fromkeys(matched))

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        k = top_k or self.top_k
        matched = self._match_nodes(query)
        passage_ids: set[str] = set()

        for nid in matched:
            expanded = self.graph.neighbours(nid, max_hops=1)
            for en in expanded:
                passage_ids.update(self.graph.nodes[en].passage_ids)

        if not passage_ids:
            # Fall back to hybrid if graph miss
            return self.fallback.retrieve(query, top_k=k, where=where)

        results = []
        for pid in passage_ids:
            if pid not in self.store._id_to_row:
                continue
            row = self.store._id_to_row[pid]
            meta = self.store.metadatas[row]
            if where and not self.store._matches_filter(meta, where):
                continue
            results.append(
                {
                    "id": pid,
                    "document": self.store.documents[row],
                    "metadata": meta,
                    "score": 0.8,  # graph-derived, high prior
                    "graph_matched": True,
                }
            )

        # Re-rank with hybrid scores if available
        hybrid_hits = {h["id"]: h["score"] for h in self.fallback.retrieve(query, top_k=20, where=where)}
        for r in results:
            if r["id"] in hybrid_hits:
                r["score"] = 0.5 * r["score"] + 0.5 * hybrid_hits[r["id"]]
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:k]

    def format_context(self, hits: list[dict]) -> str:
        if not hits:
            return "No relevant policy passages found."
        blocks = []
        for i, h in enumerate(hits, 1):
            meta = h.get("metadata", {})
            source = f"{meta.get('document_title', '?')} § {meta.get('section', '?')}"
            flag = " [graph]" if h.get("graph_matched") else ""
            blocks.append(f"[{i}] ({source}{flag})\n{h['document']}")
        return "\n\n".join(blocks)

    def answer_prompt(self, query: str, hits: list[dict]) -> str:
        context = self.format_context(hits)
        return (
            "You are the Brightpeak Academy academic assistant. "
            "Answer the user's question using ONLY the policy passages below. "
            "If the passages do not contain the answer, say so clearly. "
            "Cite the document title and section when possible.\n\n"
            f"Policy passages:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer:"
        )

    def run(self, query: str, where: dict | None = None) -> dict[str, Any]:
        hits = self.retrieve(query, where=where)
        return {
            "architecture": "graph_rag",
            "query": query,
            "hits": hits,
            "context": self.format_context(hits),
            "prompt": self.answer_prompt(query, hits),
            "matched_nodes": self._match_nodes(query),
        }


if __name__ == "__main__":
    from ingestion import ingest

    store = ingest(reset=False)
    rag = GraphRAG(store)
    result = rag.run("What does Protocol 4.2b allow for students with documented needs?")
    print("Matched nodes:", result["matched_nodes"])
    print(result["context"][:500])
