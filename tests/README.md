# Test Suite for Hywel Dda IPAR Document Miner

This directory contains a comprehensive test suite for the Hywel Dda IPAR Document Miner application, organized into unit, integration, and system test categories with full Azure service mocking.

## Test Structure

```
tests/
├── unit/                                    # Unit tests (isolated components)
│   ├── test_chunking_service.py            # Document chunking and ID generation
│   ├── test_cosmos_service.py              # Cosmos DB operations and metadata
│   ├── test_embedding_service.py           # Vector embeddings and similarity
│   ├── test_extraction_service.py          # PDF extraction and thumbnails
│   ├── test_storage_service.py             # Blob storage and SHA256 operations
│   ├── test_search_service.py              # Hybrid search and citations
│   └── test_chat_service.py                # RAG chat with grounding
├── integration/                             # Integration tests (multi-service)
│   ├── test_full_pipeline_integration.py   # Complete processing pipeline
│   ├── test_search_retrieval_integration.py # Search and result formatting
│   ├── test_rag_chat_integration.py        # Chat with search integration
│   └── test_api_endpoints_integration.py   # Flask routes with services
├── system/                                  # System tests (end-to-end)
│   └── test_end_to_end_workflows.py        # Complete user workflows
├── conftest.py                              # Shared fixtures and mocks
├── pytest.ini                              # Pytest configuration
└── README.md                               # This documentation
```

## Test Categories and Organization

### Unit Tests (`tests/unit/`) - Fast, Isolated Testing
Unit tests validate individual service methods in complete isolation using mocked dependencies. Each service has comprehensive coverage of public methods, error conditions, and edge cases.

**Coverage Target**: >90% for service layer methods  
**Execution Time**: <100ms per test  
**Mocking Strategy**: All external dependencies mocked

#### Service Test Files:
- **test_chunking_service.py**: 
  - Deterministic chunk ID generation using SHA256
  - Page-based chunking with offset tracking
  - Text preprocessing and validation
  - Edge cases: empty text, large documents, special characters

- **test_cosmos_service.py**:
  - Document CRUD operations (create, read, update, delete)
  - Event logging and lineage tracking
  - Version management and duplicate detection
  - Query operations and filtering

- **test_embedding_service.py**:
  - Text embedding generation with Azure OpenAI
  - Batch processing and rate limiting
  - Vector similarity computation
  - Near-duplicate detection algorithms

- **test_extraction_service.py**:
  - PDF text extraction using Document Intelligence
  - Thumbnail generation from PDF pages
  - Manifest creation with metadata
  - Error handling for corrupted/invalid PDFs

- **test_storage_service.py**:
  - Blob upload/download operations across containers
  - SHA256 computation and logical ID generation
  - SAS URL generation with expiration
  - Blob archival and cleanup operations

- **test_search_service.py**:
  - Hybrid search combining vector and keyword search
  - Result ranking and pagination
  - Citation generation with page references
  - Search query preprocessing and validation

- **test_chat_service.py**:
  - RAG chat with document grounding
  - Citation extraction from responses
  - Conversation context management
  - Error handling for API failures

### Integration Tests (`tests/integration/`) - Multi-Service Workflows
Integration tests validate multiple services working together with selective mocking of external Azure services only.

**Coverage Target**: >85% for multi-service workflows  
**Execution Time**: <1s per test  
**Mocking Strategy**: Azure services mocked, internal services real

#### Integration Test Files:
- **test_full_pipeline_integration.py**:
  - Complete document processing: PDF → extraction → chunking → embedding → indexing
  - Error handling and rollback in multi-step processing
  - Data transformation validation between service layers
  - Performance testing with various document sizes

- **test_search_retrieval_integration.py**:
  - Hybrid search functionality with vector and keyword components
  - Result ranking, pagination, and citation generation
  - Search index updates and document deletion from index
  - Search performance with different query types

- **test_rag_chat_integration.py**:
  - Chat service integration with search service
  - Document grounding and citation generation
  - Conversation flow with multiple turns
  - Error recovery and fallback responses

- **test_api_endpoints_integration.py**:
  - Flask route handlers with service layer integration
  - Request/response handling and validation
  - Error propagation from services to API responses
  - Authentication and authorization (if implemented)

### System Tests (`tests/system/`) - End-to-End Workflows
System tests validate complete user workflows from start to finish with all Azure services mocked.

**Coverage Target**: >80% for route handlers and workflows  
**Execution Time**: <10s per test  
**Mocking Strategy**: All Azure services mocked, full application stack tested

