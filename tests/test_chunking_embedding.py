"""
Tests for EPIC C: Chunking, Embedding & Indexing

Tests cover:
- Chunking determinism
- Embedding batch processing
- Search index operations
- Full pipeline integration
"""
import pytest
from unittest.mock import Mock, patch
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.search_index_service import SearchIndexService


class TestChunkingService:
    """Tests for ChunkingService (Epic C Story 5)."""
    
    def test_chunk_id_determinism(self):
        """Test that chunk IDs are deterministic."""
        chunker = ChunkingService()
        doc_id = "test_doc_123"
        page_no = 1
        page_text = "This is a test document. " * 50  # Longer text to get multiple chunks
        
        # Chunk the same page 3 times
        chunks_run1 = chunker.chunk_page(doc_id, page_no, page_text)
        chunks_run2 = chunker.chunk_page(doc_id, page_no, page_text)
        chunks_run3 = chunker.chunk_page(doc_id, page_no, page_text)
        
        # Extract IDs
        ids_run1 = [c["id"] for c in chunks_run1]
        ids_run2 = [c["id"] for c in chunks_run2]
        ids_run3 = [c["id"] for c in chunks_run3]
        
        # All runs should produce identical IDs
        assert ids_run1 == ids_run2 == ids_run3, "Chunking is not deterministic"
        assert len(ids_run1) > 0, "No chunks were created"
    
    def test_chunk_id_format(self):
        """Test that chunk IDs are SHA256 hashes."""
        chunker = ChunkingService()
        doc_id = "test_doc_456"
        page_no = 1
        page_text = "Test text for chunk ID validation."
        
        chunks = chunker.chunk_page(doc_id, page_no, page_text)
        
        assert len(chunks) > 0, "No chunks created"
        
        for chunk in chunks:
            chunk_id = chunk["id"]
            # SHA256 hash should be 64 hex characters
            assert len(chunk_id) == 64, f"Chunk ID length is {len(chunk_id)}, expected 64"
            assert all(c in '0123456789abcdef' for c in chunk_id), "Chunk ID contains non-hex characters"
    
    def test_chunk_has_required_fields(self):
        """Test that chunks have all required fields for indexing."""
        chunker = ChunkingService()
        doc_id = "test_doc_789"
        page_no = 2
        page_text = "This chunk should have all required fields: id, doc_id, page_no, text, spans, metadata."
        
        chunks = chunker.chunk_page(doc_id, page_no, page_text)
        
        assert len(chunks) > 0, "No chunks created"
        
        required_fields = ["id", "doc_id", "page_no", "text", "spans", "metadata"]
        for chunk in chunks:
            for field in required_fields:
                assert field in chunk, f"Chunk missing required field: {field}"
            
            # Verify types
            assert isinstance(chunk["id"], str)
            assert isinstance(chunk["doc_id"], str)
            assert isinstance(chunk["page_no"], int)
            assert isinstance(chunk["text"], str)
            assert isinstance(chunk["spans"], list)
            assert isinstance(chunk["metadata"], dict)
    
    def test_chunk_spans_are_mapped(self):
        """Test that chunks have span information for citations."""
        chunker = ChunkingService()
        doc_id = "test_doc_spans"
        page_no = 1
        page_text = "This text needs span mapping for citations. " * 20
        
        chunks = chunker.chunk_page(doc_id, page_no, page_text)
        
        assert len(chunks) > 0, "No chunks created"
        
        for chunk in chunks:
            assert len(chunk["spans"]) > 0, "Chunk has no spans"
            
            for span in chunk["spans"]:
                assert "start" in span, "Span missing 'start' field"
                assert "end" in span, "Span missing 'end' field"
                assert "page_no" in span, "Span missing 'page_no' field"
                
                # Verify span is valid
                assert span["start"] >= 0
                assert span["end"] > span["start"]
                assert span["page_no"] == page_no
    
    def test_chunk_document_with_multiple_pages(self):
        """Test chunking a multi-page document."""
        chunker = ChunkingService()
        doc_id = "test_multi_page"
        
        extraction_data = {
            "pages": [
                {"page_no": 1, "text": "First page content. " * 30, "width": 612, "height": 792, "unit": "pt"},
                {"page_no": 2, "text": "Second page content. " * 30, "width": 612, "height": 792, "unit": "pt"},
                {"page_no": 3, "text": "Third page content. " * 30, "width": 612, "height": 792, "unit": "pt"}
            ]
        }
        
        chunks = chunker.chunk_document(doc_id, extraction_data)
        
        assert len(chunks) > 0, "No chunks created for multi-page document"
        
        # Verify chunks from different pages
        page_numbers = set(c["page_no"] for c in chunks)
        assert len(page_numbers) == 3, f"Expected chunks from 3 pages, got {len(page_numbers)}"
        assert page_numbers == {1, 2, 3}
    
    def test_verify_chunk_determinism_helper(self):
        """Test the determinism verification helper method."""
        chunker = ChunkingService()
        doc_id = "determinism_test"
        page_no = 1
        page_text = "Testing determinism verification. " * 40
        
        is_deterministic = chunker.verify_chunk_determinism(doc_id, page_no, page_text, iterations=5)
        
        assert is_deterministic is True, "Chunking failed determinism verification"


