"""
Pytest configuration and shared fixtures
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List
import os
import sys

# Add app directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture
def sample_pdf_bytes():
    """Return sample PDF file bytes for testing"""
    # Minimal valid PDF structure
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
197
%%EOF"""


@pytest.fixture
def sample_extraction_result():
    """Return sample document extraction result with realistic IPAR content"""
    return {
        'doc_id': 'test_doc_123',
        'page_count': 3,
        'pages': [
            {
                'page_number': 1,
                'text': 'Hywel Dda University Health Board - Integrated Performance Assessment Report (IPAR) M12 2024-25. Executive Summary: This report presents the key performance indicators for the health board including emergency department performance, cancer pathways, and financial metrics.',
                'width': 8.5,
                'height': 11.0,
                'lines': [
                    {
                        'content': 'Hywel Dda University Health Board',
                        'bounding_box': [1.0, 1.0, 6.0, 1.5]
                    },
                    {
                        'content': 'Integrated Performance Assessment Report (IPAR)',
                        'bounding_box': [1.0, 2.0, 6.0, 2.5]
                    },
                    {
                        'content': 'M12 2024-25',
                        'bounding_box': [1.0, 3.0, 3.0, 3.5]
                    }
                ],
                'tables': []
            },
            {
                'page_number': 2,
                'text': 'Emergency Department Performance: 4-hour target achieved for 89.2% of patients (target: 95%). Cancer Services: 62-day pathway performance at 71.3% (target: 75%). Financial Position: Year-to-date deficit of £2.1M against planned deficit of £1.8M.',
                'width': 8.5,
                'height': 11.0,
                'lines': [
                    {
                        'content': 'Emergency Department Performance',
                        'bounding_box': [1.0, 1.0, 4.0, 1.5]
                    },
                    {
                        'content': '4-hour target achieved for 89.2% of patients',
                        'bounding_box': [1.0, 2.0, 5.0, 2.5]
                    }
                ],
                'tables': [
                    {
                        'row_count': 3,
                        'column_count': 3,
                        'cells': [
                            {'row_index': 0, 'column_index': 0, 'content': 'KPI'},
                            {'row_index': 0, 'column_index': 1, 'content': 'Target'},
                            {'row_index': 0, 'column_index': 2, 'content': 'Actual'},
                            {'row_index': 1, 'column_index': 0, 'content': 'ED 4-hour'},
                            {'row_index': 1, 'column_index': 1, 'content': '95%'},
                            {'row_index': 1, 'column_index': 2, 'content': '89.2%'},
                            {'row_index': 2, 'column_index': 0, 'content': 'Cancer 62-day'},
                            {'row_index': 2, 'column_index': 1, 'content': '75%'},
                            {'row_index': 2, 'column_index': 2, 'content': '71.3%'}
                        ]
                    }
                ]
            },
            {
                'page_number': 3,
                'text': 'Quality Metrics: Patient safety incidents reduced by 12% compared to previous quarter. Staff satisfaction scores improved to 7.2/10. Recommendations: Focus on ED capacity management and cancer pathway optimization.',
                'width': 8.5,
                'height': 11.0,
                'lines': [
                    {
                        'content': 'Quality Metrics',
                        'bounding_box': [1.0, 1.0, 3.0, 1.5]
                    },
                    {
                        'content': 'Patient safety incidents reduced by 12%',
                        'bounding_box': [1.0, 2.0, 5.0, 2.5]
                    }
                ],
                'tables': []
            }
        ]
    }


@pytest.fixture
def sample_chunks():
    """Return sample document chunks with realistic IPAR content"""
    return [
        {
            'id': 'e8f7a2b1c3d4e5f6789012345678901234567890abcdef1234567890abcdef12',
            'doc_id': 'test_doc_123',
            'page_no': 1,
            'offset': 0,
            'text': 'Hywel Dda University Health Board - Integrated Performance Assessment Report (IPAR) M12 2024-25. Executive Summary: This report presents the key performance indicators for the health board including emergency department performance, cancer pathways, and financial metrics.',
            'spans': [
                {'offset': 0, 'length': 35, 'type': 'title'},
                {'offset': 38, 'length': 52, 'type': 'subtitle'}
            ]
        },
        {
            'id': 'f9e8d7c6b5a4938271605948372819463728194637281946372819463728194',
            'doc_id': 'test_doc_123',
            'page_no': 2,
            'offset': 0,
            'text': 'Emergency Department Performance: 4-hour target achieved for 89.2% of patients (target: 95%). Cancer Services: 62-day pathway performance at 71.3% (target: 75%). Financial Position: Year-to-date deficit of £2.1M against planned deficit of £1.8M.',
            'spans': [
                {'offset': 0, 'length': 32, 'type': 'section_header'},
                {'offset': 95, 'length': 16, 'type': 'section_header'}
            ]
        },
        {
            'id': 'a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456',
            'doc_id': 'test_doc_123',
            'page_no': 3,
            'offset': 0,
            'text': 'Quality Metrics: Patient safety incidents reduced by 12% compared to previous quarter. Staff satisfaction scores improved to 7.2/10. Recommendations: Focus on ED capacity management and cancer pathway optimization.',
            'spans': [
                {'offset': 0, 'length': 15, 'type': 'section_header'},
                {'offset': 130, 'length': 15, 'type': 'section_header'}
            ]
        }
    ]


