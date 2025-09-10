from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import tempfile
import os
import asyncio
from datetime import datetime

from app.database.base import get_db
from app.models.models import Format, Template, SourceFile, ProcessingJob, Field, ChangeLog
from app.schemas.schemas import (
    FormatSchema, FormatSummary, TemplateSchema, UploadResponse, 
    ProcessingJobSchema, ProcessingStatus, TemplateApprovalRequest,
    TemplateEditRequest, ValidationRequest, ValidationResult, ExportType
)
from app.core.security import verify_api_key
from app.storage.file_storage import file_storage
from app.parsers.parser_factory import parser_factory
from app.ai.template_generator import TemplateGenerator
import uuid

router = APIRouter(prefix="/api/v1/formats", tags=["formats"])


@router.post("/upload", response_model=UploadResponse)
async def upload_format_package(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    format_name: Optional[str] = Form(None),
    format_version: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Upload a documentation package (PDF + sample files)"""
    
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    # Create processing job
    job = ProcessingJob(
        status=ProcessingStatus.PENDING,
        progress=0.0
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Store uploaded files temporarily
    temp_files = []
    try:
        for file in files:
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}")
            content = await file.read()
            temp_file.write(content)
            temp_file.close()
            
            temp_files.append({
                "temp_path": temp_file.name,
                "original_filename": file.filename,
                "content_type": file.content_type
            })
        
        # Start background processing
        background_tasks.add_task(
            process_upload_package,
            job.id,
            temp_files,
            format_name,
            format_version,
            db
        )
        
        return UploadResponse(
            format_id="",  # Will be updated after processing
            detected_name=format_name or "Unknown",
            detected_version=format_version or "1.0",
            template_preview_id="",  # Will be updated after processing
            processing_status=ProcessingStatus.PENDING,
            job_id=job.id
        )
        
    except Exception as e:
        # Clean up temp files on error
        for temp_file in temp_files:
            try:
                os.unlink(temp_file["temp_path"])
            except:
                pass
        
        # Update job status
        job.status = ProcessingStatus.FAILED
        job.error_message = str(e)
        db.commit()
        
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


async def process_upload_package(
    job_id: str,
    temp_files: List[dict],
    format_name: Optional[str],
    format_version: Optional[str],
    db: Session
):
    """Background task to process uploaded package"""
    
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        return
    
    try:
        job.status = ProcessingStatus.PROCESSING
        job.started_at = datetime.utcnow()
        job.progress = 0.1
        db.commit()
        
        # Parse all files
        parsed_structures = []
        stored_files = []
        pdf_structure = None
        
        for i, temp_file in enumerate(temp_files):
            try:
                # Store file permanently
                file_info = file_storage.store_file(
                    temp_file["temp_path"],
                    temp_file["original_filename"]
                )
                stored_files.append(file_info)
                
                # Parse file
                parser = parser_factory.get_parser(
                    temp_file["temp_path"],
                    temp_file["content_type"] or ""
                )
                
                if parser:
                    structure = parser.parse(temp_file["temp_path"])
                    parsed_structures.append(structure)
                    
                    # Keep track of PDF structure separately
                    if structure.file_type == "pdf":
                        pdf_structure = structure
                
                # Update progress
                job.progress = 0.1 + (0.4 * (i + 1) / len(temp_files))
                db.commit()
                
            except Exception as e:
                print(f"Error parsing file {temp_file['original_filename']}: {e}")
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file["temp_path"])
                except:
                    pass
        
        # Extract format info from PDF or use provided values
        detected_name = format_name
        detected_version = format_version
        
        if pdf_structure and pdf_structure.metadata:
            detected_name = detected_name or pdf_structure.metadata.get("format_name", "Unknown Format")
            detected_version = detected_version or pdf_structure.metadata.get("format_version", "1.0")
        
        detected_name = detected_name or "Unknown Format"
        detected_version = detected_version or "1.0"
        
        job.progress = 0.6
        db.commit()
        
        # Create or get format
        format_obj = db.query(Format).filter(Format.name == detected_name).first()
        if not format_obj:
            format_obj = Format(
                name=detected_name,
                canonical_description=f"Format specification for {detected_name}"
            )
            db.add(format_obj)
            db.commit()
            db.refresh(format_obj)
        
        # Generate template using AI
        template_generator = TemplateGenerator()
        sample_structures = [s for s in parsed_structures if s.file_type != "pdf"]
        
        template_data = template_generator.generate_template(
            pdf_structure,
            sample_structures,
            detected_name,
            detected_version
        )
        
        job.progress = 0.8
        db.commit()
        
        # Create template record
        template = Template(
            format_id=format_obj.id,
            version=detected_version,
            status="draft",
            schema_json=template_data["schema_json"],
            template_metadata=template_data["metadata"]
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        
        # Create source file records
        for file_info in stored_files:
            source_file = SourceFile(
                template_id=template.id,
                filename=file_info["stored_filename"],
                original_filename=file_info["original_filename"],
                mime_type=file_info["mime_type"],
                file_size=file_info["file_size"],
                file_path=file_info["stored_path"],
                content_hash=file_info["content_hash"],
                file_type=parser_factory.get_parser(
                    file_info["stored_path"], 
                    file_info["mime_type"] or ""
                ).get_file_type() if parser_factory.get_parser(
                    file_info["stored_path"], 
                    file_info["mime_type"] or ""
                ) else "unknown"
            )
            db.add(source_file)
        
        # Create field records
        for field_data in template_data["fields"]:
            field = Field(
                template_id=template.id,
                canonical_name=field_data.canonical_name,
                source_names=field_data.source_names,
                data_type=field_data.data_type,
                cardinality=field_data.cardinality,
                enumerations=field_data.enumerations,
                examples=field_data.examples,
                description=field_data.description,
                confidence_score=field_data.confidence_score,
                provenance=[p.dict() for p in field_data.provenance],
                relationships=field_data.relationships,
                constraints=field_data.constraints
            )
            db.add(field)
        
        # Create change log
        change_log = ChangeLog(
            template_id=template.id,
            change_type="created",
            changes={"action": "template_created", "source_files": len(stored_files)},
            author="system"
        )
        db.add(change_log)
        
        # Complete job
        job.template_id = template.id
        job.status = ProcessingStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress = 1.0
        db.commit()
        
    except Exception as e:
        job.status = ProcessingStatus.FAILED
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        db.commit()


@router.get("", response_model=List[FormatSummary])
async def list_formats(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """List all known formats"""
    
    formats = db.query(Format).all()
    
    summaries = []
    for format_obj in formats:
        # Get latest template version
        latest_template = db.query(Template).filter(
            Template.format_id == format_obj.id
        ).order_by(Template.created_at.desc()).first()
        
        template_count = db.query(Template).filter(
            Template.format_id == format_obj.id
        ).count()
        
        summary = FormatSummary(
            id=format_obj.id,
            name=format_obj.name,
            canonical_description=format_obj.canonical_description,
            created_at=format_obj.created_at,
            latest_version=latest_template.version if latest_template else None,
            template_count=template_count
        )
        summaries.append(summary)
    
    return summaries


@router.get("/{format_id}", response_model=FormatSchema)
async def get_format(
    format_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get format details with all versions"""
    
    format_obj = db.query(Format).filter(Format.id == format_id).first()
    if not format_obj:
        raise HTTPException(status_code=404, detail="Format not found")
    
    return format_obj


@router.get("/{format_id}/templates", response_model=List[TemplateSchema])
async def list_format_templates(
    format_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """List all template versions for a format"""
    
    format_obj = db.query(Format).filter(Format.id == format_id).first()
    if not format_obj:
        raise HTTPException(status_code=404, detail="Format not found")
    
    templates = db.query(Template).filter(
        Template.format_id == format_id
    ).order_by(Template.created_at.desc()).all()
    
    return templates


@router.get("/jobs/{job_id}", response_model=ProcessingJobSchema)
async def get_processing_job(
    job_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get processing job status"""
    
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job