class TestEmbeddingService:
    """Tests for EmbeddingService (Epic C Story 6)."""
    
    @patch('app.services.embedding_service.AzureOpenAI')
    def test_embedding_dimension(self, mock_openai):
        """Test that embeddings have correct dimension (3072)."""
        # Mock Azure OpenAI response
        mock_response = Mock()
        mock_embedding_item = Mock()
        mock_embedding_item.embedding = [0.1] * 3072  # 3072-dim vector
        mock_response.data = [mock_embedding_item]
        
        mock_client = Mock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        embedding_service = EmbeddingService()
        texts = ["Test text for embedding"]
        
        embeddings = embedding_service.embed_texts(texts)
        
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 3072, f"Expected dimension 3072, got {len(embeddings[0])}"
    
    @patch('app.services.embedding_service.AzureOpenAI')
    def test_batch_size_limit(self, mock_openai):
        """Test that batches respect 512 chunk limit."""
        # Mock Azure OpenAI response
        def create_mock_response(num_texts):
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 3072) for _ in range(num_texts)]
            return mock_response
        
        mock_client = Mock()
        mock_client.embeddings.create.side_effect = lambda **kwargs: create_mock_response(len(kwargs['input']))
        mock_openai.return_value = mock_client
        
        embedding_service = EmbeddingService()
        
        # Test batch under limit
        texts_small = ["Text " + str(i) for i in range(100)]
        embeddings_small = embedding_service.embed_texts(texts_small)
        assert len(embeddings_small) == 100
        assert mock_client.embeddings.create.call_count == 1
        
        # Reset mock
        mock_client.embeddings.create.reset_mock()
        
        # Test batch over limit (should split into multiple batches)
        texts_large = ["Text " + str(i) for i in range(600)]
        embeddings_large = embedding_service.embed_texts(texts_large)
        assert len(embeddings_large) == 600
        # Should be called twice: 512 + 88
        assert mock_client.embeddings.create.call_count == 2
    
    @patch('app.services.embedding_service.AzureOpenAI')
    def test_embed_chunks_adds_vector_field(self, mock_openai):
        """Test that embed_chunks adds 'vector' field to chunks."""
        # Mock Azure OpenAI response
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1] * 3072),
            Mock(embedding=[0.2] * 3072)
        ]
        
        mock_client = Mock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        embedding_service = EmbeddingService()
        
        chunks = [
            {"id": "chunk1", "text": "First chunk text"},
            {"id": "chunk2", "text": "Second chunk text"}
        ]
        
        enriched_chunks = embedding_service.embed_chunks(chunks)
        
        assert len(enriched_chunks) == 2
        for chunk in enriched_chunks:
            assert "vector" in chunk, "Chunk missing 'vector' field"
            assert len(chunk["vector"]) == 3072
    
    @patch('app.services.embedding_service.AzureOpenAI')
    def test_batch_info_calculation(self, mock_openai):
        """Test batch information calculation."""
        mock_openai.return_value = Mock()
        embedding_service = EmbeddingService()
        
        # Test exact batch size
        info_512 = embedding_service.batch_info(512)
        assert info_512["num_batches"] == 1
        assert info_512["last_batch_size"] == 512
        
        # Test over one batch
        info_600 = embedding_service.batch_info(600)
        assert info_600["num_batches"] == 2
        assert info_600["last_batch_size"] == 88
        
        # Test multiple batches
        info_1500 = embedding_service.batch_info(1500)
        assert info_1500["num_batches"] == 3
        assert info_1500["last_batch_size"] == 476


