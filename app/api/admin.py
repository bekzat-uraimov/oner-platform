"""Admin-only operations. Everything here requires the admin role.

Two jobs. The manual grant exists so the first real sales (and tests) can hand
out access without a full payment flow — the same grant() the payment webhook
calls. The rest is authoring: the only way course content gets created, since
nothing in the public API writes to the catalog.
"""

import logging
from datetime import timedelta
from typing import Annotated

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.api.deps import AdminUser
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import Course, Lesson, Material, Module, User
from app.schemas import (
    CourseAdmin,
    CourseCreate,
    CourseUpdate,
    EntitlementRead,
    GrantRequest,
    LessonAdmin,
    LessonCreate,
    LessonUpdate,
    MaterialAdmin,
    MaterialCreate,
    MaterialUpdate,
    MaterialUploadRequest,
    MaterialUploadTarget,
    ModuleAdmin,
    ModuleCreate,
    ModuleUpdate,
    SweepReport,
)
from app.services.authoring import (
    BadStorageKey,
    CourseHasSales,
    KeyAlreadyRecorded,
    Removed,
    SlugTaken,
    create_course,
    create_lesson,
    create_material,
    create_module,
    delete_course,
    delete_lesson,
    delete_material,
    delete_module,
    update_course,
    update_lesson,
    update_material,
    update_module,
)
from app.services.cleanup import reclaim, sweep
from app.services.entitlements import grant, revoke
from app.services.kinescope import KinescopeClient, get_kinescope
from app.services.lesson_video import delete_videos
from app.services.storage import (
    R2Client,
    StorageNotConfigured,
    get_storage,
    new_storage_key,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[R2Client, Depends(get_storage)]
KinescopeDep = Annotated[KinescopeClient, Depends(get_kinescope)]


def _get(session: Session, model, obj_id: int, what: str):
    obj = session.get(model, obj_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found"
        )
    return obj


def _slug_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail="Slug already in use"
    )


def _clean_up_after(
    background: BackgroundTasks,
    storage: R2Client,
    kinescope: KinescopeClient,
    removed: Removed,
) -> None:
    # After the response: the rows are already gone, and R2 and Kinescope are
    # network calls the admin shouldn't wait on.
    background.add_task(reclaim, storage, removed.storage_keys)
    background.add_task(delete_videos, kinescope, removed.video_ids)


# ---- entitlements ---------------------------------------------------------


