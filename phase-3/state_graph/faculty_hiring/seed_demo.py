"""
Faculty Hiring — demo seed script.

Creates one Job Posting and runs the REAL graph pipeline (ingest -> parse ->
score) on an initial batch of CVs, so the graph is left sitting at
`awaiting_more_applications` — ready to demo either:
  - a NEW CV arriving live (`add_cv(job_id, name, raw_cv_text)`), or
  - closing applications (`close_applications(job_id)`).

CV data itself is NOT hardcoded here — it's read from
data/demo_job.json and data/demo_candidates.json so the seed logic and the
seed data stay separate (see those files to edit/add demo candidates).

`later_arrivals` in demo_candidates.json (Youssef Mostafa) is intentionally
held back and NOT submitted here — that candidate exists so you (or the
platform, once built) can demonstrate the "new CV while waiting" event
against a job that's already mid-flow.

Run from phase-3/:
    ANTHROPIC_API_KEY=sk-... python -m state_graph.faculty_hiring.seed_demo
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from mcp_server import database as db
from state_graph.faculty_hiring.graph import start_job

DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_json(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def seed_one_job() -> int:
    job_data = _load_json("demo_job.json")
    candidates_data = _load_json("demo_candidates.json")

    row = db.query_one(
        """INSERT INTO JobPostings (title, qualifications, application_deadline, status)
           VALUES (?, ?, ?, 'open') RETURNING job_id""",
        (
            job_data["title"],
            json.dumps(job_data["qualifications"]),
            job_data.get("application_deadline"),
        ),
    )
    job_id = row["job_id"]

    print(f"[seed] Created JobPosting job_id={job_id} — {job_data['title']}")
    print(f"[seed] thread_id = faculty-hiring-{job_id}")
    print(f"[seed] Submitting initial batch through the real pipeline "
          f"(ingest -> parse -> score)...")

    result = start_job({
        "job_id": job_id,
        "job_title": job_data["title"],
        "qualifications": job_data["qualifications"],
        "initial_cvs": candidates_data["initial_batch"],
    })

    print(f"[seed] Graph status: {result.get('status')}")
    for c in result.get("candidates", []):
        print(f"         - {c['name']}: score={c.get('score')}, "
              f"parse_status={c.get('parse_status')}")

    held_back = [c["name"] for c in candidates_data.get("later_arrivals", [])]
    if held_back:
        print(f"[seed] Held back for a live 'new CV' demo: {', '.join(held_back)}")
        print(f"[seed]   -> add_cv({job_id}, name, raw_cv_text)")
    print(f"[seed]   -> close_applications({job_id})  # generates shortlist, pauses at HITL")

    return job_id


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    seed_one_job()
