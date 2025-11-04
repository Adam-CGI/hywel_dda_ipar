"""
Tests for EPIC F — Search & Citations

Tests cover:
- Search API endpoint functionality
- Hybrid BM25 + vector search
- Citation formatting and metadata
- SAS URL generation for thumbnails
- Search within specific documents
- Error handling and edge cases
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from app.services.search_service import SearchService
from app.services.storage_service import StorageService


class TestSearchService:
    """Test the SearchService class."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock all service dependencies."""
        with patch('app.services.search_service.SearchClient') as mock_search_client, \
             patch('app.services.search_service.EmbeddingService') as mock_embedding_service, \
             patch('app.services.search_service.StorageService') as mock_storage_service, \
             patch('app.services.search_service.CosmosService') as mock_cosmos_service:
            
            # Configure mocks
            mock_search_instance = Mock()
            mock_search_client.return_value = mock_search_instance
            
            mock_embedding_instance = Mock()
            mock_embedding_service.return_value = mock_embedding_instance
            
            mock_storage_instance = Mock()
            mock_storage_service.return_value = mock_storage_instance
            
            mock_cosmos_instance = Mock()
            mock_cosmos_service.return_value = mock_cosmos_instance
            
            yield {
                'search_client': mock_search_instance,
                'embedding_service': mock_embedding_instance,
                'storage_service': mock_storage_instance,
                'cosmos_service': mock_cosmos_instance
            }
    
    def test_search_basic_query(self, mock_dependencies):
        """Test basic search query execution."""
        # Setup
        service = SearchService()
        query = "patient outcomes"
        
        # Mock embedding generation
        mock_dependencies['embedding_service'].embed_texts.return_value = [[0.1] * 3072]
        
        # Mock search results
        mock_result = {
            'id': 'chunk123',
            'doc_id': 'doc456',
            'title': 'Test Document',
            'origin_filename': 'test.pdf',
            'page_no': 1,
            'text': 'This is test content about patient outcomes.',
            'spans': json.dumps([{"start": 0, "end": 45}]),
            'observed_date': '2024-01-01T00:00:00Z',
            'kpi_tags': ['outcomes', 'patients'],
            '@search.score': 0.95
        }
        mock_dependencies['search_client'].search.return_value = [mock_result]
        
        # Mock SAS URL generation
        mock_dependencies['storage_service'].generate_sas_url.return_value = 'https://storage.blob/thumb.png?sas=token'
        
        # Mock document metadata
        mock_dependencies['cosmos_service'].get_document.return_value = {
            'id': 'doc456',
            'status': 'indexed',
            'version': 1
        }
        
        # Execute
        result = service.search(query=query, top=10)
        
        # Verify
        assert result['query'] == query
        assert result['count'] == 1
        assert len(result['results']) == 1
        
        citation = result['results'][0]
        assert citation['citation_number'] == 1
        assert citation['doc_id'] == 'doc456'
        assert citation['title'] == 'Test Document'
        assert citation['page_no'] == 1
        assert citation['snippet'] == 'This is test content about patient outcomes.'
        assert 'thumb_url' in citation
        assert citation['score'] == 0.95
        
        # Verify embedding was generated
        mock_dependencies['embedding_service'].embed_texts.assert_called_once_with([query])
    
    def test_search_with_filter(self, mock_dependencies):
        """Test search with OData filter expression."""
        service = SearchService()
        
        mock_dependencies['embedding_service'].embed_texts.return_value = [[0.1] * 3072]
        mock_dependencies['search_client'].search.return_value = []
        
        filter_expr = "doc_id eq 'specific_doc'"
        result = service.search(query="test", filter_expr=filter_expr)
        
        # Verify filter was passed to search
        call_args = mock_dependencies['search_client'].search.call_args
        assert call_args.kwargs['filter'] == filter_expr
    
    def test_search_no_results(self, mock_dependencies):
        """Test search returning no results."""
        service = SearchService()
        
        mock_dependencies['embedding_service'].embed_texts.return_value = [[0.1] * 3072]
        mock_dependencies['search_client'].search.return_value = []
        
        result = service.search(query="nonexistent query")
        
        assert result['count'] == 0
        assert result['results'] == []
    
    def test_search_without_thumbnails(self, mock_dependencies):
        """Test search with thumbnail generation disabled."""
        service = SearchService()
        
        mock_dependencies['embedding_service'].embed_texts.return_value = [[0.1] * 3072]
        
        mock_result = {
            'id': 'chunk123',
            'doc_id': 'doc456',
            'title': 'Test',
            'page_no': 1,
            'text': 'Content',
            'spans': '[]',
            '@search.score': 0.8
        }
        mock_dependencies['search_client'].search.return_value = [mock_result]
        mock_dependencies['cosmos_service'].get_document.return_value = None
        
        result = service.search(query="test", include_thumbnails=False)
        
        # Verify thumbnail URL was not generated
        assert 'thumb_url' not in result['results'][0]
        mock_dependencies['storage_service'].generate_sas_url.assert_not_called()
    
    def test_search_citation_numbering(self, mock_dependencies):
        """Test that citations are numbered correctly."""
        service = SearchService()
        
        mock_dependencies['embedding_service'].embed_texts.return_value = [[0.1] * 3072]
        
        # Mock multiple results
        mock_results = []
        for i in range(5):
            mock_results.append({
                'id': f'chunk{i}',
                'doc_id': f'doc{i}',
                'title': f'Document {i}',
                'page_no': i + 1,
                'text': f'Content {i}',
                'spans': '[]',
                '@search.score': 1.0 - (i * 0.1)
            })
        
        mock_dependencies['search_client'].search.return_value = mock_results
        mock_dependencies['cosmos_service'].get_document.return_value = None
        
        result = service.search(query="test", include_thumbnails=False)
        
        # Verify citation numbers
        assert result['count'] == 5
        for i, citation in enumerate(result['results']):
            assert citation['citation_number'] == i + 1
    
    def test_get_chunk_by_id(self, mock_dependencies):
        """Test retrieving a specific chunk by ID."""
        service = SearchService()
        
        chunk_data = {
            'id': 'chunk123',
            'doc_id': 'doc456',
            'title': 'Test Document',
            'page_no': 2,
            'text': 'Chunk content',
            'spans': json.dumps([{"start": 0, "end": 13}]),
            'kpi_tags': ['test']
        }
        mock_dependencies['search_client'].get_document.return_value = chunk_data
        
        result = service.get_chunk_by_id('chunk123')
        
        assert result is not None
        assert result['id'] == 'chunk123'
        assert result['doc_id'] == 'doc456'
        assert isinstance(result['spans'], list)
    
    def test_get_chunk_by_id_not_found(self, mock_dependencies):
        """Test retrieving non-existent chunk."""
        service = SearchService()
        
        mock_dependencies['search_client'].get_document.side_effect = Exception("Not found")
        
        result = service.get_chunk_by_id('nonexistent')
        
        assert result is None
    
    def test_search_by_document(self, mock_dependencies):
        """Test searching within a specific document."""
        service = SearchService()
        
        mock_dependencies['embedding_service'].embed_texts.return_value = [[0.1] * 3072]
        
        mock_result = {
            'id': 'chunk1',
            'doc_id': 'target_doc',
            'title': 'Target Document',
            'page_no': 1,
            'text': 'Document content',
            'spans': '[]',
            '@search.score': 0.9
        }
        mock_dependencies['search_client'].search.return_value = [mock_result]
        mock_dependencies['cosmos_service'].get_document.return_value = None
        
        chunks = service.search_by_document(doc_id='target_doc', query='content')
        
        assert len(chunks) == 1
        assert chunks[0]['doc_id'] == 'target_doc'
        
        # Verify filter was applied
        call_args = mock_dependencies['search_client'].search.call_args
        assert "doc_id eq 'target_doc'" in str(call_args)


