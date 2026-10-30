
"""Cloudinary storage helpers for Smart AI Traffic Violation evidence."""

import os
import logging
from pathlib import Path

import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)

DEFAULT_FOLDER = "smart-ai-traffic/violations"
ALLOWED_FORMATS = {"jpg", "jpeg", "png", "webp"}


def _configure_cloudinary():
    """Configure Cloudinary using environment variables."""

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")

    missing = [
        name
        for name, value in (
            ("CLOUDINARY_CLOUD_NAME", cloud_name),
            ("CLOUDINARY_API_KEY", api_key),
            ("CLOUDINARY_API_SECRET", api_secret),
        )
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing Cloudinary environment variables: "
            + ", ".join(missing)
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )


def upload_evidence(
    file_path: str,
    folder: str = DEFAULT_FOLDER,
) -> dict:
    """
    Upload an evidence image to Cloudinary.

    Returns:
        {
            "url": secure image URL,
            "public_id": Cloudinary public ID
        }
    """

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Evidence image not found: {path}"
        )

    if path.suffix.lower().lstrip(".") not in ALLOWED_FORMATS:
        raise ValueError(
            "Unsupported image format. Use JPG, JPEG, PNG or WEBP."
        )

    _configure_cloudinary()

    result = cloudinary.uploader.upload(
        str(path),
        folder=folder,
        resource_type="image",
        overwrite=False,
        allowed_formats=sorted(ALLOWED_FORMATS),
    )

    url = result.get("secure_url")
    public_id = result.get("public_id")

    if not url or not public_id:
        raise RuntimeError(
            "Cloudinary upload did not return a URL and public ID."
        )

    logger.info("Evidence uploaded to Cloudinary: %s", public_id)

    return {
        "url": url,
        "public_id": public_id,
    }


def delete_evidence(
    public_id: str,
    resource_type: str = "image",
) -> dict:
    """
    Delete a Cloudinary asset using its public ID.

    A missing asset is treated as already deleted.
    Raises an exception if Cloudinary reports a failed deletion.
    """

    if not isinstance(public_id, str) or not public_id.strip():
        raise ValueError(
            "A valid Cloudinary public_id is required."
        )

    public_id = public_id.strip()

    if resource_type not in {"image", "video", "raw", "auto"}:
        raise ValueError(
            "resource_type must be image, video, raw or auto."
        )

    _configure_cloudinary()

    result = cloudinary.uploader.destroy(
        public_id,
        resource_type=resource_type,
        invalidate=True,
    )

    status = result.get("result")

    if status not in {"ok", "not found"}:
        logger.error(
            "Cloudinary deletion failed for %s: %s",
            public_id,
            result,
        )
        raise RuntimeError(
            f"Cloudinary deletion failed for {public_id!r}: {result}"
        )

    logger.info(
        "Cloudinary deletion result for %s: %s",
        public_id,
        status,
    )

    return result
