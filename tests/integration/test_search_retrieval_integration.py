"""
Integration tests for search and retrieval functionality
Tests hybrid search functionality with vector and keyword components,
result ranking, pagination, and citation generation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from app.services.search_service import SearchService
from app.services.chat_service import ChatService


class TestHybridSearchIntegration:
    """Integration tests for hybrid BM25 + vector search functionality"""

    def test_hybrid_search_with_real_service_interactions(
        self,
        mock_search_client,
        mock_embedding_service,
        mock_storage_service,
        mock_cosmos_service,
        sample_search_results
    ):
        """Test hybrid search with real service layer interactions"""
        # Arrange
        query = "performance indicators"
        
        # Mock embedding service to return query vector
        query_vector = [0.1] * 3072
        mock_embedding_service.embed_texts.return_value = [query_vector]
        
        # Mock search client to return hybrid results
        mock_search_client.search.return_value = sample_search_results
        
        # Mock document metadata from Cosmos
        mock_cosmos_service.get_document.return_value = {
            'id': 'doc1',
            'status': 'indexed',
            'version': 1,
            'uploaded_by': 'test_user',
            'uploaded_at': '2024-01-01T00:00:00Z'
        }
        
        # Mock thumbnail SAS URL generation
        mock_storage_service.generate_sas_url.return_value = "https://storage.blob.core.windows.net/thumbs/doc1/p1.png?sig=abc"

        # Create search service with mocked dependencies
        search_service = SearchService()
        search_service.search_client = mock_search_client
        search_service.embedding_service = mock_embedding_service
        search_service.storage_service = mock_storage_service
        search_service.cosmos_service = mock_cosmos_service

        # Act
        result = search_service.search(query=query, top=10, include_thumbnails=True)

        # Assert - verify service interactions
        # 1. Query embedding was generated
        mock_embedding_service.embed_texts.assert_called_once_with([query])
        
        # 2. Hybrid search was executed with both text and vector queries
        search_call = mock_search_client.search.call_args
        assert search_call[1]['search_text'] == query
        assert len(search_call[1]['vector_queries']) == 1
        assert search_call[1]['vector_queries'][0].vector == query_vector
        assert search_call[1]['top'] == 10
        
        # 3. Document metadata was retrieved for enrichment
        mock_cosmos_service.get_document.assert_called()
        
        # 4. Thumbnail URLs were generated
        mock_storage_service.generate_sas_url.assert_called()
        
        # 5. Results are properly formatted with citations
        assert result['query'] == query
        assert result['count'] > 0
        assert len(result['results']) > 0
        
        # Verify citation structure
        first_result = result['results'][0]
        assert 'citation_number' in first_result
        assert 'chunk_id' in first_result
        assert 'doc_id' in first_result
        assert 'snippet' in first_result
        assert 'thumb_url' in first_result
        assert 'score' in first_result

    def test_search_result_ranking_and_scoring(
        self,
        mock_search_client,
        mock_embedding_service,
        mock_cosmos_service
    ):
        """Test search result ranking and score calculation"""
        # Arrange
        query = "test query"
        
        # Mock results with different scores (should be returned in score order)
        mock_results = [
            {
                'id': 'chunk1',
                'doc_id': 'doc1',
                'text': 'High relevance content',
                'page_no': 1,
                '@search.score': 0.95,
                '@search.reranker_score': 0.98,
                'spans': '[]'
            },
            {
                'id': 'chunk2', 
                'doc_id': 'doc2',
                'text': 'Medium relevance content',
                'page_no': 2,
                '@search.score': 0.75,
                '@search.reranker_score': 0.80,
                'spans': '[]'
            },
            {
                'id': 'chunk3',
                'doc_id': 'doc3', 
                'text': 'Lower relevance content',
                'page_no': 1,
                '@search.score': 0.60,
                '@search.reranker_score': 0.65,
                'spans': '[]'
            }
        ]
        
        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
        mock_search_client.search.return_value = mock_results
        mock_cosmos_service.get_document.return_value = {'status': 'indexed'}

        # Create search service
        search_service = SearchService()
        search_service.search_client = mock_search_client
        search_service.embedding_service = mock_embedding_service
        search_service.cosmos_service = mock_cosmos_service

        # Act
        result = search_service.search(query=query, top=5)

        # Assert - verify ranking and scoring
        results = result['results']
        assert len(results) == 3
        
        # Results should maintain search engine ranking (highest score first)
        assert results[0]['score'] == 0.95
        assert results[1]['score'] == 0.75
        assert results[2]['score'] == 0.60
        
        # Citation numbers should be sequential
        assert results[0]['citation_number'] == 1
        assert results[1]['citation_number'] == 2
        assert results[2]['citation_number'] == 3
        
        # Reranker scores should be preserved
        assert results[0]['reranker_score'] == 0.98
        assert results[1]['reranker_score'] == 0.80
        assert results[2]['reranker_score'] == 0.65

    def test_search_with_filters_and_pagination(
        self,
        mock_search_client,
        mock_embedding_service
    ):
        """Test search with OData filters and pagination parameters"""
        # Arrange
        query = "test query"
        filter_expr = "doc_id eq 'specific_doc'"
        top = 5
        
        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
        mock_search_client.search.return_value = []

        # Create search service
        search_service = SearchService()
        search_service.search_client = mock_search_client
        search_service.embedding_service = mock_embedding_service

        # Act
        result = search_service.search(
            query=query,
            top=top,
            filter_expr=filter_expr,
            include_thumbnails=False
        )

        # Assert - verify filter and pagination parameters
        search_call = mock_search_client.search.call_args
        assert search_call[1]['search_text'] == query
        assert search_call[1]['top'] == top
        assert search_call[1]['filter'] == filter_expr
        
        # Verify result includes filter information
        assert result['filter'] == filter_expr
        assert result['query'] == query

    def test_search_index_updates_and_deletions(
        self,
        mock_search_index_service,
        sample_chunks_with_vectors
    ):
        """Test search index update and deletion operations"""
        # Arrange
        doc_id = "test_doc_123"
        
        # Mock successful upload and deletion operations
        mock_search_index_service.upload_chunks.return_value = {
            "uploaded": len(sample_chunks_with_vectors),
            "failed": 0
        }
        mock_search_index_service.delete_chunks_by_doc_id.return_value = 5

        # Act - Test chunk upload
        upload_result = mock_search_index_service.upload_chunks(sample_chunks_with_vectors)
        
        # Act - Test chunk deletion
        delete_result = mock_search_index_service.delete_chunks_by_doc_id(doc_id)

        # Assert - verify index operations
        assert upload_result["uploaded"] == len(sample_chunks_with_vectors)
        assert upload_result["failed"] == 0
        assert delete_result == 5
        
        # Verify service methods were called correctly
        mock_search_index_service.upload_chunks.assert_called_once_with(sample_chunks_with_vectors)
        mock_search_index_service.delete_chunks_by_doc_id.assert_called_once_with(doc_id)


class TestSearchCitationGeneration:
    """Integration tests for search citation generation and formatting"""

    def test_citation_generation_with_document_metadata(
        self,
        mock_search_client,
        mock_embedding_service,
        mock_storage_service,
        mock_cosmos_service
    ):
        """Test citation generation includes proper document metadata"""
        # Arrange
        query = "test citation"
        
        mock_search_result = {
            'id': 'chunk_123',
            'doc_id': 'doc_456',
            'logical_id': 'logical_789',
            'title': 'Test Document Title',
            'origin_filename': 'test.pdf',
            'page_no': 3,
            'text': 'This is a longer piece of text that should be truncated in the snippet but preserved in full text for citation purposes.',
            'spans': '[{"start": 10, "end": 20}]',
            'observed_date': '2024-01-01T00:00:00Z',
            'kpi_tags': ['performance', 'quality'],
            '@search.score': 0.85,
            '@search.reranker_score': 0.90
        }
        
        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
        mock_search_client.search.return_value = [mock_search_result]
        
        # Mock document metadata from Cosmos
        mock_cosmos_service.get_document.return_value = {
            'status': 'indexed',
            'version': 2,
            'uploaded_by': 'admin@example.com',
            'uploaded_at': '2024-01-01T10:00:00Z'
        }
        
        # Mock thumbnail URL
        mock_storage_service.generate_sas_url.return_value = "https://storage.blob.core.windows.net/thumbs/doc_456/p3.png?sig=xyz"

        # Create search service
        search_service = SearchService()
        search_service.search_client = mock_search_client
        search_service.embedding_service = mock_embedding_service
        search_service.storage_service = mock_storage_service
        search_service.cosmos_service = mock_cosmos_service

        # Act
        result = search_service.search(query=query, top=1, include_thumbnails=True)

        # Assert - verify citation structure and metadata
        citation = result['results'][0]
        
        # Basic citation fields
        assert citation['citation_number'] == 1
        assert citation['chunk_id'] == 'chunk_123'
        assert citation['doc_id'] == 'doc_456'
        assert citation['logical_id'] == 'logical_789'
        assert citation['title'] == 'Test Document Title'
        assert citation['origin_filename'] == 'test.pdf'
        assert citation['page_no'] == 3
        
        # Text and snippet handling
        assert citation['text'] == mock_search_result['text']
        assert len(citation['snippet']) <= 203  # 200 chars + "..."
        assert citation['snippet'].endswith('...')
        
        # Spans parsing
        assert citation['spans'] == [{"start": 10, "end": 20}]
        
        # Metadata fields
        assert citation['observed_date'] == '2024-01-01T00:00:00Z'
        assert citation['kpi_tags'] == ['performance', 'quality']
        
        # Scoring
        assert citation['score'] == 0.85
        assert citation['reranker_score'] == 0.90
        
        # Document metadata enrichment
        assert citation['document_status'] == 'indexed'
        assert citation['document_version'] == 2
        assert citation['uploaded_by'] == 'admin@example.com'
        assert citation['uploaded_at'] == '2024-01-01T10:00:00Z'
        
        # Thumbnail URL
        assert citation['thumb_url'] == "https://storage.blob.core.windows.net/thumbs/doc_456/p3.png?sig=xyz"

    def test_citation_formatting_edge_cases(
        self,
        mock_search_client,
        mock_embedding_service,
        mock_cosmos_service
    ):
        """Test citation formatting handles edge cases properly"""
        # Arrange
        query = "edge case test"
        
        # Mock result with edge case data
        mock_search_result = {
            'id': 'edge_chunk',
            'doc_id': 'edge_doc',
            'title': '',  # Empty title
            'origin_filename': '',  # Empty filename
            'page_no': None,  # Missing page number
            'text': 'Short',  # Short text (no truncation needed)
            'spans': 'invalid_json',  # Invalid JSON spans
            'observed_date': None,  # Missing date
            'kpi_tags': None,  # Missing tags
            '@search.score': None,  # Missing score
            '@search.reranker_score': None  # Missing reranker score
        }
        
        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
        mock_search_client.search.return_value = [mock_search_result]
        mock_cosmos_service.get_document.return_value = None  # No document metadata

        # Create search service
        search_service = SearchService()
        search_service.search_client = mock_search_client
        search_service.embedding_service = mock_embedding_service
        search_service.cosmos_service = mock_cosmos_service

        # Act
        result = search_service.search(query=query, top=1, include_thumbnails=False)

        # Assert - verify graceful handling of edge cases
        citation = result['results'][0]
        
        # Default values for missing/empty fields
        assert citation['title'] == 'Untitled Document'
        assert citation['origin_filename'] == ''
        assert citation['page_no'] == 1  # Default page number
        assert citation['snippet'] == 'Short'  # No truncation for short text
        assert citation['spans'] == []  # Empty list for invalid JSON
        assert citation['observed_date'] is None
        assert citation['kpi_tags'] == []
        assert citation['score'] == 0.0
        assert citation['reranker_score'] is None
        
        # No document metadata enrichment when document not found
        assert 'document_status' not in citation or citation['document_status'] is None


class TestDocumentSpecificSearch:
    """Integration tests for searching within specific documents"""

    def test_search_within_document_with_query(
        self,
        mock_search_client,
        mock_embedding_service
    ):
        """Test searching within a specific document with query"""
        # Arrange
        doc_id = "specific_doc_123"
        query = "performance metrics"
        
        mock_embedding_service.embed_texts.return_value = [[0.1] * 3072]
        
        # Mock search results filtered to specific document
        mock_results = [
            {
                'id': 'chunk1',
                'doc_id': doc_id,
                'page_no': 1,
                'text': 'Performance metrics content',
                'spans': '[]',
                '@search.score': 0.9
            },
            {
                'id': 'chunk2',
                'doc_id': doc_id,
                'page_no': 2,
                'text': 'More performance data',
                'spans': '[]',
                '@search.score': 0.8
            }
        ]
        mock_search_client.search.return_value = mock_results

        # Create search service
        search_service = SearchService()
        search_service.search_client = mock_search_client
        search_service.embedding_service = mock_embedding_service

        # Act
        chunks = search_service.search_by_document(doc_id=doc_id, query=query, top=10)

        # Assert - verify document-specific search
        search_call = mock_search_client.search.call_args
        
        # Should use hybrid search with document filter
        assert search_call[1]['search_text'] == query
        assert f"doc_id eq '{doc_id}'" in search_call[1]['filter']
        assert search_call[1]['top'] == 10
        
        # Results should be from specified document only
        assert len(chunks) == 2
        for chunk in chunks:
            assert chunk['doc_id'] == doc_id

    def test_get_all_chunks_for_document(
        self,
        mock_search_client
    ):
        """Test retrieving all chunks for a document without query"""
        # Arrange
        doc_id = "all_chunks_doc"
        
        # Mock all chunks for document (no query filtering)
        mock_results = [
            {
                'id': f'chunk{i}',
                'doc_id': doc_id,
                'page_no': i,
                'text': f'Content for chunk {i}',
                'spans': '[]'
            }
            for i in range(1, 6)  # 5 chunks
        ]
        mock_search_client.search.return_value = mock_results

        # Create search service
        search_service = SearchService()
        search_service.search_client = mock_search_client

        # Act
        chunks = search_service.search_by_document(doc_id=doc_id, query=None, top=100)

        # Assert - verify all chunks retrieval
        search_call = mock_search_client.search.call_args
        
        # Should use wildcard search with document filter
        assert search_call[1]['search_text'] == "*"
        assert f"doc_id eq '{doc_id}'" in search_call[1]['filter']
        assert search_call[1]['top'] == 100
        
        # Should return all chunks for document
        assert len(chunks) == 5
        for i, chunk in enumerate(chunks, 1):
            assert chunk['id'] == f'chunk{i}'
            assert chunk['doc_id'] == doc_id

    def test_get_chunk_by_id_integration(
        self,
        mock_search_client
    ):
        """Test retrieving specific chunk by ID"""
        # Arrange
        chunk_id = "specific_chunk_123"
        
        mock_chunk = {
            'id': chunk_id,
            'doc_id': 'parent_doc',
            'title': 'Document Title',
            'page_no': 5,
            'text': 'Specific chunk content for retrieval',
            'spans': '[{"start": 0, "end": 10}]',
            'kpi_tags': ['tag1', 'tag2']
        }
        mock_search_client.get_document.return_value = mock_chunk

        # Create search service
        search_service = SearchService()
        search_service.search_client = mock_search_client

        # Act
        result = search_service.get_chunk_by_id(chunk_id)

        # Assert - verify chunk retrieval and formatting
        mock_search_client.get_document.assert_called_once_with(key=chunk_id)
        
        assert result is not None
        assert result['id'] == chunk_id
        assert result['doc_id'] == 'parent_doc'
        assert result['title'] == 'Document Title'
        assert result['page_no'] == 5
        assert result['text'] == 'Specific chunk content for retrieval'
        assert result['spans'] == [{"start": 0, "end": 10}]
        assert result['kpi_tags'] == ['tag1', 'tag2']

    def test_get_chunk_by_id_not_found(
        self,
        mock_search_client
    ):
        """Test retrieving non-existent chunk returns None"""
        # Arrange
        chunk_id = "nonexistent_chunk"
        mock_search_client.get_document.side_effect = Exception("Document not found")

        # Create search service
        search_service = SearchService()
        search_service.search_client = mock_search_client

        # Act
        result = search_service.get_chunk_by_id(chunk_id)

        # Assert
        assert result is None
        mock_search_client.get_document.assert_called_once_with(key=chunk_id)