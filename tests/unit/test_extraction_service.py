"""
Unit tests for ExtractionService
Tests PDF extraction, thumbnail generation, and manifest creation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from io import BytesIO
from PIL import Image
import json

from flask_app.services.extraction_service import ExtractionService


class TestExtractDocument:
    """Test PDF text and layout extraction using Document Intelligence"""

    @patch('app.services.extraction_service.get_document_intelligence_client')
    @patch('app.services.extraction_service.StorageService')
    def test_extract_document_success(self, mock_storage_class, mock_get_doc_intel):
        """Test successful document extraction with text and tables"""
        # Arrange
        doc_id = "test_doc_123"
        file_bytes = b"fake_pdf_content"

        # Mock Document Intelligence client
        mock_doc_intel = Mock()
        mock_get_doc_intel.return_value = mock_doc_intel

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        # Mock Document Intelligence response
        mock_result = Mock()
        mock_page1 = Mock()
        mock_page1.width = 8.5
        mock_page1.height = 11.0
        mock_page1.unit = "inch"

        mock_line1 = Mock()
        mock_line1.content = "This is line 1"
        mock_line1.polygon = [Mock(), Mock(), Mock(), Mock()]

        mock_page1.lines = [mock_line1]
        mock_page1.words = []

        mock_result.pages = [mock_page1]
        mock_result.tables = []

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result
        mock_doc_intel.begin_analyze_document.return_value = mock_poller

        service = ExtractionService()

        # Act
        result = service.extract_document(doc_id, file_bytes)

        # Assert
        assert result is not None
        assert result['doc_id'] == doc_id
        assert 'pages' in result
        assert len(result['pages']) == 1
        assert result['pages'][0]['page_no'] == 1
        assert result['pages'][0]['text'] == "This is line 1\n"

        # Verify Document Intelligence was called
        mock_doc_intel.begin_analyze_document.assert_called_once()

        # Verify storage upload
        mock_storage.upload_json.assert_called_once()

    @patch('app.services.extraction_service.get_document_intelligence_client')
    @patch('app.services.extraction_service.StorageService')
    def test_extract_document_no_tables(self, mock_storage_class, mock_get_doc_intel):
        """Test extraction when document has no tables"""
        # Arrange
        doc_id = "test_doc_no_tables"
        file_bytes = b"fake_pdf_content"

        # Mock Document Intelligence client
        mock_doc_intel = Mock()
        mock_get_doc_intel.return_value = mock_doc_intel

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        mock_result = Mock()
        mock_page = Mock()
        mock_page.width = 8.5
        mock_page.height = 11.0
        mock_page.unit = "inch"
        mock_page.lines = []
        mock_page.words = []

        mock_result.pages = [mock_page]
        mock_result.tables = None  # No tables

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result
        mock_doc_intel.begin_analyze_document.return_value = mock_poller

        service = ExtractionService()

        # Act
        result = service.extract_document(doc_id, file_bytes)

        # Assert
        assert result is not None
        assert result['tables'] == []

    @patch('app.services.extraction_service.get_document_intelligence_client')
    @patch('app.services.extraction_service.StorageService')
    def test_extract_document_empty_pdf(self, mock_storage_class, mock_get_doc_intel):
        """Test extraction of empty PDF"""
        # Arrange
        doc_id = "test_doc_empty"
        file_bytes = b"fake_pdf_content"

        # Mock Document Intelligence client
        mock_doc_intel = Mock()
        mock_get_doc_intel.return_value = mock_doc_intel

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        mock_result = Mock()
        mock_result.pages = []
        mock_result.tables = []

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result
        mock_doc_intel.begin_analyze_document.return_value = mock_poller

        service = ExtractionService()

        # Act
        result = service.extract_document(doc_id, file_bytes)

        # Assert
        assert result is not None
        assert result['pages'] == []

    @patch('app.services.extraction_service.get_document_intelligence_client')
    @patch('app.services.extraction_service.StorageService')
    def test_extract_document_api_error(self, mock_storage_class, mock_get_doc_intel):
        """Test handling of Document Intelligence API errors"""
        # Arrange
        doc_id = "test_doc_error"
        file_bytes = b"fake_pdf_content"

        # Mock Document Intelligence client
        mock_doc_intel = Mock()
        mock_get_doc_intel.return_value = mock_doc_intel

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        mock_doc_intel.begin_analyze_document.side_effect = Exception("API Error")

        service = ExtractionService()

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            service.extract_document(doc_id, file_bytes)

        assert "API Error" in str(exc_info.value)


class TestGenerateThumbnails:
    """Test thumbnail generation from PDF pages"""

    @patch('app.services.extraction_service.pdfium')
    @patch('app.services.extraction_service.StorageService')
    def test_generate_thumbnails_success(self, mock_storage_class, mock_pdfium):
        """Test successful thumbnail generation"""
        # Arrange
        doc_id = "test_doc_123"
        file_bytes = b"fake_pdf_content"

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        mock_storage.upload_image.return_value = "http://example.com/thumb.png"

        # Mock PDF rendering
        mock_pdf = Mock()
        mock_page = Mock()

        # Create a fake PIL image
        fake_image = Image.new('RGB', (1000, 1000), color='white')
        mock_render_result = Mock()
        mock_render_result.to_pil.return_value = fake_image
        mock_page.render.return_value = mock_render_result

        mock_pdf.__len__ = Mock(return_value=2)
        mock_pdf.__getitem__ = Mock(side_effect=[mock_page, mock_page])

        mock_pdfium.PdfDocument.return_value = mock_pdf

        service = ExtractionService()

        # Act
        result = service.generate_thumbnails(doc_id, file_bytes)

        # Assert
        assert len(result) == 2
        assert mock_storage.upload_image.call_count == 2

    @patch('app.services.extraction_service.pdfium')
    @patch('app.services.extraction_service.StorageService')
    def test_generate_thumbnails_resize(self, mock_storage_class, mock_pdfium):
        """Test that large images are resized to max 800x800"""
        # Arrange
        doc_id = "test_doc_large"
        file_bytes = b"fake_pdf_content"

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        mock_storage.upload_image.return_value = "http://example.com/thumb.png"

        # Create a large image that should be resized
        large_image = Image.new('RGB', (2000, 3000), color='white')

        mock_pdf = Mock()
        mock_page = Mock()
        mock_render_result = Mock()
        mock_render_result.to_pil.return_value = large_image
        mock_page.render.return_value = mock_render_result

        mock_pdf.__len__ = Mock(return_value=1)
        mock_pdf.__getitem__ = Mock(return_value=mock_page)

        mock_pdfium.PdfDocument.return_value = mock_pdf

        service = ExtractionService()

        # Act
        service.generate_thumbnails(doc_id, file_bytes)

        # Assert
        # Verify that upload_image was called
        mock_storage.upload_image.assert_called_once()

    @patch('app.services.extraction_service.pdfium')
    @patch('app.services.extraction_service.StorageService')
    def test_generate_thumbnails_pdf_error(self, mock_storage_class, mock_pdfium):
        """Test handling of PDF rendering errors"""
        # Arrange
        doc_id = "test_doc_error"
        file_bytes = b"fake_pdf_content"

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        mock_pdfium.PdfDocument.side_effect = Exception("PDF rendering error")

        service = ExtractionService()

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            service.generate_thumbnails(doc_id, file_bytes)

        assert "PDF rendering error" in str(exc_info.value)


class TestCreateManifest:
    """Test manifest creation from extraction results"""

    @patch('app.services.extraction_service.StorageService')
    def test_create_manifest_complete(self, mock_storage_class):
        """Test manifest creation with complete extraction data"""
        # Arrange
        doc_id = "test_doc_123"
        origin_filename = "test.pdf"
        extraction_data = {
            'doc_id': doc_id,
            'pages': [
                {
                    'page_no': 1,
                    'text': 'Page 1 content'
                },
                {
                    'page_no': 2,
                    'text': 'Page 2 content'
                }
            ],
            'tables': [{'table_id': 0}],
            'full_text': 'Page 1 content\n\nPage 2 content\n\n'
        }
        thumbnail_urls = [
            {'page_no': 1, 'url': 'http://example.com/p1.png'},
            {'page_no': 2, 'url': 'http://example.com/p2.png'}
        ]

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        service = ExtractionService()

        # Act
        result = service.create_manifest(doc_id, origin_filename, extraction_data, thumbnail_urls)

        # Assert
        assert result is not None
        assert result['doc_id'] == doc_id
        assert result['page_count'] == 2
        assert result['has_thumbnails'] is True
        assert result['thumbnail_count'] == 2

        # Verify storage upload
        mock_storage.upload_json.assert_called_once()

    @patch('app.services.extraction_service.StorageService')
    def test_create_manifest_no_thumbnails(self, mock_storage_class):
        """Test manifest creation without thumbnails"""
        # Arrange
        doc_id = "test_doc_no_thumbs"
        origin_filename = "test.pdf"
        extraction_data = {
            'doc_id': doc_id,
            'pages': [],
            'tables': [],
            'full_text': ''
        }
        thumbnail_urls = []

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        service = ExtractionService()

        # Act
        result = service.create_manifest(doc_id, origin_filename, extraction_data, thumbnail_urls)

        # Assert
        assert result['has_thumbnails'] is False
        assert result['thumbnail_count'] == 0


class TestProcessDocument:
    """Test end-to-end document processing"""

    @patch('app.services.extraction_service.get_document_intelligence_client')
    @patch('app.services.extraction_service.StorageService')
    @patch('app.services.extraction_service.pdfium')
    def test_process_document_complete_workflow(
        self, mock_pdfium, mock_storage_class, mock_get_doc_intel
    ):
        """Test complete document processing workflow"""
        # Arrange
        doc_id = "test_doc_complete"
        file_bytes = b"fake_pdf_content"
        filename = "test.pdf"

        # Mock Document Intelligence client
        mock_doc_intel = Mock()
        mock_get_doc_intel.return_value = mock_doc_intel

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        # Mock extraction result
        mock_result = Mock()
        mock_page = Mock()
        mock_page.width = 8.5
        mock_page.height = 11.0
        mock_page.unit = "inch"
        mock_page.lines = []
        mock_page.words = []

        mock_result.pages = [mock_page]
        mock_result.tables = []

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result
        mock_doc_intel.begin_analyze_document.return_value = mock_poller

        # Mock PDF for thumbnails
        mock_pdf = Mock()
        mock_pdf_page = Mock()
        fake_image = Image.new('RGB', (100, 100), color='white')
        mock_render_result = Mock()
        mock_render_result.to_pil.return_value = fake_image
        mock_pdf_page.render.return_value = mock_render_result

        mock_pdf.__len__ = Mock(return_value=1)
        mock_pdf.__getitem__ = Mock(return_value=mock_pdf_page)
        mock_pdfium.PdfDocument.return_value = mock_pdf

        mock_storage.upload_image.return_value = "http://example.com/thumb.png"

        service = ExtractionService()

        # Act
        result = service.process_document(doc_id, file_bytes, filename)

        # Assert
        assert result is not None
        assert result['doc_id'] == doc_id
        assert result['success'] is True

        # Verify all steps were called
        mock_doc_intel.begin_analyze_document.assert_called_once()
        mock_storage.upload_json.assert_called()  # Called multiple times for extraction and manifest

    @patch('app.services.extraction_service.get_document_intelligence_client')
    @patch('app.services.extraction_service.StorageService')
    def test_process_document_extraction_failure(self, mock_storage_class, mock_get_doc_intel):
        """Test handling of extraction failures"""
        # Arrange
        doc_id = "test_doc_fail"
        file_bytes = b"fake_pdf_content"
        filename = "test.pdf"

        # Mock Document Intelligence client
        mock_doc_intel = Mock()
        mock_get_doc_intel.return_value = mock_doc_intel

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        mock_doc_intel.begin_analyze_document.side_effect = Exception("Extraction failed")

        service = ExtractionService()

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            service.process_document(doc_id, file_bytes, filename)

        assert "Extraction failed" in str(exc_info.value)

    @patch('app.services.extraction_service.get_document_intelligence_client')
    @patch('app.services.extraction_service.StorageService')
    @patch('app.services.extraction_service.pdfium')
    def test_process_document_thumbnail_failure_continues(
        self, mock_pdfium, mock_storage_class, mock_get_doc_intel
    ):
        """Test that thumbnail generation failure doesn't stop processing"""
        # Arrange
        doc_id = "test_doc_thumb_fail"
        file_bytes = b"fake_pdf_content"
        filename = "test.pdf"

        # Mock Document Intelligence client
        mock_doc_intel = Mock()
        mock_get_doc_intel.return_value = mock_doc_intel

        # Mock storage service
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        # Mock extraction result
        mock_result = Mock()
        mock_page = Mock()
        mock_page.width = 8.5
        mock_page.height = 11.0
        mock_page.unit = "inch"
        mock_page.lines = []
        mock_page.words = []

        mock_result.pages = [mock_page]
        mock_result.tables = []

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result
        mock_doc_intel.begin_analyze_document.return_value = mock_poller

        # Mock PDF failure
        mock_pdfium.PdfDocument.side_effect = Exception("Thumbnail generation failed")

        service = ExtractionService()

        # Act & Assert
        with pytest.raises(Exception) as e:
            service.process_document(doc_id, file_bytes, filename)
        assert "Thumbnail generation failed" in str(e)
