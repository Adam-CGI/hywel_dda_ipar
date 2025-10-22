"""
Unit tests for CosmosService
Tests document metadata persistence, versioning, lineage tracking, and event logging.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.services.cosmos_service import CosmosService


class TestSaveDocument:
    """Test saving document metadata to Cosmos DB"""

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_document_new(self, mock_get_container):
        """Test saving a new document"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_metadata = {
            'id': 'doc123',
            'doc_id': 'doc123',
            'origin_filename': 'test.pdf',
            'page_count': 5,
            'status': 'extracted'
        }

        mock_container.upsert_item.return_value = doc_metadata
        service = CosmosService()

        # Act
        result = service.save_document(doc_metadata)

        # Assert
        mock_container.upsert_item.assert_called_once()
        assert result == doc_metadata

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_document_with_timestamps(self, mock_get_container):
        """Test that timestamps are set correctly"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_metadata = {
            'id': 'doc123',
            'doc_id': 'doc123',
            'origin_filename': 'test.pdf'
        }

        def upsert_side_effect(item):
            return item

        mock_container.upsert_item.side_effect = upsert_side_effect
        service = CosmosService()

        # Act
        result = service.save_document(doc_metadata)

        # Assert
        assert 'updated_at' in result

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_document_update_existing(self, mock_get_container):
        """Test updating an existing document"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_metadata = {
            'id': 'doc123',
            'doc_id': 'doc123',
            'status': 'indexed',  # Updated status
            'indexed_chunk_count': 42
        }

        mock_container.upsert_item.return_value = doc_metadata
        service = CosmosService()

        # Act
        result = service.save_document(doc_metadata)

        # Assert
        assert result['status'] == 'indexed'
        assert result['indexed_chunk_count'] == 42

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_document_with_embedding(self, mock_get_container):
        """Test saving document with embedding vector"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_metadata = {
            'id': 'doc123',
            'doc_id': 'doc123',
            'doc_embedding': [0.1] * 3072
        }

        mock_container.upsert_item.return_value = doc_metadata
        service = CosmosService()

        # Act
        result = service.save_document(doc_metadata)

        # Assert
        assert 'doc_embedding' in result
        assert len(result['doc_embedding']) == 3072


class TestGetDocument:
    """Test retrieving document metadata from Cosmos DB"""

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_get_document_exists(self, mock_get_container):
        """Test retrieving an existing document"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_id = 'doc123'
        expected_doc = {
            'id': doc_id,
            'doc_id': doc_id,
            'origin_filename': 'test.pdf',
            'status': 'indexed'
        }

        mock_container.read_item.return_value = expected_doc
        service = CosmosService()

        # Act
        result = service.get_document(doc_id)

        # Assert
        mock_container.read_item.assert_called_once_with(
            item=doc_id,
            partition_key=doc_id
        )
        assert result == expected_doc

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_get_document_not_found(self, mock_get_container):
        """Test retrieving non-existent document"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_id = 'nonexistent'

        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        mock_container.read_item.side_effect = CosmosResourceNotFoundError(message="Not found")
        service = CosmosService()

        # Act
        result = service.get_document(doc_id)

        # Assert
        assert result is None

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_get_document_error_handling(self, mock_get_container):
        """Test error handling during document retrieval"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_id = 'doc123'
        mock_container.read_item.side_effect = Exception("Database error")
        service = CosmosService()

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            service.get_document(doc_id)

        assert "Database error" in str(exc_info.value)


