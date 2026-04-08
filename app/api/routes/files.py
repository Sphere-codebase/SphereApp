"""File access endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import policy
from app.core.security import get_current_user
from app.db.models import Claim, ClaimPDF, User
from app.db.session import get_db
from app.pdf.claim_pdf import generate_pdf_bytes
from app.services.claims.pdf import build_claim_pdf_data

router = APIRouter(prefix="/api/files", tags=["files"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
logger = logging.getLogger(__name__)


@router.get("/pdfs/{filename}")
def get_claim_pdf(
    filename: str,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> Response:
    safe_name = filename.rsplit("/", maxsplit=1)[-1]
    record = db.execute(select(ClaimPDF).where(ClaimPDF.storage_key == safe_name)).scalars().first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not found")

    claim = db.execute(select(Claim).where(Claim.id == record.claim_id)).scalars().first()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not found")
    if not policy.can(current_user, policy.Action.READ, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    try:
        claim_data = build_claim_pdf_data(db, claim)
        pdf_bytes = generate_pdf_bytes(claim_data)
    except Exception as exc:
        logger.exception("Failed to render PDF for claim %s storage_key=%s", claim.id, safe_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF unavailable",
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )
