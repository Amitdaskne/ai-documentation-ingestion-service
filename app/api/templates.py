from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
import json
import tempfile
import os
from datetime import datetime

from app.database.base import get_db
from app.models.models import Template, Field, ChangeLog, SourceFile
from app.schemas.schemas import (
    TemplateSchema, TemplateApprovalRequest, TemplateEditRequest,
    ValidationRequest, ValidationResult, ExportType, ChangeLogSchema
)
from app.core.security import verify_api_key
from app.storage.file_storage import file_storage

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("/{template_id}", response_model=TemplateSchema)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get full template details"""
    
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template


@router.post("/{template_id}/approve")
async def approve_template(
    template_id: str,
    approval_request: TemplateApprovalRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Mark a template as approved"""
    
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if template.status == "approved":
        raise HTTPException(status_code=400, detail="Template is already approved")
    
    # Update template
    template.status = "approved"
    template.approved_at = datetime.utcnow()
    template.approved_by = approval_request.approved_by
    
    # Create change log
    change_log = ChangeLog(
        template_id=template.id,
        change_type="approved",
        changes={
            "action": "template_approved",
            "approved_by": approval_request.approved_by,
            "notes": approval_request.notes
        },
        author=approval_request.approved_by or "system"
    )
    db.add(change_log)
    
    db.commit()
    
    return {"message": "Template approved successfully"}


