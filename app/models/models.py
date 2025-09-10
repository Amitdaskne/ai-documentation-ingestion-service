from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base
from typing import Dict, List, Any
import uuid


class Format(Base):
    """Represents a document format (e.g., HL7, FHIR, etc.)"""
    __tablename__ = "formats"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    canonical_description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    templates = relationship("Template", back_populates="format", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Format(id={self.id}, name={self.name})>"


class Template(Base):
    """Represents a versioned template for a format"""
    __tablename__ = "templates"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    format_id = Column(String, ForeignKey("formats.id"), nullable=False)
    version = Column(String, nullable=False)
    status = Column(String, default="draft")  # draft, approved
    schema_json = Column(JSON)  # The main JSON Schema
    template_metadata = Column(JSON)  # Additional metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True))
    approved_by = Column(String)
    
    # Relationships
    format = relationship("Format", back_populates="templates")
    source_files = relationship("SourceFile", back_populates="template")
    fields = relationship("Field", back_populates="template", cascade="all, delete-orphan")
    change_logs = relationship("ChangeLog", back_populates="template", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Template(id={self.id}, format_id={self.format_id}, version={self.version})>"


class SourceFile(Base):
    """Represents an uploaded source file"""
    __tablename__ = "source_files"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, ForeignKey("templates.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    mime_type = Column(String)
    file_size = Column(Integer)
    file_path = Column(String, nullable=False)  # Path to stored file
    content_hash = Column(String)  # SHA256 hash
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    file_type = Column(String)  # pdf, csv, xml, json, excel, etc.
    
    # Relationships
    template = relationship("Template", back_populates="source_files")
    
    def __repr__(self):
        return f"<SourceFile(id={self.id}, filename={self.filename})>"


class Field(Base):
    """Represents a field in a template with provenance"""
    __tablename__ = "fields"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, ForeignKey("templates.id"), nullable=False)
    canonical_name = Column(String, nullable=False)
    source_names = Column(JSON)  # List of observed names from source files
    data_type = Column(String)  # string, integer, boolean, array, object, etc.
    cardinality = Column(String)  # single, multiple, optional
    enumerations = Column(JSON)  # List of allowed values
    examples = Column(JSON)  # List of example values
    description = Column(Text)
    confidence_score = Column(Float)
    provenance = Column(JSON)  # List of provenance records
    relationships = Column(JSON)  # Parent/child, foreign keys, etc.
    constraints = Column(JSON)  # Additional constraints
    
    # Relationships
    template = relationship("Template", back_populates="fields")
    
    def __repr__(self):
        return f"<Field(id={self.id}, canonical_name={self.canonical_name})>"


class ChangeLog(Base):
    """Tracks changes to templates"""
    __tablename__ = "change_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, ForeignKey("templates.id"), nullable=False)
    change_type = Column(String, nullable=False)  # created, updated, approved, edited
    changes = Column(JSON)  # Detailed change information
    author = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    template = relationship("Template", back_populates="change_logs")
    
    def __repr__(self):
        return f"<ChangeLog(id={self.id}, change_type={self.change_type})>"


class ProcessingJob(Base):
    """Tracks processing jobs for uploaded packages"""
    __tablename__ = "processing_jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, ForeignKey("templates.id"))
    status = Column(String, default="pending")  # pending, processing, completed, failed
    progress = Column(Float, default=0.0)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ProcessingJob(id={self.id}, status={self.status})>"