#### System Test Files:
- **test_end_to_end_workflows.py**:
  - Complete document lifecycle: upload → process → index → search → chat → delete
  - Document versioning and duplicate detection workflows
  - Error recovery and cleanup in complete workflows
  - User interaction patterns and UI workflows

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install -r requirements-test.txt
```

Ensure you have Python 3.11+ and a virtual environment activated:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### Basic Test Execution

**Run all tests with coverage:**
```bash
pytest
```

**Run all tests without coverage (faster):**
```bash
pytest --no-cov
```

**Run tests in parallel (if pytest-xdist installed):**
```bash
pytest -n auto
```

### Test Categories

**Unit tests only (fast, isolated):**
```bash
pytest tests/unit/
```

**Integration tests only (moderate speed):**
```bash
pytest tests/integration/
```

**System tests only (slower, comprehensive):**
```bash
pytest tests/system/
```

### Test Markers

The test suite uses markers for fine-grained test selection:

**By test type:**
```bash
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m system        # System tests only
```

**By functionality:**
```bash
pytest -m chunking      # Chunking-related tests
pytest -m embedding     # Embedding-related tests
pytest -m search        # Search-related tests
pytest -m chat          # Chat-related tests
pytest -m storage       # Storage-related tests
pytest -m cosmos        # Cosmos DB-related tests
pytest -m extraction    # Extraction-related tests
pytest -m api           # API endpoint tests
```

**By performance:**
```bash
pytest -m "not slow"    # Skip slow tests (>1s)
pytest -m slow          # Run only slow tests
```

**Combine markers:**
```bash
pytest -m "unit and chunking"           # Unit tests for chunking only
pytest -m "integration or system"       # All integration and system tests
pytest -m "not (slow or azure)"         # Fast tests, no Azure dependencies
```

### Specific Test Execution

**Run specific test file:**
```bash
pytest tests/unit/test_extraction_service.py
```

**Run specific test class:**
```bash
pytest tests/unit/test_extraction_service.py::TestExtractDocument
```

**Run specific test method:**
```bash
pytest tests/unit/test_extraction_service.py::TestExtractDocument::test_extract_document_success
```

**Run tests matching pattern:**
```bash
pytest -k "test_chunk"              # All tests with 'chunk' in name
pytest -k "not test_error"          # Exclude error tests
pytest -k "embedding and success"   # Tests with both keywords
```

### Coverage Reporting

**HTML coverage report (detailed):**
```bash
pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

**Terminal coverage report:**
```bash
pytest --cov=app --cov-report=term-missing
```

**XML coverage report (for CI):**
```bash
pytest --cov=app --cov-report=xml
```

**Coverage with branch analysis:**
```bash
pytest --cov=app --cov-branch --cov-report=term-missing
```

**Set coverage threshold:**
```bash
pytest --cov=app --cov-fail-under=80
```

### Verbose Output and Debugging

**Verbose mode (show test names):**
```bash
pytest -v
```

**Extra verbose (show test docstrings):**
```bash
pytest -vv
```

**Show print statements and logs:**
```bash
pytest -s
```

**Show local variables on failure:**
```bash
pytest --showlocals
```

**Show slowest tests:**
```bash
pytest --durations=10
```

**Stop on first failure:**
```bash
pytest -x
```

**Drop into debugger on failure:**
```bash
pytest --pdb
```

### Performance and Optimization

**Run tests in parallel:**
```bash
pytest -n auto  # Auto-detect CPU cores
pytest -n 4     # Use 4 processes
```

**Profile test execution:**
```bash
pytest --profile
```

**Memory usage profiling:**
```bash
pytest --memray  # If pytest-memray installed
```

## Test Fixtures and Mocking Strategy

The `conftest.py` file provides comprehensive shared fixtures for consistent testing across all test categories.

### Core Data Fixtures

**Sample Data Generation:**
- `sample_pdf_bytes`: Minimal valid PDF structure for testing (247 bytes)
- `sample_extraction_result`: Realistic Document Intelligence extraction output with pages, tables, and text
- `sample_chunks`: Deterministic document chunks with consistent IDs and metadata
- `sample_chunks_with_vectors`: Chunks enhanced with embedding vectors for search testing
- `sample_document_metadata`: Complete document metadata for Cosmos DB operations
- `sample_search_results`: Realistic search response structure with scores and citations

**Utility Data:**
- `sample_chat_messages`: Conversation history for chat testing
- `sample_embeddings`: Consistent vector embeddings for similarity testing
- `sample_thumbnails`: Base64-encoded thumbnail data for PDF pages

### Azure Service Mocks

**Comprehensive Service Mocking:**
- `mock_blob_service_client`: Complete Azure Blob Storage operations
  - Upload/download with progress tracking
  - Container management and SAS URL generation
  - Blob metadata and properties handling
  - Error simulation for network/auth failures

- `mock_cosmos_client`: Full Cosmos DB functionality
  - Document CRUD operations with realistic responses
  - Query operations with filtering and pagination
  - Event logging and lineage tracking
  - Conflict resolution and retry logic

- `mock_document_intelligence_client`: Document Intelligence simulation
  - PDF analysis with realistic extraction results
  - Page layout, text, and table detection
  - Error handling for unsupported formats
  - Processing status and polling simulation

- `mock_search_client`: Azure AI Search operations
  - Index creation, updating, and deletion
  - Document upload with batch processing
  - Hybrid search with vector and keyword components
  - Result ranking and pagination

- `mock_openai_client`: OpenAI API simulation
  - Text embedding generation with consistent vectors
  - Chat completions with realistic responses
  - Rate limiting and error handling
  - Token usage tracking

### Application Fixtures