@pytest.fixture
def sample_chunks_with_vectors(sample_chunks):
    """Return sample chunks with embedding vectors"""
    import random
    chunks_with_vectors = []

    for chunk in sample_chunks:
        chunk_copy = chunk.copy()
        # Generate pseudo-random vector based on chunk text
        random.seed(hash(chunk['text']))
        chunk_copy['vector'] = [random.uniform(-1, 1) for _ in range(3072)]
        chunks_with_vectors.append(chunk_copy)

    return chunks_with_vectors


@pytest.fixture
def sample_document_metadata():
    """Return sample document metadata with realistic IPAR data"""
    return {
        'id': 'test_doc_123',
        'doc_id': 'test_doc_123',
        'logical_id': 'logical_abc123',
        'version': 1,
        'origin_filename': 'M12_2024-25_IPAR_Overview.pdf',
        'source_uri': 'raw/test_doc_123.pdf',
        'page_count': 3,
        'chunk_count': 3,
        'indexed_chunk_count': 3,
        'status': 'indexed',
        'created_at': '2024-01-15T10:30:00Z',
        'updated_at': '2024-01-15T10:35:00Z',
        'indexed_at': '2024-01-15T10:35:00Z',
        'is_deleted': False,
        'superseded': False,
        'doc_embedding': [0.1] * 3072,
        'near_duplicates': [],
        'kpi_tags': ['emergency_department', 'cancer_services', 'financial_performance', 'quality_metrics'],
        'title': 'M12 2024-25 IPAR Overview',
        'observed_date': '2024-01-15',
        'uploaded_by': 'test_user@hyweldda.wales.nhs.uk',
        'uploaded_at': '2024-01-15T10:30:00Z',
        'file_size': 2048576,  # 2MB
        'sha256_hash': 'test_doc_123',
        'content_type': 'application/pdf'
    }


@pytest.fixture
def sample_search_results():
    """Return sample search results"""
    return [
        {
            'id': 'chunk_1_hash',
            'doc_id': 'test_doc_123',
            'text': 'This is page 1 content. It contains important information about testing.',
            'page_no': 1,
            'origin_filename': 'test_document.pdf',
            '@search.score': 0.95,
            '@search.reranker_score': None
        },
        {
            'id': 'chunk_2_hash',
            'doc_id': 'test_doc_123',
            'text': 'Page 2 discusses methodologies and best practices for comprehensive testing.',
            'page_no': 2,
            'origin_filename': 'test_document.pdf',
            '@search.score': 0.88,
            '@search.reranker_score': None
        },
        {
            'id': 'chunk_5_hash',
            'doc_id': 'test_doc_456',
            'text': 'Another document about testing frameworks and tools.',
            'page_no': 1,
            'origin_filename': 'frameworks.pdf',
            '@search.score': 0.82,
            '@search.reranker_score': None
        }
    ]


@pytest.fixture
def mock_blob_service_client():
    """Mock Azure Blob Storage client"""
    mock_client = Mock()
    mock_blob_client = Mock()

    mock_blob_client.upload_blob.return_value = None
    mock_blob_client.download_blob.return_value.readall.return_value = b'{"test": "data"}'
    mock_blob_client.exists.return_value = True

    mock_client.get_blob_client.return_value = mock_blob_client

    return mock_client


@pytest.fixture
def mock_cosmos_client():
    """Mock Azure Cosmos DB client"""
    mock_client = Mock()
    mock_database = Mock()
    mock_container = Mock()

    mock_container.upsert_item.side_effect = lambda x: x
    mock_container.read_item.return_value = {'id': 'test', 'data': 'value'}
    mock_container.query_items.return_value = []
    mock_container.create_item.side_effect = lambda x: x

    mock_database.get_container_client.return_value = mock_container
    mock_client.get_database_client.return_value = mock_database

    return mock_client


