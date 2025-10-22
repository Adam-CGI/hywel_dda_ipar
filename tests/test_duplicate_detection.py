"""
Tests for EPIC D — Duplicate & Version Control

Tests cover:
1. Exact duplicate detection (sha256)
2. Logical duplicate detection and versioning
3. Near-duplicate detection
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.storage_service import StorageService
from app.services.cosmos_service import CosmosService
from app.services.embedding_service import EmbeddingService


class TestExactDuplicateDetection:
    """Test EPIC D.8 — Exact Duplicate Detection"""
    
    def test_compute_sha256(self):
        """Test SHA256 computation for exact duplicate detection"""
        storage_service = StorageService()
        
        # Same bytes should produce same hash
        file_bytes = b"Test PDF content"
        doc_id_1 = storage_service.compute_sha256(file_bytes)
        doc_id_2 = storage_service.compute_sha256(file_bytes)
        
        assert doc_id_1 == doc_id_2
        assert len(doc_id_1) == 64  # SHA256 produces 64 hex chars
    
    def test_different_files_different_hash(self):
        """Test that different files produce different hashes"""
        storage_service = StorageService()
        
        file_bytes_1 = b"Test PDF content 1"
        file_bytes_2 = b"Test PDF content 2"
        
        doc_id_1 = storage_service.compute_sha256(file_bytes_1)
        doc_id_2 = storage_service.compute_sha256(file_bytes_2)
        
        assert doc_id_1 != doc_id_2
    
    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_exact_duplicate_detected_in_cosmos(self, mock_container):
        """Test that exact duplicates are detected when checking Cosmos"""
        # Setup mock
        mock_documents_container = MagicMock()
        mock_container.return_value = mock_documents_container
        
        # Mock existing document
        existing_doc = {
            'id': 'test_doc_id',
            'doc_id': 'test_doc_id',
            'origin_filename': 'test.pdf',
            'version': 1
        }
        mock_documents_container.read_item.return_value = existing_doc
        
        # Test
        cosmos_service = CosmosService()
        result = cosmos_service.get_document('test_doc_id')
        
        assert result is not None
        assert result['doc_id'] == 'test_doc_id'
        assert cosmos_service.document_exists('test_doc_id')


class TestLogicalDuplicateDetection:
    """Test EPIC D.9 — Logical Duplicate Detection & Versioning"""
    
    def test_compute_logical_id(self):
        """Test logical_id computation from normalized text"""
        storage_service = StorageService()
        
        # Same text with different whitespace should produce same logical_id
        text1 = "This is a test document.\nWith multiple lines."
        text2 = "This   is  a   test   document.   With   multiple   lines."
        text3 = "THIS IS A TEST DOCUMENT.\nWITH MULTIPLE LINES."
        
        logical_id_1 = storage_service.compute_logical_id(text1)
        logical_id_2 = storage_service.compute_logical_id(text2)
        logical_id_3 = storage_service.compute_logical_id(text3)
        
        # All should produce same logical_id due to normalization
        assert logical_id_1 == logical_id_2 == logical_id_3
        assert len(logical_id_1) == 64  # SHA256
    
    def test_different_content_different_logical_id(self):
        """Test that different content produces different logical_id"""
        storage_service = StorageService()
        
        text1 = "This is document A"
        text2 = "This is document B"
        
        logical_id_1 = storage_service.compute_logical_id(text1)
        logical_id_2 = storage_service.compute_logical_id(text2)
        
        assert logical_id_1 != logical_id_2
    
    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_find_by_logical_id(self, mock_container):
        """Test finding documents by logical_id"""
        # Setup mock
        mock_documents_container = MagicMock()
        mock_container.return_value = mock_documents_container
        
        # Mock query results
        matching_docs = [
            {'id': 'doc1', 'logical_id': 'logical123', 'version': 1},
            {'id': 'doc2', 'logical_id': 'logical123', 'version': 2}
        ]
        mock_documents_container.query_items.return_value = matching_docs
        
        # Test
        cosmos_service = CosmosService()
        results = cosmos_service.find_by_logical_id('logical123')
        
        assert len(results) == 2
        assert all(doc['logical_id'] == 'logical123' for doc in results)
    
    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_get_latest_version(self, mock_container):
        """Test retrieving latest version by logical_id"""
        # Setup mock
        mock_documents_container = MagicMock()
        mock_container.return_value = mock_documents_container
        
        # Mock query results - version 3 should be latest
        matching_docs = [
            {'id': 'doc3', 'logical_id': 'logical123', 'version': 3, 'superseded': False}
        ]
        mock_documents_container.query_items.return_value = matching_docs
        
        # Test
        cosmos_service = CosmosService()
        latest = cosmos_service.get_latest_version('logical123')
        
        assert latest is not None
        assert latest['version'] == 3
        assert latest['superseded'] is False
    
    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_mark_as_superseded(self, mock_container):
        """Test marking a document as superseded"""
        # Setup mocks
        mock_documents_container = MagicMock()
        mock_container.return_value = mock_documents_container
        
        # Mock existing document
        existing_doc = {
            'id': 'doc1',
            'doc_id': 'doc1',
            'version': 1,
            'superseded': False
        }
        mock_documents_container.read_item.return_value = existing_doc
        mock_documents_container.upsert_item.return_value = {**existing_doc, 'superseded': True}
        
        # Test
        cosmos_service = CosmosService()
        result = cosmos_service.mark_as_superseded('doc1')
        
        assert result is not None
        # Verify upsert was called
        mock_documents_container.upsert_item.assert_called()


class TestNearDuplicateDetection:
    """Test EPIC D.10 — Near-Duplicate Detection"""
    
    def test_cosine_similarity_identical_vectors(self):
        """Test cosine similarity with identical vectors"""
        embedding_service = EmbeddingService()
        
        vec1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        vec2 = [1.0, 2.0, 3.0, 4.0, 5.0]
        
        similarity = embedding_service.compute_cosine_similarity(vec1, vec2)
        
        assert similarity == pytest.approx(1.0, abs=0.001)
    
    def test_cosine_similarity_orthogonal_vectors(self):
        """Test cosine similarity with orthogonal vectors"""
        embedding_service = EmbeddingService()
        
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        
        similarity = embedding_service.compute_cosine_similarity(vec1, vec2)
        
        assert similarity == pytest.approx(0.0, abs=0.001)
    
    def test_cosine_similarity_opposite_vectors(self):
        """Test cosine similarity with opposite vectors"""
        embedding_service = EmbeddingService()
        
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]
        
        similarity = embedding_service.compute_cosine_similarity(vec1, vec2)
        
        assert similarity == pytest.approx(-1.0, abs=0.001)
    
    def test_cosine_similarity_similar_vectors(self):
        """Test cosine similarity with highly similar vectors"""
        embedding_service = EmbeddingService()
        
        vec1 = [1.0, 2.0, 3.0, 4.0]
        vec2 = [1.01, 2.01, 3.01, 4.01]
        
        similarity = embedding_service.compute_cosine_similarity(vec1, vec2)
        
        # Should be very close to 1.0
        assert similarity > 0.999
    
    def test_is_near_duplicate_true(self):
        """Test near-duplicate detection returns True for similar vectors"""
        embedding_service = EmbeddingService()
        
        # Very similar vectors (> 0.995 similarity)
        vec1 = [1.0] * 100
        vec2 = [1.0] * 100
        
        assert embedding_service.is_near_duplicate(vec1, vec2, threshold=0.995)
    
    def test_is_near_duplicate_false(self):
        """Test near-duplicate detection returns False for dissimilar vectors"""
        embedding_service = EmbeddingService()
        
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        
        assert not embedding_service.is_near_duplicate(vec1, vec2, threshold=0.995)
    
    def test_near_duplicate_custom_threshold(self):
        """Test near-duplicate detection with custom threshold"""
        embedding_service = EmbeddingService()
        
        # Vectors with moderate similarity (~0.95)
        vec1 = [1.0, 2.0, 3.0, 4.0]
        vec2 = [1.0, 2.0, 3.0, 3.5]
        
        # Calculate actual similarity
        actual_similarity = embedding_service.compute_cosine_similarity(vec1, vec2)
        
        # Should be near-duplicate with lower threshold
        assert embedding_service.is_near_duplicate(vec1, vec2, threshold=0.85)
        
        # Use a threshold just above actual similarity for negative test
        assert not embedding_service.is_near_duplicate(vec1, vec2, threshold=actual_similarity + 0.01)
    
    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_lineage_near_duplicate(self, mock_container):
        """Test saving near-duplicate relationship to lineage"""
        # Setup mock
        mock_lineage_container = MagicMock()
        mock_container.return_value = mock_lineage_container
        
        mock_lineage_container.create_item.return_value = {'id': 'lineage1'}
        
        # Test
        cosmos_service = CosmosService()
        lineage_data = {
            'source_doc_id': 'doc1',
            'target_doc_id': 'doc2',
            'relationship_type': 'near_duplicate',
            'similarity_score': 0.996
        }
        
        result = cosmos_service.save_lineage(lineage_data)
        
        assert result is not None
        mock_lineage_container.create_item.assert_called_once()


class TestIntegrationVersioning:
    """Integration tests for versioning workflow"""
    
    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_version_increment_workflow(self, mock_container):
        """Test full versioning workflow: find existing -> increment version -> mark superseded"""
        # Setup mocks
        mock_documents_container = MagicMock()
        mock_container.return_value = mock_documents_container
        
        # Mock existing version 1
        existing_v1 = {
            'id': 'doc1',
            'doc_id': 'doc1',
            'logical_id': 'logical123',
            'version': 1,
            'superseded': False
        }
        
        # For get_latest_version query
        mock_documents_container.query_items.return_value = [existing_v1]
        
        # For get_document
        mock_documents_container.read_item.return_value = existing_v1
        
        # For mark_as_superseded
        updated_v1 = {**existing_v1, 'superseded': True}
        mock_documents_container.upsert_item.return_value = updated_v1
        
        # Test workflow
        cosmos_service = CosmosService()
        
        # Step 1: Find latest version
        latest = cosmos_service.get_latest_version('logical123')
        assert latest is not None
        assert latest['version'] == 1
        
        # Step 2: Calculate new version
        new_version = latest['version'] + 1
        assert new_version == 2
        
        # Step 3: Mark old version as superseded
        result = cosmos_service.mark_as_superseded('doc1')
        assert result is not None


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_text_logical_id(self):
        """Test logical_id computation with empty text"""
        storage_service = StorageService()
        
        logical_id = storage_service.compute_logical_id("")
        
        assert logical_id is not None
        assert len(logical_id) == 64
    
    def test_unicode_text_logical_id(self):
        """Test logical_id computation with unicode text"""
        storage_service = StorageService()
        
        text = "Document with émojis 😀 and spëcial çharacters"
        logical_id = storage_service.compute_logical_id(text)
        
        assert logical_id is not None
        assert len(logical_id) == 64
    
    def test_zero_vector_cosine_similarity(self):
        """Test cosine similarity with zero vectors"""
        embedding_service = EmbeddingService()
        
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        
        similarity = embedding_service.compute_cosine_similarity(vec1, vec2)
        
        # Should return 0 when one vector is zero
        assert similarity == 0.0
    
    def test_both_zero_vectors_cosine_similarity(self):
        """Test cosine similarity when both vectors are zero"""
        embedding_service = EmbeddingService()
        
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [0.0, 0.0, 0.0]
        
        similarity = embedding_service.compute_cosine_similarity(vec1, vec2)
        
        # Should return 0 when both vectors are zero
        assert similarity == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
