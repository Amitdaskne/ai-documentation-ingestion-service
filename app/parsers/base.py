from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class ParsedField:
    """Represents a field extracted from a source file"""
    name: str
    data_type: str
    examples: List[Any]
    location: str  # Where in the file this was found
    confidence: float
    constraints: Dict[str, Any] = None
    relationships: Dict[str, Any] = None


@dataclass
class ParsedStructure:
    """Represents the overall structure extracted from a file"""
    fields: List[ParsedField]
    metadata: Dict[str, Any]
    file_type: str
    confidence: float


class BaseParser(ABC):
    """Base class for all file parsers"""
    
    @abstractmethod
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """Check if this parser can handle the given file"""
        pass
    
    @abstractmethod
    def parse(self, file_path: str) -> ParsedStructure:
        """Parse the file and extract structure"""
        pass
    
    def get_file_type(self) -> str:
        """Return the file type this parser handles"""
        return "unknown"