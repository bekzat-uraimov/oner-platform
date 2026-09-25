"""Request/response shapes for the API. Kept separate from DB models so the wire
contract never accidentally leaks a column like password_hash.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, ClassVar, Generic, Literal, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.models.base import (
    CourseStatus,
    Currency,
    Gateway,
    MaterialType,
    PurchaseStatus,
    UserRole,
)


def _as_utc(value: datetime) -> datetime:
    # SQLite hands back naive datetimes; Postgres answers in the session's zone.
    # The wire always gets UTC with its offset, so a browser can't read it as
    # local time.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    created_at: UtcDatetime


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ---- catalog --------------------------------------------------------------
# Read models for the public catalog. Crucially, LessonPublic does NOT expose
# kinescope_video_id — the playable video id is handed out only after an
# entitlement check (Day 8), never in the browse response.


class MaterialPublic(BaseModel):
    """What a material is called, never where it's stored. The file itself comes
    from /materials/{id}/download, which checks ownership."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    type: MaterialType


class LessonPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    order: int
    description: str | None = None
    duration: int | None = None
    # Titles show to everyone as a preview, the way lesson titles do.
    materials: list[MaterialPublic] = []


class ModulePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    order: int
    description: str | None = None
    lessons: list[LessonPublic] = []


class CourseListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    description: str | None = None
    segment: str | None = None
    price: Decimal
    currency: Currency
    status: CourseStatus
    cover: str | None = None


class CourseDetail(CourseListItem):
    learning_outcomes: str | None = None
    requirements: str | None = None
    modules: list[ModulePublic] = []
    materials: list[MaterialPublic] = []  # course-wide, not tied to one lesson


# ---- entitlements / gated lesson ------------------------------------------


class LessonDetail(BaseModel):
    """Returned only to a user who owns the course (or an admin). Still no raw
    kinescope id — playback goes through the DRM token endpoint (Day 8). This
    just confirms access and whether a video is attached."""

    id: int
    module_id: int
    title: str
    order: int
    description: str | None = None
    duration: int | None = None
    video_available: bool
    materials: list[MaterialPublic] = []


class GrantRequest(BaseModel):
    user_id: int
    course_id: int


class EntitlementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    course_id: int
    granted_at: UtcDatetime
    source_purchase_id: int | None = None


# ---- checkout -------------------------------------------------------------


class CheckoutRequest(BaseModel):
    course_id: int


class CheckoutResponse(BaseModel):
    """What the frontend needs to send the buyer to FreedomPay's hosted page."""

    purchase_id: int
    payment_id: str
    redirect_url: str
    amount: Decimal
    currency: Currency
    status: PurchaseStatus


class MyPurchase(BaseModel):
    """A buyer's own order, for the page FreedomPay sends them back to. The
    redirect proves nothing; this is what the payment callback recorded."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    amount: Decimal
    currency: Currency
    status: PurchaseStatus
    created_at: UtcDatetime


# ---- video ----------------------------------------------------------------


class DrmTokenResponse(BaseModel):
    """Everything the player needs. The video id has been withheld from every
    catalog response up to this point — owning the course is what releases it."""

    video_id: str
    drm_auth_token: str
    expires_in: int


class DrmAuthRequest(BaseModel):
    """Kinescope's playback check. Fields are optional so a malformed body
    answers 400 on our terms rather than FastAPI's 422."""

    id: str | None = None
    token: str | None = None
    type: str | None = None
    ip: str | None = None
    user_agent: str | None = None


# ---- materials ------------------------------------------------------------


class MaterialDownload(BaseModel):
    """A short-lived link. Deliberately not stored anywhere — ask again when it
    expires rather than caching it."""

    id: int
    title: str
    type: MaterialType
    filename: str
    url: str
    expires_in: int


# ---- authoring (admin only) -----------------------------------------------
# Write shapes for the admin API. Update models are all-optional so a PATCH can
# carry one field; the router sends only what was actually set.

SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"

# Kinescope ids are opaque, so only the shape is checked: non-blank. A blank id
# reads as "has a video" to one route and "no video" to another.
VideoId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]


class PatchModel(BaseModel):
    """Base for PATCH bodies. Any field can be left out, but a field whose column
    can't be empty can't be sent as null either. Otherwise the null reaches the
    database and comes back as a 500."""

    not_null: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def reject_null_on_required(self):
        nulls = [
            name
            for name in self.not_null
            if name in self.model_fields_set and getattr(self, name) is None
        ]
        if nulls:
            raise ValueError(f"cannot be null: {', '.join(nulls)}")
        return self


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    # The slug is a public URL segment, so it's constrained here rather than
    # left to whatever the admin UI happens to send.
    slug: str = Field(pattern=SLUG_PATTERN, max_length=120)
    description: str | None = None
    learning_outcomes: str | None = None
    requirements: str | None = None
    segment: str | None = None
    price: Decimal = Field(default=Decimal("0"), ge=0)
    currency: Currency = Currency.KGS
    # New courses start hidden. Publishing is a deliberate second step.
    status: CourseStatus = CourseStatus.draft
    cover: str | None = None


class CourseUpdate(PatchModel):
    not_null = ("title", "slug", "price", "currency", "status")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, pattern=SLUG_PATTERN, max_length=120)
    description: str | None = None
    learning_outcomes: str | None = None
    requirements: str | None = None
    segment: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    currency: Currency | None = None
    status: CourseStatus | None = None
    cover: str | None = None


class ModuleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    order: int | None = Field(default=None, ge=0)  # None appends to the end