@router.post(
    "/entitlements",
    response_model=EntitlementRead,
    status_code=status.HTTP_201_CREATED,
)
def grant_entitlement(
    body: GrantRequest,
    _admin: AdminUser,
    session: SessionDep,
):
    """Manually grant a user access to a course. Idempotent — re-granting an
    existing entitlement returns it rather than erroring."""
    if session.get(User, body.user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if session.get(Course, body.course_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    return grant(session, body.user_id, body.course_id)


@router.delete("/entitlements", status_code=status.HTTP_204_NO_CONTENT)
def revoke_entitlement(
    user_id: int, course_id: int, admin: AdminUser, session: SessionDep
):
    """Take a course away: a manual grant, or access kept after a refund. The
    purchase history is left as it is."""
    if not revoke(session, user_id, course_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That user doesn't own that course",
        )
    log.info("admin %s revoked course %s from user %s", admin.id, course_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- courses --------------------------------------------------------------


@router.post("/courses", response_model=CourseAdmin, status_code=status.HTTP_201_CREATED)
def add_course(body: CourseCreate, _admin: AdminUser, session: SessionDep):
    try:
        return create_course(session, body.model_dump())
    except SlugTaken:
        raise _slug_conflict()


@router.get("/courses/{course_id}", response_model=CourseAdmin)
def read_course(course_id: int, _admin: AdminUser, session: SessionDep):
    """The full tree including video ids, which no public route exposes."""
    return _get(session, Course, course_id, "Course")


@router.patch("/courses/{course_id}", response_model=CourseAdmin)
def edit_course(
    course_id: int, body: CourseUpdate, admin: AdminUser, session: SessionDep
):
    course = _get(session, Course, course_id, "Course")
    try:
        return update_course(
            session,
            course,
            body.model_dump(exclude_unset=True),
            admin_id=admin.id,
        )
    except SlugTaken:
        raise _slug_conflict()


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_course(
    course_id: int,
    _admin: AdminUser,
    session: SessionDep,
    storage: StorageDep,
    kinescope: KinescopeDep,
    background: BackgroundTasks,
):
    course = _get(session, Course, course_id, "Course")
    try:
        removed = delete_course(session, course)
    except CourseHasSales:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course has been purchased; unpublish it instead",
        )
    _clean_up_after(background, storage, kinescope, removed)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- modules --------------------------------------------------------------


@router.post(
    "/courses/{course_id}/modules",
    response_model=ModuleAdmin,
    status_code=status.HTTP_201_CREATED,
)
def add_module(
    course_id: int, body: ModuleCreate, _admin: AdminUser, session: SessionDep
):
    course = _get(session, Course, course_id, "Course")
    return create_module(session, course, body.model_dump())


@router.patch("/modules/{module_id}", response_model=ModuleAdmin)
def edit_module(
    module_id: int, body: ModuleUpdate, _admin: AdminUser, session: SessionDep
):
    module = _get(session, Module, module_id, "Module")
    return update_module(session, module, body.model_dump(exclude_unset=True))


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_module(
    module_id: int,
    _admin: AdminUser,
    session: SessionDep,
    storage: StorageDep,
    kinescope: KinescopeDep,
    background: BackgroundTasks,
):
    removed = delete_module(session, _get(session, Module, module_id, "Module"))
    _clean_up_after(background, storage, kinescope, removed)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- lessons --------------------------------------------------------------


@router.post(
    "/modules/{module_id}/lessons",
    response_model=LessonAdmin,
    status_code=status.HTTP_201_CREATED,
)
def add_lesson(
    module_id: int, body: LessonCreate, _admin: AdminUser, session: SessionDep
):
    module = _get(session, Module, module_id, "Module")
    return create_lesson(session, module, body.model_dump())


@router.patch("/lessons/{lesson_id}", response_model=LessonAdmin)
def edit_lesson(
    lesson_id: int, body: LessonUpdate, _admin: AdminUser, session: SessionDep
):
    """Setting kinescope_video_id here links a video that already exists in
    Kinescope. Uploading a new one goes through /admin/lessons/{id}/video."""
    lesson = _get(session, Lesson, lesson_id, "Lesson")
    return update_lesson(session, lesson, body.model_dump(exclude_unset=True))


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_lesson(
    lesson_id: int,
    _admin: AdminUser,
    session: SessionDep,
    storage: StorageDep,
    kinescope: KinescopeDep,
    background: BackgroundTasks,
):
    removed = delete_lesson(session, _get(session, Lesson, lesson_id, "Lesson"))
    _clean_up_after(background, storage, kinescope, removed)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- materials ------------------------------------------------------------
# Two steps, because the file never passes through this API. We hand back a
# presigned PUT, the browser sends the bytes straight to R2, and then a second
# call records where they landed.


@router.post("/materials/upload-url", response_model=MaterialUploadTarget)
def create_upload_url(
    body: MaterialUploadRequest,
    _admin: AdminUser,
    storage: Annotated[R2Client, Depends(get_storage)],
):
    key = new_storage_key(body.filename)
    try:
        url = storage.upload_url(key)
    except StorageNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Uploads are unavailable",
        )
    return MaterialUploadTarget(
        storage_key=key, url=url, expires_in=storage.upload_ttl_s
    )


@router.post(
    "/materials", response_model=MaterialAdmin, status_code=status.HTTP_201_CREATED
)
def add_material(body: MaterialCreate, _admin: AdminUser, session: SessionDep):
    if body.course_id is not None:
        _get(session, Course, body.course_id, "Course")
    else:
        _get(session, Lesson, body.lesson_id, "Lesson")

    try:
        return create_material(session, body.model_dump())
    except BadStorageKey:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="storage_key must come from /admin/materials/upload-url",
        )
    except KeyAlreadyRecorded:
        # Two rows on one file would mean deleting either one deletes the other's.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That upload is already recorded as a material",
        )


@router.patch("/materials/{material_id}", response_model=MaterialAdmin)
def edit_material(
    material_id: int, body: MaterialUpdate, _admin: AdminUser, session: SessionDep
):
    material = _get(session, Material, material_id, "Material")
    return update_material(session, material, body.model_dump(exclude_unset=True))


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_material(
    material_id: int,
    _admin: AdminUser,
    session: SessionDep,
    storage: StorageDep,
    background: BackgroundTasks,
):
    removed = delete_material(session, _get(session, Material, material_id, "Material"))
    background.add_task(reclaim, storage, removed.storage_keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- storage --------------------------------------------------------------


@router.post("/storage/sweep", response_model=SweepReport)
def sweep_storage(
    admin: AdminUser,
    session: SessionDep,
    storage: StorageDep,
    settings: Annotated[Settings, Depends(get_settings)],
    apply: bool = False,
):
    """Find R2 files no material points at, and delete them only if apply=true.

    A dry run by default, so an admin page can show what would go before
    anything does.
    """
    try:
        result = sweep(
            session,
            storage,
            grace=timedelta(hours=settings.material_orphan_grace_h),
            dry_run=not apply,
        )
    except StorageNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage is unavailable",
        )
    except (BotoCoreError, ClientError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Storage did not respond"
        )

    log.info(
        "storage sweep by admin %s: %d scanned, %d orphaned, %d deleted",
        admin.id,
        result.scanned,
        len(result.orphans),
        result.deleted,
    )
    return SweepReport(
        scanned=result.scanned,
        orphan_count=len(result.orphans),
        orphans=result.orphans[:100],
        deleted=result.deleted,
        applied=apply,
    )