**Flask Application Setup:**
- `app`: Flask application instance with test configuration
- `client`: Flask test client for API endpoint testing
- `app_context`: Application context for service testing

**Service Fixtures:**
- `mock_all_services`: All service mocks configured together for system tests
- Individual service fixtures for unit testing (e.g., `mock_extraction_service`)

### Fixture Usage Patterns

**Automatic Fixture Application:**
```python
# Fixtures are automatically applied based on test markers
@pytest.mark.unit
def test_service_method():
    # All Azure services automatically mocked
    pass

@pytest.mark.integration  
def test_workflow():
    # External services mocked, internal services real
    pass
```

**Explicit Fixture Usage:**
```python
def test_with_specific_data(sample_chunks, mock_cosmos_client):
    # Use specific fixtures as needed
    pass
```

**Fixture Customization:**
```python
def test_custom_scenario(sample_chunks):
    # Modify fixture data for specific test needs
    sample_chunks[0]['text'] = 'Custom test content'
    # Test with modified data
```

## Writing New Tests

### Test Structure and Patterns

All tests follow the **Arrange-Act-Assert (AAA)** pattern with clear separation of concerns and comprehensive error testing.

### Unit Test Examples

**Basic Service Method Testing:**
```python
import pytest
from unittest.mock import Mock, patch
from app.services.chunking_service import ChunkingService

class TestChunkingService:
    """Unit tests for ChunkingService class."""
    
    def test_generate_chunk_id_deterministic(self):
        """Test that same input generates same chunk ID."""
        # Arrange
        service = ChunkingService()
        doc_id = "test_doc"
        page_no = 1
        offset = 0
        text = "Sample chunk text"
        
        # Act
        chunk_id_1 = service._generate_chunk_id(doc_id, page_no, offset, text)
        chunk_id_2 = service._generate_chunk_id(doc_id, page_no, offset, text)
        
        # Assert
        assert chunk_id_1 == chunk_id_2
        assert isinstance(chunk_id_1, str)
        assert len(chunk_id_1) == 64  # SHA256 hex length
    
    @patch('app.services.chunking_service.LlamaIndex')
    def test_chunk_page_with_mocked_dependency(self, mock_llama_index):
        """Test page chunking with external dependency mocked."""
        # Arrange
        service = ChunkingService()
        mock_llama_index.chunk_text.return_value = [
            {"text": "Chunk 1", "start": 0, "end": 50},
            {"text": "Chunk 2", "start": 51, "end": 100}
        ]
        
        # Act
        result = service.chunk_page("Sample page text", "doc123", 1)
        
        # Assert
        assert len(result) == 2
        assert all('id' in chunk for chunk in result)
        mock_llama_index.chunk_text.assert_called_once()
    
    def test_chunk_page_error_handling(self):
        """Test error handling for invalid input."""
        # Arrange
        service = ChunkingService()
        
        # Act & Assert
        with pytest.raises(ValueError, match="Text cannot be empty"):
            service.chunk_page("", "doc123", 1)
```

**Testing with Fixtures:**
```python
class TestExtractionService:
    """Unit tests for ExtractionService with fixtures."""
    
    def test_extract_document_success(
        self, 
        mock_document_intelligence_client,
        sample_pdf_bytes,
        sample_extraction_result
    ):
        """Test successful document extraction."""
        # Arrange
        service = ExtractionService()
        mock_document_intelligence_client.begin_analyze_document.return_value.result.return_value = sample_extraction_result
        
        # Act
        result = service.extract_document(sample_pdf_bytes, "test.pdf")
        
        # Assert
        assert result['status'] == 'success'
        assert 'pages' in result['extraction_data']
        assert len(result['thumbnails']) > 0
```

### Integration Test Examples

**Multi-Service Workflow Testing:**
```python
class TestDocumentProcessingPipeline:
    """Integration tests for document processing pipeline."""
    
    def test_full_pipeline_success(
        self,
        mock_extraction_service,
        mock_chunking_service, 
        mock_embedding_service,
        sample_pdf_bytes,
        sample_chunks
    ):
        """Test complete pipeline with real service interactions."""
        # Arrange
        pipeline = IndexingPipelineService()
        
        # Configure mocks for successful flow
        mock_extraction_service.process_document.return_value = {
            "status": "success",
            "extraction_data": {"pages": [{"text": "Sample text"}]}
        }
        mock_chunking_service.chunk_document.return_value = sample_chunks
        mock_embedding_service.embed_chunks.return_value = sample_chunks
        
        # Act
        result = pipeline.process_document(sample_pdf_bytes, "test.pdf")
        
        # Assert
        assert result['status'] == 'success'
        assert result['chunks_processed'] == len(sample_chunks)
        
        # Verify service interactions
        mock_extraction_service.process_document.assert_called_once()
        mock_chunking_service.chunk_document.assert_called_once()
        mock_embedding_service.embed_chunks.assert_called_once()
    
    def test_pipeline_error_recovery(self, mock_services_with_errors):
        """Test error handling and recovery in pipeline."""
        # Arrange
        pipeline = IndexingPipelineService()
        mock_services_with_errors.extraction_service.process_document.side_effect = Exception("Extraction failed")
        
        # Act
        result = pipeline.process_document(b"invalid_pdf", "test.pdf")
        
        # Assert
        assert result['status'] == 'error'
        assert 'Extraction failed' in result['error_message']
```

