import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Set
from collections import defaultdict
from .base import BaseParser, ParsedField, ParsedStructure


class XMLParser(BaseParser):
    """Parser for XML sample files"""
    
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        return (mime_type in ["application/xml", "text/xml"] or 
                file_path.lower().endswith('.xml'))
    
    def get_file_type(self) -> str:
        return "xml"
    
    def parse(self, file_path: str) -> ParsedStructure:
        """Parse XML file and extract structure"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Analyze the XML structure
            structure_info = self._analyze_structure(root)
            
            # Extract fields from the structure
            fields = self._extract_fields(structure_info)
            
            metadata = {
                "root_element": root.tag,
                "namespace": self._extract_namespace(root),
                "total_elements": structure_info["total_elements"],
                "max_depth": structure_info["max_depth"],
                "sample_structure": self._get_sample_structure(root)
            }
            
            return ParsedStructure(
                fields=fields,
                metadata=metadata,
                file_type="xml",
                confidence=0.85
            )
            
        except ET.ParseError as e:
            return ParsedStructure(
                fields=[],
                metadata={"error": f"XML Parse Error: {str(e)}"},
                file_type="xml",
                confidence=0.0
            )
        except Exception as e:
            return ParsedStructure(
                fields=[],
                metadata={"error": str(e)},
                file_type="xml",
                confidence=0.0
            )
    
    def _analyze_structure(self, root: ET.Element) -> Dict[str, Any]:
        """Analyze the overall XML structure"""
        element_info = defaultdict(lambda: {
            "count": 0,
            "attributes": set(),
            "text_values": [],
            "children": set(),
            "parents": set(),
            "paths": set()
        })
        
        total_elements = 0
        max_depth = 0
        
        def traverse(element, path="", depth=0):
            nonlocal total_elements, max_depth
            
            total_elements += 1
            max_depth = max(max_depth, depth)
            
            current_path = f"{path}/{element.tag}" if path else element.tag
            
            info = element_info[element.tag]
            info["count"] += 1
            info["paths"].add(current_path)
            
            # Collect attributes
            for attr_name in element.attrib:
                info["attributes"].add(attr_name)
            
            # Collect text content
            if element.text and element.text.strip():
                info["text_values"].append(element.text.strip())
            
            # Collect children
            for child in element:
                info["children"].add(child.tag)
                element_info[child.tag]["parents"].add(element.tag)
                traverse(child, current_path, depth + 1)
        
        traverse(root)
        
        return {
            "element_info": dict(element_info),
            "total_elements": total_elements,
            "max_depth": max_depth
        }
    
    def _extract_fields(self, structure_info: Dict[str, Any]) -> List[ParsedField]:
        """Extract fields from XML structure analysis"""
        fields = []
        element_info = structure_info["element_info"]
        
        for element_name, info in element_info.items():
            # Create field for the element itself
            field = self._create_element_field(element_name, info)
            fields.append(field)
            
            # Create fields for attributes
            for attr_name in info["attributes"]:
                attr_field = self._create_attribute_field(element_name, attr_name, info)
                fields.append(attr_field)
        
        return fields
    
    def _create_element_field(self, element_name: str, info: Dict[str, Any]) -> ParsedField:
        """Create a field for an XML element"""
        # Infer data type from text values
        data_type = self._infer_data_type_from_values(info["text_values"])
        
        # Determine cardinality
        cardinality = "multiple" if info["count"] > 1 else "single"
        if not info["text_values"] and not info["children"]:
            cardinality = "optional"
        
        # Get example values
        examples = info["text_values"][:5] if info["text_values"] else []
        
        # Build relationships
        relationships = {}
        if info["children"]:
            relationships["children"] = list(info["children"])
        if info["parents"]:
            relationships["parents"] = list(info["parents"])
        
        # Calculate confidence
        confidence = self._calculate_element_confidence(info)
        
        return ParsedField(
            name=element_name,
            data_type=data_type,
            examples=examples,
            location=f"element {element_name}",
            confidence=confidence,
            constraints={},
            relationships=relationships
        )
    
    def _create_attribute_field(self, element_name: str, attr_name: str, info: Dict[str, Any]) -> ParsedField:
        """Create a field for an XML attribute"""
        # For attributes, we need to collect their values separately
        # This is a simplified approach - in a real implementation,
        # we'd need to traverse the XML again to collect attribute values
        
        field_name = f"{element_name}@{attr_name}"
        
        return ParsedField(
            name=field_name,
            data_type="string",  # Default for attributes
            examples=[],
            location=f"attribute {attr_name} of {element_name}",
            confidence=0.8,
            constraints={},
            relationships={"parent_element": element_name}
        )
    
    def _infer_data_type_from_values(self, values: List[str]) -> str:
        """Infer data type from a list of text values"""
        if not values:
            return "string"
        
        # Check if all values are integers
        try:
            for value in values[:10]:  # Check first 10 values
                int(value)
            return "integer"
        except ValueError:
            pass
        
        # Check if all values are numbers
        try:
            for value in values[:10]:
                float(value)
            return "number"
        except ValueError:
            pass
        
        # Check for boolean values
        bool_values = {"true", "false", "1", "0", "yes", "no"}
        if all(value.lower() in bool_values for value in values[:10]):
            return "boolean"
        
        # Check for date patterns
        import re
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
        ]
        
        if values and any(re.match(pattern, values[0]) for pattern in date_patterns):
            return "string"  # Date as string
        
        return "string"
    
    def _calculate_element_confidence(self, info: Dict[str, Any]) -> float:
        """Calculate confidence score for an element"""
        confidence = 0.8  # Base confidence for XML structure
        
        # Higher confidence if element has consistent structure
        if info["count"] > 1:
            confidence += 0.1
        
        # Higher confidence if element has text content
        if info["text_values"]:
            confidence += 0.05
        
        # Higher confidence if element has attributes
        if info["attributes"]:
            confidence += 0.05
        
        return min(1.0, confidence)
    
    def _extract_namespace(self, root: ET.Element) -> str:
        """Extract namespace from root element"""
        if root.tag.startswith('{'):
            return root.tag[1:root.tag.find('}')]
        return ""
    
    def _get_sample_structure(self, root: ET.Element, max_depth: int = 3) -> Dict[str, Any]:
        """Get a sample of the XML structure for metadata"""
        def element_to_dict(element, depth=0):
            if depth > max_depth:
                return "..."
            
            result = {
                "tag": element.tag,
                "attributes": dict(element.attrib) if element.attrib else {},
            }
            
            if element.text and element.text.strip():
                result["text"] = element.text.strip()[:100]  # Truncate long text
            
            children = {}
            for child in element:
                if child.tag not in children:
                    children[child.tag] = []
                children[child.tag].append(element_to_dict(child, depth + 1))
            
            if children:
                result["children"] = children
            
            return result
        
        return element_to_dict(root)