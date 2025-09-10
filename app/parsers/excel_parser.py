import pandas as pd
import numpy as np
from typing import Dict, List, Any
from .base import BaseParser, ParsedField, ParsedStructure


class ExcelParser(BaseParser):
    """Parser for Excel sample files"""
    
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        return (mime_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             "application/vnd.ms-excel"] or
                file_path.lower().endswith(('.xlsx', '.xls')))
    
    def get_file_type(self) -> str:
        return "excel"
    
    def parse(self, file_path: str) -> ParsedStructure:
        """Parse Excel file and extract field information"""
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            all_fields = []
            sheet_metadata = {}
            
            for sheet_name in excel_file.sheet_names:
                try:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    # Parse each sheet like a CSV
                    sheet_fields = []
                    for col_name in df.columns:
                        field = self._analyze_column(df, col_name, sheet_name)
                        sheet_fields.append(field)
                    
                    all_fields.extend(sheet_fields)
                    
                    sheet_metadata[sheet_name] = {
                        "row_count": len(df),
                        "column_count": len(df.columns),
                        "columns": list(df.columns),
                        "sample_rows": df.head(3).to_dict('records') if len(df) > 0 else []
                    }
                    
                except Exception as e:
                    sheet_metadata[sheet_name] = {"error": str(e)}
            
            metadata = {
                "sheet_count": len(excel_file.sheet_names),
                "sheet_names": excel_file.sheet_names,
                "sheets": sheet_metadata
            }
            
            return ParsedStructure(
                fields=all_fields,
                metadata=metadata,
                file_type="excel",
                confidence=0.85
            )
            
        except Exception as e:
            return ParsedStructure(
                fields=[],
                metadata={"error": str(e)},
                file_type="excel",
                confidence=0.0
            )
    
    def _analyze_column(self, df: pd.DataFrame, col_name: str, sheet_name: str) -> ParsedField:
        """Analyze a single column to extract field information"""
        column = df[col_name]
        
        # Get non-null values for analysis
        non_null_values = column.dropna()
        
        # Infer data type
        data_type = self._infer_data_type(column)
        
        # Get example values (up to 5 unique values)
        examples = []
        if len(non_null_values) > 0:
            unique_values = non_null_values.unique()
            examples = [self._convert_value(val) for val in unique_values[:5]]
        
        # Check for enumerations (if limited unique values)
        enumerations = []
        if len(non_null_values) > 0:
            unique_count = len(non_null_values.unique())
            total_count = len(non_null_values)
            
            # If unique values are less than 20% of total and less than 50 values
            if unique_count < min(total_count * 0.2, 50) and unique_count > 1:
                enumerations = [self._convert_value(val) for val in non_null_values.unique()]
        
        # Determine cardinality
        cardinality = "optional" if column.isnull().any() else "single"
        
        # Calculate confidence based on data quality
        confidence = self._calculate_confidence(column)
        
        constraints = {}
        
        # Add constraints based on data type
        if data_type in ["integer", "number"]:
            if len(non_null_values) > 0:
                constraints["minimum"] = float(non_null_values.min())
                constraints["maximum"] = float(non_null_values.max())
        
        elif data_type == "string":
            if len(non_null_values) > 0:
                lengths = non_null_values.astype(str).str.len()
                constraints["minLength"] = int(lengths.min())
                constraints["maxLength"] = int(lengths.max())
        
        # Include sheet information in relationships
        relationships = {
            "sheet": sheet_name,
            "column_index": df.columns.get_loc(col_name)
        }
        
        return ParsedField(
            name=f"{sheet_name}.{col_name}",  # Prefix with sheet name
            data_type=data_type,
            examples=examples,
            location=f"sheet '{sheet_name}', column '{col_name}'",
            confidence=confidence,
            constraints=constraints,
            relationships=relationships
        )
    
    def _infer_data_type(self, column: pd.Series) -> str:
        """Infer the data type of a pandas column"""
        # Check pandas dtype first
        if pd.api.types.is_integer_dtype(column):
            return "integer"
        elif pd.api.types.is_float_dtype(column):
            return "number"
        elif pd.api.types.is_bool_dtype(column):
            return "boolean"
        elif pd.api.types.is_datetime64_any_dtype(column):
            return "string"  # ISO date format
        
        # For object columns, analyze the actual values
        non_null_values = column.dropna()
        if len(non_null_values) == 0:
            return "string"
        
        # Sample some values for type inference
        sample_values = non_null_values.head(100)
        
        # Check if all values can be converted to numbers
        try:
            pd.to_numeric(sample_values)
            # Check if they're all integers
            numeric_values = pd.to_numeric(sample_values)
            if all(val == int(val) for val in numeric_values if not pd.isna(val)):
                return "integer"
            else:
                return "number"
        except (ValueError, TypeError):
            pass
        
        # Check for boolean-like values
        bool_values = {"true", "false", "yes", "no", "1", "0", "y", "n"}
        if all(str(val).lower() in bool_values for val in sample_values):
            return "boolean"
        
        # Check for date-like strings
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
        ]
        
        import re
        sample_str = str(sample_values.iloc[0]) if len(sample_values) > 0 else ""
        for pattern in date_patterns:
            if re.match(pattern, sample_str):
                return "string"  # Date as string
        
        return "string"
    
    def _convert_value(self, value) -> Any:
        """Convert pandas value to JSON-serializable format"""
        if pd.isna(value):
            return None
        elif isinstance(value, (np.integer, np.int64)):
            return int(value)
        elif isinstance(value, (np.floating, np.float64)):
            return float(value)
        elif isinstance(value, np.bool_):
            return bool(value)
        else:
            return str(value)
    
    def _calculate_confidence(self, column: pd.Series) -> float:
        """Calculate confidence score based on data quality"""
        total_count = len(column)
        if total_count == 0:
            return 0.0
        
        non_null_count = column.count()
        null_ratio = (total_count - non_null_count) / total_count
        
        # Base confidence starts high for structured data
        confidence = 0.85
        
        # Reduce confidence based on null ratio
        confidence -= null_ratio * 0.3
        
        # Reduce confidence if too many unique values (might be messy data)
        if non_null_count > 0:
            unique_ratio = len(column.unique()) / non_null_count
            if unique_ratio > 0.8:  # Very high uniqueness might indicate messy data
                confidence -= 0.1
        
        return max(0.1, confidence)  # Minimum confidence of 0.1