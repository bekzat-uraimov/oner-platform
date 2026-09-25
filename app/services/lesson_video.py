"""A lesson's video, from upload to playable to deleted.

A lesson holds at most two videos. kinescope_video_id is what students play.
pending_video_id is an upload still processing, and it takes over only once
Kinescope says it's done, so replacing a video never leaves a lesson dark.

Kinescope deletes happen after the database change commits, and only for videos
no lesson still plays or waits on: one video can sit in several courses.
"""

import logging
from collections.abc import Iterable

import httpx
from sqlmodel import Session, or_, select

from app.models import Lesson
from app.services.kinescope import DONE, KinescopeClient, KinescopeError, UploadLink

log = logging.getLogger("oner.video")

# Reported when Kinescope no longer has the pending upload, e.g. someone deleted
# it in their dashboard. The admin can discard it and upload again.
MISSING = "missing"

# What an upload widget shows, boiled down from Kinescope's eight statuses.
IN_PROGRESS = "in_progress"
COMPLETE = "complete"
FAILED = "failed"

# Statuses an upload never recovers from on its own. Anything else counts as in
# progress, so a status Kinescope adds later shows a spinner rather than an error.
_DEAD = {"error", "aborted", "suspended", MISSING}


class NoPendingUpload(Exception):
    """There's no upload in progress to discard."""


def unused_videos(session: Session, video_ids: Iterable[str | None]) -> list[str]:
    """The ids no lesson still plays or waits on. Call after the change that
    dropped them has committed."""
    unused = []
    for video_id in dict.fromkeys(v for v in video_ids if v):
        in_use = session.exec(
            select(Lesson.id).where(
                or_(
                    Lesson.kinescope_video_id == video_id,
                    Lesson.pending_video_id == video_id,
                )
            )
        ).first()
        if in_use is None:
            unused.append(video_id)
    return unused


def start_upload(
    session: Session,
    kinescope: KinescopeClient,
    lesson: Lesson,
    *,
    filename: str,
    filesize: int,
) -> tuple[UploadLink, list[str]]:
    """Reserve a Kinescope video for the lesson and return its upload link, plus
    any videos that became unused.

    Starting again before the last upload finished replaces that upload.
    """
    link = kinescope.create_upload(title=lesson.title, filename=filename, filesize=filesize)
    abandoned = lesson.pending_video_id
    lesson.pending_video_id = link.video_id
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return link, unused_videos(session, [abandoned])


def refresh(
    session: Session, kinescope: KinescopeClient, lesson: Lesson
) -> tuple[str | None, list[str]]:
    """Check on the pending upload and swap it in once Kinescope is done.

    Returns the upload's status (None when nothing is pending) and any videos
    the swap left unused. The status is always read from Kinescope's API, never
    taken from a webhook payload, which nobody signs.
    """
    if lesson.pending_video_id is None:
        return None, []
    state = kinescope.video_state(lesson.pending_video_id)
    if state is None:
        return MISSING, []
    if state.status != DONE:
        return state.status, []

    replaced = lesson.kinescope_video_id
    lesson.kinescope_video_id = lesson.pending_video_id
    lesson.pending_video_id = None
    if state.duration:
        lesson.duration = round(state.duration)
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return DONE, unused_videos(session, [replaced])


def upload_state(lesson: Lesson, pending_status: str | None) -> str | None:
    """in_progress, complete or failed; None for a lesson with no video at all.

    Takes the status refresh() returned, so a finished upload has already been
    swapped in and reads as complete. A failed upload leaves the old video
    playing until the admin uploads again or discards it.
    """
    if lesson.pending_video_id is None:
        return COMPLETE if lesson.kinescope_video_id else None
    return FAILED if pending_status in _DEAD else IN_PROGRESS


def discard_upload(session: Session, lesson: Lesson) -> list[str]:
    if lesson.pending_video_id is None:
        raise NoPendingUpload(f"lesson {lesson.id}")
    discarded = lesson.pending_video_id
    lesson.pending_video_id = None
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return unused_videos(session, [discarded])


def delete_videos(kinescope: KinescopeClient, video_ids: Iterable[str]) -> None:
    """Delete videos from Kinescope. Never raises: a failure leaves a video that
    costs storage but breaks nothing, and it must not fail an admin's request."""
    if not kinescope.configured:
        return
    for video_id in video_ids:
        try:
            kinescope.delete_video(video_id)
        except (KinescopeError, httpx.HTTPError) as e:
            log.warning("kinescope delete of %s failed: %s", video_id, e)