class ModuleUpdate(PatchModel):
    not_null = ("title", "order")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    order: int | None = Field(default=None, ge=0)


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    order: int | None = Field(default=None, ge=0)
    duration: int | None = Field(default=None, ge=0)
    kinescope_video_id: VideoId | None = None


class LessonUpdate(PatchModel):
    not_null = ("title", "order")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    order: int | None = Field(default=None, ge=0)
    duration: int | None = Field(default=None, ge=0)
    kinescope_video_id: VideoId | None = None  # null detaches the video


class LessonAdmin(BaseModel):
    """Unlike LessonPublic and LessonDetail, this one does show the video id —
    the author is the one person who needs to see what's attached."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    title: str
    order: int
    description: str | None = None
    duration: int | None = None
    kinescope_video_id: str | None = None
    pending_video_id: str | None = None  # an upload still processing


class ModuleAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    order: int
    description: str | None = None
    lessons: list[LessonAdmin] = []


class MaterialUploadRequest(BaseModel):
    """Only the filename — the server picks where the bytes actually land."""

    filename: str = Field(min_length=1, max_length=255)


class MaterialUploadTarget(BaseModel):
    storage_key: str
    url: str
    expires_in: int


class MaterialCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    storage_key: str
    type: MaterialType | None = None  # inferred from the key when omitted
    course_id: int | None = None
    lesson_id: int | None = None

    @model_validator(mode="after")
    def one_parent(self):
        # The model has always documented "a lesson OR a course (exactly one)";
        # nothing enforced it until now, and a material with neither is a row no
        # ownership rule can reach.
        if (self.course_id is None) == (self.lesson_id is None):
            raise ValueError("attach to exactly one of course_id or lesson_id")
        return self


class MaterialUpdate(PatchModel):
    """Title and type only.

    storage_key and the parent are fixed at creation: repointing a row would
    strand the uploaded object, and moving a material to another course would
    quietly hand it to a different set of owners.
    """

    not_null = ("title", "type")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    type: MaterialType | None = None


class MaterialAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    type: MaterialType
    storage_key: str
    course_id: int | None = None
    lesson_id: int | None = None


class LessonAdminWithMaterials(LessonAdmin):
    materials: list[MaterialAdmin] = []


class ModuleAdminWithMaterials(ModuleAdmin):
    lessons: list[LessonAdminWithMaterials] = []


class CourseAdmin(CourseListItem):
    learning_outcomes: str | None = None
    requirements: str | None = None
    modules: list[ModuleAdminWithMaterials] = []
    materials: list[MaterialAdmin] = []


class SweepReport(BaseModel):
    scanned: int
    orphan_count: int
    orphans: list[str]  # the first 100; orphan_count is the full number
    deleted: int
    applied: bool


# ---- accounts and payments (admin only) -----------------------------------

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """One page of search results. total counts every match, not just this page."""

    items: list[T]
    total: int


class UserAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: UtcDatetime


class UserUpdate(PatchModel):
    """What an admin can change on an account. The email stays its owner's, and
    any other field sent is a 422 rather than silently ignored."""

    model_config = ConfigDict(extra="forbid")
    not_null = ("role", "is_active", "password")

    role: UserRole | None = None
    is_active: bool | None = None
    # Replaces the password outright: support's only fix until email reset exists.
    password: str | None = Field(default=None, min_length=8, max_length=128)


class PurchaseAdmin(BaseModel):
    id: int
    user_id: int
    user_email: str
    course_id: int
    course_title: str
    gateway: Gateway
    gateway_txn_id: str | None = None
    amount: Decimal
    currency: Currency
    status: PurchaseStatus
    created_at: UtcDatetime
    refunded_at: UtcDatetime | None = None
    refunded_by: int | None = None  # admin user id
    refund_note: str | None = None


class RefundRequest(BaseModel):
    """A refund already made in FreedomPay's merchant cabinet."""

    model_config = ConfigDict(extra="forbid")

    # No default: keeping or removing the course has to be a decision.
    revoke_access: bool
    note: str | None = Field(default=None, max_length=500)


class OwnedCourseAdmin(BaseModel):
    course_id: int
    course_title: str
    granted_at: UtcDatetime
    source_purchase_id: int | None = None  # null for a manual grant


class UserAdminDetail(UserAdmin):
    owned_courses: list[OwnedCourseAdmin] = []
    purchases: list[PurchaseAdmin] = []


# ---- lesson video (admin only) --------------------------------------------


class VideoUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    filesize: int = Field(gt=0)  # Tus needs the length before the first byte


class VideoUploadTarget(BaseModel):
    """Give `endpoint` to tus-js-client. It takes no token."""

    video_id: str
    endpoint: str


class LessonVideo(BaseModel):
    video_id: str | None = None  # what students play right now
    pending_video_id: str | None = None
    # Kinescope's status for the pending upload: uploading, processing, error...
    # "done" means it was just swapped in; "missing" means Kinescope no longer
    # has it. None when nothing was pending.
    pending_status: str | None = None
    # The same thing for an upload widget. complete: video_id plays. failed: the
    # upload is dead; upload again or discard it. None: no video and no upload.
    state: Literal["in_progress", "complete", "failed"] | None = None
    duration: int | None = None


class KinescopeWebhookData(BaseModel):
    id: str | None = None
    status: str | None = None


class KinescopeWebhook(BaseModel):
    """Kinescope's status notification. Only the video id is used, to pick which
    lesson to re-check; the status itself is read back from the API."""

    event: str | None = None
    data: KinescopeWebhookData | None = None