### System Test Examples

**End-to-End Workflow Testing:**
```python
class TestCompleteWorkflows:
    """System tests for complete user workflows."""
    
    def test_document_upload_to_search_workflow(self, client, mock_all_azure_services):
        """Test complete workflow: upload → process → search."""
        # Arrange
        test_file_data = {
            'file': (io.BytesIO(b'%PDF-1.4 test content'), 'test.pdf', 'application/pdf')
        }
        
        # Act - Upload document
        upload_response = client.post('/api/documents/upload', data=test_file_data)
        
        # Act - Search for document
        search_response = client.get('/api/documents/search?q=test')
        
        # Assert
        assert upload_response.status_code == 200
        upload_data = upload_response.get_json()
        assert upload_data['status'] == 'success'
        
        assert search_response.status_code == 200
        search_data = search_response.get_json()
        assert len(search_data['results']) > 0
    
    def test_chat_with_document_context(self, client, mock_all_azure_services):
        """Test chat functionality with document grounding."""
        # Arrange - Upload document first
        upload_response = client.post('/api/documents/upload', data=test_file_data)
        doc_id = upload_response.get_json()['doc_id']
        
        # Act - Chat about the document
        chat_response = client.post('/api/chat', json={
            'message': 'What is this document about?',
            'doc_id': doc_id
        })
        
        # Assert
        assert chat_response.status_code == 200
        chat_data = chat_response.get_json()
        assert 'response' in chat_data
        assert 'citations' in chat_data
        assert len(chat_data['citations']) > 0
```

### Test Naming Conventions

**Class Names:**
- `TestServiceName` for unit tests
- `TestWorkflowName` for integration tests  
- `TestCompleteWorkflows` for system tests

**Method Names:**
- `test_method_name_success` - Happy path testing
- `test_method_name_error_handling` - Error condition testing
- `test_method_name_edge_cases` - Boundary condition testing
- `test_method_name_validation` - Input validation testing

**Descriptive Test Names:**
```python
def test_generate_chunk_id_deterministic_with_same_input(self):
def test_extract_document_handles_corrupted_pdf_gracefully(self):
def test_search_returns_empty_results_for_nonexistent_query(self):
def test_chat_service_includes_citations_in_response(self):
```

## Mocking Strategy and Best Practices

### Azure Service Mocking Philosophy

All Azure services are comprehensively mocked to ensure tests are:
- **Fast**: No network calls or external dependencies
- **Reliable**: No flaky failures due to service availability
- **Isolated**: Tests don't affect real resources
- **Consistent**: Deterministic responses for reproducible results

### Service-Specific Mocking Patterns

**Azure Blob Storage (`mock_blob_service_client`):**
```python
# Realistic blob operations with metadata
mock_blob_client.upload_blob.return_value = Mock(
    url="https://storage.blob.core.windows.net/container/blob",
    etag="0x8D9A1B2C3D4E5F6",
    last_modified=datetime.utcnow()
)

# Error simulation for testing resilience
mock_blob_client.download_blob.side_effect = [
    BlobNotFoundError("Blob not found"),  # First call fails
    Mock(readall=lambda: b"file content")  # Retry succeeds
]
```

**Azure Cosmos DB (`mock_cosmos_client`):**
```python
# Document operations with realistic responses
mock_container.create_item.return_value = {
    "id": "doc123",
    "_rid": "abc123",
    "_ts": 1640995200,
    "_etag": "\"0x8D9A1B2C3D4E5F6\""
}

# Query operations with pagination
mock_container.query_items.return_value = iter([
    {"id": "doc1", "status": "indexed"},
    {"id": "doc2", "status": "processing"}
])
```

**Document Intelligence (`mock_document_intelligence_client`):**
```python
# Realistic extraction results
mock_poller = Mock()
mock_poller.result.return_value = Mock(
    pages=[
        Mock(
            page_number=1,
            lines=[Mock(content="Sample text line 1")],
            tables=[Mock(cells=[Mock(content="Cell 1")])]
        )
    ]
)
mock_client.begin_analyze_document.return_value = mock_poller
```

**Azure AI Search (`mock_search_client`):**
```python
# Search results with realistic scoring
mock_search_client.search.return_value = [
    {
        "@search.score": 0.95,
        "id": "chunk123",
        "content": "Relevant document content",
        "doc_id": "doc123",
        "page_no": 1
    }
]
```

**OpenAI API (`mock_openai_client`):**
```python
# Consistent embeddings for testing
mock_openai_client.embeddings.create.return_value = Mock(
    data=[Mock(embedding=[0.1, 0.2, 0.3] * 512)]  # 1536-dim vector
)

# Chat responses with citations
mock_openai_client.chat.completions.create.return_value = Mock(
    choices=[Mock(
        message=Mock(content="Response with [doc123:1] citation")
    )]
)
```

