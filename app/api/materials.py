"""Material downloads. Ownership is checked here; the link expires on its own."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import CurrentUser
from app.core.db import get_session
from app.schemas import MaterialDownload
from app.services.materials import AccessDenied, MaterialNotFound, download_url_for
from app.services.storage import R2Client, StorageNotConfigured, get_storage

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("/{material_id}/download", response_model=MaterialDownload)
def download_material(
    material_id: int,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[R2Client, Depends(get_storage)],
):
    try:
        material, filename, url = download_url_for(session, storage, user, material_id)
    except MaterialNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Material not found"
        )
    except AccessDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this course"
        )
    except StorageNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Downloads are unavailable",
        )

    return MaterialDownload(
        id=material.id,
        title=material.title,
        type=material.type,
        filename=filename,
        url=url,
        # Read from the signer, not from settings — the reported lifetime and
        # the signed one must be the same number.
        expires_in=storage.url_ttl_s,
    )
