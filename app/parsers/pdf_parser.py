import fitz  # PyMuPDF
import re
from typing import Dict, List, Any, Tuple
from .base import BaseParser, ParsedField, ParsedStructure


class PDFParser(BaseParser):
    """Parser for PDF specification documents"""
    
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        return mime_type == "application/pdf" or file_path.lower().endswith('.pdf')
    
    def get_file_type(self) -> str:
        return "pdf"
    
    def parse(self, file_path: str) -> ParsedStructure:
        """Parse PDF and extract format specifications"""
        doc = fitz.open(file_path)
        
        # Extract text from all pages
        full_text = ""
        page_texts = {}
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            page_texts[page_num + 1] = text
            full_text += f"\n--- Page {page_num + 1} ---\n{text}"
        
        doc.close()
        
        # Extract format name and version
        format_info = self._extract_format_info(full_text)
        
        # Extract field definitions
        fields = self._extract_field_definitions(page_texts)
        
        # Extract enumerations and constraints
        enumerations = self._extract_enumerations(full_text)
        
        # Extract rules and constraints
        rules = self._extract_rules(full_text)
        
        metadata = {
            "format_name": format_info.get("name"),
            "format_version": format_info.get("version"),
            "total_pages": len(page_texts),
            "enumerations": enumerations,
            "rules": rules,
            "extraction_confidence": 0.8  # Base confidence for PDF extraction
        }
        
        return ParsedStructure(
            fields=fields,
            metadata=metadata,
            file_type="pdf",
            confidence=0.8
        )
    
    def _extract_format_info(self, text: str) -> Dict[str, str]:
        """Extract format name and version from PDF text"""
        info = {}
        
        # Common patterns for format names
        name_patterns = [
            r"(?i)format\s*:\s*([A-Za-z0-9\s\-_]+)",
            r"(?i)specification\s*:\s*([A-Za-z0-9\s\-_]+)",
            r"(?i)standard\s*:\s*([A-Za-z0-9\s\-_]+)",
            r"(?i)([A-Z]{2,}(?:\s+[A-Z]{2,})*)\s+specification",
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                info["name"] = match.group(1).strip()
                break
        
        # Common patterns for versions
        version_patterns = [
            r"(?i)version\s*:?\s*([0-9]+(?:\.[0-9]+)*)",
            r"(?i)v\.?\s*([0-9]+(?:\.[0-9]+)*)",
            r"(?i)release\s*:?\s*([0-9]+(?:\.[0-9]+)*)",
        ]
        
        for pattern in version_patterns:
            match = re.search(pattern, text)
            if match:
                info["version"] = match.group(1).strip()
                break
        
        return info
    
    def _extract_field_definitions(self, page_texts: Dict[int, str]) -> List[ParsedField]:
        """Extract field definitions from PDF pages"""
        fields = []
        
        for page_num, text in page_texts.items():
            # Look for field definition patterns
            field_patterns = [
                # Pattern: Field Name: Description
                r"([A-Za-z][A-Za-z0-9_]*)\s*:\s*([^\n]+)",
                # Pattern: Field Name (Type): Description
                r"([A-Za-z][A-Za-z0-9_]*)\s*\(([^)]+)\)\s*:\s*([^\n]+)",
                # Pattern: Field Name - Description
                r"([A-Za-z][A-Za-z0-9_]*)\s*-\s*([^\n]+)",
            ]
            
            for pattern in field_patterns:
                matches = re.finditer(pattern, text, re.MULTILINE)
                for match in matches:
                    if len(match.groups()) == 2:
                        field_name, description = match.groups()
                        data_type = "string"  # Default type
                    else:
                        field_name, data_type, description = match.groups()
                    
                    # Infer data type from description
                    inferred_type = self._infer_data_type(description)
                    if inferred_type:
                        data_type = inferred_type
                    
                    field = ParsedField(
                        name=field_name.strip(),
                        data_type=data_type.lower() if data_type else "string",
                        examples=[],
                        location=f"page {page_num}",
                        confidence=0.7,
                        constraints={},
                        relationships={}
                    )
                    fields.append(field)
        
        return fields
    
    def _infer_data_type(self, description: str) -> str:
        """Infer data type from field description"""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ["number", "numeric", "integer", "count"]):
            return "integer"
        elif any(word in description_lower for word in ["decimal", "float", "amount", "price"]):
            return "number"
        elif any(word in description_lower for word in ["date", "time", "timestamp"]):
            return "string"  # ISO date format
        elif any(word in description_lower for word in ["boolean", "true", "false", "yes", "no"]):
            return "boolean"
        elif any(word in description_lower for word in ["array", "list", "multiple"]):
            return "array"
        else:
            return "string"
    
    def _extract_enumerations(self, text: str) -> Dict[str, List[str]]:
        """Extract enumeration values from PDF text"""
        enumerations = {}
        
        # Look for enumeration patterns
        enum_patterns = [
            r"(?i)valid\s+values?\s*:?\s*([^\n]+)",
            r"(?i)allowed\s+values?\s*:?\s*([^\n]+)",
            r"(?i)possible\s+values?\s*:?\s*([^\n]+)",
        ]
        
        for pattern in enum_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                values_text = match.group(1)
                # Split by common delimiters
                values = re.split(r'[,;|]', values_text)
                values = [v.strip().strip('"\'') for v in values if v.strip()]
                if values:
                    # Try to find the field name this enumeration belongs to
                    # This is a simplified approach
                    enumerations["unknown_field"] = values
        
        return enumerations
    
    def _extract_rules(self, text: str) -> List[str]:
        """Extract business rules and constraints from PDF text"""
        rules = []
        
        # Look for rule patterns
        rule_patterns = [
            r"(?i)rule\s*:?\s*([^\n]+)",
            r"(?i)constraint\s*:?\s*([^\n]+)",
            r"(?i)requirement\s*:?\s*([^\n]+)",
            r"(?i)must\s+([^\n]+)",
            r"(?i)shall\s+([^\n]+)",
        ]
        
        for pattern in rule_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                rule = match.group(1).strip()
                if len(rule) > 10:  # Filter out very short matches
                    rules.append(rule)
        
        return rules