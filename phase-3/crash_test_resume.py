import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "mcp_server"))

import state_graph.academic_integrity.graph as g

result = g.resume_case(9500, update={
    "decisions": [{"decision_stage": "committee_review", "decided_by": "admin_crash_test",
                   "decision": "uphold", "notes": "resumed after simulated crash"}]
})
print("✅ resumed successfully. status:", result.get("status"))
print("paused at:", g.build_academic_integrity_graph().get_state(
    {"configurable": {"thread_id": g.thread_id_for_case(9500)}}
).next)