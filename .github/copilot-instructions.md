# Hywel Dda IPAR Document Miner - AI Agent Instructions

## Project Overview

Flask-based RAG system for NHS IPAR documents. Ingests PDFs, extracts text with Azure Document Intelligence, chunks with LlamaIndex, embeds with Azure OpenAI (text-embedding-3-large, 3072-dim), and indexes in Azure AI Search for hybrid search + page-level citations.

## Critical Architecture Decisions

### Directory Structure with Shim Pattern (IMPORTANT!)
**Single Flask app in `flask_app/` with root-level shims for backward compatibility:**

```
flask_app/ (PRIMARY - all business logic lives here):
├── application.py       # WSGI entry (Azure auto-detects)
├── config.py            # Azure clients & env config
├── services/            # Business logic (relative imports: from services.x import)
├── routes/              # Flask blueprints
└── templates/           # HTMX + Tailwind templates

Root shims (for test/script compatibility):
├── config.py            # Re-exports from flask_app.config
├── services/            # Re-exports from flask_app.services/*
└── run.py               # Dev entry (imports from app, which doesn't exist - broken)
```

**Import patterns by location:**
- **`flask_app/`**: Relative imports (`from services.x import Y`, `from config import Z`)
- **`scripts/`**: Full path (`from flask_app.services.x import Y`)
- **`tests/`**: Legacy imports (`from app.services.x import Y`) - requires `services/` shims

**When editing code:** Always edit files in `flask_app/`. Root `services/` files are shims only.

### Service-Oriented Pipeline Pattern
- **Routes** (`flask_app/routes/documents.py`): Module-level service instantiation (singleton pattern)
```python
storage_service = StorageService()  # Instantiated once at module load
extraction_service = ExtractionService()
```
- **Services** (`flask_app/services/`): Each wraps one Azure SDK, initialized with client factories from `config.py`
- **Orchestration**: `IndexingPipelineService` chains: extract → chunk → embed → index
- **Temporal Metadata**: `DateParserService` extracts date from filenames (pattern: `_DD-MM-YY.pdf`)
- **Error Handling**: Services return `{"success": bool, "error": str, ...}` dicts, pipeline logs failures but continues

### Deterministic Identifiers (Critical for Deduplication)
```python
doc_id = sha256(file_bytes)  # Exact duplicate detection (file-level)
logical_id = sha256(normalized_text)  # Content duplicate (ignores whitespace)
chunk_id = sha256(doc_id + page_no + start_offset + text[:256])  # Reproducible chunking
```
**Why:** Enables idempotent reprocessing, version tracking, and duplicate detection without Cosmos queries

## Development Workflows

### Local Development (Windows PowerShell)
```powershell
# Setup
cd flask_app  # Always work from flask_app/ for deployment-ready code
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Configure Azure connection strings (15+ required)

# Run locally (development server)
python application.py  # Runs on port 8000, auto-reload enabled

# Run with production server (Gunicorn - Linux/WSL only)
gunicorn --bind=0.0.0.0:8000 --timeout 600 application:app
```

### Testing Strategy
```powershell
# From repository root (NOT flask_app/)
# Tests import from app.services.* which uses root shims → flask_app.services

pytest tests/test_epic_b.py -v  # Ingestion pipeline (integration - hits API)
pytest tests/test_epic_c.py -v  # Chunking & embeddings (unit tests)
pytest tests/test_epic_f.py -v  # Hybrid search
pytest tests/test_epic_g.py -v  # RAG chat with citations

# Note: pytest.ini has --cov=app but app/ doesn't exist - coverage will fail
# Use --no-cov for quick runs:
pytest tests/test_epic_c.py -v --no-cov
```

**Test patterns:**
- Tests use `from app.services.*` imports (resolved via root `services/` shims)
- Use `@pytest.mark.integration` for Azure service tests
- Epic-based test files map to feature requirements (EPIC B-G)