@pytest.fixture
def mock_document_intelligence_client():
    """Mock Azure Document Intelligence client"""
    mock_client = Mock()
    mock_poller = Mock()
    mock_result = Mock()

    # Mock page
    mock_page = Mock()
    mock_page.page_number = 1
    mock_page.width = 8.5
    mock_page.height = 11.0
    mock_page.lines = []
    mock_page.tables = None

    mock_result.pages = [mock_page]
    mock_result.content = "Sample extracted text"

    mock_poller.result.return_value = mock_result
    mock_client.begin_analyze_document.return_value = mock_poller

    return mock_client


@pytest.fixture
def mock_search_client():
    """Mock Azure AI Search client"""
    mock_client = Mock()
    mock_result = Mock()

    # Mock search results with realistic data
    mock_search_results = [
        {
            'id': 'chunk_1_hash',
            'doc_id': 'test_doc_123',
            'logical_id': 'logical_abc123',
            'title': 'Test Document',
            'origin_filename': 'test_document.pdf',
            'page_no': 1,
            'text': 'This is page 1 content. It contains important information about testing.',
            'spans': '[]',
            'observed_date': '2024-01-15',
            'kpi_tags': ['testing', 'methodology'],
            '@search.score': 0.95,
            '@search.reranker_score': None
        }
    ]

    mock_result.get_count.return_value = len(mock_search_results)
    mock_result.__iter__.return_value = iter(mock_search_results)

    mock_client.search.return_value = mock_result
    mock_client.get_document.return_value = mock_search_results[0]

    return mock_client


@pytest.fixture
def mock_search_index_client():
    """Mock Azure AI Search Index client"""
    mock_client = Mock()

    mock_client.create_index.return_value = None
    mock_client.get_index.return_value = Mock(name='test-index')
    mock_client.delete_index.return_value = None

    return mock_client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embeddings and chat"""
    mock_client = Mock()

    # Mock embeddings
    mock_embedding_response = Mock()
    mock_embedding_response.data = [Mock(embedding=[0.1] * 3072)]
    mock_client.embeddings.create.return_value = mock_embedding_response

    # Mock chat completions
    mock_chat_response = Mock()
    mock_message = Mock()
    mock_message.content = "This is a sample response from the AI."
    mock_choice = Mock()
    mock_choice.message = mock_message
    mock_chat_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_chat_response

    return mock_client


@pytest.fixture
def mock_search_service():
    """Mock SearchService with realistic search functionality"""
    mock_service = Mock()
    
    # Mock search method
    mock_search_response = {
        'query': 'test query',
        'count': 2,
        'results': [
            {
                'citation_number': 1,
                'chunk_id': 'chunk_1_hash',
                'doc_id': 'test_doc_123',
                'logical_id': 'logical_abc123',
                'title': 'Test Document',
                'origin_filename': 'test_document.pdf',
                'page_no': 1,
                'snippet': 'This is page 1 content...',
                'text': 'This is page 1 content. It contains important information about testing.',
                'observed_date': '2024-01-15',
                'kpi_tags': ['testing', 'methodology'],
                'score': 0.95,
                'reranker_score': None,
                'thumb_url': 'https://storage.blob.core.windows.net/thumbs/test_doc_123/p1.png?sas=token'
            },
            {
                'citation_number': 2,
                'chunk_id': 'chunk_2_hash',
                'doc_id': 'test_doc_123',
                'logical_id': 'logical_abc123',
                'title': 'Test Document',
                'origin_filename': 'test_document.pdf',
                'page_no': 2,
                'snippet': 'Page 2 discusses methodologies...',
                'text': 'Page 2 discusses methodologies and best practices for comprehensive testing.',
                'observed_date': '2024-01-15',
                'kpi_tags': ['testing', 'methodology'],
                'score': 0.88,
                'reranker_score': None,
                'thumb_url': 'https://storage.blob.core.windows.net/thumbs/test_doc_123/p2.png?sas=token'
            }
        ],
        'filter': None
    }
    
    mock_service.search.return_value = mock_search_response
    
    # Mock get_chunk_by_id method
    mock_service.get_chunk_by_id.return_value = {
        'id': 'chunk_1_hash',
        'doc_id': 'test_doc_123',
        'title': 'Test Document',
        'page_no': 1,
        'text': 'This is page 1 content. It contains important information about testing.',
        'spans': [],
        'kpi_tags': ['testing', 'methodology']
    }
    
    # Mock search_by_document method
    mock_service.search_by_document.return_value = [
        {
            'id': 'chunk_1_hash',
            'doc_id': 'test_doc_123',
            'page_no': 1,
            'text': 'This is page 1 content. It contains important information about testing.',
            'spans': []
        }
    ]
    
    return mock_service


@pytest.fixture
def mock_chat_service():
    """Mock ChatService with realistic chat functionality"""
    mock_service = Mock()
    
    # Mock chat method
    mock_chat_response = {
        'response': 'Based on the available documents, the key performance indicators include emergency department waiting times and cancer treatment pathways [Doc 1].',
        'sources': [
            {
                'citation_number': 1,
                'chunk_id': 'chunk_1_hash',
                'doc_id': 'test_doc_123',
                'title': 'Test Document',
                'origin_filename': 'test_document.pdf',
                'page_no': 1,
                'text': 'This is page 1 content. It contains important information about testing.',
                'score': 0.95
            }
        ],
        'usage': {
            'prompt_tokens': 150,
            'completion_tokens': 50,
            'total_tokens': 200
        },
        'model': 'gpt-4o-mini',
        'finish_reason': 'stop',
        'query': 'What are the key performance indicators?'
    }
    
    mock_service.chat.return_value = mock_chat_response
    
    # Mock stream_chat method (generator)
    def mock_stream_generator():
        yield {'type': 'content', 'content': 'Based on the available documents, '}
        yield {'type': 'content', 'content': 'the key performance indicators include '}
        yield {'type': 'content', 'content': 'emergency department waiting times [Doc 1].'}
        yield {'type': 'sources', 'sources': mock_chat_response['sources']}
    
    mock_service.stream_chat.return_value = mock_stream_generator()
    
    return mock_service


@pytest.fixture
def mock_all_azure_services(
    mock_blob_service_client,
    mock_cosmos_client,
    mock_document_intelligence_client,
    mock_search_client,
    mock_search_index_client,
    mock_openai_client
):
    """Mock all Azure services at once"""
    with patch('app.services.storage_service.blob_service_client', mock_blob_service_client), \
         patch('app.services.cosmos_service.cosmos_client', mock_cosmos_client), \
         patch('app.services.extraction_service.doc_intel_client', mock_document_intelligence_client), \
         patch('app.services.search_service.search_client', mock_search_client), \
         patch('app.services.search_index_service.search_index_client', mock_search_index_client), \
         patch('app.services.embedding_service.openai_client', mock_openai_client):

        yield {
            'blob': mock_blob_service_client,
            'cosmos': mock_cosmos_client,
            'doc_intel': mock_document_intelligence_client,
            'search': mock_search_client,
            'search_index': mock_search_index_client,
            'openai': mock_openai_client
        }


@pytest.fixture
def mock_all_services(mock_search_service, mock_chat_service):
    """Mock all application services"""
    return {
        'search_service': mock_search_service,
        'chat_service': mock_chat_service
    }


@pytest.fixture
def app():
    """Create Flask app for testing"""
    from app import create_app

    app = create_app()
    app.config['TESTING'] = True

    yield app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create CLI test runner"""
    return app.test_cli_runner()