### Mock Configuration Patterns

**Automatic Mock Application by Test Type:**
```python
# conftest.py automatically applies mocks based on markers
@pytest.fixture(autouse=True)
def auto_mock_azure_services(request):
    """Automatically mock Azure services for unit tests."""
    if 'unit' in request.keywords:
        # Apply all Azure service mocks
        with patch('app.config.get_blob_service_client') as mock_blob, \
             patch('app.config.get_cosmos_client') as mock_cosmos:
            yield
```

**Selective Mocking for Integration Tests:**
```python
# Integration tests mock external services only
@pytest.fixture
def mock_external_services_only():
    """Mock only external Azure services, keep internal services real."""
    with patch('app.config.get_openai_client') as mock_openai, \
         patch('app.config.get_document_intelligence_client') as mock_di:
        yield {
            'openai': mock_openai,
            'document_intelligence': mock_di
        }
```

**Error Injection for Resilience Testing:**
```python
@pytest.fixture
def mock_services_with_errors():
    """Mock services that simulate various error conditions."""
    mock_service = Mock()
    mock_service.process.side_effect = [
        Exception("Temporary failure"),  # First call fails
        {"status": "success"}           # Second call succeeds
    ]
    return mock_service
```

### Advanced Mocking Techniques

**Stateful Mocks for Complex Workflows:**
```python
class StatefulBlobMock:
    def __init__(self):
        self.uploaded_blobs = {}
    
    def upload_blob(self, name, data):
        self.uploaded_blobs[name] = data
        return Mock(url=f"https://storage/{name}")
    
    def download_blob(self, name):
        if name in self.uploaded_blobs:
            return Mock(readall=lambda: self.uploaded_blobs[name])
        raise BlobNotFoundError(f"Blob {name} not found")
```

**Mock Validation and Assertions:**
```python
def test_service_calls_azure_correctly(mock_blob_service_client):
    # Act
    service.upload_document(b"content", "test.pdf")
    
    # Assert mock was called correctly
    mock_blob_service_client.upload_blob.assert_called_once_with(
        name="test.pdf",
        data=b"content",
        overwrite=True
    )
    
    # Verify call order for complex workflows
    expected_calls = [
        call.upload_blob(name="test.pdf", data=b"content"),
        call.set_blob_metadata(name="test.pdf", metadata={"processed": "true"})
    ]
    mock_blob_service_client.assert_has_calls(expected_calls, any_order=False)
```

## Test Coverage Goals and Quality Metrics

### Coverage Targets by Module

**Service Layer (Primary Business Logic):**
- Target: >90% line coverage, >85% branch coverage
- Critical: 100% coverage for core workflows (document processing, search, chat)
- Focus: All public methods, error handling, edge cases

**Route Handlers (API Layer):**
- Target: >85% line coverage, >80% branch coverage  
- Critical: All endpoints, request validation, error responses
- Focus: HTTP status codes, request/response formats, authentication

**Overall Application:**
- Target: >80% line coverage, >75% branch coverage
- Minimum: No module below 70% coverage
- Exclusions: Configuration files, migrations, scripts

### Coverage Monitoring and Reporting

**Automated Coverage Checking:**
```bash
# Fail build if coverage drops below threshold
pytest --cov=app --cov-fail-under=80

# Generate multiple report formats
pytest --cov=app \
       --cov-report=html:htmlcov \
       --cov-report=xml:coverage.xml \
       --cov-report=term-missing
```

**Coverage Report Analysis:**
```bash
# View missing lines in terminal
pytest --cov=app --cov-report=term-missing

# Generate detailed HTML report
pytest --cov=app --cov-report=html
# Open htmlcov/index.html for interactive analysis

# Branch coverage analysis
pytest --cov=app --cov-branch --cov-report=term-missing
```

### Quality Metrics and Standards

**Test Performance Targets:**
- Unit tests: <100ms per test (target: <50ms)
- Integration tests: <1s per test (target: <500ms)  
- System tests: <10s per test (target: <5s)
- Full suite: <60s total execution time

**Test Reliability Standards:**
- Flaky test rate: <1% (target: 0%)
- Test isolation: No shared state between tests
- Deterministic results: Same input always produces same output
- Error clarity: Clear failure messages with actionable information

**Code Quality Metrics:**
- Test code coverage: >95% of test code should be executed
- Assertion density: Average 2-4 assertions per test
- Mock usage: <50% of test code should be mock setup
- Documentation: All test classes and complex tests documented

### Coverage Exclusions and Exceptions

**Automatically Excluded:**
```python
# In pytest.ini and .coveragerc
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError", 
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:"
]
```

**Justified Low Coverage Areas:**
- Configuration files (`app/config.py`): Infrastructure code
- Error handling for impossible conditions: Defensive programming
- Debug/development utilities: Non-production code
- Third-party integration glue: Thin wrapper code

### Continuous Monitoring

**Coverage Trend Tracking:**
```bash
# Store coverage history for trend analysis
pytest --cov=app --cov-report=json:coverage.json
# Parse JSON for CI/CD dashboard integration
```

