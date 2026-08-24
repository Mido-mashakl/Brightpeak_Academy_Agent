"""
core/notifications.py
======================
Lightweight in-process pub/sub used to push real-time events to connected
advisors over Server-Sent Events (SSE) — e.g. "a request just landed in
human_review and needs your decision."

Why in-process and not Redis/etc: main.py runs as a single
`uvicorn main:app` process (see its own docstring — one process, no worker
pool configured anywhere in this repo), so every request this backend ever
handles shares the same Python memory. A plain dict of asyncio.Queues is
enough; there is no second process/worker that could miss a publish(). If
this backend is ever run with multiple uvicorn workers, this module stops
being correct and would need to move to a shared broker — worth a comment,
not worth building now for a problem this deployment doesn't have.

Channels are just string keys. Today there's one: "advisor_requests" (all
advisors share one queue of certificate/scholarship requests — see
advisor_router.list_requests, which never filters by advisor_id, so a
single broadcast channel matches how the queue is actually modeled). The
shape here is generic on purpose so a future per-student channel (e.g.
"student:{id}") for the wait_for_student -> student notification direction
can reuse the same publish()/event_stream() without changes.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

_subscribers: dict[str, set[asyncio.Queue]] = {}

_KEEPALIVE_SECONDS = 15


def subscribe(channel: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(channel, set()).add(q)
    return q


def unsubscribe(channel: str, q: asyncio.Queue) -> None:
    _subscribers.get(channel, set()).discard(q)


def publish(channel: str, event: str, data: dict[str, Any]) -> None:
    """Fire-and-forget: fans `data` out to every queue currently subscribed
    to `channel`. Safe to call with zero subscribers (e.g. no advisor has
    the Requests page open right now) — the event is simply dropped, which
    is correct because the DB row (status='needs_review') is the durable
    source of truth; SSE only shortens how long it takes someone watching
    to notice it."""
    for q in list(_subscribers.get(channel, set())):
        q.put_nowait({"event": event, "data": data})


async def event_stream(channel: str) -> AsyncIterator[str]:
    """Async generator yielding SSE-formatted text. Sends a `: keepalive`
    comment line every 15s so idle connections don't get killed by a proxy
    or the browser's own idle timeout while nothing is happening."""
    q = subscribe(channel)
    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=_KEEPALIVE_SECONDS)
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        unsubscribe(channel, q)
