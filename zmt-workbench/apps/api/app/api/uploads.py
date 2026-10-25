"""上传路由：multipart 本地直传 + COS 预签名直传。"""

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.video import AssetFileRead, UploadPresignRequest, UploadPresignResponse
from app.services.upload import presign_upload, save_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=AssetFileRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    lifecycle: str = Form("user-uploads"),
    project_id: int = Form(0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await save_upload(db, file, lifecycle, project_id)


@router.post("/presign", response_model=UploadPresignResponse)
async def presign(
    payload: UploadPresignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadPresignResponse:
    asset, upload_url = await presign_upload(
        db, payload.filename, payload.content_type, payload.lifecycle
    )
    return UploadPresignResponse(key=asset.key, upload_url=upload_url, asset_file_id=asset.id)