**Quality Gates:**
- Pull requests must maintain or improve coverage
- New code must have >90% coverage
- Critical path changes require 100% coverage
- Coverage regressions >5% require justification

## Continuous Integration and Automation

### CI/CD Pipeline Integration

Tests are designed to run in automated pipelines without requiring Azure credentials or external dependencies.

**GitHub Actions Example:**
```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-test.txt
    
    - name: Run unit tests
      run: pytest tests/unit/ -v --cov=app --cov-report=xml
    
    - name: Run integration tests  
      run: pytest tests/integration/ -v
    
    - name: Run system tests
      run: pytest tests/system/ -v
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
```

**Azure DevOps Pipeline Example:**
```yaml
trigger:
- main
- develop

pool:
  vmImage: 'ubuntu-latest'

variables:
  pythonVersion: '3.11'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '$(pythonVersion)'
  displayName: 'Use Python $(pythonVersion)'

- script: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    pip install -r requirements-test.txt
  displayName: 'Install dependencies'

- script: |
    pytest tests/ --junitxml=test-results.xml --cov=app --cov-report=xml --cov-report=html
  displayName: 'Run tests with coverage'

- task: PublishTestResults@2
  inputs:
    testResultsFiles: 'test-results.xml'
    testRunTitle: 'Python $(pythonVersion) Test Results'
  condition: succeededOrFailed()

- task: PublishCodeCoverageResults@1
  inputs:
    codeCoverageTool: 'Cobertura'
    summaryFileLocation: 'coverage.xml'
    reportDirectory: 'htmlcov'
```

### Pre-commit Hooks

**Setup pre-commit hooks for local development:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-unit
        name: pytest-unit
        entry: pytest tests/unit/ -x -v
        language: system
        pass_filenames: false
        always_run: true
      
      - id: pytest-coverage
        name: pytest-coverage-check
        entry: pytest tests/unit/ --cov=app --cov-fail-under=80
        language: system
        pass_filenames: false
        always_run: true
```

**Install and activate:**
```bash
pip install pre-commit
pre-commit install
```

### Test Environment Configuration

**Environment Variables for CI:**
```bash
# Set in CI/CD environment
export FLASK_ENV=testing
export TESTING=true
export AZURE_MOCK_MODE=true
export LOG_LEVEL=WARNING
```

**Test-specific Configuration:**
```python
# app/config.py
class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    AZURE_MOCK_MODE = True
    LOG_LEVEL = 'WARNING'
    
    # Disable external service calls
    AZURE_STORAGE_CONNECTION_STRING = 'mock://storage'
    COSMOS_DB_ENDPOINT = 'mock://cosmos'
    OPENAI_API_KEY = 'mock-key'
```

## Troubleshooting Common Issues

### Import and Path Issues

**Import Errors:**
```bash
# Error: ModuleNotFoundError: No module named 'app'
# Solution: Ensure conftest.py is properly configured
# conftest.py automatically adds app directory to Python path
```

**Relative Import Issues:**
```python
# Problem: ImportError: attempted relative import with no known parent package
# Solution: Use absolute imports in test files
from app.services.chunking_service import ChunkingService  # Correct
from ..services.chunking_service import ChunkingService    # Incorrect
```

### Mocking Problems

**Mock Not Taking Effect:**
```python
# Problem: Mock not working
@patch('external_library.function')  # Wrong - patches at definition point
def test_function(mock_func):
    pass

# Solution: Patch at point of use
@patch('app.services.my_service.external_library.function')  # Correct
def test_function(mock_func):
    pass
```

**Mock Configuration Issues:**
```python
# Problem: Mock returns Mock object instead of expected value
mock_service.method.return_value = Mock()  # Returns Mock object

# Solution: Return actual expected data
mock_service.method.return_value = {"status": "success"}  # Returns dict
```

**Side Effect vs Return Value:**
```python
# For single return value
mock_service.method.return_value = "result"

# For multiple calls or exceptions
mock_service.method.side_effect = ["result1", "result2", Exception("error")]

# For callable behavior
mock_service.method.side_effect = lambda x: f"processed_{x}"
```

### Test Environment Issues

**Tests Passing Locally but Failing in CI:**
```python
# Problem: Hardcoded paths
file_path = "C:\\Users\\dev\\project\\test.pdf"  # Windows-specific

# Solution: Use relative paths and os.path
import os
file_path = os.path.join(os.path.dirname(__file__), "test.pdf")
```

**Timezone and Date Issues:**
```python
# Problem: Tests fail in different timezones
from datetime import datetime
now = datetime.now()  # Local timezone

# Solution: Use UTC consistently
from datetime import datetime, timezone
now = datetime.now(timezone.utc)  # UTC timezone
```

**Missing Test Dependencies:**
```bash
# Problem: ModuleNotFoundError for test-specific packages
# Solution: Install test requirements
pip install -r requirements-test.txt

# Or install specific packages
pip install pytest pytest-cov pytest-mock
```

### Performance and Reliability Issues

**Slow Tests:**
```python
# Problem: Tests taking too long
def test_slow_operation():
    time.sleep(5)  # Don't do this
    