### Debugging & Verification Scripts
Located in `scripts/`, import from `flask_app.services`:
```powershell
python scripts/verify_embeddings.py        # Test embedding generation + search connectivity
python scripts/verify_indexed_vectors.py   # Validate search index vector storage
python scripts/test_hybrid_search.py       # End-to-end search test
python scripts/debug_upload.py             # Debug document upload pipeline
python scripts/recreate_index.py           # Recreate search index from scratch
python scripts/test_temporal_queries.py    # Test date-based filtering
```

## Azure Services Integration

### Required Environment Variables (~15)
See `flask_app/.env.example` for full list. Key groups:
- **Storage**: `AZURE_STORAGE_CONNSTR`, containers: raw/extracted/thumbs/manifests/archive
- **AI Search**: `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_ADMIN_KEY`, index: `ipar-chunks`
- **OpenAI**: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, deployments: `text-embedding-3-large`, `gpt-4o-mini`
- **Document Intelligence**: `AZURE_DOCINTEL_ENDPOINT`, `AZURE_DOCINTEL_KEY`
- **Cosmos DB**: `COSMOS_ENDPOINT`, `COSMOS_KEY`, database: `ipar`

### Storage Containers (sthdipardev)
```
raw/          # Original PDFs (SHA256-named)
extracted/    # Document Intelligence JSON output  
thumbs/       # Page thumbnails (doc_id/pN.png)
manifests/    # Processing metadata
archive/      # Soft-deleted documents
```

### Cosmos DB Schema (ipar database)
- `documents` - Document metadata + lineage (partition key: `doc_id`)
- `events` - Processing audit trail (partition key: `doc_id`)
- `lineage` - Version relationships (partition key: `logical_id`)

### Search Index Schema (ipar-chunks)
- **Vector field**: 3072-dim embeddings, HNSW profile "veconf"
- **Filterable**: `doc_id`, `logical_id`, `page_no`, `year`, `quarter`, `fiscal_year`
- **Temporal**: `document_date`, `year`, `month`, `quarter`, `fiscal_year` (extracted from filename)

## Project-Specific Conventions

### Service Pattern
```python
# Each service wraps ONE Azure SDK
class StorageService:
    def __init__(self):
        self.blob_client = get_blob_service_client()  # from config.py

# Services return dict responses
def upload_to_raw(...) -> dict:
    return {"success": True, "doc_id": "...", "blob_url": "..."}
    # or: {"success": False, "error": "reason"}
```

### RAG Chat Implementation
`ChatService` (flask_app/services/chat_service.py) implements RAG with:
- System prompt enforcing source-only responses
- Inline citations format: `[Doc 1]`, `[Doc 2, Doc 3]`
- Few-shot examples for consistent output
- Never adds sources section (UI displays separately)

### HTMX Frontend
- `templates/base.html`: 3000+ line file with Tailwind CSS, animations, all styling
- Dynamic updates via HTMX attributes, minimal JavaScript
- Partial templates for AJAX updates (e.g., `document_table_rows.html`)

## Key Files

| Purpose | File |
|---------|------|
| App entry (Azure) | `flask_app/application.py` |
| Azure clients | `flask_app/config.py` |
| Upload pipeline | `flask_app/routes/documents.py` |
| Orchestration | `flask_app/services/indexing_pipeline_service.py` |
| Hybrid search | `flask_app/services/search_service.py` |
| RAG chat | `flask_app/services/chat_service.py` |
| Date parsing | `flask_app/services/date_parser_service.py` |

## Technology Stack

- **Flask 3.0** + Python 3.11+
- **LlamaIndex** for chunking (512 tokens, 128 overlap)
- **HTMX 1.9** + Tailwind CSS (no build step)
- **Azure SDK**: blob storage, cosmos, search, openai, document intelligence

This is a production healthcare system - prioritize data integrity, audit trails, and deterministic processing.