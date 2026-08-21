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

from routers.hiring_router import router as hiring_router

app = FastAPI(title="Brightpeak Academy Platform")

app.include_router(hiring_router)


@app.get("/health")
def health():
    """Quick check that the server is up and phase-3 imported successfully."""
    return {"status": "ok"}