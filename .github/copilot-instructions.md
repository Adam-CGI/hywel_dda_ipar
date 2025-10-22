# Hywel Dda IPAR Document Miner - AI Agent Instructions

## Project Overview

This is a Flask-based RAG (Retrieval-Augmented Generation) application for processing NHS IPAR documents. The system ingests PDFs, extracts text, creates vector embeddings, and enables semantic search with page-level citations.

## Core Architecture

### Service-Oriented Architecture
- **Routes Layer**: `app/routes/documents.py` - Single blueprint (`documents_bp`) handling all document operations
- **Service Layer**: `app/services/` - Each Azure service wrapped in dedicated service classes
- **Pipeline Pattern**: `IndexingPipelineService` orchestrates: extract → chunk → embed → index
- **Template Layer**: HTMX + Tailwind CSS for dynamic UI without JavaScript, base template provides navigation

### Key Data Flow
1. PDF upload → SHA256 doc_id generation (exact duplicate detection)
2. Azure Document Intelligence extraction → text + page thumbnails  
3. LlamaIndex chunking with deterministic chunk_ids
4. Azure OpenAI embeddings (text-embedding-3-large, 3072 dimensions)
5. Azure AI Search indexing with hybrid search (vector + keyword)

### Critical Identifiers
```python
doc_id = sha256(file_bytes)  # Exact duplicate detection
logical_id = sha256(normalized_text)  # Content-based duplicate detection  
chunk_id = sha256(doc_id + page_no + start_offset + text[:256])  # Deterministic chunking
```

## Development Workflows

### Local Development
```bash
# Standard workflow
make install  # pip install -r requirements.txt
make run      # python app.py (runs on port 8000)
make test     # pytest tests/ -v

# Document testing  
make upload FILE=path/to/test.pdf  # Curl-based upload test
```

### Environment Setup
- Copy `.env` template with 15+ Azure service connection strings
- All Azure clients initialized in `app/config.py` with get_*_client() factory methods
- Required: Storage, Search, OpenAI, Document Intelligence, Cosmos DB connection strings
- **Python 3.11+** required; recommend virtual environment setup:
  ```bash
  python -m venv .venv
  .venv\Scripts\activate  # Windows
  ```

### Testing Patterns
- **Epic-based tests**: `test_epic_b.py` (ingestion), `test_epic_c.py` (chunking/embeddings)
- **Integration verification**: Scripts in `scripts/` verify live Azure service connections
- **Determinism testing**: Chunking and embedding reproducibility validation
- **Coverage**: Run with `pytest tests/ -v --cov=app` for coverage reporting
- **All tests cover EPICs A-G**: Each feature group has dedicated test file

## Azure Services Integration

### Storage Containers (sthdipardev)
```
raw/          # Original PDFs (SHA256 named)
extracted/    # Document Intelligence JSON output  
thumbs/       # Page thumbnails for citations
manifests/    # Processing metadata
archive/      # Deleted document archive
```

### Cosmos DB Collections (ipar database)
- `documents` - Document metadata and lineage tracking
- `events` - Processing audit trail
- `lineage` - Document version relationships  
- `users` - User access control (future)

### Search Index Schema (ipar-chunks)
- Vector field: 3072-dimension embeddings with HNSW profile "veconf"
- Filterable: doc_id, logical_id, version, page_no
- Searchable: title, origin_filename, text content

## Project-Specific Conventions

### Directory Organization
```
app/
├── config.py          # Azure client factories & environment config
├── routes/            # Flask blueprints (currently documents_bp only)
├── services/          # Business logic layer (one service per Azure service)
├── templates/         # HTMX templates with base.html navigation
└── models/            # Data models (currently empty)
```

### Naming Conventions
- **Files**: snake_case, services end with `_service.py`, tests start with `test_`
- **Azure Resources**: `{service}-hdipar-{env}` pattern (e.g., `ais-hdipar-dev`)
- **Variables**: snake_case for Python, UPPER_CASE for environment variables

### Service Initialization Pattern
```python
# In routes - services instantiated at module level
storage_service = StorageService()
extraction_service = ExtractionService()
# All services follow this pattern for singleton-like behavior
```

### Error Handling Convention
- Services return structured dicts with success/error status
- Pipeline failures logged but don't halt processing completely
- Cosmos events track all processing attempts for debugging

### Hybrid Search Implementation
- `SearchService.hybrid_search()` combines vector and keyword search
- Results include page-level citations with thumbnail links
- Chat service (`ChatService`) implements RAG with strict source citation requirements

### HTMX Frontend Pattern
- **Base Template**: `templates/base.html` provides navigation and Tailwind CSS
- **Dynamic Updates**: HTMX handles UI updates without JavaScript
- **Partial Templates**: `document_table_rows.html` for dynamic content updates
- **Target Deployment**: Azure App Service Linux B1 tier

## Key Debugging Points

### Common Issues
- **Embedding dimension mismatches**: Verify 3072-dim vectors (text-embedding-3-large)
- **Search index creation**: Index auto-created on first upload, check `SearchIndexService.create_index()`
- **Duplicate detection**: Both exact (file hash) and logical (content hash) systems in play

### Verification Scripts
- `scripts/verify_embeddings.py` - Test embedding generation and search connectivity
- `scripts/verify_indexed_vectors.py` - Validate search index vector storage
- `scripts/test_hybrid_search.py` - End-to-end search functionality testing
- `scripts/debug_upload.py` - Debug document upload issues
- `scripts/recreate_index.py` - Recreate search index from scratch

### Deployment
- PowerShell script: `deploy_hdipar_delta.ps1` provisions full Azure infrastructure
- Idempotent deployment with resource existence checks
- App Service deployment uses managed identity for Azure service access

## File Patterns to Know

- **All services**: Instantiate Azure clients in constructor, implement business logic methods
- **Route handlers**: Minimal logic, delegate to services, return JSON responses  
- **Templates**: HTMX-based with Tailwind CSS, server-side rendering for document management UI
- **Configuration**: Environment-driven with sensible defaults (see `app/config.py`)

## Key Technology Stack

### Core Dependencies
- **Flask 3.0.0** + **Python 3.11+** for web framework
- **LlamaIndex 0.10.12** for document chunking and processing
- **HTMX 1.9.10** + **Tailwind CSS** for dynamic frontend without JavaScript
- **Azure SDK suite**: blob storage, cosmos, search, openai, document intelligence

### Development Tools
- **pytest** with coverage for testing
- **Makefile** for standardized commands
- **PowerShell** deployment scripts for Azure infrastructure provisioning

This is a production healthcare system handling sensitive documents - prioritize data integrity, audit trails, and deterministic processing in all modifications.