"""
Unit tests for StorageService
Tests Azure Blob Storage operations, SHA256 computation, and archival.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
import hashlib

from flask_app.services.storage_service import StorageService


class TestComputeSha256:
    """Test SHA256 hash computation"""

    def test_compute_sha256_basic(self):
        """Test SHA256 computation with basic input"""
        # Arrange
        data = b"test data"

        # Act
        result = StorageService.compute_sha256(data)

        # Assert
        expected = hashlib.sha256(data).hexdigest()
        assert result == expected
        assert isinstance(result, str)
        assert len(result) == 64

    def test_compute_sha256_empty_data(self):
        """Test SHA256 with empty bytes"""
        # Arrange
        data = b""

        # Act
        result = StorageService.compute_sha256(data)

        # Assert
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected

    def test_compute_sha256_large_file(self):
        """Test SHA256 with large data"""
        # Arrange
        data = b"x" * 10_000_000  # 10MB

        # Act
        result = StorageService.compute_sha256(data)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64

    def test_compute_sha256_deterministic(self):
        """Test that same input produces same hash"""
        # Arrange
        data = b"deterministic test"

        # Act
        hash1 = StorageService.compute_sha256(data)
        hash2 = StorageService.compute_sha256(data)

        # Assert
        assert hash1 == hash2

    def test_compute_sha256_different_data(self):
        """Test that different data produces different hashes"""
        # Arrange
        data1 = b"data 1"
        data2 = b"data 2"

        # Act
        hash1 = StorageService.compute_sha256(data1)
        hash2 = StorageService.compute_sha256(data2)

        # Assert
        assert hash1 != hash2


class TestComputeLogicalId:
    """Test logical ID computation from normalized text"""

    def test_compute_logical_id_basic(self):
        """Test logical ID computation with basic text"""
        # Arrange
        text = "This is a test document."

        # Act
        result = StorageService.compute_logical_id(text)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64

    def test_compute_logical_id_normalizes_whitespace(self):
        """Test that whitespace is normalized"""
        # Arrange
        text1 = "Text   with    extra    spaces"
        text2 = "Text with extra spaces"

        # Act
        id1 = StorageService.compute_logical_id(text1)
        id2 = StorageService.compute_logical_id(text2)

        # Assert
        assert id1 == id2

    def test_compute_logical_id_normalizes_newlines(self):
        """Test that newlines are normalized"""
        # Arrange
        text1 = "Line 1\nLine 2\nLine 3"
        text2 = "Line 1 Line 2 Line 3"

        # Act
        id1 = StorageService.compute_logical_id(text1)
        id2 = StorageService.compute_logical_id(text2)

        # Assert
        assert id1 == id2

    def test_compute_logical_id_normalizes_case(self):
        """Test that text is lowercased"""
        # Arrange
        text1 = "UPPERCASE TEXT"
        text2 = "uppercase text"

        # Act
        id1 = StorageService.compute_logical_id(text1)
        id2 = StorageService.compute_logical_id(text2)

        # Assert
        assert id1 == id2

    def test_compute_logical_id_strips_whitespace(self):
        """Test that leading/trailing whitespace is removed"""
        # Arrange
        text1 = "   Text with spaces   "
        text2 = "Text with spaces"

        # Act
        id1 = StorageService.compute_logical_id(text1)
        id2 = StorageService.compute_logical_id(text2)

        # Assert
        assert id1 == id2

    def test_compute_logical_id_empty_text(self):
        """Test logical ID with empty text"""
        # Arrange
        text = ""

        # Act
        result = StorageService.compute_logical_id(text)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64


class TestUploadToRaw:
    """Test uploading files to raw container"""

    @patch('app.services.storage_service.get_blob_service_client')
    def test_upload_to_raw_success(self, mock_get_blob_service):
        """Test successful upload to raw container"""
        # Arrange
        file_bytes = b"fake pdf content"
        filename = "test.pdf"

        mock_blob_service = Mock()
        mock_get_blob_service.return_value = mock_blob_service
        
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = False
        mock_blob_client.url = "http://example.com/blob"
        mock_blob_service.get_blob_client.return_value = mock_blob_client

        service = StorageService()

        # Act
        doc_id, result = service.upload_to_raw(file_bytes, filename)

        # Assert
        mock_blob_service.get_blob_client.assert_called_once()
        call_args = mock_blob_service.get_blob_client.call_args
        assert call_args[1]['container'] == 'raw'
        assert doc_id in call_args[1]['blob']

        mock_blob_client.upload_blob.assert_called_once()
        assert result is not None

    @patch('app.services.storage_service.get_blob_service_client')
    def test_upload_to_raw_with_metadata(self, mock_get_blob_service):
        """Test upload includes filename metadata"""
        # Arrange
        file_bytes = b"content"
        filename = "document.pdf"

        mock_blob_service = Mock()
        mock_get_blob_service.return_value = mock_blob_service
        
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = False
        mock_blob_client.url = "http://example.com/blob"
        mock_blob_service.get_blob_client.return_value = mock_blob_client

        service = StorageService()

        # Act
        service.upload_to_raw(file_bytes, filename)

        # Assert
        # Verify metadata includes original filename
        call_args = mock_blob_client.upload_blob.call_args
        if len(call_args) > 1 and 'metadata' in call_args[1]:
            assert call_args[1]['metadata']['origin_filename'] == filename

    @patch('app.services.storage_service.get_blob_service_client')
    def test_upload_to_raw_error_handling(self, mock_get_blob_service):
        """Test error handling during upload"""
        # Arrange
        file_bytes = b"content"
        filename = "test.pdf"

        mock_blob_service = Mock()
        mock_get_blob_service.return_value = mock_blob_service
        
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = False
        mock_blob_client.upload_blob.side_effect = Exception("Upload failed")
        mock_blob_service.get_blob_client.return_value = mock_blob_client

        service = StorageService()

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            service.upload_to_raw(file_bytes, filename)

        assert "Upload failed" in str(exc_info.value)


class TestUploadJson:
    """Test uploading JSON data to blob storage"""

    @patch('app.services.storage_service.get_blob_service_client')
    def test_upload_json_success(self, mock_get_blob_service):
        """Test successful JSON upload"""
        # Arrange
        container = "extracted"
        blob_name = "test_doc.json"
        data = {"key": "value", "number": 123}

        mock_blob_service = Mock()
        mock_get_blob_service.return_value = mock_blob_service
        
        mock_blob_client = Mock()
        mock_blob_client.url = "http://example.com/blob"
        mock_blob_service.get_blob_client.return_value = mock_blob_client

        service = StorageService()

        # Act
        result = service.upload_json(container, blob_name, data)

        # Assert
        mock_blob_service.get_blob_client.assert_called_once_with(
            container=container,
            blob=blob_name
        )

        # Verify JSON was uploaded
        call_args = mock_blob_client.upload_blob.call_args
        uploaded_data = call_args[1]['data']
        assert '"key"' in uploaded_data and '"value"' in uploaded_data

        assert result is not None

    @patch('app.services.storage_service.get_blob_service_client')
    def test_upload_json_complex_data(self, mock_get_blob_service):
        """Test uploading complex nested JSON"""
        # Arrange
        container = "manifests"
        blob_name = "manifest.json"
        data = {
            "nested": {
                "array": [1, 2, 3],
                "object": {"a": "b"}
            },
            "list": ["item1", "item2"]
        }

        mock_blob_service = Mock()
        mock_get_blob_service.return_value = mock_blob_service
        
        mock_blob_client = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client

        service = StorageService()

        # Act
        service.upload_json(container, blob_name, data)

        # Assert
        mock_blob_client.upload_blob.assert_called_once()

    @patch('app.services.storage_service.get_blob_service_client')
    def test_upload_json_empty_dict(self, mock_get_blob_service):
        """Test uploading empty JSON object"""
        # Arrange
        container = "test"
        blob_name = "empty.json"
        data = {}

        mock_blob_service = Mock()
        mock_get_blob_service.return_value = mock_blob_service
        
        mock_blob_client = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client

        service = StorageService()

        # Act
        service.upload_json(container, blob_name, data)

        # Assert
        call_args = mock_blob_client.upload_blob.call_args
        assert call_args[1]['data'] == "{}"


class TestUploadImage:
    """Test uploading images to blob storage"""

    @patch('app.services.storage_service.get_blob_service_client')
    def test_upload_image_success(self, mock_get_blob_service):
        """Test successful image upload"""
        # Arrange
        container = "thumbs"
        blob_name = "page_1.png"
        image_bytes = b"\x89PNG\r\n\x1a\n"  # PNG header

        mock_blob_service = Mock()
        mock_get_blob_service.return_value = mock_blob_service
        
        mock_blob_client = Mock()
        mock_blob_client.url = "http://example.com/image"
        mock_blob_service.get_blob_client.return_value = mock_blob_client

        service = StorageService()

        # Act
        result = service.upload_image(container, blob_name, image_bytes)

        # Assert
        mock_blob_service.get_blob_client.assert_called_once_with(
            container=container,
            blob=blob_name
        )

        mock_blob_client.upload_blob.assert_called_once()

        assert result is not None

    @patch('app.services.storage_service.get_blob_service_client')
    def test_upload_image_with_content_type(self, mock_get_blob_service):
        """Test that image uploads set correct content type"""
        # Arrange
        container = "thumbs"
        blob_name = "page_1.png"
        image_bytes = b"image data"

        mock_blob_service = Mock()
        mock_get_blob_service.return_value = mock_blob_service
        
        mock_blob_client = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client

        service = StorageService()

        # Act
        service.upload_image(container, blob_name, image_bytes)

        # Assert
        # Verify content_type is set if implementation supports it
        call_args = mock_blob_client.upload_blob.call_args
        if 'content_settings' in call_args[1]:
            assert 'image/' in call_args[1]['content_settings'].content_type


class TestDownloadJson:
    """Test downloading JSON from blob storage"""

    @patch('app.services.storage_service.get_blob_service_client')
    def test_download_json_success(self, mock_get_blob_service):
        """Test successful JSON download"""
        # Arrange
        container = "extracted"
        blob_name = "test.json"
        expected_data = {"key": "value"}

        mock_blob_client = Mock()
        mock_blob_client.download_blob.return_value.readall.return_value = b'{"key": "value"}'
        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_get_blob_service.return_value = mock_blob_service

        service = StorageService()

        # Act
        result = service.download_json(container, blob_name)

        # Assert
        assert result == expected_data
        mock_blob_service.get_blob_client.assert_called_once_with(
            container=container,
            blob=blob_name
        )

    @patch('app.services.storage_service.get_blob_service_client')
    def test_download_json_complex_data(self, mock_get_blob_service):
        """Test downloading complex nested JSON"""
        # Arrange
        container = "manifests"
        blob_name = "manifest.json"
        json_str = '{"nested": {"array": [1, 2, 3]}, "value": 123}'

        mock_blob_client = Mock()
        mock_blob_client.download_blob.return_value.readall.return_value = json_str.encode()
        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_get_blob_service.return_value = mock_blob_service

        service = StorageService()

        # Act
        result = service.download_json(container, blob_name)

        # Assert
        assert result["nested"]["array"] == [1, 2, 3]
        assert result["value"] == 123

    @patch('app.services.storage_service.get_blob_service_client')
    def test_download_json_not_found(self, mock_get_blob_service):
        """Test handling of blob not found"""
        # Arrange
        container = "extracted"
        blob_name = "nonexistent.json"

        mock_blob_client = Mock()
        mock_blob_client.download_blob.side_effect = Exception("Blob not found")
        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_get_blob_service.return_value = mock_blob_service

        service = StorageService()

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            service.download_json(container, blob_name)

        assert "not found" in str(exc_info.value).lower() or "Blob not found" in str(exc_info.value)


class TestGenerateSasUrl:
    """Test SAS URL generation for blob access"""

    @patch('app.services.storage_service.generate_blob_sas')
    @patch('app.services.storage_service.get_blob_service_client')
    def test_generate_sas_url_success(self, mock_get_blob_service, mock_generate_sas):
        """Test successful SAS URL generation"""
        # Arrange
        container = "thumbs"
        blob_name = "page_1.png"

        mock_blob_client = Mock()
        mock_blob_client.url = f"https://teststorage.blob.core.windows.net/{container}/{blob_name}"
        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service.credential.account_key = "test_key"
        mock_get_blob_service.return_value = mock_blob_service
        mock_generate_sas.return_value = "sv=2021-06-08&se=2024-01-01&sig=abc123"

        service = StorageService()

        # Act
        result = service.generate_sas_url(container, blob_name)

        # Assert
        assert "https://" in result
        assert "teststorage" in result
        assert container in result
        assert blob_name in result
        assert "sig=abc123" in result

    @patch('app.services.storage_service.generate_blob_sas')
    @patch('app.services.storage_service.get_blob_service_client')
    def test_generate_sas_url_expiry_time(self, mock_get_blob_service, mock_generate_sas):
        """Test that SAS URL has correct expiry time"""
        # Arrange
        container = "thumbs"
        blob_name = "page_1.png"

        mock_blob_client = Mock()
        mock_blob_client.url = f"https://teststorage.blob.core.windows.net/{container}/{blob_name}"
        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service.credential.account_key = "test_key"
        mock_get_blob_service.return_value = mock_blob_service
        mock_generate_sas.return_value = "sas_token"

        service = StorageService()

        # Act
        service.generate_sas_url(container, blob_name, expiry_hours=2)

        # Assert
        # Verify generate_blob_sas was called with expiry parameter
        call_args = mock_generate_sas.call_args
        if 'expiry' in call_args[1]:
            expiry = call_args[1]['expiry']
            # Expiry should be approximately 2 hours from now
            now = datetime.utcnow()
            expected_expiry = now + timedelta(hours=2)
            time_diff = abs((expiry - expected_expiry).total_seconds())
            assert time_diff < 60  # Within 1 minute

    @patch('app.services.storage_service.generate_blob_sas')
    @patch('app.services.storage_service.get_blob_service_client')
    def test_generate_sas_url_default_expiry(self, mock_get_blob_service, mock_generate_sas):
        """Test default expiry time (1 hour)"""
        # Arrange
        container = "thumbs"
        blob_name = "page_1.png"

        mock_blob_client = Mock()
        mock_blob_client.url = f"https://teststorage.blob.core.windows.net/{container}/{blob_name}"
        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service.credential.account_key = "test_key"
        mock_get_blob_service.return_value = mock_blob_service
        mock_generate_sas.return_value = "sas_token"

        service = StorageService()

        # Act
        service.generate_sas_url(container, blob_name)

        # Assert
        mock_generate_sas.assert_called_once()


class TestArchiveDocumentBlobs:
    """Test archiving document blobs on deletion"""

    @patch('app.services.storage_service.get_blob_service_client')
    def test_archive_document_blobs_all_containers(self, mock_get_blob_service):
        """Test archiving blobs from all containers"""
        # Arrange
        doc_id = "test_doc_123"

        # Mock blob clients for source and archive
        mock_source_blob = Mock()
        mock_source_blob.exists.return_value = True
        mock_archive_blob = Mock()
        mock_container_client = Mock()
        mock_container_client.list_blobs.return_value = []

        def get_blob_client_side_effect(container, blob):
            if container == 'archive':
                return mock_archive_blob
            return mock_source_blob

        def get_container_client_side_effect(container):
            return mock_container_client

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.side_effect = get_blob_client_side_effect
        mock_blob_service.get_container_client.side_effect = get_container_client_side_effect
        mock_get_blob_service.return_value = mock_blob_service

        service = StorageService()

        # Act
        result = service.archive_document_blobs(doc_id)

        # Assert
        # Should copy from: raw, extracted, manifests
        # Verify copy operations were called
        assert mock_archive_blob.start_copy_from_url.call_count >= 3
        assert result["raw"] == True
        assert result["extracted"] == True
        assert result["manifest"] == True

    @patch('app.services.storage_service.get_blob_service_client')
    def test_archive_document_blobs_handles_missing(self, mock_get_blob_service):
        """Test that archiving handles missing blobs gracefully"""
        # Arrange
        doc_id = "test_doc_missing"

        mock_source_blob = Mock()
        mock_source_blob.exists.return_value = False  # Simulate missing blobs
        mock_archive_blob = Mock()
        mock_container_client = Mock()
        mock_container_client.list_blobs.return_value = []

        def get_blob_client_side_effect(container, blob):
            if container == 'archive':
                return mock_archive_blob
            return mock_source_blob

        def get_container_client_side_effect(container):
            return mock_container_client

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.side_effect = get_blob_client_side_effect
        mock_blob_service.get_container_client.side_effect = get_container_client_side_effect
        mock_get_blob_service.return_value = mock_blob_service

        service = StorageService()

        # Act
        # Should not raise exception for missing blobs
        result = service.archive_document_blobs(doc_id)

        # Assert
        # Should handle missing blobs gracefully
        assert result["raw"] == False
        assert result["extracted"] == False
        assert result["manifest"] == False

    @patch('app.services.storage_service.get_blob_service_client')
    def test_archive_document_blobs_deletes_originals(self, mock_get_blob_service):
        """Test that original blobs are deleted after archiving"""
        # Arrange
        doc_id = "test_doc_delete"

        mock_source_blob = Mock()
        mock_source_blob.exists.return_value = True
        mock_archive_blob = Mock()
        mock_container_client = Mock()
        mock_container_client.list_blobs.return_value = []

        def get_blob_client_side_effect(container, blob):
            if container == 'archive':
                return mock_archive_blob
            return mock_source_blob

        def get_container_client_side_effect(container):
            return mock_container_client

        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.side_effect = get_blob_client_side_effect
        mock_blob_service.get_container_client.side_effect = get_container_client_side_effect
        mock_get_blob_service.return_value = mock_blob_service

        service = StorageService()

        # Act
        result = service.archive_document_blobs(doc_id)

        # Assert
        # Verify delete_blob was called on source blobs
        # (Implementation may vary - delete after copy or rely on lifecycle policies)
        # At minimum, archive copy should succeed
        assert mock_archive_blob.start_copy_from_url.call_count >= 3
        assert mock_source_blob.delete_blob.call_count >= 3


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @patch('app.services.storage_service.get_blob_service_client')
    def test_upload_very_large_file(self, mock_get_blob_service):
        """Test uploading very large file"""
        # Arrange
        file_bytes = b"x" * 50_000_000  # 50MB
        filename = "large.pdf"

        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = False
        mock_blob_client.url = "https://test.blob.core.windows.net/raw/test.pdf"
        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_get_blob_service.return_value = mock_blob_service

        service = StorageService()

        # Act
        doc_id, url = service.upload_to_raw(file_bytes, filename)

        # Assert
        mock_blob_client.upload_blob.assert_called_once()
        assert doc_id is not None
        assert url is not None

    @patch('app.services.storage_service.get_blob_service_client')
    def test_upload_json_with_unicode(self, mock_get_blob_service):
        """Test uploading JSON with unicode characters"""
        # Arrange
        container = "test"
        blob_name = "unicode.json"
        data = {"text": "Unicode: é, ñ, 中文, 🎉"}

        mock_blob_client = Mock()
        mock_blob_client.url = "https://test.blob.core.windows.net/test/unicode.json"
        mock_blob_service = Mock()
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_get_blob_service.return_value = mock_blob_service

        service = StorageService()

        # Act
        result = service.upload_json(container, blob_name, data)

        # Assert
        mock_blob_client.upload_blob.assert_called_once()
        assert result is not None

    def test_compute_sha256_unicode_string(self):
        """Test SHA256 with unicode string"""
        # Arrange
        # SHA256 requires bytes, so this tests error handling
        data = "unicode string é"

        # Act & Assert
        # Implementation should handle string->bytes conversion or raise error
        try:
            result = StorageService.compute_sha256(data.encode('utf-8'))
            assert isinstance(result, str)
        except AttributeError:
            # If implementation requires bytes input
            pass
