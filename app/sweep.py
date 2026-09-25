"""Delete R2 files no material points at. Meant for a scheduled job such as a
daily Railway cron:

    uv run python -m app.sweep           # report only
    uv run python -m app.sweep --apply   # delete
"""

import sys
from datetime import timedelta

from sqlmodel import Session

from app.core.config import get_settings
from app.core.db import engine
from app.services.cleanup import sweep
from app.services.storage import get_storage


def main(argv: list[str]) -> None:
    apply = "--apply" in argv
    grace = timedelta(hours=get_settings().material_orphan_grace_h)
    with Session(engine) as session:
        result = sweep(session, get_storage(), grace=grace, dry_run=not apply)
    for key in result.orphans:
        print("orphan", key)
    print(
        f"{result.scanned} scanned, {len(result.orphans)} orphaned, "
        f"{result.deleted} deleted"
    )


if __name__ == "__main__":
    main(sys.argv[1:])