# Solution: Mock time-consuming operations
@patch('time.sleep')
def test_fast_operation(mock_sleep):
    # Test logic without actual delay
    pass
```

**Flaky Tests:**
```python
# Problem: Tests sometimes pass, sometimes fail
def test_flaky():
    result = random.choice([True, False])  # Non-deterministic
    assert result

# Solution: Use deterministic test data
def test_reliable():
    with patch('random.choice', return_value=True):
        result = random.choice([True, False])
        assert result
```

**Memory Issues with Large Test Data:**
```python
# Problem: Tests consuming too much memory
@pytest.fixture
def large_data():
    return [generate_large_object() for _ in range(10000)]  # Memory intensive

# Solution: Use generators or smaller datasets
@pytest.fixture  
def large_data():
    def _generate():
        for i in range(100):  # Smaller, representative dataset
            yield generate_small_object(i)
    return _generate()
```

### Azure Service Mock Issues

**Authentication Errors in Tests:**
```python
# Problem: Tests trying to authenticate with Azure
# Solution: Ensure mocks are applied before service initialization
@pytest.fixture(autouse=True)
def mock_azure_auth():
    with patch('azure.identity.DefaultAzureCredential'):
        yield
```

**Service Client Configuration:**
```python
# Problem: Real Azure clients being created
# Solution: Mock client factory functions
@patch('app.config.get_blob_service_client')
@patch('app.config.get_cosmos_client')
def test_with_mocked_clients(mock_cosmos, mock_blob):
    # Test code here
    pass
```

### Debugging Test Failures

**Verbose Test Output:**
```bash
# Show detailed test output
pytest -vv -s tests/unit/test_chunking_service.py

# Show local variables on failure
pytest --showlocals tests/unit/test_chunking_service.py

# Drop into debugger on failure
pytest --pdb tests/unit/test_chunking_service.py
```

**Logging in Tests:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)

def test_with_logging():
    logger = logging.getLogger(__name__)
    logger.debug("Test debug information")
    # Test code
```

**Test Data Inspection:**
```python
def test_debug_data(sample_chunks):
    import pprint
    pprint.pprint(sample_chunks)  # Inspect fixture data
    # Test code
```

## Best Practices and Guidelines

### Test Design Principles

**1. Test Isolation and Independence**
```python
# Good: Each test is completely independent
def test_chunk_generation():
    service = ChunkingService()  # Fresh instance
    result = service.chunk_text("test")
    assert len(result) > 0

def test_chunk_id_generation():
    service = ChunkingService()  # Fresh instance  
    chunk_id = service.generate_id("test", 1, 0, "text")
    assert isinstance(chunk_id, str)

# Bad: Tests depend on shared state
class TestChunkingService:
    def setup_method(self):
        self.service = ChunkingService()
        self.service.cache = {}  # Shared state
    
    def test_first(self):
        self.service.cache['key'] = 'value'  # Modifies shared state
    
    def test_second(self):
        assert 'key' in self.service.cache  # Depends on first test
```

**2. Clear and Descriptive Test Naming**
```python
# Good: Names describe what is being tested
def test_generate_chunk_id_returns_consistent_hash_for_same_input(self):
def test_extract_document_raises_exception_for_corrupted_pdf(self):
def test_search_service_returns_empty_results_for_nonexistent_query(self):

# Bad: Vague or unclear names
def test_chunk_id(self):
def test_extraction(self):
def test_search(self):
```

**3. Arrange-Act-Assert (AAA) Pattern**
```python
def test_chunk_document_success(self):
    # Arrange - Set up test data and mocks
    service = ChunkingService()
    document_text = "This is a sample document for testing chunking."
    doc_id = "test_doc_123"
    
    # Act - Execute the method being tested
    result = service.chunk_document(document_text, doc_id)
    
    # Assert - Verify the expected outcomes
    assert isinstance(result, list)
    assert len(result) > 0
    assert all('id' in chunk for chunk in result)
    assert all(chunk['doc_id'] == doc_id for chunk in result)
```

**4. Comprehensive Error Testing**
```python
# Test both success and failure scenarios
def test_extract_document_success(self, mock_document_intelligence):
    # Test successful extraction
    pass

def test_extract_document_handles_invalid_pdf(self, mock_document_intelligence):
    # Test error handling for invalid input
    mock_document_intelligence.side_effect = Exception("Invalid PDF")
    with pytest.raises(DocumentExtractionError):
        service.extract_document(b"invalid", "test.pdf")

def test_extract_document_handles_service_timeout(self, mock_document_intelligence):
    # Test timeout handling
    mock_document_intelligence.side_effect = TimeoutError("Service timeout")
    result = service.extract_document(b"valid_pdf", "test.pdf")
    assert result['status'] == 'error'
    assert 'timeout' in result['error_message'].lower()
```