class TestFindByLogicalId:
    """Test finding documents by logical ID"""

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_find_by_logical_id_single_match(self, mock_get_container):
        """Test finding document with matching logical ID"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        logical_id = 'logical123'
        expected_docs = [
            {
                'id': 'doc123',
                'logical_id': logical_id,
                'version': 1
            }
        ]

        mock_container.query_items.return_value = expected_docs
        service = CosmosService()

        # Act
        result = service.find_by_logical_id(logical_id)

        # Assert
        mock_container.query_items.assert_called_once()
        call_args = mock_container.query_items.call_args
        query = call_args[1]['query']
        assert 'logical_id' in query
        assert len(result) == 1
        assert result[0]['logical_id'] == logical_id

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_find_by_logical_id_multiple_versions(self, mock_get_container):
        """Test finding multiple versions with same logical ID"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        logical_id = 'logical123'
        expected_docs = [
            {'id': 'doc1', 'logical_id': logical_id, 'version': 1},
            {'id': 'doc2', 'logical_id': logical_id, 'version': 2},
            {'id': 'doc3', 'logical_id': logical_id, 'version': 3}
        ]

        mock_container.query_items.return_value = expected_docs
        service = CosmosService()

        # Act
        result = service.find_by_logical_id(logical_id)

        # Assert
        assert len(result) == 3
        assert all(doc['logical_id'] == logical_id for doc in result)

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_find_by_logical_id_no_matches(self, mock_get_container):
        """Test finding with no matches"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        logical_id = 'nonexistent'
        mock_container.query_items.return_value = []
        service = CosmosService()

        # Act
        result = service.find_by_logical_id(logical_id)

        # Assert
        assert result == []


class TestMarkAsDeleted:
    """Test marking documents as deleted (soft delete)"""

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_mark_as_deleted_success(self, mock_get_container):
        """Test successfully marking document as deleted"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_id = 'doc123'
        existing_doc = {
            'id': doc_id,
            'doc_id': doc_id,
            'is_deleted': False,
            'status': 'indexed'
        }

        # Mock get_document to return existing doc, then save_document to return updated doc
        mock_container.read_item.return_value = existing_doc
        mock_container.upsert_item.return_value = {**existing_doc, 'is_deleted': True}
        
        service = CosmosService()

        # Act
        result = service.mark_as_deleted(doc_id)

        # Assert
        mock_container.read_item.assert_called_once_with(item=doc_id, partition_key=doc_id)
        mock_container.upsert_item.assert_called_once()

        saved_doc = mock_container.upsert_item.call_args[0][0]
        assert saved_doc['is_deleted'] is True

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_mark_as_deleted_not_found(self, mock_get_container):
        """Test marking non-existent document as deleted"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_id = 'nonexistent'
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        mock_container.read_item.side_effect = CosmosResourceNotFoundError(message="Not found")
        
        service = CosmosService()

        # Act
        result = service.mark_as_deleted(doc_id)

        # Assert
        assert result is None

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_mark_as_deleted_already_deleted(self, mock_get_container):
        """Test marking already deleted document"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_id = 'doc123'
        existing_doc = {
            'id': doc_id,
            'is_deleted': True
        }

        mock_container.read_item.return_value = existing_doc
        mock_container.upsert_item.return_value = existing_doc
        
        service = CosmosService()

        # Act
        result = service.mark_as_deleted(doc_id)

        # Assert
        # Should still work, may be idempotent
        assert result is not None


class TestMarkAsSuperseded:
    """Test marking documents as superseded"""

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_mark_as_superseded_success(self, mock_get_container):
        """Test successfully marking document as superseded"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        old_doc_id = 'doc_old'

        existing_doc = {
            'id': old_doc_id,
            'superseded': False
        }

        mock_container.read_item.return_value = existing_doc
        mock_container.upsert_item.return_value = {
            **existing_doc,
            'superseded': True
        }
        
        service = CosmosService()

        # Act
        result = service.mark_as_superseded(old_doc_id)

        # Assert
        saved_doc = mock_container.upsert_item.call_args[0][0]
        assert saved_doc['superseded'] is True

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_mark_as_superseded_not_found(self, mock_get_container):
        """Test marking non-existent document as superseded"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        old_doc_id = 'nonexistent'

        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        mock_container.read_item.side_effect = CosmosResourceNotFoundError(message="Not found")
        
        service = CosmosService()

        # Act
        result = service.mark_as_superseded(old_doc_id)

        # Assert
        assert result is None


class TestLogEvent:
    """Test event logging to Cosmos DB"""

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_log_event_upload(self, mock_get_container):
        """Test logging upload event"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        event_type = 'upload'
        doc_id = 'doc123'
        details = {'filename': 'test.pdf', 'size_bytes': 1024}

        mock_container.create_item.return_value = {'id': 'event1'}
        service = CosmosService()

        # Act
        result = service.log_event(event_type, doc_id, details)

        # Assert
        mock_container.create_item.assert_called_once()

        event = mock_container.create_item.call_args[0][0]
        assert event['event_type'] == event_type
        assert event['doc_id'] == doc_id
        assert event['details'] == details
        assert 'timestamp' in event
        assert 'id' in event

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_log_event_indexed(self, mock_get_container):
        """Test logging indexed event"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        event_type = 'indexed'
        doc_id = 'doc123'
        details = {'chunk_count': 42}

        mock_container.create_item.return_value = {'id': 'event2'}
        service = CosmosService()

        # Act
        service.log_event(event_type, doc_id, details)

        # Assert
        event = mock_container.create_item.call_args[0][0]
        assert event['event_type'] == 'indexed'
        assert event['details']['chunk_count'] == 42

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_log_event_with_user_id(self, mock_get_container):
        """Test logging event with user ID"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        event_type = 'search'
        doc_id = None  # Search not tied to specific doc
        details = {'query': 'test query'}
        user_id = 'user123'

        mock_container.create_item.return_value = {'id': 'event3'}
        service = CosmosService()

        # Act
        service.log_event(event_type, doc_id, details, user_id=user_id)

        # Assert
        event = mock_container.create_item.call_args[0][0]
        assert event.get('user_id') == user_id

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_log_event_generates_unique_id(self, mock_get_container):
        """Test that each event gets unique ID"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        mock_container.create_item.side_effect = lambda x: x
        
        service = CosmosService()

        # Act
        event1 = service.log_event('test', 'doc1', {})
        event2 = service.log_event('test', 'doc2', {})

        # Assert
        assert event1['id'] != event2['id']


