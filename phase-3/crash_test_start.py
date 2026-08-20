import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "mcp_server"))

import mcp_server.database as db
import state_graph.academic_integrity.graph as g

db.execute(
    "INSERT OR IGNORE INTO Students (student_id,name,email,level) VALUES (?,?,?,?)",
    (9998, "Crash Test Student", "crash-test@brightpeak.test", "Beginner"),
)
db.execute(
    "INSERT OR IGNORE INTO Courses (course_id,title,category,duration) VALUES (?,?,?,?)",
    (9998, "Crash Test Course", "test", 10),
)
db.execute(
    "INSERT OR IGNORE INTO Instructors (instructor_id,name,email) VALUES (?,?,?)",
    (9998, "Crash Test Instructor", "instructor-crash@brightpeak.test"),
)
db.execute(
    """INSERT OR IGNORE INTO IntegrityCases
       (case_id, student_id, course_id, reported_by, description, similarity_score)
       VALUES (?,?,?,?,?,?)""",
    (9500, 9998, 9998, 9998, "crash recovery test", 0.9),
)

g.start_case({
    "case_id": 9500, "student_id": 9998, "course_id": 9998,
    "reported_by": 9998, "description": "crash recovery test", "similarity_score": 0.9,
})
print("✅ started and paused at needs_committee_review.")
print("Now CLOSE this whole terminal window (not just Ctrl+C) to simulate a real crash.")