@router.post("/{template_id}/edit")
async def edit_template(
    template_id: str,
    edit_request: TemplateEditRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Accept manual edits to a template"""
    
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create new version of the template
    new_template = Template(
        format_id=template.format_id,
        version=f"{template.version}.1",  # Increment version
        status="draft",
        schema_json=template.schema_json,  # Will be updated below
        template_metadata={**template.template_metadata, **edit_request.template_metadata}
    )
    db.add(new_template)
    db.flush()  # Get the ID
    
    # Update fields
    db.query(Field).filter(Field.template_id == template.id).delete()
    
    for field_data in edit_request.fields:
        field = Field(
            template_id=new_template.id,
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
    
    # Regenerate JSON Schema
    new_template.schema_json = _generate_json_schema_from_fields(edit_request.fields)
    
    # Create change log
    change_log = ChangeLog(
        template_id=new_template.id,
        change_type="edited",
        changes={
            "action": "template_edited",
            "previous_template_id": template.id,
            "field_count": len(edit_request.fields),
            "notes": edit_request.change_notes
        },
        author=edit_request.author or "user"
    )
    db.add(change_log)
    
    db.commit()
    db.refresh(new_template)
    
    return {"message": "Template edited successfully", "new_template_id": new_template.id}


@router.post("/validate", response_model=ValidationResult)
async def validate_template(
    validation_request: ValidationRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Validate sample data against a template"""
    
    template = db.query(Template).filter(Template.id == validation_request.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Perform validation using JSON Schema
    try:
        import jsonschema
        
        schema = template.schema_json
        data = validation_request.sample_data
        
        # Validate against schema
        validator = jsonschema.Draft202012Validator(schema)
        errors = []
        warnings = []
        
        for error in validator.iter_errors(data):
            errors.append({
                "field": ".".join(str(p) for p in error.absolute_path),
                "message": error.message,
                "invalid_value": error.instance
            })
        
        # Field-level validation
        field_validations = {}
        fields = db.query(Field).filter(Field.template_id == template.id).all()
        
        for field in fields:
            field_name = field.canonical_name
            field_validations[field_name] = {
                "present": field_name in data,
                "valid": True,
                "issues": []
            }
            
            if field_name in data:
                value = data[field_name]
                
                # Check enumerations
                if field.enumerations and value not in field.enumerations:
                    field_validations[field_name]["valid"] = False
                    field_validations[field_name]["issues"].append(
                        f"Value '{value}' not in allowed values: {field.enumerations}"
                    )
                
                # Check constraints
                if field.constraints:
                    for constraint, constraint_value in field.constraints.items():
                        if constraint == "minimum" and isinstance(value, (int, float)):
                            if value < constraint_value:
                                field_validations[field_name]["valid"] = False
                                field_validations[field_name]["issues"].append(
                                    f"Value {value} is below minimum {constraint_value}"
                                )
                        elif constraint == "maximum" and isinstance(value, (int, float)):
                            if value > constraint_value:
                                field_validations[field_name]["valid"] = False
                                field_validations[field_name]["issues"].append(
                                    f"Value {value} is above maximum {constraint_value}"
                                )
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            field_validations=field_validations
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get("/{template_id}/download")
async def download_template(
    template_id: str,
    type: ExportType = ExportType.JSON_SCHEMA,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Download template in various formats"""
    
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if type == ExportType.JSON_SCHEMA:
        return _export_json_schema(template)
    elif type == ExportType.XSD:
        return _export_xsd(template)
    elif type == ExportType.MAPPING_CSV:
        return _export_mapping_csv(template, db)
    elif type == ExportType.REPORT:
        return _export_html_report(template, db)
    else:
        raise HTTPException(status_code=400, detail="Unsupported export type")


@router.get("/{template_id}/changelog", response_model=list[ChangeLogSchema])
async def get_template_changelog(
    template_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get change history for a template"""
    
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    change_logs = db.query(ChangeLog).filter(
        ChangeLog.template_id == template_id
    ).order_by(ChangeLog.timestamp.desc()).all()
    
    return change_logs


def _generate_json_schema_from_fields(fields) -> Dict[str, Any]:
    """Generate JSON Schema from field list"""
    
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {},
        "required": []
    }
    
    for field in fields:
        property_schema = {
            "type": field.data_type,
            "description": field.description or f"Field {field.canonical_name}"
        }
        
        if field.examples:
            property_schema["examples"] = field.examples[:5]
        
        if field.enumerations:
            property_schema["enum"] = field.enumerations
        
        if field.constraints:
            property_schema.update(field.constraints)
        
        if field.cardinality == "multiple":
            property_schema = {
                "type": "array",
                "items": property_schema
            }
        
        schema["properties"][field.canonical_name] = property_schema
        
        if field.cardinality != "optional":
            schema["required"].append(field.canonical_name)
    
    return schema


def _export_json_schema(template: Template) -> Response:
    """Export template as JSON Schema"""
    
    schema_json = json.dumps(template.schema_json, indent=2)
    
    return Response(
        content=schema_json,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=template_{template.id}_schema.json"
        }
    )


def _export_xsd(template: Template) -> Response:
    """Export template as XSD (simplified)"""
    
    # This is a simplified XSD generation
    # In a real implementation, you'd want a more sophisticated XSD generator
    
    xsd_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="http://example.com/{template.format.name.lower()}"
           xmlns:tns="http://example.com/{template.format.name.lower()}"
           elementFormDefault="qualified">
    
    <xs:element name="root" type="tns:RootType"/>
    
    <xs:complexType name="RootType">
        <xs:sequence>
"""
    
    fields = template.fields
    for field in fields:
        field_type = _map_json_type_to_xsd_type(field.data_type)
        occurs = "0..unbounded" if field.cardinality == "multiple" else "1"
        if field.cardinality == "optional":
            occurs = "0..1"
        
        xsd_content += f'            <xs:element name="{field.canonical_name}" type="{field_type}" minOccurs="{occurs.split("..")[0]}" maxOccurs="{occurs.split("..")[-1]}"/>\n'
    
    xsd_content += """        </xs:sequence>
    </xs:complexType>
</xs:schema>"""
    
    return Response(
        content=xsd_content,
        media_type="application/xml",
        headers={
            "Content-Disposition": f"attachment; filename=template_{template.id}_schema.xsd"
        }
    )


def _export_mapping_csv(template: Template, db: Session) -> Response:
    """Export field mappings as CSV"""
    
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Canonical Name", "Source Names", "Data Type", "Cardinality",
        "Description", "Examples", "Confidence", "Constraints"
    ])
    
    fields = db.query(Field).filter(Field.template_id == template.id).all()
    
    for field in fields:
        writer.writerow([
            field.canonical_name,
            "; ".join(field.source_names or []),
            field.data_type,
            field.cardinality,
            field.description or "",
            "; ".join(str(ex) for ex in (field.examples or [])[:3]),
            f"{field.confidence_score:.2f}",
            json.dumps(field.constraints or {})
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=template_{template.id}_mapping.csv"
        }
    )


def _export_html_report(template: Template, db: Session) -> Response:
    """Export template as HTML report"""
    
    fields = db.query(Field).filter(Field.template_id == template.id).all()
    source_files = db.query(SourceFile).filter(SourceFile.template_id == template.id).all()
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Template Report - {template.format.name} v{template.version}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .confidence-high {{ color: green; }}
        .confidence-medium {{ color: orange; }}
        .confidence-low {{ color: red; }}
    </style>
</head>
<body>
    <h1>Template Report</h1>
    <h2>{template.format.name} - Version {template.version}</h2>
    
    <h3>Summary</h3>
    <ul>
        <li>Status: {template.status}</li>
        <li>Created: {template.created_at}</li>
        <li>Total Fields: {len(fields)}</li>
        <li>Source Files: {len(source_files)}</li>
    </ul>
    
    <h3>Source Files</h3>
    <ul>
"""
    
    for source_file in source_files:
        html_content += f"        <li>{source_file.original_filename} ({source_file.file_type})</li>\n"
    
    html_content += """    </ul>
    
    <h3>Field Definitions</h3>
    <table>
        <tr>
            <th>Canonical Name</th>
            <th>Data Type</th>
            <th>Cardinality</th>
            <th>Description</th>
            <th>Examples</th>
            <th>Confidence</th>
        </tr>
"""
    
    for field in fields:
        confidence_class = "confidence-high" if field.confidence_score > 0.8 else "confidence-medium" if field.confidence_score > 0.6 else "confidence-low"
        examples_str = ", ".join(str(ex) for ex in (field.examples or [])[:3])
        
        html_content += f"""        <tr>
            <td>{field.canonical_name}</td>
            <td>{field.data_type}</td>
            <td>{field.cardinality}</td>
            <td>{field.description or ""}</td>
            <td>{examples_str}</td>
            <td class="{confidence_class}">{field.confidence_score:.2f}</td>
        </tr>
"""
    
    html_content += """    </table>
</body>
</html>"""
    
    return Response(
        content=html_content,
        media_type="text/html",
        headers={
            "Content-Disposition": f"attachment; filename=template_{template.id}_report.html"
        }
    )


def _map_json_type_to_xsd_type(json_type: str) -> str:
    """Map JSON Schema types to XSD types"""
    mapping = {
        "string": "xs:string",
        "integer": "xs:int",
        "number": "xs:decimal",
        "boolean": "xs:boolean",
        "array": "xs:string",  # Simplified
        "object": "xs:string"  # Simplified
    }
    return mapping.get(json_type, "xs:string")