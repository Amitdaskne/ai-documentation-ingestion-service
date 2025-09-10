from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class TemplateStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FieldCardinality(str, Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"
    OPTIONAL = "optional"


class ProvenanceRecord(BaseModel):
    source_file_id: str
    source_type: str  # pdf, csv, xml, json, excel
    location: str  # page number, line number, xpath, etc.
    confidence: float
    evidence: str  # The actual text/data that provided evidence


class FieldSchema(BaseModel):
    id: str
    canonical_name: str
    source_names: List[str] = []
    data_type: str
    cardinality: FieldCardinality
    enumerations: List[str] = []
    examples: List[Any] = []
    description: Optional[str] = None
    confidence_score: float
    provenance: List[ProvenanceRecord] = []
    relationships: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}


class SourceFileSchema(BaseModel):
    id: str
    filename: str
    original_filename: str
    mime_type: Optional[str] = None
    file_size: int
    content_hash: str
    upload_date: datetime
    file_type: str

    class Config:
        from_attributes = True


class TemplateSchema(BaseModel):
    id: str
    format_id: str
    version: str
    status: TemplateStatus
    schema_json: Optional[Dict[str, Any]] = None
    template_metadata: Dict[str, Any] = {}
    created_at: datetime
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    source_files: List[SourceFileSchema] = []
    fields: List[FieldSchema] = []

    class Config:
        from_attributes = True


class FormatSchema(BaseModel):
    id: str
    name: str
    canonical_description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    templates: List[TemplateSchema] = []

    class Config:
        from_attributes = True


class FormatSummary(BaseModel):
    id: str
    name: str
    canonical_description: Optional[str] = None
    created_at: datetime
    latest_version: Optional[str] = None
    template_count: int


class UploadResponse(BaseModel):
    format_id: str
    detected_name: str
    detected_version: str
    template_preview_id: str
    processing_status: ProcessingStatus
    job_id: str


class ProcessingJobSchema(BaseModel):
    id: str
    template_id: Optional[str] = None
    status: ProcessingStatus
    progress: float
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateApprovalRequest(BaseModel):
    approved_by: Optional[str] = None
    notes: Optional[str] = None


class TemplateEditRequest(BaseModel):
    fields: List[FieldSchema]
    template_metadata: Dict[str, Any] = {}
    change_notes: Optional[str] = None
    author: Optional[str] = None


class ValidationRequest(BaseModel):
    template_id: str
    sample_data: Dict[str, Any]


class ValidationResult(BaseModel):
    valid: bool
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    field_validations: Dict[str, Dict[str, Any]] = {}


class ExportType(str, Enum):
    JSON_SCHEMA = "json_schema"
    XSD = "xsd"
    MAPPING_CSV = "mapping_csv"
    REPORT = "report"


class ChangeLogSchema(BaseModel):
    id: str
    change_type: str
    changes: Dict[str, Any]
    author: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True