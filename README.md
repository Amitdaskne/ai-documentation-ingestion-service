# AI-Powered Documentation Ingestion Service

An intelligent service for ingesting documentation packages and generating reusable, versioned export templates with full provenance tracking.

## 🚀 Features

- **Multi-format Support**: Ingest PDF specifications with CSV, XML, JSON, and Excel sample files
- **AI-Powered Analysis**: Automatically extract field definitions, data types, and relationships
- **Template Generation**: Create machine-readable JSON Schema templates with confidence scoring
- **Provenance Tracking**: Full audit trail linking every inferred field to source documents
- **Version Management**: Immutable versioning with change history
- **Multiple Export Formats**: JSON Schema, XSD, CSV mappings, and HTML reports
- **RESTful API**: Complete API for integration with external systems
- **Web Interface**: User-friendly frontend for package upload and template management

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   Database      │
│   (React)       │◄──►│   Backend       │◄──►│   (SQLite)      │
│   Port 59420    │    │   Port 51955    │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   AI Pipeline   │
                    │   - PDF Parser  │
                    │   - File Parser │
                    │   - Template    │
                    │     Generator   │
                    └─────────────────┘
```

## 📋 Requirements

- Python 3.8+
- Node.js 16+ (for frontend)
- SQLite (included)

## 🛠️ Installation & Quick Start

### Backend Setup

1. **Install dependencies**:
```bash
pip install fastapi uvicorn python-multipart sqlalchemy pydantic pydantic-settings python-dotenv aiofiles PyMuPDF pandas openpyxl lxml jsonschema reportlab
```

2. **Start the backend**:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 51955 --reload
```

### Frontend Setup

1. **Install and start frontend**:
```bash
cd frontend
npm install
npm run dev
```

### Access the Application

- **Web Interface**: http://localhost:59420
- **API Documentation**: http://localhost:51955/docs
- **API Base URL**: http://localhost:51955/api/v1

## 🎯 Usage

### Web Interface

1. Open http://localhost:59420 in your browser
2. Upload a documentation package (PDF + sample files)
3. Review the generated template with confidence scores
4. Download templates in various formats

### API Usage

#### Upload Documentation Package

```bash
curl -X POST \
  -H "Authorization: Bearer dev-api-key" \
  -F "files=@spec.pdf" \
  -F "files=@sample.csv" \
  -F "files=@sample.json" \
  -F "format_name=My Format" \
  -F "format_version=1.0" \
  http://localhost:51955/api/v1/formats/upload
```

#### List Formats

```bash
curl -H "Authorization: Bearer dev-api-key" \
  http://localhost:51955/api/v1/formats
```

#### Get Template Details

```bash
curl -H "Authorization: Bearer dev-api-key" \
  http://localhost:51955/api/v1/templates/{template_id}
```

#### Download Template

```bash
curl -H "Authorization: Bearer dev-api-key" \
  "http://localhost:51955/api/v1/templates/{template_id}/download?type=json_schema" \
  -o template.json
```

## 📊 Data Model

### Core Entities

- **Format**: Represents a documentation format (e.g., "Customer Data Format")
- **Template**: Versioned schema generated from a format
- **Field**: Individual field definitions with provenance
- **SourceFile**: Original uploaded files with metadata
- **ProcessingJob**: Async job tracking for uploads

### Template Structure

Each generated template includes:

- **JSON Schema**: Primary machine-readable format
- **Field Definitions**: Canonical names, types, constraints
- **Provenance**: Source file references and confidence scores
- **Examples**: Sample values extracted from source files
- **Relationships**: Field dependencies and hierarchies

## 🔧 API Reference

### Authentication

All API endpoints require authentication via Bearer token:

```
Authorization: Bearer dev-api-key
```

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/formats/upload` | Upload documentation package |
| GET | `/api/v1/formats` | List all formats |
| GET | `/api/v1/formats/{id}` | Get format details |
| GET | `/api/v1/formats/{id}/templates` | List format templates |
| GET | `/api/v1/templates/{id}` | Get template details |
| POST | `/api/v1/templates/{id}/approve` | Approve template |
| POST | `/api/v1/templates/{id}/edit` | Edit template |
| GET | `/api/v1/templates/{id}/download` | Download template |
| POST | `/api/v1/templates/validate` | Validate data against template |
| GET | `/api/v1/files/{id}` | Download original file |

### Export Types

- `json_schema`: JSON Schema format (default)
- `xsd`: XML Schema Definition
- `mapping_csv`: Field mapping CSV
- `report`: HTML report with full details

## 🧠 AI Processing Pipeline

### 1. File Parsing
- **PDF**: Extract text using PyMuPDF with OCR fallback
- **CSV**: Parse with pandas, detect delimiters and encodings
- **JSON**: Parse and flatten nested structures
- **XML**: Parse with lxml, extract elements and attributes
- **Excel**: Read all sheets, handle multiple formats

### 2. Field Extraction
- Identify field names from structured files
- Extract sample values and detect data types
- Calculate statistics (min/max, length, patterns)
- Detect enumerations and constraints

### 3. Template Generation
- Reconcile PDF specifications with sample data
- Generate canonical field names
- Assign confidence scores based on evidence
- Create JSON Schema with full validation rules
- Track provenance for every inference

### 4. Quality Assurance
- Confidence scoring for all inferences
- Provenance tracking to source documents
- Validation against sample data
- Human review and approval workflow

## 📈 Confidence Scoring

The system assigns confidence scores (0.0-1.0) based on:

- **Source Agreement**: Multiple files containing same field
- **Type Consistency**: Consistent data types across samples
- **PDF Evidence**: Field mentioned in specification document
- **Pattern Recognition**: Standard naming conventions
- **Validation Success**: Sample data validates against schema

## 🧪 Testing

### Sample Data

The repository includes test data in `/test_data/`:
- `customer_data_format_spec.pdf`: Sample specification
- `sample_customers.csv`: Customer data
- `sample_orders.json`: Order data
- `sample_products.xml`: Product catalog

### Running Tests

```bash
# Test API endpoints
curl -X POST -H "Authorization: Bearer dev-api-key" \
  -F "files=@test_data/sample_customers.csv" \
  -F "format_name=Test Format" \
  http://localhost:51955/api/v1/formats/upload

# Validate generated template
curl -H "Authorization: Bearer dev-api-key" \
  http://localhost:51955/api/v1/formats
```

## 🔒 Security Features

- API key authentication
- Input validation and sanitization
- File type restrictions
- Size limits on uploads
- SQL injection protection
- XSS prevention in frontend

## 🚀 Production Deployment

### Environment Variables

```bash
DATABASE_URL=sqlite:///./doc_ingestion.db
SECRET_KEY=your-secret-key
API_KEY_HEADER=X-API-Key
DEFAULT_API_KEY=your-api-key
DEBUG=false
HOST=0.0.0.0
PORT=51955
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 51955
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "51955"]
```

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the API documentation at http://localhost:51955/docs
2. Review the sample data and examples
3. Open an issue on GitHub