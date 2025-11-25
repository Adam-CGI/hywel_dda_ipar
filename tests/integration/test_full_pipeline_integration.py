"""
Integration tests for document processing pipeline
Tests complete flow: PDF upload → extraction → chunking → embedding → indexing
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from flask_app.services.indexing_pipeline_service import IndexingPipelineService


class TestDocumentProcessingPipeline:
    """Integration tests for complete document processing pipeline"""

    def test_full_pipeline_success(
        self,
        mock_extraction_service,
        mock_chunking_service,
        mock_embedding_service,
        mock_search_index_service,
        mock_cosmos_service,
        mock_storage_service,
        sample_pdf_bytes,
        sample_extraction_result,
        sample_chunks,
        sample_chunks_with_vectors
    ):
        """Test successful end-to-end pipeline execution"""
        # Arrange
        doc_id = "test_doc_123"
        filename = "test.pdf"
        
        # Configure mocks for successful pipeline
        mock_extraction_service.process_document.return_value = {
            "extraction_data": sample_extraction_result,
            "thumbnails": ["thumb1.png", "thumb2.png"],
            "manifest": {"page_count": 2, "table_count": 1, "text_length": 500, "thumbnail_count": 2}
        }
        mock_chunking_service.chunk_document.return_value = sample_chunks
        mock_embedding_service.embed_chunks.return_value = sample_chunks_with_vectors
        mock_search_index_service.upload_chunks.return_value = {"uploaded": 2, "failed": 0}
        mock_cosmos_service.create_document.return_value = None
        mock_cosmos_service.create_event.return_value = None

        # Create pipeline service
        pipeline = IndexingPipelineService()
        pipeline.extraction_service = mock_extraction_service
        pipeline.chunking_service = mock_chunking_service
        pipeline.embedding_service = mock_embedding_service
        pipeline.search_index_service = mock_search_index_service
        pipeline.cosmos_service = mock_cosmos_service
        pipeline.storage_service = mock_storage_service

        # Act
        result = pipeline.process_and_index_document(doc_id, sample_pdf_bytes, filename)

        # Assert - verify all pipeline steps were called in correct order
        mock_extraction_service.process_document.assert_called_once_with(doc_id, sample_pdf_bytes, filename)
        mock_chunking_service.chunk_document.assert_called_once_with(doc_id, sample_extraction_result)
        mock_embedding_service.embed_chunks.assert_called_once_with(sample_chunks)
        mock_search_index_service.upload_chunks.assert_called_once_with(sample_chunks_with_vectors)
        mock_cosmos_service.create_document.assert_called_once()
        mock_cosmos_service.create_event.assert_called_once()

        # Verify result structure
        assert result["doc_id"] == doc_id
        assert result["success"] is True
        assert result["chunks_created"] == 2
        assert result["chunks_uploaded"] == 2
        assert result["chunks_failed"] == 0
        assert "duration_seconds" in result
        assert "extraction_data" in result
        assert "thumbnails" in result
        assert "manifest" in result

    def test_pipeline_extraction_failure(
        self,
        mock_extraction_service,
        mock_cosmos_service,
        sample_pdf_bytes
    ):
        """Test pipeline handles extraction failures gracefully"""
        # Arrange
        doc_id = "test_doc_fail"
        filename = "bad.pdf"
        
        mock_extraction_service.process_document.side_effect = Exception("Document Intelligence extraction failed")
        
        # Create pipeline service
        pipeline = IndexingPipelineService()
        pipeline.extraction_service = mock_extraction_service
        pipeline.cosmos_service = mock_cosmos_service

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            pipeline.process_and_index_document(doc_id, sample_pdf_bytes, filename)

        assert "Document Intelligence extraction failed" in str(exc_info.value)
        
        # Verify error event was logged
        mock_cosmos_service.create_event.assert_called_once()
        event_call = mock_cosmos_service.create_event.call_args[0][0]
        assert event_call["event_type"] == "indexing_failed"
        assert event_call["doc_id"] == doc_id

    def test_pipeline_indexing_failure(
        self,
        mock_extraction_service,
        mock_chunking_service,
        mock_embedding_service,
        mock_search_index_service,
        mock_cosmos_service,
        sample_pdf_bytes,
        sample_extraction_result,
        sample_chunks,
        sample_chunks_with_vectors
    ):
        """Test pipeline handles search indexing failures"""
        # Arrange
        doc_id = "test_doc_index_fail"
        filename = "test.pdf"

        # Mock successful extraction, chunking, and embedding
        mock_extraction_service.process_document.return_value = {
            "extraction_data": sample_extraction_result,
            "thumbnails": ["thumb1.png"],
            "manifest": {"page_count": 1, "table_count": 0, "text_length": 100, "thumbnail_count": 1}
        }
        mock_chunking_service.chunk_document.return_value = sample_chunks
        mock_embedding_service.embed_chunks.return_value = sample_chunks_with_vectors

        # Mock indexing failure
        mock_search_index_service.upload_chunks.side_effect = Exception("AI Search service unavailable")

        # Create pipeline service
        pipeline = IndexingPipelineService()
        pipeline.extraction_service = mock_extraction_service
        pipeline.chunking_service = mock_chunking_service
        pipeline.embedding_service = mock_embedding_service
        pipeline.search_index_service = mock_search_index_service
        pipeline.cosmos_service = mock_cosmos_service

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            pipeline.process_and_index_document(doc_id, sample_pdf_bytes, filename)

        assert "AI Search service unavailable" in str(exc_info.value)

        # Verify error event was logged
        mock_cosmos_service.create_event.assert_called_once()
        event_call = mock_cosmos_service.create_event.call_args[0][0]
        assert event_call["event_type"] == "indexing_failed"

    def test_pipeline_data_transformation_validation(
        self,
        mock_extraction_service,
        mock_chunking_service,
        mock_embedding_service,
        mock_search_index_service,
        mock_cosmos_service,
        sample_pdf_bytes,
        sample_extraction_result,
        sample_chunks
    ):
        """Test data transformation and validation between service layers"""
        # Arrange
        doc_id = "test_transform"
        filename = "transform.pdf"
        
        # Configure mocks to return specific data structures
        mock_extraction_service.process_document.return_value = {
            "extraction_data": sample_extraction_result,
            "thumbnails": ["thumb1.png"],
            "manifest": {"page_count": 1, "table_count": 0, "text_length": 200, "thumbnail_count": 1}
        }
        
        # Chunks should be enriched with metadata during pipeline
        enriched_chunks = []
        for chunk in sample_chunks:
            enriched_chunk = chunk.copy()
            enriched_chunk.update({
                "logical_id": doc_id,
                "version": 1,
                "title": filename,
                "origin_filename": filename,
                "source_uri": f"blob://{doc_id}",
                "kpi_tags": []
            })
            enriched_chunks.append(enriched_chunk)
        
        mock_chunking_service.chunk_document.return_value = sample_chunks
        
        # Embedding service should receive enriched chunks
        chunks_with_vectors = [
            {**chunk, "vector": [0.1] * 3072} for chunk in enriched_chunks
        ]
        mock_embedding_service.embed_chunks.return_value = chunks_with_vectors
        mock_search_index_service.upload_chunks.return_value = {"uploaded": len(chunks_with_vectors), "failed": 0}

        # Create pipeline service
        pipeline = IndexingPipelineService()
        pipeline.extraction_service = mock_extraction_service
        pipeline.chunking_service = mock_chunking_service
        pipeline.embedding_service = mock_embedding_service
        pipeline.search_index_service = mock_search_index_service
        pipeline.cosmos_service = mock_cosmos_service

        # Act
        result = pipeline.process_and_index_document(doc_id, sample_pdf_bytes, filename)

        # Assert - verify data transformations
        # Check that chunking received extraction data
        chunking_call_args = mock_chunking_service.chunk_document.call_args
        assert chunking_call_args[0][0] == doc_id
        assert chunking_call_args[0][1] == sample_extraction_result

        # Check that embedding received enriched chunks
        embedding_call_args = mock_embedding_service.embed_chunks.call_args[0][0]
        for chunk in embedding_call_args:
            assert "logical_id" in chunk
            assert "version" in chunk
            assert "title" in chunk
            assert "origin_filename" in chunk
            assert "source_uri" in chunk
            assert "kpi_tags" in chunk

        # Check that search index received chunks with vectors
        search_call_args = mock_search_index_service.upload_chunks.call_args[0][0]
        for chunk in search_call_args:
            assert "vector" in chunk
            assert len(chunk["vector"]) == 3072

        # Verify Cosmos document metadata includes all required fields
        cosmos_call_args = mock_cosmos_service.create_document.call_args[0][0]
        required_fields = ["id", "doc_id", "logical_id", "origin_filename", "page_count", 
                          "chunk_count", "indexed_chunk_count", "status", "created_at", "indexed_at"]
        for field in required_fields:
            assert field in cosmos_call_args


class TestDocumentReindexing:
    """Integration tests for document reindexing functionality"""

    def test_reindex_document_success(
        self,
        mock_search_index_service,
        mock_cosmos_service,
        mock_storage_service,
        mock_chunking_service,
        mock_embedding_service,
        sample_extraction_result,
        sample_chunks,
        sample_chunks_with_vectors
    ):
        """Test successful document reindexing workflow"""
        # Arrange
        doc_id = "doc_to_reindex"

        # Mock existing document metadata
        existing_doc = {
            'id': doc_id,
            'doc_id': doc_id,
            'logical_id': 'logical_123',
            'version': 1,
            'title': 'Original Title',
            'origin_filename': 'original.pdf',
            'source_uri': f'blob://{doc_id}',
            'status': 'indexed',
            'indexed_chunk_count': 5
        }
        mock_cosmos_service.get_document.return_value = existing_doc

        # Mock extraction data from blob storage
        mock_storage_service.download_json.return_value = sample_extraction_result

        # Mock reindexing operations
        mock_search_index_service.delete_chunks_by_doc_id.return_value = 5  # Deleted old chunks
        mock_chunking_service.chunk_document.return_value = sample_chunks
        mock_embedding_service.embed_chunks.return_value = sample_chunks_with_vectors
        mock_search_index_service.upload_chunks.return_value = {"uploaded": 3, "failed": 0}

        # Create pipeline service
        pipeline = IndexingPipelineService()
        pipeline.search_index_service = mock_search_index_service
        pipeline.cosmos_service = mock_cosmos_service
        pipeline.storage_service = mock_storage_service
        pipeline.chunking_service = mock_chunking_service
        pipeline.embedding_service = mock_embedding_service

        # Act
        result = pipeline.reindex_document(doc_id)

        # Assert - verify reindexing workflow
        # 1. Old chunks deleted
        mock_search_index_service.delete_chunks_by_doc_id.assert_called_once_with(doc_id)
        
        # 2. Document metadata retrieved
        mock_cosmos_service.get_document.assert_called_once_with(doc_id)
        
        # 3. Extraction data downloaded
        mock_storage_service.download_json.assert_called_once()
        
        # 4. Document re-chunked with metadata enrichment
        chunking_call_args = mock_chunking_service.chunk_document.call_args[0]
        assert chunking_call_args[0] == doc_id
        assert chunking_call_args[1] == sample_extraction_result
        
        # 5. Chunks re-embedded
        mock_embedding_service.embed_chunks.assert_called_once()
        
        # 6. New chunks uploaded
        mock_search_index_service.upload_chunks.assert_called_once()
        
        # 7. Document metadata updated
        mock_cosmos_service.update_document.assert_called_once()
        
        # 8. Reindex event logged
        mock_cosmos_service.create_event.assert_called_once()

        # Verify result structure
        assert result["doc_id"] == doc_id
        assert result["success"] is True
        assert result["chunks_deleted"] == 5
        assert result["chunks_created"] == len(sample_chunks)
        assert result["chunks_uploaded"] == 3
        assert result["chunks_failed"] == 0

    def test_reindex_document_not_found(self, mock_cosmos_service):
        """Test reindexing non-existent document raises appropriate error"""
        # Arrange
        doc_id = "nonexistent"
        mock_cosmos_service.get_document.return_value = None

        # Create pipeline service
        pipeline = IndexingPipelineService()
        pipeline.cosmos_service = mock_cosmos_service

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            pipeline.reindex_document(doc_id)

        assert "not found" in str(exc_info.value).lower()
        mock_cosmos_service.get_document.assert_called_once_with(doc_id)

    def test_reindex_document_missing_extraction_data(
        self,
        mock_cosmos_service,
        mock_storage_service
    ):
        """Test reindexing when extraction data is missing from blob storage"""
        # Arrange
        doc_id = "doc_no_extraction"
        
        mock_cosmos_service.get_document.return_value = {
            'id': doc_id,
            'status': 'indexed'
        }

        # Extraction data not found in blob storage
        mock_storage_service.download_json.side_effect = Exception("Blob not found")

        # Create pipeline service
        pipeline = IndexingPipelineService()
        pipeline.cosmos_service = mock_cosmos_service
        pipeline.storage_service = mock_storage_service

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            pipeline.reindex_document(doc_id)
            
        assert "Blob not found" in str(exc_info.value)
        mock_storage_service.download_json.assert_called_once()


class TestPipelineErrorRecovery:
    """Integration tests for pipeline error recovery and rollback scenarios"""

    def test_pipeline_partial_failure_recovery(
        self,
        mock_extraction_service,
        mock_chunking_service,
        mock_embedding_service,
        mock_search_index_service,
        mock_cosmos_service,
        sample_pdf_bytes,
        sample_extraction_result,
        sample_chunks
    ):
        """Test pipeline handles partial failures with proper error logging"""
        # Arrange
        doc_id = "partial_failure_doc"
        filename = "partial.pdf"
        
        # Configure successful extraction and chunking
        mock_extraction_service.process_document.return_value = {
            "extraction_data": sample_extraction_result,
            "thumbnails": ["thumb1.png"],
            "manifest": {"page_count": 1, "table_count": 0, "text_length": 100, "thumbnail_count": 1}
        }
        mock_chunking_service.chunk_document.return_value = sample_chunks
        
        # Embedding succeeds but search indexing fails
        chunks_with_vectors = [{**chunk, "vector": [0.1] * 3072} for chunk in sample_chunks]
        mock_embedding_service.embed_chunks.return_value = chunks_with_vectors
        mock_search_index_service.upload_chunks.side_effect = Exception("Search service timeout")

        # Create pipeline service
        pipeline = IndexingPipelineService()
        pipeline.extraction_service = mock_extraction_service
        pipeline.chunking_service = mock_chunking_service
        pipeline.embedding_service = mock_embedding_service
        pipeline.search_index_service = mock_search_index_service
        pipeline.cosmos_service = mock_cosmos_service

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            pipeline.process_and_index_document(doc_id, sample_pdf_bytes, filename)

        assert "Search service timeout" in str(exc_info.value)
        
        # Verify that extraction and chunking completed successfully before failure
        mock_extraction_service.process_document.assert_called_once()
        mock_chunking_service.chunk_document.assert_called_once()
        mock_embedding_service.embed_chunks.assert_called_once()
        
        # Verify error event was logged
        mock_cosmos_service.create_event.assert_called_once()
        event_call = mock_cosmos_service.create_event.call_args[0][0]
        assert event_call["event_type"] == "indexing_failed"
        assert "Search service timeout" in event_call["error"]

    def test_pipeline_multi_step_error_handling(
        self,
        mock_extraction_service,
        mock_chunking_service,
        mock_cosmos_service,
        sample_pdf_bytes
    ):
        """Test pipeline error handling across multiple processing steps"""
        # Arrange
        doc_id = "multi_error_doc"
        filename = "error.pdf"
        
        # First call succeeds, second call fails
        mock_extraction_service.process_document.side_effect = [
            Exception("Temporary extraction failure"),
            Exception("Persistent extraction failure")
        ]

        # Create pipeline service
        pipeline = IndexingPipelineService()
        pipeline.extraction_service = mock_extraction_service
        pipeline.cosmos_service = mock_cosmos_service

        # Act & Assert - First attempt
        with pytest.raises(Exception) as exc_info:
            pipeline.process_and_index_document(doc_id, sample_pdf_bytes, filename)
        
        assert "Temporary extraction failure" in str(exc_info.value)
        
        # Verify error was logged
        first_event_call = mock_cosmos_service.create_event.call_args[0][0]
        assert first_event_call["event_type"] == "indexing_failed"
        
        # Reset mock for second attempt
        mock_cosmos_service.reset_mock()
        
        # Act & Assert - Second attempt
        with pytest.raises(Exception) as exc_info:
            pipeline.process_and_index_document(doc_id, sample_pdf_bytes, filename)
        
        assert "Persistent extraction failure" in str(exc_info.value)
        
        # Verify second error was also logged
        second_event_call = mock_cosmos_service.create_event.call_args[0][0]
        assert second_event_call["event_type"] == "indexing_failed"


    def test_pipeline_rollback_on_critical_failure(
        self,
        mock_extraction_service,
        mock_chunking_service,
        mock_embedding_service,
        mock_search_index_service,
        mock_cosmos_service,
        sample_pdf_bytes,
        sample_extraction_result,
        sample_chunks
    ):
        """Test pipeline behavior when critical failures occur during processing"""
        # Arrange
        doc_id = "rollback_doc"
        filename = "rollback.pdf"
        
        # Configure successful early stages
        mock_extraction_service.process_document.return_value = {
            "extraction_data": sample_extraction_result,
            "thumbnails": ["thumb1.png"],
            "manifest": {"page_count": 1, "table_count": 0, "text_length": 100, "thumbnail_count": 1}
        }
        mock_chunking_service.chunk_document.return_value = sample_chunks
        
        # Embedding fails with critical error
        mock_embedding_service.embed_chunks.side_effect = Exception("OpenAI API quota exceeded")

        # Create pipeline service
        pipeline = IndexingPipelineService()
        pipeline.extraction_service = mock_extraction_service
        pipeline.chunking_service = mock_chunking_service
        pipeline.embedding_service = mock_embedding_service
        pipeline.search_index_service = mock_search_index_service
        pipeline.cosmos_service = mock_cosmos_service

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            pipeline.process_and_index_document(doc_id, sample_pdf_bytes, filename)

        assert "OpenAI API quota exceeded" in str(exc_info.value)
        
        # Verify that processing stopped at embedding stage
        mock_extraction_service.process_document.assert_called_once()
        mock_chunking_service.chunk_document.assert_called_once()
        mock_embedding_service.embed_chunks.assert_called_once()
        
        # Search indexing should not have been attempted
        mock_search_index_service.upload_chunks.assert_not_called()
        
        # Error should be logged
        mock_cosmos_service.create_event.assert_called_once()
        event_call = mock_cosmos_service.create_event.call_args[0][0]
        assert event_call["event_type"] == "indexing_failed"
        assert "OpenAI API quota exceeded" in event_call["error"]