# Markers for different test categories
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests for multiple components"
    )
    config.addinivalue_line(
        "markers", "system: System tests for end-to-end workflows"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take a long time to run"
    )
    config.addinivalue_line(
        "markers", "azure: Tests that require Azure services (skip in CI)"
    )


# Utility functions for generating test data
def create_mock_pdf_file():
    """Helper to create a mock PDF file for testing"""
    from io import BytesIO
    return BytesIO(b'%PDF-1.4\nfake pdf content\n%%EOF')


def create_sample_vector(dimension=3072, seed=None):
    """Helper to create a sample embedding vector"""
    import random
    if seed is not None:
        random.seed(seed)
    return [random.uniform(-1, 1) for _ in range(dimension)]


def generate_test_doc_id(filename: str = "test_document.pdf") -> str:
    """Generate a deterministic document ID for testing"""
    import hashlib
    return hashlib.sha256(filename.encode()).hexdigest()


def generate_test_chunk_id(doc_id: str, page_no: int, text: str) -> str:
    """Generate a deterministic chunk ID for testing"""
    import hashlib
    chunk_data = f"{doc_id}_{page_no}_{text[:256]}"
    return hashlib.sha256(chunk_data.encode()).hexdigest()


def create_test_extraction_result(doc_id: str, page_count: int = 3) -> Dict[str, Any]:
    """Create a test extraction result with specified parameters"""
    pages = []
    for i in range(1, page_count + 1):
        pages.append({
            'page_number': i,
            'text': f'This is page {i} content with test data for document {doc_id}.',
            'width': 8.5,
            'height': 11.0,
            'lines': [
                {
                    'content': f'Page {i} header',
                    'bounding_box': [1.0, 1.0, 6.0, 1.5]
                }
            ],
            'tables': [] if i % 2 == 1 else [
                {
                    'row_count': 2,
                    'column_count': 2,
                    'cells': [
                        {'row_index': 0, 'column_index': 0, 'content': 'Header 1'},
                        {'row_index': 0, 'column_index': 1, 'content': 'Header 2'},
                        {'row_index': 1, 'column_index': 0, 'content': 'Data 1'},
                        {'row_index': 1, 'column_index': 1, 'content': 'Data 2'}
                    ]
                }
            ]
        })
    
    return {
        'doc_id': doc_id,
        'page_count': page_count,
        'pages': pages
    }


