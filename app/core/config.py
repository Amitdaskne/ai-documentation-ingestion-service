from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./doc_ingestion.db"
    
    # Security
    secret_key: str = "dev-secret-key"
    api_key_header: str = "X-API-Key"
    default_api_key: str = "dev-api-key"
    
    # File Storage
    upload_dir: str = "./uploads"
    max_file_size: str = "100MB"
    
    # AI/ML
    spacy_model: str = "en_core_web_sm"
    confidence_threshold: float = 0.7
    
    # Server
    host: str = "0.0.0.0"
    port: int = 51955
    debug: bool = True
    
    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:51955,http://localhost:59420"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    def get_allowed_origins(self) -> List[str]:
        """Parse allowed origins from comma-separated string"""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    def get_max_file_size_bytes(self) -> int:
        """Convert max_file_size string to bytes"""
        size_str = self.max_file_size.upper()
        if size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.upload_dir, exist_ok=True)