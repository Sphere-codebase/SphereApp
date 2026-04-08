"""File access endpoints."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import policy
from app.core.security import get_current_user
from app.db.models import Claim, ClaimPDF, User
from app.db.session import get_db

router = APIRouter(prefix="/api/files", tags=["files"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]

PDF_STORAGE_DIR = os.path.join("var", "pdfs")


@router.get("/pdfs/{filename}")
def get_claim_pdf(
    filename: str,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> FileResponse:
    safe_name = os.path.basename(filename)
    record = db.execute(select(ClaimPDF).where(ClaimPDF.storage_key == safe_name)).scalars().first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not found")

    claim = db.execute(select(Claim).where(Claim.id == record.claim_id)).scalars().first()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not found")
    if not policy.can(current_user, policy.Action.READ, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    file_path = os.path.join(PDF_STORAGE_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not found")

    return FileResponse(
        file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )
