"""Thin async wrapper around the (synchronous) Cloudinary SDK.

Files live under lifeos/<user_id>/ and are purged by the nightly maintenance job
once they are older than attachment_ttl_days.
"""

import asyncio

import cloudinary
import cloudinary.uploader

from ..config import get_settings

_configured = False


def is_configured() -> bool:
    s = get_settings()
    return bool(s.cloudinary_cloud_name and s.cloudinary_api_key and s.cloudinary_api_secret)


def _ensure_config() -> None:
    global _configured
    if _configured:
        return
    s = get_settings()
    cloudinary.config(
        cloud_name=s.cloudinary_cloud_name,
        api_key=s.cloudinary_api_key,
        api_secret=s.cloudinary_api_secret,
        secure=True,
    )
    _configured = True


def resource_type_for(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith(("video/", "audio/")):
        return "video"
    return "raw"


async def upload(data: bytes, user_id: int, resource_type: str) -> dict:
    _ensure_config()
    return await asyncio.to_thread(
        cloudinary.uploader.upload,
        data,
        folder=f"lifeos/{user_id}",
        resource_type=resource_type,
    )


async def destroy(public_id: str, resource_type: str) -> None:
    _ensure_config()
    await asyncio.to_thread(
        cloudinary.uploader.destroy,
        public_id,
        resource_type=resource_type,
        invalidate=True,
    )
