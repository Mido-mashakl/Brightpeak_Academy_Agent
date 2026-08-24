"""
routers/notifications_router.py
================================
REST endpoints for the student-facing durable notification store
(core/student_notifications.py).

Three simple endpoints:

  GET  /notifications          — page-load poll: return all unread for the
                                 current student. The frontend calls this on
                                 every chat/tracks page open so missed SSE
                                 events (student was offline) surface
                                 automatically.

  POST /notifications/{id}/read — mark one notification as read (student
                                   acted on / dismissed the card).

  POST /notifications/read-all  — dismiss everything at once (e.g. when
                                   the student opens the notification bell).

Only students can access their own notifications (role guard + student_id
from the auth header, never a query param the student can spoof).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.auth import require_role, CurrentUser
from core import student_notifications as sn

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def get_unread(user: CurrentUser = Depends(require_role("student"))):
    """Return all unread notifications for the logged-in student.
    Called on every page load — cheap (indexed by student_id + read=0).
    """
    return sn.get_unread(user.user_id)


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user: CurrentUser = Depends(require_role("student"))):
    updated = sn.mark_read(notification_id, user.user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"status": "ok"}


@router.post("/read-all")
def mark_all_read(user: CurrentUser = Depends(require_role("student"))):
    count = sn.mark_all_read(user.user_id)
    return {"status": "ok", "marked": count}