class TestSearchIndexService:
    """Tests for SearchIndexService (Epic C Story 7)."""
    
    @patch('app.services.search_index_service.SearchIndexClient')
    @patch('app.services.search_index_service.SearchClient')
    def test_create_index_structure(self, mock_search_client, mock_index_client):
        """Test that index is created with correct structure."""
        # Mock index client
        mock_idx_client_instance = Mock()
        mock_idx_client_instance.get_index.side_effect = Exception("Index does not exist")
        mock_idx_client_instance.create_index.return_value = Mock(name="ipar-chunks")
        mock_index_client.return_value = mock_idx_client_instance
        
        mock_search_client.return_value = Mock()
        
        search_service = SearchIndexService()
        search_service.create_index()
        
        # Verify create_index was called
        assert mock_idx_client_instance.create_index.called
        call_args = mock_idx_client_instance.create_index.call_args[0][0]
        
        # Verify index name
        assert call_args.name == "ipar-chunks"
        
        # Verify key field exists
        field_names = [f.name for f in call_args.fields]
        assert "id" in field_names
        assert "doc_id" in field_names
        assert "page_no" in field_names
        assert "text" in field_names
        assert "vector" in field_names
    
    @patch('app.services.search_index_service.SearchIndexClient')
    @patch('app.services.search_index_service.SearchClient')
    def test_upload_chunks_format(self, mock_search_client, mock_index_client):
        """Test that chunks are correctly formatted for upload."""
        # Mock clients
        mock_idx_client_instance = Mock()
        mock_idx_client_instance.get_index.return_value = Mock(name="ipar-chunks")
        mock_index_client.return_value = mock_idx_client_instance
        
        mock_search_instance = Mock()
        mock_upload_result = [Mock(succeeded=True), Mock(succeeded=True)]
        mock_search_instance.upload_documents.return_value = mock_upload_result
        mock_search_client.return_value = mock_search_instance
        
        search_service = SearchIndexService()
        
        chunks = [
            {
                "id": "chunk1",
                "doc_id": "doc123",
                "page_no": 1,
                "text": "Test chunk text",
                "vector": [0.1] * 3072,
                "spans": [{"start": 0, "end": 15, "page_no": 1}]
            },
            {
                "id": "chunk2",
                "doc_id": "doc123",
                "page_no": 2,
                "text": "Another chunk",
                "vector": [0.2] * 3072,
                "spans": [{"start": 0, "end": 13, "page_no": 2}]
            }
        ]
        
        result = search_service.upload_chunks(chunks)
        
        assert result["uploaded"] == 2
        assert result["failed"] == 0
        assert mock_search_instance.upload_documents.called
    
    @patch('app.services.search_index_service.SearchIndexClient')
    @patch('app.services.search_index_service.SearchClient')
    def test_delete_chunks_by_doc_id(self, mock_search_client, mock_index_client):
        """Test deletion of chunks by document ID."""
        # Mock clients
        mock_index_client.return_value = Mock()
        
        mock_search_instance = Mock()
        # Mock search results
        mock_search_instance.search.return_value = [
            {"id": "chunk1"},
            {"id": "chunk2"},
            {"id": "chunk3"}
        ]
        # Mock delete results
        mock_delete_result = [Mock(succeeded=True) for _ in range(3)]
        mock_search_instance.delete_documents.return_value = mock_delete_result
        mock_search_client.return_value = mock_search_instance
        
        search_service = SearchIndexService()
        
        deleted_count = search_service.delete_chunks_by_doc_id("doc123")
        
        assert deleted_count == 3
        assert mock_search_instance.search.called
        assert mock_search_instance.delete_documents.called


class TestIntegration:
    """Integration tests for full pipeline."""
    
    def test_chunking_to_embedding_compatibility(self):
        """Test that chunked output is compatible with embedding service input."""
        chunker = ChunkingService()
        
        # Create sample extraction data
        extraction_data = {
            "pages": [
                {"page_no": 1, "text": "Sample page text for testing. " * 30}
            ]
        }
        
        chunks = chunker.chunk_document("test_doc", extraction_data)
        
        # Verify chunks can be passed to embedding service
        assert len(chunks) > 0
        for chunk in chunks:
            assert "text" in chunk
            assert isinstance(chunk["text"], str)
            assert len(chunk["text"]) > 0
    
    def test_embedded_chunks_ready_for_indexing(self):
        """Test that embedded chunks have all fields required for indexing."""
        # Create mock chunks with embeddings
        chunks = [
            {
                "id": "chunk_abc123",
                "doc_id": "doc_xyz789",
                "logical_id": "doc_xyz789",
                "version": 1,
                "source_uri": "blob://doc_xyz789",
                "title": "Test Document",
                "origin_filename": "test.pdf",
                "page_no": 1,
                "observed_date": "2024-01-01T00:00:00",
                "kpi_tags": [],
                "text": "This is test chunk text.",
                "spans": [{"start": 0, "end": 24, "page_no": 1}],
                "vector": [0.1] * 3072,
                "metadata": {}
            }
        ]
        
        # Verify all required fields for AI Search are present
        required_fields = [
            "id", "doc_id", "logical_id", "version", "source_uri",
            "title", "origin_filename", "page_no", "observed_date",
            "kpi_tags", "text", "spans", "vector"
        ]
        
        for chunk in chunks:
            for field in required_fields:
                assert field in chunk, f"Chunk missing required field for indexing: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
