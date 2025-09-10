from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from app.database.base import get_db
from app.models.models import SourceFile
from app.core.security import verify_api_key
from app.storage.file_storage import file_storage

router = APIRouter(prefix="/api/v1/files", tags=["files"])


@router.get("/{file_id}")
async def download_file(
    file_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Download an original uploaded file"""
    
    source_file = db.query(SourceFile).filter(SourceFile.id == file_id).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not os.path.exists(source_file.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=source_file.file_path,
        filename=source_file.original_filename,
        media_type=source_file.mime_type
    )


@router.get("/{file_id}/info")
async def get_file_info(
    file_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get file information"""
    
    source_file = db.query(SourceFile).filter(SourceFile.id == file_id).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {
        "id": source_file.id,
        "original_filename": source_file.original_filename,
        "mime_type": source_file.mime_type,
        "file_size": source_file.file_size,
        "upload_date": source_file.upload_date,
        "file_type": source_file.file_type,
        "content_hash": source_file.content_hash
    }