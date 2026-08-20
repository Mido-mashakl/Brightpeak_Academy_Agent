"""
Faculty Hiring State Graph — Demo Script.

Demonstrates the full scenario from the design spec:

1.  Create job: Data Science Instructor
2.  Upload initial batch: Sara, Omar, Mariam
3.  Graph processes → awaiting_more_applications
4.  WHILE WAITING: upload Youssef (only Youssef is processed)
5.  Admin closes applications → generate_shortlist
6.  HITL: Dept Head review
7a. Hire path
7b. Interview path
7c. Re-score path (only selected candidates)

Run from phase-3/ directory:
    GEMINI_API_KEY=... python -m state_graph.faculty_hiring.demo_faculty_hiring

Crash-and-resume demo:
    Kill the process while waiting at awaiting_more_applications.
    Restart with the same job_id — the graph resumes from the checkpoint,
    no re-ingestion/re-parsing of Sara, Omar, Mariam.
"""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path

# Ensure phase-3 is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Load GEMINI_API_KEY / GEMINI_MODEL / etc. from phase-3/.env if present.
# Without this call, a .env file sitting on disk is never actually read —
# python does not load .env files automatically.
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from mcp_server import database as db
from mcp_server import roles
from state_graph.faculty_hiring.graph import (
    start_job, add_cv, close_applications, resume_job
)
from state_graph.faculty_hiring.hitl import (
    submit_hire_decision, submit_rescore_request, submit_interview_request
)

# Default seeded dept head (see db/seed.sql: DeptHeads) + default passcode
# (see mcp_server/roles.py: DEPT_HEAD_PASSCODE_HASH). Override via env vars
# if you changed either in your own copy of the DB.
DEMO_DEPT_HEAD_ID = int(os.environ.get("DEMO_DEPT_HEAD_ID", "1"))
DEMO_DEPT_HEAD_PASSCODE = os.environ.get("DEMO_DEPT_HEAD_PASSCODE", "brightpeak-depthead-2026")

# ---------------------------------------------------------------------------
# Demo candidates & job — loaded from data/, NOT hardcoded here and NOT
# hardcoded in documents/ (CVs are dynamic user data, never static RAG docs).
# See data/demo_job.json and data/demo_candidates.json to edit/add candidates.
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parent / "data"

with open(_DATA_DIR / "demo_job.json", encoding="utf-8") as _f:
    JOB_DATA = json.load(_f)

with open(_DATA_DIR / "demo_candidates.json", encoding="utf-8") as _f:
    CANDIDATES_DATA = json.load(_f)

INITIAL_BATCH = CANDIDATES_DATA["initial_batch"]  # Sara, Omar, Mariam
YOUSSEF = CANDIDATES_DATA["later_arrivals"][0]     # arrives while waiting
# NOTE: Mariam's CV intentionally omits experience/teaching fields — the
# system MUST NOT invent them (see documents/hiring/hiring_policies.md).


def run_demo():
    print("=" * 60)
    print("FACULTY HIRING DEMO — Brightpeak Academy")
    print("=" * 60)



    # ------------------------------------------------------------------
    # 1. Create the Job Posting in DB
    # ------------------------------------------------------------------
    print("\n[1] Creating Job Posting: Data Science Instructor")

    row = db.query_one(
        """INSERT INTO JobPostings (title, qualifications, application_deadline, status)
           VALUES (?, ?, ?, 'open') RETURNING job_id""",
        (
            JOB_DATA["title"],
            json.dumps(JOB_DATA["qualifications"]),
            JOB_DATA.get("application_deadline"),
        ),
    )
    job_id = row["job_id"]
    print(f"    Created job_id={job_id}, thread_id=faculty-hiring-{job_id}")

    # ------------------------------------------------------------------
    # 2. Submit initial batch
    # ------------------------------------------------------------------
    print("\n[2] Submitting initial batch: Sara, Omar, Mariam")

    result = start_job({
        "job_id": job_id,
        "job_title": JOB_DATA["title"],
        "qualifications": JOB_DATA["qualifications"],
        "initial_cvs": INITIAL_BATCH,
    })

    print(f"    Graph status: {result.get('status')}")
    print(f"    Candidates processed: {len(result.get('candidates', []))}")
    for c in result.get("candidates", []):
        print(f"      - {c.name}: score={c.score}, parse_status={c.parse_status}")

    # ------------------------------------------------------------------
    # 3. WHILE WAITING: upload Youssef
    # ------------------------------------------------------------------
    print("\n[3] Uploading NEW CV while graph is waiting: Youssef Mostafa")
    print("    (Sara/Omar/Mariam will NOT be reprocessed)")

    result2 = add_cv(job_id, YOUSSEF["name"], YOUSSEF["raw_cv_text"])

    print(f"    Graph status: {result2.get('status')}")
    print(f"    Total candidates: {len(result2.get('candidates', []))}")
    for c in result2.get("candidates", []):
        print(f"      - {c.name}: score={c.score}")

    # ------------------------------------------------------------------
    # 4. Admin closes applications
    # ------------------------------------------------------------------
    print("\n[4] Admin clicks 'Close Applications / Generate Shortlist'")

    result3 = close_applications(job_id)
    print(f"    Graph status: {result3.get('status')}")
    print(f"    Shortlist ID: {result3.get('current_shortlist_id')}")

    # Show shortlist from DB
    entries = []
    with db._conn() as conn:
        entries = conn.execute(
            """SELECT c.name, se.score, se.rank
               FROM ShortlistEntries se
               JOIN Candidates c ON se.candidate_id = c.candidate_id
               WHERE se.shortlist_id = ?
               ORDER BY se.rank""",
            (result3.get("current_shortlist_id"),),
        ).fetchall()

    print("\n    SHORTLIST:")
    for e in entries:
        print(f"      #{e['rank']}  {e['name']} — {e['score']:.1f}%")

    # ------------------------------------------------------------------
    # 5. HITL: Dept Head hires Sara (top candidate)
    # ------------------------------------------------------------------
    print("\n[5] Dept Head Review (HITL): hiring Sara Ahmed")

    ok, msg = roles.authenticate(
        role="dept_head",
        dept_head_id=DEMO_DEPT_HEAD_ID,
        passcode=DEMO_DEPT_HEAD_PASSCODE,
    )
    print(f"    {msg}")
    if not ok:
        print("    ERROR: could not authenticate as dept_head — aborting HITL step.")
        return

    sara_row = db.query_one(
        "SELECT candidate_id FROM Candidates WHERE name = ? AND job_id = ?",
        ("Sara Ahmed", job_id),
    )
    sara_id = sara_row["candidate_id"] if sara_row else None

    final = submit_hire_decision(
        job_id=job_id,
        candidate_id=sara_id,
        notes="Strong match across all qualifications.",
    )
    print(f"    Final status: {final.get('status')}")
    decisions = final.get('hitl_decisions', [])
    print(f"    Decided by: {decisions[-1].decided_by if decisions else 'N/A'}")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nTo demo crash-and-resume:")
    print(f"  Kill this process while waiting, then run:")
    print(f"  resume_job({job_id})  # resumes from last checkpoint")
    print("\nTo demo re-score (after authenticating as dept_head):")
    print(f"  submit_rescore_request(job_id={job_id},")
    print(f"      candidate_ids=[<id>], reason='...')")


if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)
    run_demo()