def create_test_chunks(doc_id: str, page_count: int = 3) -> List[Dict[str, Any]]:
    """Create test chunks for a document"""
    chunks = []
    for i in range(1, page_count + 1):
        text = f'This is page {i} content with test data for document {doc_id}.'
        chunk_id = generate_test_chunk_id(doc_id, i, text)
        
        chunks.append({
            'id': chunk_id,
            'doc_id': doc_id,
            'page_no': i,
            'offset': 0,
            'text': text,
            'spans': [
                {'offset': 0, 'length': 12, 'type': 'section_header'}
            ]
        })
    
    return chunks


def create_test_document_metadata(
    doc_id: str,
    filename: str = "test_document.pdf",
    status: str = "indexed"
) -> Dict[str, Any]:
    """Create test document metadata"""
    return {
        'id': doc_id,
        'doc_id': doc_id,
        'logical_id': f'logical_{doc_id[:8]}',
        'version': 1,
        'origin_filename': filename,
        'source_uri': f'raw/{doc_id}.pdf',
        'page_count': 3,
        'chunk_count': 3,
        'indexed_chunk_count': 3 if status == 'indexed' else 0,
        'status': status,
        'created_at': '2024-01-15T10:30:00Z',
        'updated_at': '2024-01-15T10:35:00Z',
        'indexed_at': '2024-01-15T10:35:00Z' if status == 'indexed' else None,
        'is_deleted': False,
        'superseded': False,
        'doc_embedding': create_sample_vector(seed=hash(doc_id)),
        'near_duplicates': [],
        'kpi_tags': ['test_tag'],
        'title': filename.replace('.pdf', ''),
        'observed_date': '2024-01-15',
        'uploaded_by': 'test_user@hyweldda.wales.nhs.uk',
        'uploaded_at': '2024-01-15T10:30:00Z',
        'file_size': 1024000,
        'sha256_hash': doc_id,
        'content_type': 'application/pdf'
    }


def create_mock_search_results(query: str, count: int = 3) -> Dict[str, Any]:
    """Create mock search results for testing"""
    results = []
    for i in range(count):
        doc_id = f'test_doc_{i+1}'
        results.append({
            'citation_number': i + 1,
            'chunk_id': f'chunk_{i+1}_hash',
            'doc_id': doc_id,
            'logical_id': f'logical_{doc_id}',
            'title': f'Test Document {i+1}',
            'origin_filename': f'test_document_{i+1}.pdf',
            'page_no': 1,
            'snippet': f'This is a snippet from document {i+1}...',
            'text': f'This is the full text content from document {i+1} that matches the query.',
            'observed_date': '2024-01-15',
            'kpi_tags': ['test_tag'],
            'score': 0.9 - (i * 0.1),
            'reranker_score': None,
            'thumb_url': f'https://storage.blob.core.windows.net/thumbs/{doc_id}/p1.png?sas=token'
        })
    
    return {
        'query': query,
        'count': count,
        'results': results,
        'filter': None
    }


def create_mock_chat_response(query: str, source_count: int = 2) -> Dict[str, Any]:
    """Create mock chat response for testing"""
    sources = []
    for i in range(source_count):
        sources.append({
            'citation_number': i + 1,
            'chunk_id': f'chunk_{i+1}_hash',
            'doc_id': f'test_doc_{i+1}',
            'title': f'Test Document {i+1}',
            'origin_filename': f'test_document_{i+1}.pdf',
            'page_no': 1,
            'text': f'Source text from document {i+1}',
            'score': 0.9 - (i * 0.1)
        })
    
    return {
        'response': f'Based on the available documents, here is the answer to: {query} [Doc 1, Doc 2]',
        'sources': sources,
        'usage': {
            'prompt_tokens': 150,
            'completion_tokens': 50,
            'total_tokens': 200
        },
        'model': 'gpt-4o-mini',
        'finish_reason': 'stop',
        'query': query
    }
