"""
core/auth.py
============
FastAPI-level identity check for the platform's authenticated roles
(student, instructor, dept_head, advisor). Every router in
phase-4/backend/routers imports `require_role` / `CurrentUser` from
here — this file was missing, which meant the FastAPI app could not
even start. This closes that gap.

How identity gets here
-----------------------
Login itself happens against the real DB in the Express process
(phase-4/backend/server.js -> POST /api/login), which looks the email
up across Instructors / DeptHeads / Advisors / Students and returns
`{ id, name, email, role, ... }`. The frontend stores that object
(shared/auth.js, localStorage "user") and is the ONLY place that
knows who's logged in — there is no server-side session shared
between the Express process (port 3000) and this FastAPI process
(port 8000), the two were never bridged (see main.py's comment).

So every authenticated request to this API must carry the logged-in
user's identity explicitly. We use two plain headers set by the
frontend's shared API client from the stored user object:

    X-User-Id:   the numeric id from localStorage "user" (student_id /
                 instructor_id / dept_head_id / advisor_id depending on role)
    X-User-Role: "student" | "instructor" | "dept_head" | "advisor"

This dependency does NOT just trust those headers — it re-verifies
the id actually exists in the matching role table on every request,
the same "real identity, not a bare claim" pattern hiring_router.py's
dept_head passcode gate already uses. It is intentionally not a
cryptographic session/token scheme (no such mechanism exists anywhere
else in this codebase to hook into); that is a real gap worth calling
out in the final report, not something to silently paper over.

Faculty Hiring's decision endpoint additionally layers phase-3's own
passcode-based mcp_server.roles gate on top of this — that is a second,
stricter check specific to that one endpoint and is unaffected by this
file.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException

import mcp_server.database as db

ROLE_TABLE_LOOKUP = {
    "student": ("Students", "student_id"),
    "instructor": ("Instructors", "instructor_id"),
    "dept_head": ("DeptHeads", "dept_head_id"),
    "advisor": ("Advisors", "advisor_id"),
}


@dataclass
class CurrentUser:
    user_id: int
    role: str
    name: str
    email: str | None = None


def _load_user(role: str, user_id: int) -> CurrentUser:
    table, id_col = ROLE_TABLE_LOOKUP[role]
    row = db.query_one(f"SELECT * FROM {table} WHERE {id_col} = ?", (user_id,))
    if row is None:
        raise HTTPException(
            status_code=401,
            detail=f"No {role} with id {user_id}. Log in again.",
        )
    return CurrentUser(user_id=user_id, role=role, name=row.get("name"), email=row.get("email"))


def verify_user_query(role: str, user_id: int, allowed_roles: tuple[str, ...]) -> CurrentUser:
    """Same identity check as require_role's dependency, but for endpoints
    that can't rely on the X-User-Id/X-User-Role headers — specifically
    Server-Sent Events. Browsers' EventSource API cannot set custom request
    headers, so the SSE endpoint (advisor_router.py's
    /advisor/notifications/stream) takes user_id/role as query params
    instead and verifies them through this same _load_user() lookup rather
    than trusting them as a bare claim.

    This is strictly weaker than the header scheme (a URL is more likely to
    end up in logs/browser history than a header), which is an acceptable
    trade for a read-only, no-PII notification stream in a codebase that
    doesn't have a token/session scheme to begin with (see this file's
    module docstring) — but it's worth keeping this path away from any
    endpoint that returns or accepts sensitive data.
    """
    if role not in ROLE_TABLE_LOOKUP:
        raise HTTPException(status_code=401, detail=f"Unknown role '{role}'.")
    user = _load_user(role, user_id)
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{user.role}' is not permitted here. Requires one of {list(allowed_roles)}.",
        )
    return user


def require_role(*allowed_roles: str):
    """FastAPI dependency factory. Usage:

        user: CurrentUser = Depends(require_role("student", "advisor"))

    Reads X-User-Id / X-User-Role headers, verifies the id is real in
    the corresponding role table, then checks the role is one of
    `allowed_roles`. Raises 401 if the caller isn't identifiable at
    all, 403 if they're a real, identifiable user but the wrong role.
    """

    def dependency(
        x_user_id: str | None = Header(default=None),
        x_user_role: str | None = Header(default=None),
    ) -> CurrentUser:
        if not x_user_id or not x_user_role:
            raise HTTPException(
                status_code=401,
                detail="Missing X-User-Id / X-User-Role headers. Log in first.",
            )
        if x_user_role not in ROLE_TABLE_LOOKUP:
            raise HTTPException(status_code=401, detail=f"Unknown role '{x_user_role}'.")
        try:
            user_id_int = int(x_user_id)
        except ValueError:
            raise HTTPException(status_code=401, detail="X-User-Id must be numeric.")

        user = _load_user(x_user_role, user_id_int)

        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' is not permitted here. Requires one of {list(allowed_roles)}.",
            )
        return user

    return dependency