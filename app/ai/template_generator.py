from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import re
import json
from difflib import SequenceMatcher
from app.parsers.base import ParsedStructure, ParsedField
from app.schemas.schemas import FieldSchema, ProvenanceRecord


class TemplateGenerator:
    """AI-powered template generator that reconciles PDF specs with structured samples"""
    
    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
    
    def generate_template(
        self, 
        pdf_structure: Optional[ParsedStructure],
        sample_structures: List[ParsedStructure],
        format_name: str,
        format_version: str
    ) -> Dict[str, Any]:
        """Generate a unified template from PDF and sample files"""
        
        # Step 1: Extract fields from all sources
        pdf_fields = pdf_structure.fields if pdf_structure else []
        sample_fields = []
        for structure in sample_structures:
            sample_fields.extend(structure.fields)
        
        # Step 2: Reconcile field names and create canonical mapping
        field_mapping = self._reconcile_field_names(pdf_fields, sample_fields)
        
        # Step 3: Generate unified field definitions
        unified_fields = self._generate_unified_fields(field_mapping, pdf_structure, sample_structures)
        
        # Step 4: Generate JSON Schema
        json_schema = self._generate_json_schema(unified_fields, format_name, format_version)
        
        # Step 5: Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(unified_fields)
        
        return {
            "schema_json": json_schema,
            "fields": unified_fields,
            "metadata": {
                "format_name": format_name,
                "format_version": format_version,
                "confidence": overall_confidence,
                "source_files_count": len(sample_structures) + (1 if pdf_structure else 0),
                "total_fields": len(unified_fields)
            }
        }
    
    def _reconcile_field_names(
        self, 
        pdf_fields: List[ParsedField], 
        sample_fields: List[ParsedField]
    ) -> Dict[str, Dict[str, Any]]:
        """Reconcile field names between PDF and sample files"""
        
        # Group sample fields by similarity
        sample_field_groups = self._group_similar_fields(sample_fields)
        
        # Create mapping structure
        field_mapping = {}
        
        # First, try to match PDF fields with sample field groups
        for pdf_field in pdf_fields:
            best_match = self._find_best_match(pdf_field.name, sample_field_groups)
            
            canonical_name = self._normalize_field_name(pdf_field.name)
            
            field_mapping[canonical_name] = {
                "canonical_name": canonical_name,
                "pdf_field": pdf_field,
                "sample_fields": best_match["fields"] if best_match else [],
                "confidence": best_match["confidence"] if best_match else 0.5
            }
        
        # Add unmatched sample fields
        matched_sample_fields = set()
        for mapping in field_mapping.values():
            for field in mapping["sample_fields"]:
                matched_sample_fields.add(id(field))
        
        for group_name, fields in sample_field_groups.items():
            if not any(id(field) in matched_sample_fields for field in fields):
                canonical_name = self._normalize_field_name(group_name)
                if canonical_name not in field_mapping:
                    field_mapping[canonical_name] = {
                        "canonical_name": canonical_name,
                        "pdf_field": None,
                        "sample_fields": fields,
                        "confidence": 0.6  # Lower confidence for unmatched fields
                    }
        
        return field_mapping
    
    def _group_similar_fields(self, fields: List[ParsedField]) -> Dict[str, List[ParsedField]]:
        """Group similar field names together"""
        groups = defaultdict(list)
        
        for field in fields:
            # Normalize the field name for grouping
            normalized_name = self._normalize_field_name(field.name)
            groups[normalized_name].append(field)
        
        return dict(groups)
    
    def _normalize_field_name(self, name: str) -> str:
        """Normalize field name for comparison"""
        # Remove common prefixes/suffixes and normalize case
        normalized = re.sub(r'^(field_|col_|column_)', '', name.lower())
        normalized = re.sub(r'(_field|_col|_column)$', '', normalized)
        
        # Replace common separators with underscores
        normalized = re.sub(r'[-\s\.]+', '_', normalized)
        
        # Remove special characters
        normalized = re.sub(r'[^\w]', '_', normalized)
        
        # Remove multiple underscores
        normalized = re.sub(r'_+', '_', normalized)
        
        return normalized.strip('_')
    
    def _find_best_match(
        self, 
        target_name: str, 
        field_groups: Dict[str, List[ParsedField]]
    ) -> Optional[Dict[str, Any]]:
        """Find the best matching field group for a target name"""
        
        target_normalized = self._normalize_field_name(target_name)
        best_match = None
        best_score = 0.0
        
        for group_name, fields in field_groups.items():
            # Calculate similarity score
            score = SequenceMatcher(None, target_normalized, group_name).ratio()
            
            # Boost score for exact matches
            if target_normalized == group_name:
                score = 1.0
            
            # Boost score for partial matches
            elif target_normalized in group_name or group_name in target_normalized:
                score += 0.2
            
            if score > best_score and score > 0.5:  # Minimum threshold
                best_score = score
                best_match = {
                    "fields": fields,
                    "confidence": score
                }
        
        return best_match
    
    def _generate_unified_fields(
        self,
        field_mapping: Dict[str, Dict[str, Any]],
        pdf_structure: Optional[ParsedStructure],
        sample_structures: List[ParsedStructure]
    ) -> List[FieldSchema]:
        """Generate unified field definitions"""
        
        unified_fields = []
        
        for canonical_name, mapping in field_mapping.items():
            pdf_field = mapping["pdf_field"]
            sample_fields = mapping["sample_fields"]
            
            # Create unified field
            unified_field = self._create_unified_field(
                canonical_name, pdf_field, sample_fields, sample_structures
            )
            
            unified_fields.append(unified_field)
        
        return unified_fields
    
    def _create_unified_field(
        self,
        canonical_name: str,
        pdf_field: Optional[ParsedField],
        sample_fields: List[ParsedField],
        sample_structures: List[ParsedStructure]
    ) -> FieldSchema:
        """Create a unified field definition"""
        
        # Collect source names
        source_names = []
        if pdf_field:
            source_names.append(pdf_field.name)
        source_names.extend([f.name for f in sample_fields])
        source_names = list(set(source_names))  # Remove duplicates
        
        # Determine data type (prioritize sample data over PDF)
        data_type = self._determine_unified_data_type(pdf_field, sample_fields)
        
        # Determine cardinality
        cardinality = self._determine_unified_cardinality(pdf_field, sample_fields)
        
        # Collect examples
        examples = []
        for field in sample_fields:
            examples.extend(field.examples)
        examples = list(set(examples))[:10]  # Limit to 10 unique examples
        
        # Collect enumerations
        enumerations = self._collect_enumerations(pdf_field, sample_fields)
        
        # Create description
        description = pdf_field.description if pdf_field else None
        if not description and sample_fields:
            # Try to infer description from field names and examples
            description = self._infer_description(canonical_name, examples)
        
        # Calculate confidence
        confidence = self._calculate_field_confidence(pdf_field, sample_fields)
        
        # Create provenance records
        provenance = self._create_provenance_records(pdf_field, sample_fields, sample_structures)
        
        # Collect relationships
        relationships = self._merge_relationships(pdf_field, sample_fields)
        
        # Collect constraints
        constraints = self._merge_constraints(pdf_field, sample_fields)
        
        return FieldSchema(
            id=f"field_{canonical_name}",
            canonical_name=canonical_name,
            source_names=source_names,
            data_type=data_type,
            cardinality=cardinality,
            enumerations=enumerations,
            examples=examples,
            description=description,
            confidence_score=confidence,
            provenance=provenance,
            relationships=relationships,
            constraints=constraints
        )
    
    def _determine_unified_data_type(
        self, 
        pdf_field: Optional[ParsedField], 
        sample_fields: List[ParsedField]
    ) -> str:
        """Determine the unified data type"""
        
        # Prioritize sample data types (more reliable)
        if sample_fields:
            sample_types = [f.data_type for f in sample_fields]
            # Use the most common type
            type_counts = defaultdict(int)
            for t in sample_types:
                type_counts[t] += 1
            most_common_type = max(type_counts.items(), key=lambda x: x[1])[0]
            return most_common_type
        
        # Fall back to PDF type
        if pdf_field:
            return pdf_field.data_type
        
        return "string"  # Default
    
    def _determine_unified_cardinality(
        self, 
        pdf_field: Optional[ParsedField], 
        sample_fields: List[ParsedField]
    ) -> str:
        """Determine the unified cardinality"""
        
        # Check sample fields first
        if sample_fields:
            # If any sample field suggests multiple, use multiple
            for field in sample_fields:
                if hasattr(field, 'cardinality') and field.cardinality == "multiple":
                    return "multiple"
            
            # If any field has array-like relationships, suggest multiple
            for field in sample_fields:
                if field.relationships and "array" in str(field.relationships).lower():
                    return "multiple"
        
        # Check PDF field
        if pdf_field and hasattr(pdf_field, 'cardinality'):
            return pdf_field.cardinality
        
        return "single"  # Default
    
    def _collect_enumerations(
        self, 
        pdf_field: Optional[ParsedField], 
        sample_fields: List[ParsedField]
    ) -> List[str]:
        """Collect enumeration values from all sources"""
        
        enumerations = set()
        
        # From PDF
        if pdf_field and hasattr(pdf_field, 'enumerations'):
            enumerations.update(pdf_field.enumerations or [])
        
        # From sample fields
        for field in sample_fields:
            if hasattr(field, 'enumerations'):
                enumerations.update(field.enumerations or [])
            
            # If field has limited unique examples, treat as enumerations
            if field.examples and len(field.examples) <= 10:
                # Check if examples look like enumerations (not too varied)
                if all(isinstance(ex, str) and len(str(ex)) < 50 for ex in field.examples):
                    enumerations.update(str(ex) for ex in field.examples)
        
        return sorted(list(enumerations))
    
    def _infer_description(self, canonical_name: str, examples: List[Any]) -> str:
        """Infer a description from field name and examples"""
        
        # Basic description based on field name
        name_words = canonical_name.replace('_', ' ').title()
        description = f"Field representing {name_words}"
        
        # Add information from examples
        if examples:
            example_str = ", ".join(str(ex)[:20] for ex in examples[:3])
            description += f". Example values: {example_str}"
            if len(examples) > 3:
                description += f" (and {len(examples) - 3} more)"
        
        return description
    
    def _calculate_field_confidence(
        self, 
        pdf_field: Optional[ParsedField], 
        sample_fields: List[ParsedField]
    ) -> float:
        """Calculate confidence score for a unified field"""
        
        confidence = 0.5  # Base confidence
        
        # Boost confidence if we have PDF documentation
        if pdf_field:
            confidence += 0.2
            if hasattr(pdf_field, 'confidence'):
                confidence += pdf_field.confidence * 0.2
        
        # Boost confidence based on sample field quality
        if sample_fields:
            sample_confidences = [getattr(f, 'confidence', 0.7) for f in sample_fields]
            avg_sample_confidence = sum(sample_confidences) / len(sample_confidences)
            confidence += avg_sample_confidence * 0.3
            
            # Boost if multiple samples agree
            if len(sample_fields) > 1:
                confidence += 0.1
        
        return min(1.0, confidence)
    
    def _create_provenance_records(
        self,
        pdf_field: Optional[ParsedField],
        sample_fields: List[ParsedField],
        sample_structures: List[ParsedStructure]
    ) -> List[ProvenanceRecord]:
        """Create provenance records for field sources"""
        
        provenance = []
        
        # PDF provenance
        if pdf_field:
            provenance.append(ProvenanceRecord(
                source_file_id="pdf_source",  # Will be updated with actual file ID
                source_type="pdf",
                location=pdf_field.location,
                confidence=getattr(pdf_field, 'confidence', 0.7),
                evidence=f"Field '{pdf_field.name}' found in PDF specification"
            ))
        
        # Sample file provenance
        for field in sample_fields:
            # Find which structure this field belongs to
            source_structure = None
            for structure in sample_structures:
                if field in structure.fields:
                    source_structure = structure
                    break
            
            provenance.append(ProvenanceRecord(
                source_file_id="sample_source",  # Will be updated with actual file ID
                source_type=source_structure.file_type if source_structure else "unknown",
                location=field.location,
                confidence=getattr(field, 'confidence', 0.8),
                evidence=f"Field '{field.name}' found in {source_structure.file_type if source_structure else 'sample'} file"
            ))
        
        return provenance
    
    def _merge_relationships(
        self, 
        pdf_field: Optional[ParsedField], 
        sample_fields: List[ParsedField]
    ) -> Dict[str, Any]:
        """Merge relationship information from all sources"""
        
        relationships = {}
        
        # From PDF
        if pdf_field and pdf_field.relationships:
            relationships.update(pdf_field.relationships)
        
        # From sample fields
        for field in sample_fields:
            if field.relationships:
                for key, value in field.relationships.items():
                    if key in relationships:
                        # Merge lists
                        if isinstance(relationships[key], list) and isinstance(value, list):
                            relationships[key] = list(set(relationships[key] + value))
                        elif relationships[key] != value:
                            # Convert to list if different values
                            if not isinstance(relationships[key], list):
                                relationships[key] = [relationships[key]]
                            if value not in relationships[key]:
                                relationships[key].append(value)
                    else:
                        relationships[key] = value
        
        return relationships
    
    def _merge_constraints(
        self, 
        pdf_field: Optional[ParsedField], 
        sample_fields: List[ParsedField]
    ) -> Dict[str, Any]:
        """Merge constraint information from all sources"""
        
        constraints = {}
        
        # From PDF
        if pdf_field and pdf_field.constraints:
            constraints.update(pdf_field.constraints)
        
        # From sample fields (prioritize sample data for numeric constraints)
        numeric_constraints = ["minimum", "maximum", "minLength", "maxLength"]
        
        for field in sample_fields:
            if field.constraints:
                for key, value in field.constraints.items():
                    if key in numeric_constraints:
                        # For numeric constraints, use the most restrictive values
                        if key in ["minimum", "minLength"]:
                            constraints[key] = max(constraints.get(key, value), value)
                        elif key in ["maximum", "maxLength"]:
                            constraints[key] = min(constraints.get(key, value), value)
                    else:
                        constraints[key] = value
        
        return constraints
    
    def _generate_json_schema(
        self, 
        fields: List[FieldSchema], 
        format_name: str, 
        format_version: str
    ) -> Dict[str, Any]:
        """Generate JSON Schema from unified fields"""
        
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://schemas.example.com/{format_name.lower()}/{format_version}",
            "title": f"{format_name} Schema",
            "description": f"JSON Schema for {format_name} version {format_version}",
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for field in fields:
            property_schema = {
                "type": field.data_type,
                "description": field.description or f"Field {field.canonical_name}"
            }
            
            # Add examples
            if field.examples:
                property_schema["examples"] = field.examples[:5]
            
            # Add enumerations
            if field.enumerations:
                property_schema["enum"] = field.enumerations
            
            # Add constraints
            if field.constraints:
                property_schema.update(field.constraints)
            
            # Handle arrays
            if field.cardinality == "multiple":
                property_schema = {
                    "type": "array",
                    "items": property_schema,
                    "description": f"Array of {field.canonical_name}"
                }
            
            schema["properties"][field.canonical_name] = property_schema
            
            # Add to required if not optional
            if field.cardinality != "optional":
                schema["required"].append(field.canonical_name)
        
        return schema
    
    def _calculate_overall_confidence(self, fields: List[FieldSchema]) -> float:
        """Calculate overall confidence for the template"""
        
        if not fields:
            return 0.0
        
        field_confidences = [field.confidence_score for field in fields]
        return sum(field_confidences) / len(field_confidences)