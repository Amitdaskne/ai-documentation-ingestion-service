from typing import List, Optional
from .base import BaseParser
from .pdf_parser import PDFParser
from .csv_parser import CSVParser
from .xml_parser import XMLParser
from .json_parser import JSONParser
from .excel_parser import ExcelParser


class ParserFactory:
    """Factory class for creating appropriate parsers for different file types"""
    
    def __init__(self):
        self._parsers: List[BaseParser] = [
            PDFParser(),
            CSVParser(),
            XMLParser(),
            JSONParser(),
            ExcelParser(),
        ]
    
    def get_parser(self, file_path: str, mime_type: str) -> Optional[BaseParser]:
        """Get the appropriate parser for a file"""
        for parser in self._parsers:
            if parser.can_parse(file_path, mime_type):
                return parser
        return None
    
    def get_supported_types(self) -> List[str]:
        """Get list of supported file types"""
        types = []
        for parser in self._parsers:
            types.append(parser.get_file_type())
        return types
    
    def register_parser(self, parser: BaseParser):
        """Register a new parser"""
        self._parsers.append(parser)


# Global parser factory instance
parser_factory = ParserFactory()