class TestSaveLineage:
    """Test saving document lineage relationships"""

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_lineage_near_duplicate(self, mock_get_container):
        """Test saving near-duplicate lineage"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        lineage_data = {
            'source_doc_id': 'doc1',
            'target_doc_id': 'doc2',
            'relationship_type': 'near_duplicate',
            'similarity_score': 0.997
        }

        mock_container.create_item.return_value = {'id': 'lineage1'}
        service = CosmosService()

        # Act
        result = service.save_lineage(lineage_data)

        # Assert
        mock_container.create_item.assert_called_once()

        lineage = mock_container.create_item.call_args[0][0]
        assert lineage['source_doc_id'] == 'doc1'
        assert lineage['target_doc_id'] == 'doc2'
        assert lineage['relationship_type'] == 'near_duplicate'
        assert lineage['similarity_score'] == 0.997
        assert 'created_at' in lineage

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_lineage_version(self, mock_get_container):
        """Test saving version lineage"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        lineage_data = {
            'source_doc_id': 'doc_v1',
            'target_doc_id': 'doc_v2',
            'relationship_type': 'version'
        }

        mock_container.create_item.return_value = {'id': 'lineage2'}
        service = CosmosService()

        # Act
        service.save_lineage(lineage_data)

        # Assert
        lineage = mock_container.create_item.call_args[0][0]
        assert lineage['relationship_type'] == 'version'

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_lineage_generates_unique_id(self, mock_get_container):
        """Test that each lineage record gets unique ID"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        mock_container.create_item.side_effect = lambda x: x
        
        service = CosmosService()

        # Act
        lineage1 = service.save_lineage({'source_doc_id': 'doc1', 'target_doc_id': 'doc2', 'relationship_type': 'test'})
        lineage2 = service.save_lineage({'source_doc_id': 'doc3', 'target_doc_id': 'doc4', 'relationship_type': 'test'})

        # Assert
        assert lineage1['id'] != lineage2['id']


class TestVersioning:
    """Test document versioning logic"""

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_create_new_version(self, mock_get_container):
        """Test creating a new version of an existing document"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        logical_id = 'logical123'
        old_doc_id = 'doc_v1'
        new_doc_id = 'doc_v2'

        # Mock find_by_logical_id to return existing versions
        mock_container.query_items.return_value = [
            {'id': old_doc_id, 'logical_id': logical_id, 'version': 1}
        ]

        new_doc = {
            'id': new_doc_id,
            'logical_id': logical_id,
            'version': 2,
            'supersedes': old_doc_id
        }

        mock_container.upsert_item.return_value = new_doc
        service = CosmosService()

        # Act
        result = service.save_document(new_doc)

        # Assert
        assert result['version'] == 2
        assert result['supersedes'] == old_doc_id


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_document_with_unicode(self, mock_get_container):
        """Test saving document with unicode characters"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_metadata = {
            'id': 'doc123',
            'origin_filename': 'テスト.pdf',  # Japanese
            'content': 'Español, 中文, العربية'
        }

        mock_container.upsert_item.return_value = doc_metadata
        service = CosmosService()

        # Act
        result = service.save_document(doc_metadata)

        # Assert
        assert result['origin_filename'] == 'テスト.pdf'

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_document_large_metadata(self, mock_get_container):
        """Test saving document with large metadata"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        doc_metadata = {
            'id': 'doc123',
            'doc_embedding': [0.1] * 3072,  # Large vector
            'manifest': {'pages': [{'text': 'x' * 10000}] * 100}  # Large manifest
        }

        mock_container.upsert_item.return_value = doc_metadata
        service = CosmosService()

        # Act
        result = service.save_document(doc_metadata)

        # Assert
        assert len(result['doc_embedding']) == 3072

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_log_event_without_doc_id(self, mock_get_container):
        """Test logging event not tied to specific document"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        
        event_type = 'system_health_check'
        details = {'status': 'healthy'}

        mock_container.create_item.return_value = {'id': 'event1'}
        service = CosmosService()

        # Act
        result = service.log_event(event_type, None, details)

        # Assert
        assert result is not None
        event = mock_container.create_item.call_args[0][0]
        assert event['doc_id'] is None

    @patch('app.services.cosmos_service.get_cosmos_container')
    def test_save_lineage_bidirectional(self, mock_get_container):
        """Test that lineage can be saved in both directions"""
        # Arrange
        mock_container = Mock()
        mock_get_container.return_value = mock_container
        mock_container.create_item.side_effect = lambda x: x
        
        service = CosmosService()

        # Act
        lineage1 = service.save_lineage({
            'source_doc_id': 'doc1',
            'target_doc_id': 'doc2',
            'relationship_type': 'related',
            'similarity_score': 0.98
        })
        lineage2 = service.save_lineage({
            'source_doc_id': 'doc2',
            'target_doc_id': 'doc1',
            'relationship_type': 'related',
            'similarity_score': 0.98
        })

        # Assert
        assert lineage1['source_doc_id'] == 'doc1'
        assert lineage1['target_doc_id'] == 'doc2'
        assert lineage2['source_doc_id'] == 'doc2'
        assert lineage2['target_doc_id'] == 'doc1'
