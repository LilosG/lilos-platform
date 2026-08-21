"""Short-lived, signed media proxy used by external providers.

This route is intentionally unauthenticated: Google Business Profile fetches
media server-to-server and cannot present a LILOs user session. Access is
instead authorized by an expiring HMAC-signed token that contains the Drive
file identity and purpose.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from apps.api.app.config import Settings
from apps.api.app.integrations.google_drive_media import GoogleDriveMediaService
from apps.api.app.routes.health import settings_from_request

router = APIRouter(prefix="/api/v1/provider-media", tags=["provider-media"])
service = GoogleDriveMediaService()


@router.get("/google-drive/{token}", include_in_schema=False)
async def google_drive_media(
    token: str,
    settings: Annotated[Settings, Depends(settings_from_request)],
) -> Response:
    try:
        content, mime_type = await service.fetch_image(settings, token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider media is unavailable",
        ) from exc
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Cache-Control": "public, max-age=3600, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
