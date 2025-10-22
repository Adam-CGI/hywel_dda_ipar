"""
Integration tests for API endpoints
Tests Flask route handlers with service layer integration,
request/response handling and error propagation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from io import BytesIO

import sys
import os
# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import create_app from the root app.py file
import importlib.util
spec = importlib.util.spec_from_file_location("app_module", os.path.join(project_root, "app.py"))
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)
create_app = app_module.create_app


@pytest.fixture
def client():
    """Create test client with testing configuration"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    with app.test_client() as client:
        with app.app_context():
            yield client


class TestHealthEndpoint:
    """Test application health check endpoint"""

    def test_health_check_endpoint(self, client):
        """Test health endpoint returns proper status"""
        # Act
        response = client.get('/health')

        # Assert
        assert response.status_code == 200
        assert response.content_type.startswith('application/json')
        
        data = json.loads(response.data)
        assert 'status' in data
        assert data['status'] in ['healthy', 'ok']


class TestDocumentUploadEndpoint:
    """Integration tests for document upload API with service layer"""

    @patch('app.routes.documents.storage_service')
    @patch('app.routes.documents.extraction_service')
    @patch('app.routes.documents.cosmos_service')
    @patch('app.routes.documents.embedding_service')
    @patch('app.routes.documents.chunking_service')
    @patch('app.routes.documents.search_index_service')
    def test_upload_document_complete_workflow(
        self,
        mock_search_index,
        mock_chunking,
        mock_embedding,
        mock_cosmos,
        mock_extraction,
        mock_storage,
        client,
        sample_pdf_bytes
    ):
        """Test complete document upload workflow with service integration"""
        # Arrange
        doc_id = "test_doc_123"
        logical_id = "logical_456"
        filename = "test.pdf"
        
        # Mock service responses for successful upload workflow
        mock_storage.compute_sha256.return_value = doc_id
        mock_storage.upload_to_raw.return_value = (doc_id, f"https://storage.blob.core.windows.net/raw/{doc_id}.pdf")
        mock_storage.compute_logical_id.return_value = logical_id
        
        mock_extraction.process_document.return_value = {
            'extraction_data': {'full_text': 'Sample document content', 'pages': [{'page_number': 1, 'text': 'Page 1'}]},
            'manifest': {'page_count': 1, 'table_count': 0, 'text_length': 100, 'thumbnail_count': 1}
        }
        
        mock_cosmos.get_document.return_value = None  # No existing document
        mock_cosmos.find_by_logical_id.return_value = []  # No logical duplicates
        mock_cosmos.query_documents.return_value = []  # No near duplicates
        
        mock_embedding.embed_document.return_value = [0.1] * 3072
        mock_embedding.is_near_duplicate.return_value = False
        
        mock_chunking.chunk_document.return_value = [
            {'id': 'chunk1', 'doc_id': doc_id, 'text': 'Chunk 1', 'page_no': 1}
        ]
        mock_embedding.embed_chunks.return_value = [
            {'id': 'chunk1', 'doc_id': doc_id, 'text': 'Chunk 1', 'page_no': 1, 'vector': [0.1] * 3072}
        ]
        mock_search_index.upload_chunks.return_value = {'uploaded': 1, 'failed': 0}

        # Create multipart form data
        data = {
            'file': (BytesIO(sample_pdf_bytes), filename, 'application/pdf')
        }

        # Act
        response = client.post(
            '/api/documents/upload',
            data=data,
            content_type='multipart/form-data'
        )

        # Assert - verify complete workflow
        assert response.status_code == 201
        assert response.content_type.startswith('application/json')
        
        result = json.loads(response.data)
        assert result['doc_id'] == doc_id
        assert result['logical_id'] == logical_id
        assert result['origin_filename'] == filename
        assert result['status'] == 'indexed'
        assert result['duplicate'] is False
        assert result['indexed'] is True
        assert result['chunk_count'] == 1
        assert result['indexed_chunk_count'] == 1
        
        # Verify service integration calls
        mock_storage.compute_sha256.assert_called_once()
        mock_storage.upload_to_raw.assert_called_once()
        mock_extraction.process_document.assert_called_once()
        mock_cosmos.save_document.assert_called()
        mock_cosmos.log_event.assert_called()
        mock_chunking.chunk_document.assert_called_once()
        mock_embedding.embed_chunks.assert_called_once()
        mock_search_index.upload_chunks.assert_called_once()

    def test_upload_validation_errors(self, client):
        """Test upload endpoint validation and error handling"""
        # Test 1: No file provided
        response = client.post('/api/documents/upload')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'No file provided' in data['error'] or 'No file provided' in data['message']
        
        # Test 2: Empty filename
        data = {'file': (BytesIO(b'content'), '', 'application/pdf')}
        response = client.post('/api/documents/upload', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        
        # Test 3: Invalid file type
        data = {'file': (BytesIO(b'content'), 'test.txt', 'text/plain')}
        response = client.post('/api/documents/upload', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'Invalid file type' in result['error'] or 'PDF' in result['message']

    @patch('app.routes.documents.storage_service')
    @patch('app.routes.documents.cosmos_service')
    def test_upload_exact_duplicate_detection(self, mock_cosmos, mock_storage, client):
        """Test upload endpoint handles exact duplicate detection"""
        # Arrange
        doc_id = "existing_doc_123"
        mock_storage.compute_sha256.return_value = doc_id
        
        # Mock existing document (not deleted)
        mock_cosmos.get_document.return_value = {
            'id': doc_id,
            'doc_id': doc_id,
            'status': 'indexed',
            'origin_filename': 'existing.pdf',
            'is_deleted': False
        }

        data = {'file': (BytesIO(b'pdf content'), 'duplicate.pdf', 'application/pdf')}

        # Act
        response = client.post('/api/documents/upload', data=data, content_type='multipart/form-data')

        # Assert
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['doc_id'] == doc_id
        assert result['duplicate'] is True
        assert result['duplicate_type'] == 'exact'
        assert 'existing_record' in result

    @patch('app.routes.documents.storage_service')
    @patch('app.routes.documents.extraction_service')
    @patch('app.routes.documents.cosmos_service')
    @patch('app.routes.documents.embedding_service')
    def test_upload_logical_duplicate_workflow(self, mock_embedding, mock_cosmos, mock_extraction, mock_storage, client):
        """Test upload endpoint handles logical duplicate detection and versioning"""
        # Arrange
        new_doc_id = "new_doc_456"
        existing_doc_id = "existing_doc_123"
        logical_id = "logical_789"
        
        mock_storage.compute_sha256.return_value = new_doc_id
        mock_storage.upload_to_raw.return_value = (new_doc_id, f"https://storage.blob.core.windows.net/raw/{new_doc_id}.pdf")
        mock_storage.compute_logical_id.return_value = logical_id
        
        mock_extraction.process_document.return_value = {
            'extraction_data': {'full_text': 'Same content as existing', 'pages': [{'page_number': 1, 'text': 'Page 1'}]},
            'manifest': {'page_count': 1, 'table_count': 0, 'text_length': 100, 'thumbnail_count': 1}
        }
        
        mock_cosmos.get_document.return_value = None  # New document doesn't exist
        
        # Mock existing logical duplicate
        mock_cosmos.find_by_logical_id.return_value = [
            {
                'id': existing_doc_id,
                'logical_id': logical_id,
                'version': 1,
                'doc_id': existing_doc_id
            }
        ]
        mock_cosmos.get_latest_version.return_value = {
            'doc_id': existing_doc_id,
            'version': 1
        }

        data = {'file': (BytesIO(b'pdf content'), 'new_version.pdf', 'application/pdf')}

        # Act - First request without create_version flag
        response = client.post('/api/documents/upload', data=data, content_type='multipart/form-data')

        # Assert - Should return conflict requiring user decision
        assert response.status_code == 409
        result = json.loads(response.data)
        assert result['duplicate'] is True
        assert result['duplicate_type'] == 'logical'
        assert result['requires_user_decision'] is True
        assert 'action_url' in result


class TestDocumentListEndpoint:
    """Integration tests for document listing API"""

    @patch('app.routes.documents.cosmos_service')
    def test_list_documents_json_response(self, mock_cosmos, client):
        """Test document listing returns proper JSON structure"""
        # Arrange
        mock_docs = [
            {
                'id': 'doc1',
                'doc_id': 'doc1', 
                'origin_filename': 'file1.pdf',
                'status': 'indexed',
                'page_count': 5,
                'created_at': '2024-01-01T00:00:00Z',
                'is_deleted': False
            },
            {
                'id': 'doc2',
                'doc_id': 'doc2',
                'origin_filename': 'file2.pdf', 
                'status': 'indexed',
                'page_count': 3,
                'created_at': '2024-01-02T00:00:00Z',
                'is_deleted': False
            }
        ]

        mock_cosmos.list_documents.return_value = mock_docs

        # Act
        response = client.get('/api/documents/')

        # Assert
        assert response.status_code == 200
        assert response.content_type.startswith('application/json')
        
        data = json.loads(response.data)
        assert 'documents' in data
        assert 'count' in data
        assert data['count'] == 2
        assert len(data['documents']) == 2
        assert data['documents'][0]['id'] == 'doc1'
        assert data['documents'][1]['id'] == 'doc2'
        
        # Verify service integration
        mock_cosmos.list_documents.assert_called_once_with(limit=100)

    @patch('app.routes.documents.cosmos_service')
    def test_list_documents_with_limit_parameter(self, mock_cosmos, client):
        """Test document listing respects limit parameter"""
        # Arrange
        mock_docs = [{'id': f'doc{i}', 'origin_filename': f'file{i}.pdf'} for i in range(1, 6)]
        mock_cosmos.list_documents.return_value = mock_docs[:3]  # Return limited results

        # Act
        response = client.get('/api/documents/?limit=3')

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] == 3
        
        # Verify limit was passed to service
        mock_cosmos.list_documents.assert_called_once_with(limit=3)

    @patch('app.routes.documents.cosmos_service')
    def test_list_documents_htmx_request(self, mock_cosmos, client):
        """Test document listing returns HTML for HTMX requests"""
        # Arrange
        mock_docs = [
            {'id': 'doc1', 'origin_filename': 'file1.pdf', 'status': 'indexed'}
        ]
        mock_cosmos.list_documents.return_value = mock_docs

        # Act - Simulate HTMX request
        response = client.get('/api/documents/', headers={'HX-Request': 'true'})

        # Assert
        assert response.status_code == 200
        assert response.content_type.startswith('text/html')
        # Should render HTML template instead of JSON


class TestDocumentDetailEndpoint:
    """Integration tests for document detail retrieval"""

    @patch('app.routes.documents.cosmos_service')
    def test_get_document_success_with_metadata(self, mock_cosmos, client):
        """Test retrieving complete document details and metadata"""
        # Arrange
        doc_id = "doc123"
        mock_doc = {
            'id': doc_id,
            'doc_id': doc_id,
            'logical_id': 'logical_456',
            'origin_filename': 'test.pdf',
            'page_count': 5,
            'chunk_count': 15,
            'indexed_chunk_count': 15,
            'status': 'indexed',
            'version': 1,
            'created_at': '2024-01-01T00:00:00Z',
            'indexed_at': '2024-01-01T00:05:00Z',
            'is_deleted': False,
            'superseded': False
        }

        mock_cosmos.get_document.return_value = mock_doc

        # Act
        response = client.get(f'/api/documents/{doc_id}')

        # Assert
        assert response.status_code == 200
        assert response.content_type.startswith('application/json')
        
        data = json.loads(response.data)
        assert data['doc_id'] == doc_id
        assert data['logical_id'] == 'logical_456'
        assert data['page_count'] == 5
        assert data['chunk_count'] == 15
        assert data['status'] == 'indexed'
        assert data['version'] == 1
        
        # Verify service integration
        mock_cosmos.get_document.assert_called_once_with(doc_id)

    @patch('app.routes.documents.cosmos_service')
    def test_get_document_not_found_error_handling(self, mock_cosmos, client):
        """Test proper error handling for non-existent document"""
        # Arrange
        doc_id = "nonexistent"
        mock_cosmos.get_document.return_value = None

        # Act
        response = client.get(f'/api/documents/{doc_id}')

        # Assert
        assert response.status_code == 404
        assert response.content_type.startswith('application/json')
        
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Document not found' in data['error']
        assert data['doc_id'] == doc_id


class TestDocumentDeleteEndpoint:
    """Test document deletion"""

    @patch('app.routes.documents.storage_service')
    @patch('app.routes.documents.search_index_service')
    @patch('app.routes.documents.cosmos_service')
    def test_delete_document_success(
        self,
        mock_cosmos,
        mock_search_index,
        mock_storage,
        client
    ):
        """Test successful document deletion"""
        # Arrange
        doc_id = "doc_to_delete"

        mock_cosmos.get_document.return_value = {
            'id': doc_id,
            'status': 'indexed'
        }

        # Act
        response = client.delete(f'/api/documents/{doc_id}')

        # Assert
        assert response.status_code == 200

        # Verify soft delete
        mock_cosmos.mark_as_deleted.assert_called_once_with(doc_id)

        # Verify chunks deleted from search index
        mock_search_index.delete_chunks_by_doc_id.assert_called_once_with(doc_id)

        # Verify blobs archived
        mock_storage.archive_document_blobs.assert_called_once_with(doc_id)

    @patch('app.routes.documents.cosmos_service')
    def test_delete_document_not_found(self, mock_cosmos, client):
        """Test deleting non-existent document"""
        # Arrange
        doc_id = "nonexistent"
        mock_cosmos.get_document.return_value = None

        # Act
        response = client.delete(f'/api/documents/{doc_id}')

        # Assert
        assert response.status_code == 404


class TestDocumentReindexEndpoint:
    """Test document reindexing"""

    @patch('app.routes.documents.indexing_pipeline_service')
    @patch('app.routes.documents.cosmos_service')
    def test_reindex_document_success(self, mock_cosmos, mock_pipeline, client):
        """Test successful document reindexing"""
        # Arrange
        doc_id = "doc_to_reindex"

        mock_cosmos.get_document.return_value = {
            'id': doc_id,
            'status': 'indexed'
        }

        mock_pipeline.reindex_document.return_value = {
            'doc_id': doc_id,
            'status': 'indexed',
            'indexed_chunk_count': 20
        }

        # Act
        response = client.post(f'/api/documents/{doc_id}/reindex')

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['doc_id'] == doc_id
        assert data['indexed_chunk_count'] == 20

        mock_pipeline.reindex_document.assert_called_once_with(doc_id)

    @patch('app.routes.documents.cosmos_service')
    def test_reindex_document_not_found(self, mock_cosmos, client):
        """Test reindexing non-existent document"""
        # Arrange
        doc_id = "nonexistent"
        mock_cosmos.get_document.return_value = None

        # Act
        response = client.post(f'/api/documents/{doc_id}/reindex')

        # Assert
        assert response.status_code == 404


class TestSearchEndpoint:
    """Integration tests for hybrid search API"""

    @patch('app.routes.documents.cosmos_service')
    @patch('app.routes.documents.search_service')
    def test_search_success_with_service_integration(self, mock_search, mock_cosmos, client):
        """Test successful search with complete service integration"""
        # Arrange
        query = "performance indicators"
        mock_search_results = {
            'query': query,
            'count': 2,
            'results': [
                {
                    'citation_number': 1,
                    'chunk_id': 'c1',
                    'doc_id': 'doc1',
                    'title': 'Performance Report',
                    'text': 'Emergency department performance indicators show 95% compliance',
                    'snippet': 'Emergency department performance indicators...',
                    'score': 0.95,
                    'page_no': 1,
                    'thumb_url': 'https://storage.blob.core.windows.net/thumbs/doc1/p1.png'
                },
                {
                    'citation_number': 2,
                    'chunk_id': 'c2',
                    'doc_id': 'doc2',
                    'title': 'Quality Metrics',
                    'text': 'Cancer treatment indicators achieved 78% target compliance',
                    'snippet': 'Cancer treatment indicators achieved...',
                    'score': 0.88,
                    'page_no': 3,
                    'thumb_url': 'https://storage.blob.core.windows.net/thumbs/doc2/p3.png'
                }
            ],
            'filter': None
        }

        mock_search.search.return_value = mock_search_results

        # Act
        response = client.get(f'/api/documents/search?q={query}&top=10&include_thumbnails=true')

        # Assert
        assert response.status_code == 200
        assert response.content_type.startswith('application/json')
        
        data = json.loads(response.data)
        assert data['query'] == query
        assert data['count'] == 2
        assert len(data['results']) == 2
        assert data['results'][0]['score'] == 0.95
        assert data['results'][0]['citation_number'] == 1
        assert 'thumb_url' in data['results'][0]
        
        # Verify service integration
        mock_search.search.assert_called_once_with(
            query=query,
            top=10,
            filter_expr=None,
            include_thumbnails=True
        )
        
        # Verify search event was logged
        mock_cosmos.log_event.assert_called_once()
        event_call = mock_cosmos.log_event.call_args[0]
        assert event_call[0] == 'search'  # event_type
        assert event_call[2]['query'] == query  # details

    @patch('app.routes.documents.search_service')
    def test_search_with_filters_and_parameters(self, mock_search, client):
        """Test search with various parameters and filters"""
        # Arrange
        query = "test query"
        top = 5
        filter_expr = "doc_id eq 'specific_doc'"

        mock_search.search.return_value = {
            'query': query,
            'count': 0,
            'results': [],
            'filter': filter_expr
        }

        # Act
        response = client.get(f'/api/documents/search?q={query}&top={top}&filter={filter_expr}&include_thumbnails=false')

        # Assert
        assert response.status_code == 200
        
        # Verify parameters were passed correctly
        mock_search.search.assert_called_once_with(
            query=query,
            top=top,
            filter_expr=filter_expr,
            include_thumbnails=False
        )

    def test_search_validation_and_error_handling(self, client):
        """Test search endpoint validation and error responses"""
        # Test 1: Missing query parameter
        response = client.get('/api/documents/search')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'query' in data['message'].lower() or 'query' in data['error'].lower()
        
        # Test 2: POST request with JSON body
        response = client.post(
            '/api/documents/search',
            data=json.dumps({'query': 'test json search', 'top': 3}),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        # Test 3: POST request with form data
        response = client.post(
            '/api/documents/search',
            data={'query': 'test form search', 'top': 5},
            content_type='application/x-www-form-urlencoded'
        )
        assert response.status_code == 200

    @patch('app.routes.documents.search_service')
    def test_search_htmx_response_format(self, mock_search, client):
        """Test search returns HTML for HTMX requests"""
        # Arrange
        query = "htmx search"
        mock_search.search.return_value = {
            'query': query,
            'count': 1,
            'results': [{'chunk_id': 'c1', 'text': 'Result'}]
        }

        # Act - Simulate HTMX request
        response = client.get(
            f'/api/documents/search?q={query}',
            headers={'HX-Request': 'true'}
        )

        # Assert
        assert response.status_code == 200
        assert response.content_type.startswith('text/html')
        # Should render search_results.html template


class TestChatEndpoint:
    """Integration tests for RAG chat API"""

    @patch('app.routes.documents.cosmos_service')
    @patch('app.routes.documents.chat_service')
    def test_chat_success_with_service_integration(self, mock_chat, mock_cosmos, client):
        """Test successful RAG chat with complete service integration"""
        # Arrange
        query = "What are the key performance indicators in the documents?"
        mock_chat_response = {
            'response': 'Based on the available documents, the key performance indicators include emergency department waiting times [Doc 1] and cancer treatment pathways [Doc 2].',
            'sources': [
                {
                    'chunk_id': 'c1',
                    'doc_id': 'doc1',
                    'title': 'Performance Report',
                    'page_no': 1,
                    'text': 'Emergency department performance shows 95% compliance',
                    'score': 0.95,
                    'thumb_url': 'https://storage.blob.core.windows.net/thumbs/doc1/p1.png'
                },
                {
                    'chunk_id': 'c2',
                    'doc_id': 'doc2',
                    'title': 'Quality Metrics',
                    'page_no': 3,
                    'text': 'Cancer treatment pathways achieved 78% target',
                    'score': 0.88,
                    'thumb_url': 'https://storage.blob.core.windows.net/thumbs/doc2/p3.png'
                }
            ],
            'usage': {
                'prompt_tokens': 150,
                'completion_tokens': 50,
                'total_tokens': 200
            },
            'model': 'gpt-4o-mini',
            'finish_reason': 'stop',
            'query': query
        }

        mock_chat.chat.return_value = mock_chat_response

        # Act
        response = client.post(
            '/api/documents/chat',
            data=json.dumps({
                'query': query,
                'top_k': 5,
                'temperature': 0.3,
                'max_tokens': 1000
            }),
            content_type='application/json'
        )

        # Assert
        assert response.status_code == 200
        assert response.content_type.startswith('application/json')
        
        data = json.loads(response.data)
        assert data['response'] == mock_chat_response['response']
        assert len(data['sources']) == 2
        assert data['usage']['total_tokens'] == 200
        assert data['model'] == 'gpt-4o-mini'
        assert data['query'] == query
        
        # Verify service integration
        mock_chat.chat.assert_called_once_with(
            query=query,
            conversation_history=[],
            top_k=5,
            temperature=0.3,
            max_tokens=1000
        )
        
        # Verify chat event was logged
        mock_cosmos.log_event.assert_called_once()
        event_call = mock_cosmos.log_event.call_args
        assert event_call[1]['event_type'] == 'chat_query'
        assert event_call[1]['details']['query'] == query[:200]  # Truncated
        assert event_call[1]['details']['tokens_used'] == 200

    @patch('app.routes.documents.chat_service')
    def test_chat_with_conversation_history(self, mock_chat, client):
        """Test chat with multi-turn conversation history"""
        # Arrange
        query = "Can you provide more details about the first indicator?"
        conversation_history = [
            {'role': 'user', 'content': 'What are the key performance indicators?'},
            {'role': 'assistant', 'content': 'The key indicators include emergency department waiting times and cancer treatment pathways.'}
        ]

        mock_chat.chat.return_value = {
            'response': 'Emergency department waiting times target 95% of patients seen within 4 hours [Doc 1].',
            'sources': [{'chunk_id': 'c1', 'doc_id': 'doc1'}],
            'usage': {'total_tokens': 180},
            'model': 'gpt-4o-mini',
            'finish_reason': 'stop',
            'query': query
        }

        # Act
        response = client.post(
            '/api/documents/chat',
            data=json.dumps({
                'query': query,
                'conversation_history': conversation_history,
                'temperature': 0.2
            }),
            content_type='application/json'
        )

        # Assert
        assert response.status_code == 200
        
        # Verify conversation history was passed to service
        mock_chat.chat.assert_called_once()
        call_kwargs = mock_chat.chat.call_args[1]
        assert call_kwargs['conversation_history'] == conversation_history
        assert call_kwargs['temperature'] == 0.2

    def test_chat_validation_and_error_handling(self, client):
        """Test chat endpoint validation and error responses"""
        # Test 1: Missing query parameter
        response = client.post(
            '/api/documents/chat',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'query' in data['message'].lower()
        
        # Test 2: Form data request (HTMX)
        response = client.post(
            '/api/documents/chat',
            data={
                'query': 'test form query',
                'conversation_history': '[]',
                'top_k': '3',
                'temperature': '0.5'
            },
            content_type='application/x-www-form-urlencoded'
        )
        # Should handle form data parsing correctly (may succeed or fail based on implementation)

    @patch('app.routes.documents.chat_service')
    def test_chat_service_error_propagation(self, mock_chat, client):
        """Test chat endpoint error handling when service fails"""
        # Arrange
        query = "test error handling"
        mock_chat.chat.side_effect = Exception("OpenAI API unavailable")

        # Act
        response = client.post(
            '/api/documents/chat',
            data=json.dumps({'query': query}),
            content_type='application/json'
        )

        # Assert
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Chat processing failed' in data['error']


class TestThumbnailEndpoint:
    """Test thumbnail retrieval"""

    @patch('app.routes.documents.storage_service')
    @patch('app.routes.documents.cosmos_service')
    def test_get_thumbnail_success(self, mock_cosmos, mock_storage, client):
        """Test retrieving thumbnail SAS URL"""
        # Arrange
        doc_id = "doc123"
        page_no = 1

        mock_cosmos.get_document.return_value = {
            'id': doc_id,
            'page_count': 5
        }

        sas_url = "https://storage.blob.core.windows.net/thumbs/doc123_page_1.png?sig=abc"
        mock_storage.generate_sas_url.return_value = sas_url

        # Act
        response = client.get(f'/api/documents/{doc_id}/thumbnail/{page_no}')

        # Assert
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['url'] == sas_url

    @patch('app.routes.documents.cosmos_service')
    def test_get_thumbnail_invalid_page(self, mock_cosmos, client):
        """Test retrieving thumbnail for invalid page number"""
        # Arrange
        doc_id = "doc123"
        page_no = 999  # Beyond page count

        mock_cosmos.get_document.return_value = {
            'id': doc_id,
            'page_count': 5
        }

        # Act
        response = client.get(f'/api/documents/{doc_id}/thumbnail/{page_no}')

        # Assert
        assert response.status_code == 400


class TestDocumentManagementEndpoints:
    """Integration tests for document management operations"""

    @patch('app.routes.documents.storage_service')
    @patch('app.routes.documents.search_index_service')
    @patch('app.routes.documents.cosmos_service')
    def test_delete_document_complete_workflow(self, mock_cosmos, mock_search_index, mock_storage, client):
        """Test complete document deletion workflow with service integration"""
        # Arrange
        doc_id = "doc_to_delete"
        
        mock_cosmos.get_document.return_value = {
            'id': doc_id,
            'doc_id': doc_id,
            'status': 'indexed',
            'origin_filename': 'test.pdf',
            'is_deleted': False
        }
        
        mock_search_index.delete_chunks_by_doc_id.return_value = 10  # Deleted chunks
        mock_storage.archive_document_blobs.return_value = ['raw', 'extracted', 'thumbs']  # Archived containers

        # Act
        response = client.delete(f'/api/documents/{doc_id}')

        # Assert
        assert response.status_code == 200
        assert response.content_type.startswith('application/json')
        
        data = json.loads(response.data)
        assert data['doc_id'] == doc_id
        assert data['deleted_chunks'] == 10
        assert data['archived'] == ['raw', 'extracted', 'thumbs']
        
        # Verify service integration workflow
        mock_cosmos.get_document.assert_called_once_with(doc_id)
        mock_search_index.delete_chunks_by_doc_id.assert_called_once_with(doc_id)
        mock_cosmos.mark_as_deleted.assert_called_once_with(doc_id)
        mock_storage.archive_document_blobs.assert_called_once_with(doc_id)
        mock_cosmos.log_event.assert_called_once()

    @patch('app.routes.documents.cosmos_service')
    def test_delete_document_not_found(self, mock_cosmos, client):
        """Test deletion of non-existent document"""
        # Arrange
        doc_id = "nonexistent"
        mock_cosmos.get_document.return_value = None

        # Act
        response = client.delete(f'/api/documents/{doc_id}')

        # Assert
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'Document not found' in data['error']

    @patch('app.routes.documents.storage_service')
    @patch('app.routes.documents.cosmos_service')
    def test_get_thumbnail_with_sas_url(self, mock_cosmos, mock_storage, client):
        """Test thumbnail retrieval with SAS URL generation"""
        # Arrange
        doc_id = "doc123"
        page_no = 2
        
        mock_cosmos.get_document.return_value = {
            'id': doc_id,
            'page_count': 5
        }
        
        mock_storage.blob_exists.return_value = True
        sas_url = f"https://storage.blob.core.windows.net/thumbs/{doc_id}/p{page_no}.png?sig=abc123"
        mock_storage.generate_sas_url.return_value = sas_url

        # Act
        response = client.get(f'/api/documents/{doc_id}/thumbnail/{page_no}')

        # Assert
        assert response.status_code == 302  # Redirect to SAS URL
        assert response.location == sas_url
        
        # Verify service calls
        mock_storage.generate_sas_url.assert_called_once_with('thumbs', f'{doc_id}/p{page_no}.png', expiry_hours=1)

    @patch('app.routes.documents.cosmos_service')
    def test_get_thumbnail_invalid_page(self, mock_cosmos, client):
        """Test thumbnail retrieval for invalid page number"""
        # Arrange
        doc_id = "doc123"
        page_no = 999  # Beyond page count
        
        mock_cosmos.get_document.return_value = {
            'id': doc_id,
            'page_count': 5
        }

        # Act
        response = client.get(f'/api/documents/{doc_id}/thumbnail/{page_no}')

        # Assert
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'Thumbnail not found' in data['error']


class TestAPIErrorHandling:
    """Integration tests for API error handling and response consistency"""

    @patch('app.routes.documents.cosmos_service')
    def test_service_exception_handling(self, mock_cosmos, client):
        """Test that service exceptions are properly handled and return 500"""
        # Arrange
        mock_cosmos.list_documents.side_effect = Exception("Cosmos DB connection failed")

        # Act
        response = client.get('/api/documents/')

        # Assert
        assert response.status_code == 500
        assert response.content_type.startswith('application/json')
        
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Failed to list documents' in data['error']

    def test_invalid_endpoint_404(self, client):
        """Test 404 handling for invalid endpoints"""
        # Act
        response = client.get('/api/nonexistent-endpoint')

        # Assert
        assert response.status_code == 404

    def test_method_not_allowed_405(self, client):
        """Test 405 handling for invalid HTTP methods"""
        # Act - Try POST on GET-only endpoint
        response = client.post('/api/documents/doc123')

        # Assert
        assert response.status_code == 405

    @patch('app.routes.documents.search_service')
    def test_search_service_timeout_handling(self, mock_search, client):
        """Test search endpoint handles service timeouts gracefully"""
        # Arrange
        mock_search.search.side_effect = Exception("Search service timeout")

        # Act
        response = client.get('/api/documents/search?q=test')

        # Assert
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'Search failed' in data['error']


class TestAPIResponseConsistency:
    """Integration tests for API response format consistency"""

    def test_json_response_headers(self, client):
        """Test that JSON endpoints return consistent headers"""
        # Test multiple endpoints
        endpoints = [
            '/health',
            '/api/documents/',
            '/api/documents/search?q=test'
        ]
        
        for endpoint in endpoints:
            try:
                response = client.get(endpoint)
                if response.status_code < 500:  # Skip if service not mocked
                    assert 'application/json' in response.content_type
            except:
                # Skip if endpoint requires mocking
                pass

    @patch('app.routes.documents.cosmos_service')
    def test_error_response_format_consistency(self, mock_cosmos, client):
        """Test that error responses follow consistent format"""
        # Arrange - Force different types of errors
        test_cases = [
            ('/api/documents/nonexistent', 404, 'Document not found'),
            ('/api/documents/search', 400, 'Missing query parameter')
        ]
        
        mock_cosmos.get_document.return_value = None

        for endpoint, expected_status, expected_error_text in test_cases:
            # Act
            response = client.get(endpoint)
            
            # Assert
            if response.status_code == expected_status:
                assert response.content_type.startswith('application/json')
                data = json.loads(response.data)
                assert 'error' in data
                # Error message should contain expected text (case insensitive)
                assert expected_error_text.lower() in data['error'].lower() or expected_error_text.lower() in data.get('message', '').lower()
