"""
Unit tests for SearchService
Tests hybrid search operations, result formatting, and citation generation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from app.services.search_service import SearchService


class TestSearchService:
    """Test SearchService initialization and configuration"""

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    @patch('app.services.search_service.AZURE_SEARCH_INDEX', 'test-index')
    def test_search_service_initialization(self):
        """Test SearchService initializes with correct configuration"""
        # Arrange & Act
        with patch('app.services.search_service.SearchClient') as mock_search_client:
            with patch('app.services.search_service.EmbeddingService'):
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        service = SearchService()

                        # Assert
                        assert service.index_name == 'test-index'
                        mock_search_client.assert_called_once()

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', '')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', '')
    def test_search_service_missing_config(self):
        """Test SearchService raises error with missing configuration"""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            SearchService()
        
        assert "AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY must be configured" in str(exc_info.value)


class TestSearch:
    """Test hybrid search functionality"""

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    @patch('app.services.search_service.AZURE_SEARCH_INDEX', 'test-index')
    def test_search_success(self):
        """Test successful hybrid search execution"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService') as mock_embedding_class:
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService') as mock_cosmos_class:
                        
                        # Mock search client
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        # Mock embedding service
                        mock_embedding_service = Mock()
                        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
                        mock_embedding_class.return_value = mock_embedding_service
                        
                        # Mock cosmos service
                        mock_cosmos_service = Mock()
                        mock_cosmos_service.get_document.return_value = {
                            'status': 'indexed',
                            'version': 1
                        }
                        mock_cosmos_class.return_value = mock_cosmos_service
                        
                        # Mock search results
                        mock_result = {
                            'id': 'chunk1',
                            'doc_id': 'doc123',
                            'title': 'Test Document',
                            'page_no': 1,
                            'text': 'This is test content for search',
                            'spans': '[{"start": 0, "end": 32, "page_no": 1}]',
                            '@search.score': 0.95
                        }
                        mock_search_client.search.return_value = [mock_result]
                        
                        service = SearchService()
                        
                        # Act
                        result = service.search("test query", top=5)
                        
                        # Assert
                        assert result['query'] == "test query"
                        assert result['count'] == 1
                        assert len(result['results']) == 1
                        
                        citation = result['results'][0]
                        assert citation['citation_number'] == 1
                        assert citation['chunk_id'] == 'chunk1'
                        assert citation['doc_id'] == 'doc123'
                        assert citation['title'] == 'Test Document'
                        assert citation['page_no'] == 1
                        assert 'snippet' in citation
                        
                        # Verify search was called with correct parameters
                        mock_search_client.search.assert_called_once()

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    def test_search_with_filter(self):
        """Test search with OData filter"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService') as mock_embedding_class:
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        mock_embedding_service = Mock()
                        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
                        mock_embedding_class.return_value = mock_embedding_service
                        
                        mock_search_client.search.return_value = []
                        
                        service = SearchService()
                        
                        # Act
                        result = service.search("test query", filter_expr="doc_id eq 'doc123'")
                        
                        # Assert
                        assert result['filter'] == "doc_id eq 'doc123'"
                        
                        # Verify filter was passed to search
                        call_args = mock_search_client.search.call_args
                        assert call_args[1]['filter'] == "doc_id eq 'doc123'"

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    def test_search_empty_results(self):
        """Test search with no results"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService') as mock_embedding_class:
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        mock_embedding_service = Mock()
                        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
                        mock_embedding_class.return_value = mock_embedding_service
                        
                        mock_search_client.search.return_value = []
                        
                        service = SearchService()
                        
                        # Act
                        result = service.search("no results query")
                        
                        # Assert
                        assert result['count'] == 0
                        assert result['results'] == []

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    def test_search_error_handling(self):
        """Test search error handling"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService') as mock_embedding_class:
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        mock_embedding_service = Mock()
                        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
                        mock_embedding_class.return_value = mock_embedding_service
                        
                        mock_search_client.search.side_effect = Exception("Search failed")
                        
                        service = SearchService()
                        
                        # Act & Assert
                        with pytest.raises(Exception) as exc_info:
                            service.search("test query")
                        
                        assert "Search failed" in str(exc_info.value)


class TestGetChunkById:
    """Test retrieving specific chunks by ID"""

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    def test_get_chunk_by_id_success(self):
        """Test successful chunk retrieval by ID"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService'):
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        mock_chunk = {
                            'id': 'chunk123',
                            'doc_id': 'doc123',
                            'title': 'Test Document',
                            'page_no': 1,
                            'text': 'Chunk content',
                            'spans': '[{"start": 0, "end": 13, "page_no": 1}]',
                            'kpi_tags': ['performance', 'quality']
                        }
                        mock_search_client.get_document.return_value = mock_chunk
                        
                        service = SearchService()
                        
                        # Act
                        result = service.get_chunk_by_id('chunk123')
                        
                        # Assert
                        assert result is not None
                        assert result['id'] == 'chunk123'
                        assert result['doc_id'] == 'doc123'
                        assert result['spans'] == [{"start": 0, "end": 13, "page_no": 1}]
                        assert result['kpi_tags'] == ['performance', 'quality']

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    def test_get_chunk_by_id_not_found(self):
        """Test chunk retrieval when chunk doesn't exist"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService'):
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        mock_search_client.get_document.side_effect = Exception("Document not found")
                        
                        service = SearchService()
                        
                        # Act
                        result = service.get_chunk_by_id('nonexistent')
                        
                        # Assert
                        assert result is None


class TestSearchByDocument:
    """Test searching within specific documents"""

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    def test_search_by_document_with_query(self):
        """Test searching within a specific document with query"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService') as mock_embedding_class:
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        mock_embedding_service = Mock()
                        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
                        mock_embedding_class.return_value = mock_embedding_service
                        
                        # Mock search results
                        mock_result = {
                            'id': 'chunk1',
                            'doc_id': 'doc123',
                            'page_no': 1,
                            'text': 'Document content',
                            'spans': '[]',
                            '@search.score': 0.8
                        }
                        mock_search_client.search.return_value = [mock_result]
                        
                        service = SearchService()
                        
                        # Act
                        result = service.search_by_document('doc123', 'test query')
                        
                        # Assert
                        assert len(result) == 1
                        assert result[0]['chunk_id'] == 'chunk1'
                        assert result[0]['doc_id'] == 'doc123'

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    def test_search_by_document_all_chunks(self):
        """Test retrieving all chunks from a specific document"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService'):
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        # Mock search results for all chunks
                        mock_results = [
                            {
                                'id': 'chunk1',
                                'doc_id': 'doc123',
                                'page_no': 1,
                                'text': 'First chunk',
                                'spans': '[]'
                            },
                            {
                                'id': 'chunk2',
                                'doc_id': 'doc123',
                                'page_no': 1,
                                'text': 'Second chunk',
                                'spans': '[]'
                            }
                        ]
                        mock_search_client.search.return_value = mock_results
                        
                        service = SearchService()
                        
                        # Act
                        result = service.search_by_document('doc123', query=None)
                        
                        # Assert
                        assert len(result) == 2
                        assert all(chunk['doc_id'] == 'doc123' for chunk in result)


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    def test_search_with_malformed_spans(self):
        """Test search with malformed spans JSON"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService') as mock_embedding_class:
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        mock_embedding_service = Mock()
                        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
                        mock_embedding_class.return_value = mock_embedding_service
                        
                        # Mock result with malformed spans
                        mock_result = {
                            'id': 'chunk1',
                            'doc_id': 'doc123',
                            'title': 'Test Document',
                            'page_no': 1,
                            'text': 'Test content',
                            'spans': 'invalid json',  # Malformed JSON
                            '@search.score': 0.8
                        }
                        mock_search_client.search.return_value = [mock_result]
                        
                        service = SearchService()
                        
                        # Act
                        result = service.search("test query")
                        
                        # Assert
                        assert result['count'] == 1
                        citation = result['results'][0]
                        assert citation['spans'] == []  # Should default to empty list

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    def test_search_with_unicode_query(self):
        """Test search with unicode characters in query"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService') as mock_embedding_class:
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        mock_embedding_service = Mock()
                        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
                        mock_embedding_class.return_value = mock_embedding_service
                        
                        mock_search_client.search.return_value = []
                        
                        service = SearchService()
                        
                        # Act
                        result = service.search("测试查询 with émojis 🔍")
                        
                        # Assert
                        assert result['query'] == "测试查询 with émojis 🔍"
                        assert result['count'] == 0

    @patch('app.services.search_service.AZURE_SEARCH_ENDPOINT', 'https://test.search.windows.net')
    @patch('app.services.search_service.AZURE_SEARCH_ADMIN_KEY', 'test-key')
    def test_search_with_very_long_text(self):
        """Test search result with very long text content"""
        # Arrange
        with patch('app.services.search_service.SearchClient') as mock_search_client_class:
            with patch('app.services.search_service.EmbeddingService') as mock_embedding_class:
                with patch('app.services.search_service.StorageService'):
                    with patch('app.services.search_service.CosmosService'):
                        
                        mock_search_client = Mock()
                        mock_search_client_class.return_value = mock_search_client
                        
                        mock_embedding_service = Mock()
                        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
                        mock_embedding_class.return_value = mock_embedding_service
                        
                        # Mock result with very long text
                        long_text = "This is a very long text content. " * 100  # >200 chars
                        mock_result = {
                            'id': 'chunk1',
                            'doc_id': 'doc123',
                            'title': 'Test Document',
                            'page_no': 1,
                            'text': long_text,
                            'spans': '[]',
                            '@search.score': 0.8
                        }
                        mock_search_client.search.return_value = [mock_result]
                        
                        service = SearchService()
                        
                        # Act
                        result = service.search("test query")
                        
                        # Assert
                        citation = result['results'][0]
                        assert len(citation['snippet']) <= 203  # 200 chars + "..."
                        assert citation['snippet'].endswith("...")
                        assert citation['text'] == long_text  # Full text preserved