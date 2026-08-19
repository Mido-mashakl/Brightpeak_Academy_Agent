"""
roles.py
========
Authentication, session state, and authorization for the Brightpeak
Academy MCP server.

Three responsibilities:
  1. authenticate()       — verify credentials and set SESSION.role
  2. SESSION              — module-level object that holds the current
                            session's role and instructor_id (one session
                            per process with stdio transport; each HTTP
                            request should reset SESSION at the start of
                            the tool call if you move to multi-tenant HTTP)
  3. can_grade_course()   — check whether the current session is allowed
                            to write grades / attendance for a given course

Passcodes are stored as bcrypt hashes.  To generate a new registrar
passcode hash run:
    python -c "import bcrypt; print(bcrypt.hashpw(b'your-passcode', bcrypt.gensalt()).decode())"
and put the result in REGISTRAR_PASSCODE_HASH below (or load it from an
environment variable / secrets manager in production).
"""

import os
from dataclasses import dataclass, field
from typing import Literal

import bcrypt

# ------------------------------------------------------------------
# Registrar passcode (hashed)
# ------------------------------------------------------------------
# Default is the bcrypt hash of "brightpeak2026" — change before prod.
# Override by setting the REGISTRAR_PASSCODE_HASH environment variable.

_DEFAULT_HASH = b"$2b$12$JQRb8ndLSPj2gRFx2iZm3O/05FbWfTudfylrXZOh1Rq6QVHjFrk9e"

REGISTRAR_PASSCODE_HASH: bytes = (
    os.environ.get("REGISTRAR_PASSCODE_HASH", "").encode()
    or _DEFAULT_HASH
)

# ------------------------------------------------------------------
# Dept Head passcode (hashed) — Faculty Hiring HITL reviewer role
# ------------------------------------------------------------------
# Default is the bcrypt hash of "brightpeak-depthead-2026" — change before prod.
# Override by setting the DEPT_HEAD_PASSCODE_HASH environment variable.
# Generate a new hash the same way as REGISTRAR_PASSCODE_HASH above.

_DEPT_HEAD_DEFAULT_HASH = b"$2b$12$Jz0cIIW4w3Q2XYC0PZXHNuTJtsYS.uIyR9AbkxBniszS15SHllQn2"

DEPT_HEAD_PASSCODE_HASH: bytes = (
    os.environ.get("DEPT_HEAD_PASSCODE_HASH", "").encode()
    or _DEPT_HEAD_DEFAULT_HASH
)


# ------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------

RoleType = Literal["guest", "instructor", "registrar", "dept_head"]


@dataclass
class _Session:
    """Holds authentication state for the current MCP session.

    Reset to guest at process start.  With stdio transport there is one
    process per client session, so this is safe.  For multi-tenant HTTP
    you would need per-request state (e.g. a context-var or a dict keyed
    by session ID).
    """

    role: RoleType = "guest"
    instructor_id: int | None = None

    def reset(self) -> None:
        """Drop back to unauthenticated guest state."""
        self.role = "guest"
        self.instructor_id = None


# Module-level singleton — imported as `roles.SESSION` everywhere.
SESSION = _Session()


# ------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------

def authenticate(
    role: str,
    instructor_id: int | None = None,
    passcode: str | None = None,
) -> tuple[bool, str]:
    """Verify credentials and, on success, update SESSION.

    Args:
        role:          'instructor' or 'registrar'.
        instructor_id: required when role == 'instructor'.
                       Must be a positive integer that exists in the DB.
        passcode:      required when role == 'registrar'.

    Returns:
        (success, message) — message is shown to the caller.
    """
    if role == "instructor":
        return _authenticate_instructor(instructor_id)
    if role == "registrar":
        return _authenticate_registrar(passcode)
    if role == "dept_head":
        return _authenticate_dept_head(passcode)
    return False, f"Unknown role '{role}'. Use 'instructor', 'registrar', or 'dept_head'."


def _authenticate_instructor(instructor_id: int | None) -> tuple[bool, str]:
    if instructor_id is None:
        return False, "instructor_id is required for the 'instructor' role."
    if not isinstance(instructor_id, int) or instructor_id <= 0:
        return False, "instructor_id must be a positive integer."

    # Verify the instructor exists in the database.
    import database as db  # local import to avoid circular dependency at module load

    instructor = db.get_instructor(instructor_id)
    if instructor is None:
        return False, f"No instructor with id {instructor_id}."

    SESSION.role = "instructor"
    SESSION.instructor_id = instructor_id
    return True, f"Authenticated as instructor '{instructor['name']}' (id {instructor_id})."


def _authenticate_registrar(passcode: str | None) -> tuple[bool, str]:
    if not passcode:
        return False, "passcode is required for the 'registrar' role."

    try:
        match = bcrypt.checkpw(passcode.encode(), REGISTRAR_PASSCODE_HASH)
    except Exception:
        match = False

    if not match:
        return False, "Incorrect passcode."

    SESSION.role = "registrar"
    SESSION.instructor_id = None
    return True, "Authenticated as registrar."


def _authenticate_dept_head(passcode: str | None) -> tuple[bool, str]:
    """Faculty Hiring HITL reviewer role. Same passcode pattern as registrar —
    no per-user identity, just a shared role passcode (matches how
    HiringDecisions.decided_by is recorded as a role label, not a username)."""
    if not passcode:
        return False, "passcode is required for the 'dept_head' role."

    try:
        match = bcrypt.checkpw(passcode.encode(), DEPT_HEAD_PASSCODE_HASH)
    except Exception:
        match = False

    if not match:
        return False, "Incorrect passcode."

    SESSION.role = "dept_head"
    SESSION.instructor_id = None
    return True, "Authenticated as dept_head."


# ------------------------------------------------------------------
# Authorization
# ------------------------------------------------------------------

def can_grade_course(course_id: int, course_instructor_id: int | None) -> bool:
    """Return True if the current session may write grades/attendance for
    this course.

    Rules:
      - registrar  → can touch any course.
      - instructor → can only touch courses they own
                     (their SESSION.instructor_id matches course_instructor_id).
      - guest      → never.

    Args:
        course_id:            the course being modified (used for logging /
                              future fine-grained rules; not checked here).
        course_instructor_id: the instructor_id stored on the course row.
    """
    if SESSION.role == "registrar":
        return True
    if SESSION.role == "instructor":
        return (
            SESSION.instructor_id is not None
            and SESSION.instructor_id == course_instructor_id
        )
    return False


def is_dept_head() -> bool:
    """Return True if the current session authenticated as dept_head.

    Used by the Faculty Hiring HITL surface (state_graph/faculty_hiring/hitl.py)
    to gate hire/interview/rescore decisions — the AI must never make the
    final hiring call, only an authenticated dept_head session may.
    """
    return SESSION.role == "dept_head"