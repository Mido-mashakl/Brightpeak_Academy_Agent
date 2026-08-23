"""
main.py
=======
phase-4 backend entry point. Run from inside phase-4/backend/:

    cd phase-4/backend
    pip install -r ../../phase-3/requirements.txt fastapi uvicorn
    uvicorn main:app --reload

Then open http://127.0.0.1:8000/docs to see and test the endpoints
(FastAPI builds this page for you automatically — that's the fastest
way to check everything is wired correctly before touching the frontend).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.hiring_router import router as hiring_router
from routers.academic_integrity_router import router as academic_integrity_router
from routers.advisor_router import router as advisor_router
from routers.assessment_router import router as assessment_router
from routers.tracks_router import router as tracks_router
from routers.teaching_router import router as teaching_router
from routers.ai_assistant_router import router as ai_assistant_router

app = FastAPI(title="Brightpeak Academy Platform")

# The frontend is served by the Express process (port 3000, see
# phase-4/backend/server.js's static middleware) and calls this FastAPI
# process (port 8000) directly for every graph-backed feature (same
# pattern hiring already established — see department-head-api.js's
# own comment: "the two backends aren't bridged yet"). CORS must allow
# that cross-origin call.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hiring_router)
app.include_router(academic_integrity_router)
app.include_router(advisor_router)
app.include_router(assessment_router)
app.include_router(tracks_router)
app.include_router(teaching_router)
app.include_router(ai_assistant_router)


@app.get("/health")
def health():
    """Quick check that the server is up and phase-3 imported successfully."""
    return {"status": "ok"}