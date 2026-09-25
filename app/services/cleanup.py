"""Reclaiming R2 storage. Every stored file should have exactly one material
row; anything else is paid-for space nobody can download.

Files go dead two ways. A material, lesson, module or course is deleted, and
reclaim() removes its files right after the delete commits. Or an upload is
never recorded, because the admin closed the tab between the PUT and the POST.
Nothing points at those, so only sweep() can find them.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta

from botocore.exceptions import BotoCoreError, ClientError
from sqlmodel import Session, select

from app.models import Material
from app.models.base import utcnow
from app.services.storage import MATERIAL_PREFIX, R2Client

log = logging.getLogger("oner.storage")


def reclaim(storage: R2Client, keys: Iterable[str]) -> None:
    """Delete the files of rows that are already gone. Never raises.

    A failure only leaves an orphan for the next sweep, so it must not turn an
    admin's successful delete into an error.
    """
    keys = list(keys)
    if not keys or not storage.configured:
        return
    try:
        refused = storage.delete_objects(keys)
    except (BotoCoreError, ClientError) as e:
        log.warning(
            "r2 delete of %d files failed, leaving them to the sweep: %s", len(keys), e
        )
        return
    if refused:
        log.warning("r2 refused to delete %s, leaving them to the sweep", refused)


@dataclass
class SweepResult:
    scanned: int
    orphans: list[str]
    deleted: int


def sweep(
    session: Session, storage: R2Client, *, grace: timedelta, dry_run: bool
) -> SweepResult:
    """Find files under materials/ that no row points at, and delete them unless
    this is a dry run.

    Only files older than `grace` count. A fresh upload has no row until the
    admin page records it, and must not be swept out from under it.
    """
    cutoff = utcnow() - grace
    known = set(session.exec(select(Material.storage_key)).all())

    scanned = 0
    orphans = []
    for key, modified in storage.list_objects(MATERIAL_PREFIX):
        scanned += 1
        if key not in known and modified < cutoff:
            orphans.append(key)

    deleted = 0
    if orphans and not dry_run:
        deleted = len(orphans) - len(storage.delete_objects(orphans))
    return SweepResult(scanned=scanned, orphans=orphans, deleted=deleted)