**5. Effective Mock Usage**
```python
# Good: Mock external dependencies, test real logic
@patch('app.services.extraction_service.DocumentIntelligenceClient')
def test_extract_document_processes_pages_correctly(self, mock_client):
    # Mock external service
    mock_client.return_value.analyze_document.return_value = sample_extraction_result
    
    # Test real service logic
    service = ExtractionService()
    result = service.extract_document(sample_pdf_bytes, "test.pdf")
    
    # Verify real processing logic
    assert result['page_count'] == 2
    assert len(result['thumbnails']) == 2

# Bad: Over-mocking internal logic
@patch('app.services.extraction_service.ExtractionService.process_pages')
def test_extract_document(self, mock_process):
    mock_process.return_value = "mocked_result"
    # This doesn't test any real logic
```

### Performance Guidelines

**6. Keep Tests Fast and Focused**
```python
# Good: Fast, focused unit test
def test_generate_chunk_id_deterministic(self):
    service = ChunkingService()
    chunk_id = service._generate_chunk_id("doc", 1, 0, "text")
    assert len(chunk_id) == 64

# Bad: Slow test with unnecessary operations
def test_generate_chunk_id_deterministic(self):
    service = ChunkingService()
    # Don't do expensive setup for simple tests
    large_text = "x" * 1000000  # Unnecessary large data
    time.sleep(0.1)  # Unnecessary delays
    chunk_id = service._generate_chunk_id("doc", 1, 0, large_text)
    assert len(chunk_id) == 64
```

**7. Efficient Fixture Usage**
```python
# Good: Reuse fixtures for common data
def test_chunk_processing(sample_chunks):
    # Use shared fixture data
    assert len(sample_chunks) > 0

def test_chunk_validation(sample_chunks):
    # Reuse same fixture
    for chunk in sample_chunks:
        assert 'id' in chunk

# Bad: Recreate data in each test
def test_chunk_processing():
    chunks = [{"id": "1", "text": "test"}]  # Duplicated setup
    assert len(chunks) > 0

def test_chunk_validation():
    chunks = [{"id": "1", "text": "test"}]  # Duplicated setup
    for chunk in chunks:
        assert 'id' in chunk
```

### Code Quality Standards

**8. Readable and Maintainable Test Code**
```python
# Good: Clear, well-documented test
def test_search_service_hybrid_search_combines_vector_and_keyword_results(
    self, 
    mock_search_client,
    sample_search_results
):
    """
    Test that hybrid search properly combines vector similarity and keyword matching.
    
    This test verifies that:
    1. Both vector and keyword searches are performed
    2. Results are properly merged and ranked
    3. Duplicate results are deduplicated
    """
    # Arrange
    service = SearchService()
    query = "test query"
    mock_search_client.search.return_value = sample_search_results
    
    # Act
    results = service.hybrid_search(query, top_k=10)
    
    # Assert
    assert len(results) <= 10  # Respects top_k limit
    assert all('score' in result for result in results)  # All results have scores
    # Verify search was called for both vector and keyword
    assert mock_search_client.search.call_count == 2
```

**9. Appropriate Test Coverage**
```python
# Good: Test public interface and critical paths
class TestChunkingService:
    def test_chunk_document_public_method(self):
        # Test main public method
        pass
    
    def test_chunk_document_error_handling(self):
        # Test critical error paths
        pass

# Don't test: Private methods unless they contain complex logic
# Don't test: Simple getters/setters
# Don't test: Third-party library behavior
```

**10. Documentation and Comments**
```python
# Good: Document complex test scenarios
def test_document_processing_pipeline_handles_partial_failures(self):
    """
    Test pipeline resilience when some services fail.
    
    Scenario: Extraction succeeds, chunking fails, embedding not attempted.
    Expected: Pipeline returns partial results with error details.
    """
    # Test implementation
    pass

# Good: Explain non-obvious assertions
def test_chunk_id_generation(self):
    chunk_id = service.generate_chunk_id("doc", 1, 0, "text")
    assert len(chunk_id) == 64  # SHA256 produces 64 hex characters
    assert chunk_id.isalnum()   # Should only contain alphanumeric characters
```

## Resources and References

### Documentation
- **[Pytest Documentation](https://docs.pytest.org/)** - Comprehensive pytest guide
- **[unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)** - Python mocking library
- **[Flask Testing](https://flask.palletsprojects.com/en/latest/testing/)** - Flask-specific testing patterns
- **[Azure SDK Testing](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/core/azure-core/tests)** - Azure SDK test examples

### Testing Philosophy
- **[Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)** - Martin Fowler's testing strategy
- **[Testing Best Practices](https://docs.python-guide.org/writing/tests/)** - Python testing guide
- **[Mocking Best Practices](https://realpython.com/python-mock-library/)** - Effective mocking strategies

### Tools and Extensions
- **pytest-cov** - Coverage reporting
- **pytest-mock** - Enhanced mocking capabilities  
- **pytest-xdist** - Parallel test execution
- **pytest-benchmark** - Performance testing
- **pytest-html** - HTML test reports

### Project-Specific Resources
- **Application Architecture**: See `architecture-diagram.md`
- **Service Documentation**: Individual service docstrings in `app/services/`
- **API Documentation**: Route handler docstrings in `app/routes/`
- **Configuration Guide**: Environment setup in `app/config.py`