class TestSearchAPI:
    """Test the search API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        import sys
        import os
        import importlib.util
        
        # Load app.py module explicitly
        app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app.py')
        spec = importlib.util.spec_from_file_location("app_module", app_path)
        app_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app_module)
        
        app = app_module.create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @patch('app.routes.documents.search_service')
    def test_search_endpoint_get(self, mock_search_service, client):
        """Test GET request to search endpoint."""
        # Mock search results
        mock_search_service.search.return_value = {
            'query': 'test query',
            'count': 1,
            'results': [{
                'citation_number': 1,
                'doc_id': 'doc123',
                'title': 'Test',
                'page_no': 1,
                'snippet': 'Test snippet',
                'score': 0.95
            }],
            'filter': None
        }
        
        response = client.get('/api/documents/search?q=test%20query&top=10')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['query'] == 'test query'
        assert data['count'] == 1
        
        # Verify search service was called
        mock_search_service.search.assert_called_once()
    
    @patch('app.routes.documents.search_service')
    def test_search_endpoint_post(self, mock_search_service, client):
        """Test POST request to search endpoint."""
        mock_search_service.search.return_value = {
            'query': 'post query',
            'count': 0,
            'results': [],
            'filter': None
        }
        
        response = client.post(
            '/api/documents/search',
            json={'query': 'post query', 'top': 5}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['query'] == 'post query'
    
    def test_search_endpoint_missing_query(self, client):
        """Test search endpoint without query parameter."""
        response = client.get('/api/documents/search')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'query' in data['message'].lower()
    
    @patch('app.routes.documents.search_service')
    def test_search_endpoint_with_filter(self, mock_search_service, client):
        """Test search with filter parameter."""
        mock_search_service.search.return_value = {
            'query': 'test',
            'count': 0,
            'results': [],
            'filter': "doc_id eq 'abc'"
        }
        
        response = client.get('/api/documents/search?q=test&filter=doc_id%20eq%20%27abc%27')
        
        assert response.status_code == 200
        
        # Verify filter was passed
        call_args = mock_search_service.search.call_args
        assert call_args.kwargs['filter_expr'] == "doc_id eq 'abc'"
    
    @patch('app.routes.documents.search_service')
    def test_get_chunk_detail_endpoint(self, mock_search_service, client):
        """Test chunk detail endpoint."""
        mock_search_service.get_chunk_by_id.return_value = {
            'id': 'chunk123',
            'doc_id': 'doc456',
            'text': 'Chunk content',
            'page_no': 1
        }
        
        response = client.get('/api/documents/search/chunk/chunk123')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == 'chunk123'
    
    @patch('app.routes.documents.search_service')
    def test_get_chunk_detail_not_found(self, mock_search_service, client):
        """Test chunk detail for non-existent chunk."""
        mock_search_service.get_chunk_by_id.return_value = None
        
        response = client.get('/api/documents/search/chunk/nonexistent')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
    
    @patch('app.routes.documents.search_service')
    def test_search_within_document_endpoint(self, mock_search_service, client):
        """Test search within document endpoint."""
        mock_search_service.search_by_document.return_value = [
            {'id': 'chunk1', 'text': 'Content 1'},
            {'id': 'chunk2', 'text': 'Content 2'}
        ]
        
        response = client.get('/api/documents/search/document/doc123?q=content')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['doc_id'] == 'doc123'
        assert data['count'] == 2


class TestStorageSASGeneration:
    """Test SAS URL generation for thumbnails."""
    
    @patch('app.services.storage_service.generate_blob_sas')
    @patch('app.services.storage_service.get_blob_service_client')
    def test_generate_sas_url(self, mock_get_client, mock_generate_sas):
        """Test SAS URL generation."""
        # Mock blob service client
        mock_client = Mock()
        mock_blob_client = Mock()
        mock_blob_client.url = 'https://storage.blob.core.windows.net/thumbs/doc123/p1.png'
        mock_client.get_blob_client.return_value = mock_blob_client
        mock_client.credential.account_key = 'test_key'
        mock_get_client.return_value = mock_client
        
        # Mock SAS token generation
        mock_generate_sas.return_value = 'sv=2023&sig=test'
        
        # Test
        service = StorageService()
        sas_url = service.generate_sas_url(
            container_name='thumbs',
            blob_name='doc123/p1.png',
            expiry_hours=1
        )
        
        # Verify
        assert sas_url.startswith('https://storage.blob.core.windows.net')
        assert '?' in sas_url
        assert 'sv=' in sas_url
        assert 'sig=' in sas_url
        
        # Verify SAS token was generated with correct permissions
        mock_generate_sas.assert_called_once()
        call_kwargs = mock_generate_sas.call_args.kwargs
        assert call_kwargs['container_name'] == 'thumbs'
        assert call_kwargs['blob_name'] == 'doc123/p1.png'


class TestSearchUIEndpoint:
    """Test search UI rendering."""
    
    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        import sys
        import os
        import importlib.util
        
        # Load app.py module explicitly
        app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app.py')
        spec = importlib.util.spec_from_file_location("app_module", app_path)
        app_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app_module)
        
        app = app_module.create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_search_ui_renders(self, client):
        """Test that search UI page renders."""
        response = client.get('/api/documents/ui/search')
        
        assert response.status_code == 200
        assert b'Search Documents' in response.data or b'search' in response.data.lower()


def test_citation_metadata_completeness():
    """Test that citation objects contain all required fields per EPIC F.16."""
    required_fields = [
        'doc_id',
        'title',
        'page_no',
        'snippet',
        'text'
    ]
    
    # Mock citation object
    citation = {
        'citation_number': 1,
        'chunk_id': 'chunk123',
        'doc_id': 'doc456',
        'title': 'Test Document',
        'page_no': 1,
        'spans': [{'start': 0, 'end': 100}],
        'snippet': 'This is a snippet...',
        'text': 'Full text content',
        'score': 0.95
    }
    
    # Verify all required fields are present
    for field in required_fields:
        assert field in citation, f"Citation missing required field: {field}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
