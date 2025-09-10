import json
from typing import Dict, List, Any, Union
from collections import defaultdict
from .base import BaseParser, ParsedField, ParsedStructure


class JSONParser(BaseParser):
    """Parser for JSON sample files"""
    
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        return (mime_type == "application/json" or 
                file_path.lower().endswith('.json'))
    
    def get_file_type(self) -> str:
        return "json"
    
    def parse(self, file_path: str) -> ParsedStructure:
        """Parse JSON file and extract structure"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Analyze the JSON structure
            structure_info = self._analyze_structure(data)
            
            # Extract fields from the structure
            fields = self._extract_fields(structure_info)
            
            metadata = {
                "root_type": type(data).__name__,
                "total_fields": len(structure_info["field_info"]),
                "max_depth": structure_info["max_depth"],
                "sample_data": self._get_sample_data(data)
            }
            
            return ParsedStructure(
                fields=fields,
                metadata=metadata,
                file_type="json",
                confidence=0.9
            )
            
        except json.JSONDecodeError as e:
            return ParsedStructure(
                fields=[],
                metadata={"error": f"JSON Parse Error: {str(e)}"},
                file_type="json",
                confidence=0.0
            )
        except Exception as e:
            return ParsedStructure(
                fields=[],
                metadata={"error": str(e)},
                file_type="json",
                confidence=0.0
            )
    
    def _analyze_structure(self, data: Any, path: str = "", depth: int = 0) -> Dict[str, Any]:
        """Analyze the JSON structure recursively"""
        field_info = defaultdict(lambda: {
            "paths": set(),
            "types": set(),
            "values": [],
            "is_array": False,
            "array_item_types": set(),
            "object_keys": set(),
            "depth": 0
        })
        
        max_depth = depth
        
        def traverse(obj: Any, current_path: str = "", current_depth: int = 0):
            nonlocal max_depth
            max_depth = max(max_depth, current_depth)
            
            if isinstance(obj, dict):
                for key, value in obj.items():
                    field_path = f"{current_path}.{key}" if current_path else key
                    info = field_info[key]
                    info["paths"].add(field_path)
                    info["depth"] = max(info["depth"], current_depth)
                    
                    # Analyze the value
                    self._analyze_value(value, info)
                    
                    # Recurse into nested structures
                    if isinstance(value, (dict, list)):
                        traverse(value, field_path, current_depth + 1)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, dict):
                        # For array items, analyze each object's keys
                        for key, value in item.items():
                            field_path = f"{current_path}[].{key}" if current_path else f"[].{key}"
                            info = field_info[key]
                            info["paths"].add(field_path)
                            info["depth"] = max(info["depth"], current_depth)
                            info["is_array"] = True
                            
                            self._analyze_value(value, info)
                            
                            if isinstance(value, (dict, list)):
                                traverse(value, field_path, current_depth + 1)
                    else:
                        # Array of primitives
                        if current_path:
                            info = field_info[current_path.split('.')[-1]]
                            info["is_array"] = True
                            info["array_item_types"].add(type(item).__name__)
                            if len(info["values"]) < 10:
                                info["values"].append(item)
        
        traverse(data)
        
        return {
            "field_info": dict(field_info),
            "max_depth": max_depth
        }
    
    def _analyze_value(self, value: Any, info: Dict[str, Any]):
        """Analyze a single value and update field info"""
        value_type = type(value).__name__
        info["types"].add(value_type)
        
        # Store sample values (limit to 10)
        if len(info["values"]) < 10 and not isinstance(value, (dict, list)):
            info["values"].append(value)
        
        # For objects, store keys
        if isinstance(value, dict):
            info["object_keys"].update(value.keys())
        
        # For arrays, analyze item types
        elif isinstance(value, list):
            info["is_array"] = True
            for item in value[:5]:  # Sample first 5 items
                info["array_item_types"].add(type(item).__name__)
    
    def _extract_fields(self, structure_info: Dict[str, Any]) -> List[ParsedField]:
        """Extract fields from JSON structure analysis"""
        fields = []
        field_info = structure_info["field_info"]
        
        for field_name, info in field_info.items():
            field = self._create_field(field_name, info)
            fields.append(field)
        
        return fields
    
    def _create_field(self, field_name: str, info: Dict[str, Any]) -> ParsedField:
        """Create a field from analyzed information"""
        # Determine primary data type
        data_type = self._determine_data_type(info)
        
        # Determine cardinality
        cardinality = "multiple" if info["is_array"] else "single"
        
        # Get example values
        examples = info["values"][:5] if info["values"] else []
        
        # Build relationships
        relationships = {}
        if info["object_keys"]:
            relationships["object_properties"] = list(info["object_keys"])
        if info["array_item_types"]:
            relationships["array_item_types"] = list(info["array_item_types"])
        
        # Build constraints
        constraints = {}
        if data_type in ["integer", "number"] and info["values"]:
            numeric_values = [v for v in info["values"] if isinstance(v, (int, float))]
            if numeric_values:
                constraints["minimum"] = min(numeric_values)
                constraints["maximum"] = max(numeric_values)
        
        elif data_type == "string" and info["values"]:
            string_values = [str(v) for v in info["values"] if v is not None]
            if string_values:
                lengths = [len(s) for s in string_values]
                constraints["minLength"] = min(lengths)
                constraints["maxLength"] = max(lengths)
        
        # Calculate confidence
        confidence = self._calculate_confidence(info)
        
        # Determine location
        location = f"field {field_name}"
        if info["paths"]:
            location = f"paths: {', '.join(list(info['paths'])[:3])}"
        
        return ParsedField(
            name=field_name,
            data_type=data_type,
            examples=examples,
            location=location,
            confidence=confidence,
            constraints=constraints,
            relationships=relationships
        )
    
    def _determine_data_type(self, info: Dict[str, Any]) -> str:
        """Determine the primary data type for a field"""
        types = info["types"]
        
        if not types:
            return "string"
        
        # If only one type, use it
        if len(types) == 1:
            type_name = list(types)[0]
            return self._map_python_type_to_json_type(type_name)
        
        # Multiple types - determine the most appropriate
        type_priority = {
            "bool": 1,
            "int": 2,
            "float": 3,
            "str": 4,
            "list": 5,
            "dict": 6,
            "NoneType": 7
        }
        
        # Get the highest priority type (lowest number)
        primary_type = min(types, key=lambda t: type_priority.get(t, 10))
        return self._map_python_type_to_json_type(primary_type)
    
    def _map_python_type_to_json_type(self, python_type: str) -> str:
        """Map Python type names to JSON Schema types"""
        mapping = {
            "bool": "boolean",
            "int": "integer",
            "float": "number",
            "str": "string",
            "list": "array",
            "dict": "object",
            "NoneType": "null"
        }
        return mapping.get(python_type, "string")
    
    def _calculate_confidence(self, info: Dict[str, Any]) -> float:
        """Calculate confidence score for a field"""
        confidence = 0.9  # Base confidence for JSON structure
        
        # Reduce confidence if multiple types detected
        if len(info["types"]) > 1:
            confidence -= 0.1 * (len(info["types"]) - 1)
        
        # Increase confidence if we have sample values
        if info["values"]:
            confidence += 0.05
        
        # Increase confidence if field appears in multiple paths (consistent structure)
        if len(info["paths"]) > 1:
            confidence += 0.05
        
        return max(0.1, min(1.0, confidence))
    
    def _get_sample_data(self, data: Any, max_items: int = 3) -> Any:
        """Get a sample of the JSON data for metadata"""
        if isinstance(data, dict):
            # Return first few key-value pairs
            items = list(data.items())[:max_items]
            result = {}
            for key, value in items:
                if isinstance(value, (dict, list)):
                    result[key] = self._get_sample_data(value, max_items)
                else:
                    result[key] = value
            if len(data) > max_items:
                result["..."] = f"and {len(data) - max_items} more items"
            return result
        
        elif isinstance(data, list):
            # Return first few items
            result = []
            for item in data[:max_items]:
                if isinstance(item, (dict, list)):
                    result.append(self._get_sample_data(item, max_items))
                else:
                    result.append(item)
            if len(data) > max_items:
                result.append(f"... and {len(data) - max_items} more items")
            return result
        
        else:
            return data