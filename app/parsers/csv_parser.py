import pandas as pd
import numpy as np
from typing import Dict, List, Any
from .base import BaseParser, ParsedField, ParsedStructure


class CSVParser(BaseParser):
    """Parser for CSV sample files"""
    
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        return (mime_type == "text/csv" or 
                file_path.lower().endswith('.csv') or
                mime_type == "application/csv")
    
    def get_file_type(self) -> str:
        return "csv"
    
    def parse(self, file_path: str) -> ParsedStructure:
        """Parse CSV file and extract field information"""
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                raise ValueError("Could not read CSV file with any encoding")
            
            fields = []
            
            for col_name in df.columns:
                field = self._analyze_column(df, col_name)
                fields.append(field)
            
            metadata = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "has_header": True,  # Assumed since we're using column names
                "sample_rows": df.head(5).to_dict('records') if len(df) > 0 else []
            }
            
            return ParsedStructure(
                fields=fields,
                metadata=metadata,
                file_type="csv",
                confidence=0.9  # High confidence for structured data
            )
            
        except Exception as e:
            # Return minimal structure on error
            return ParsedStructure(
                fields=[],
                metadata={"error": str(e)},
                file_type="csv",
                confidence=0.0
            )
    
    def _analyze_column(self, df: pd.DataFrame, col_name: str) -> ParsedField:
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
        
        return ParsedField(
            name=col_name,
            data_type=data_type,
            examples=examples,
            location=f"column {col_name}",
            confidence=confidence,
            constraints=constraints,
            relationships={}
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
            if all(str(val).replace('.', '').replace('-', '').isdigit() for val in sample_values):
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
        confidence = 0.9
        
        # Reduce confidence based on null ratio
        confidence -= null_ratio * 0.3
        
        # Reduce confidence if too many unique values (might be messy data)
        if non_null_count > 0:
            unique_ratio = len(column.unique()) / non_null_count
            if unique_ratio > 0.8:  # Very high uniqueness might indicate messy data
                confidence -= 0.1
        
        return max(0.1, confidence)  # Minimum confidence of 0.1