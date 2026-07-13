import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..deps import get_current_user, require_db
from ..models import Attachment, User
from ..schemas import AttachmentOut
from ..services import cloudstore
from ..services.vision import describe_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["uploads"])


@router.post("/uploads", response_model=AttachmentOut)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(require_db),
    user: User = Depends(get_current_user),
):
    """Upload a chat attachment to Cloudinary. The file is captioned with Gemini
    vision (so the companion can 'see' it) and purged from Cloudinary after
    attachment_ttl_days by the nightly maintenance job."""
    settings = get_settings()
    if not cloudstore.is_configured():
        raise HTTPException(503, "File uploads are not configured (Cloudinary credentials missing).")

    data = await file.read()
    if not data:
        raise HTTPException(422, "The file is empty.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is too large (max {settings.max_upload_mb} MB).")

    mime = file.content_type or "application/octet-stream"
    resource_type = cloudstore.resource_type_for(mime)
    try:
        result = await cloudstore.upload(data, user.id, resource_type)
    except Exception:
        logger.exception("Cloudinary upload failed.")
        raise HTTPException(502, "Upload to storage failed — please try again.")

    caption = await describe_file(data, mime)

    att = Attachment(
        user_id=user.id,
        url=result["secure_url"],
        public_id=result["public_id"],
        resource_type=result.get("resource_type", resource_type),
        filename=(file.filename or "file")[:255],
        mime_type=mime[:100],
        caption=caption,
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    return att
