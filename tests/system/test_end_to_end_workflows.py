"""
System tests for end-to-end workflows
Tests complete user journeys from document upload through search and chat.

This module implements comprehensive system tests that validate:
- Complete document lifecycle: upload → process → index → search → chat → delete
- Document versioning and duplicate detection workflows
- Error recovery and cleanup in complete workflows
- Multi-document search and retrieval scenarios
- Data persistence and retrieval across service boundaries

Requirements covered: 4.1, 4.2, 4.3, 4.4, 4.5
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from io import BytesIO
from datetime import datetime

# Import create_app from the main app.py file
import importlib.util
import os

# Load the app.py module directly
app_py_path = os.path.join(os.path.dirname(__file__), "..", "..", "app.py")
spec = importlib.util.spec_from_file_location("app_main", app_py_path)
app_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_main)
create_app = app_main.create_app


@pytest.fixture
def system_test_client():
    """Create test client for system tests with proper configuration"""
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False  # Disable CSRF for testing
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def mock_all_azure_services():
    """Comprehensive mock of all Azure services for system tests"""
    with (
        patch(
            "app.services.storage_service.get_blob_service_client"
        ) as mock_storage_func,
        patch(
            "app.services.cosmos_service.get_cosmos_container"
        ) as mock_cosmos_container_func,
        patch(
            "app.services.extraction_service.get_document_intelligence_client"
        ) as mock_doc_intel_func,
    ):
        # Configure storage service mocks
        mock_blob_service = Mock()
        mock_blob_client = Mock()
        mock_blob_client.upload_blob.return_value = None
        mock_blob_client.download_blob.return_value.readall.return_value = (
            b'{"test": "data"}'
        )
        mock_blob_client.exists.return_value = True
        mock_blob_service.get_blob_client.return_value = mock_blob_client
        mock_storage_func.return_value = mock_blob_service

        # Configure Cosmos DB mocks
        mock_container = Mock()
        mock_container.upsert_item.side_effect = lambda x: x
        mock_container.create_item.side_effect = lambda x: x
        mock_container.query_items.return_value = []
        mock_container.read_item.return_value = {"id": "test", "status": "indexed"}
        mock_cosmos_container_func.return_value = mock_container

        # Configure Document Intelligence mock
        mock_doc_intel_client = Mock()
        mock_poller = Mock()
        mock_result = Mock()
        mock_page = Mock()
        mock_page.page_number = 1
        mock_page.width = 8.5
        mock_page.height = 11.0
        mock_page.lines = []
        mock_page.tables = None
        mock_result.pages = [mock_page]
        mock_result.content = "Sample extracted text"
        mock_poller.result.return_value = mock_result
        mock_doc_intel_client.begin_analyze_document.return_value = mock_poller
        mock_doc_intel_func.return_value = mock_doc_intel_client

        yield {
            "storage": mock_blob_service,
            "doc_intel": mock_doc_intel_client,
            "containers": {
                "documents": mock_container,
                "events": mock_container,
                "lineage": mock_container,
            },
        }


class TestCompleteDocumentLifecycle:
    """
    Test the complete lifecycle of a document from upload to deletion.

    This test class validates the full end-to-end workflow:
    1. Document upload with processing and indexing
    2. Document appears in listing
    3. Document is searchable
    4. Document can be used in chat
    5. Document can be deleted
    6. Deleted document is no longer accessible

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """

    def test_complete_document_lifecycle_workflow(
        self, system_test_client, mock_all_azure_services
    ):
        """
        Test complete workflow: upload → process → index → search → chat → delete

        This is the primary system test that validates the entire document lifecycle
        from initial upload through final deletion, ensuring data persistence and
        retrieval work correctly across all service boundaries.
        """
        client = system_test_client
        mocks = mock_all_azure_services

        doc_id = "lifecycle_test_doc_123"
        filename = "IPAR_M12_2024-25_Test.pdf"
        logical_id = f"logical_{doc_id}"

        # Step 1: Upload document with comprehensive mocking
        with (
            patch(
                "app.services.storage_service.StorageService.compute_sha256",
                return_value=doc_id,
            ),
            patch(
                "app.services.storage_service.StorageService.compute_logical_id",
                return_value=logical_id,
            ),
            patch(
                "app.services.extraction_service.ExtractionService.process_document"
            ) as mock_extract,
            patch(
                "app.services.chunking_service.ChunkingService.chunk_document"
            ) as mock_chunk,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_chunks"
            ) as mock_embed_chunks,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_document"
            ) as mock_embed_doc,
            patch(
                "app.services.search_index_service.SearchIndexService.upload_chunks"
            ) as mock_upload,
        ):
            # Configure extraction mock
            mock_extract.return_value = {
                "extraction_data": {
                    "doc_id": doc_id,
                    "full_text": "Emergency Department Performance: 4-hour target achieved for 89.2% of patients. Cancer Services: 62-day pathway performance at 71.3%.",
                    "pages": [
                        {
                            "page_number": 1,
                            "text": "Emergency Department Performance: 4-hour target achieved for 89.2% of patients.",
                            "tables": [],
                        },
                        {
                            "page_number": 2,
                            "text": "Cancer Services: 62-day pathway performance at 71.3%.",
                            "tables": [],
                        },
                    ],
                },
                "manifest": {
                    "page_count": 2,
                    "table_count": 0,
                    "text_length": 120,
                    "thumbnail_count": 2,
                },
            }

            # Configure chunking mock
            mock_chunk.return_value = [
                {
                    "id": f"{doc_id}_chunk_1",
                    "doc_id": doc_id,
                    "page_no": 1,
                    "text": "Emergency Department Performance: 4-hour target achieved for 89.2% of patients.",
                    "offset": 0,
                },
                {
                    "id": f"{doc_id}_chunk_2",
                    "doc_id": doc_id,
                    "page_no": 2,
                    "text": "Cancer Services: 62-day pathway performance at 71.3%.",
                    "offset": 0,
                },
            ]

            # Configure embedding mocks
            mock_embed_chunks.return_value = [
                {
                    "id": f"{doc_id}_chunk_1",
                    "doc_id": doc_id,
                    "text": "Emergency Department Performance: 4-hour target achieved for 89.2% of patients.",
                    "vector": [0.1] * 3072,
                },
                {
                    "id": f"{doc_id}_chunk_2",
                    "doc_id": doc_id,
                    "text": "Cancer Services: 62-day pathway performance at 71.3%.",
                    "vector": [0.2] * 3072,
                },
            ]

            mock_embed_doc.return_value = [0.15] * 3072
            mock_upload.return_value = {"uploaded": 2, "failed": 0}

            # Configure Cosmos mocks for document operations
            mocks["containers"][
                "documents"
            ].query_items.return_value = []  # No existing docs
            mocks["containers"]["documents"].read_item.side_effect = [
                # First call during upload (check existing)
                None,
                # Second call after save
                {
                    "id": doc_id,
                    "doc_id": doc_id,
                    "logical_id": logical_id,
                    "status": "indexed",
                    "page_count": 2,
                    "chunk_count": 2,
                    "indexed_chunk_count": 2,
                    "origin_filename": filename,
                    "is_deleted": False,
                },
            ]

            # Execute upload
            upload_response = client.post(
                "/api/documents/upload",
                data={"file": (BytesIO(b"%PDF-1.4 fake pdf content"), filename)},
                content_type="multipart/form-data",
            )

        # Verify upload success
        assert upload_response.status_code == 201
        upload_data = json.loads(upload_response.data)
        assert upload_data["doc_id"] == doc_id
        assert upload_data["status"] == "indexed"
        assert upload_data["chunk_count"] == 2
        assert upload_data["indexed_chunk_count"] == 2

        # Step 2: Verify document appears in listing
        mocks["containers"]["documents"].query_items.return_value = [
            {
                "id": doc_id,
                "doc_id": doc_id,
                "origin_filename": filename,
                "status": "indexed",
                "page_count": 2,
                "chunk_count": 2,
                "indexed_chunk_count": 2,
                "created_at": datetime.utcnow().isoformat(),
                "is_deleted": False,
                "superseded": False,
            }
        ]

        list_response = client.get("/api/documents/")
        assert list_response.status_code == 200
        list_data = json.loads(list_response.data)
        assert "documents" in list_data
        assert len(list_data["documents"]) >= 1

        # Find our document in the list
        uploaded_doc = next(
            (doc for doc in list_data["documents"] if doc["id"] == doc_id), None
        )
        assert uploaded_doc is not None
        assert uploaded_doc["origin_filename"] == filename
        assert uploaded_doc["status"] == "indexed"

        # Step 3: Search for document content
        with patch(
            "app.services.search_service.SearchService.search"
        ) as mock_search_method:
            mock_search_method.return_value = {
                "query": "emergency department",
                "count": 1,
                "results": [
                    {
                        "citation_number": 1,
                        "chunk_id": f"{doc_id}_chunk_1",
                        "doc_id": doc_id,
                        "logical_id": logical_id,
                        "title": filename,
                        "origin_filename": filename,
                        "page_no": 1,
                        "snippet": "Emergency Department Performance...",
                        "text": "Emergency Department Performance: 4-hour target achieved for 89.2% of patients.",
                        "score": 0.95,
                        "observed_date": datetime.utcnow().isoformat(),
                    }
                ],
                "filter": None,
            }

            search_response = client.get("/api/documents/search?q=emergency+department")

        assert search_response.status_code == 200
        search_data = json.loads(search_response.data)
        assert search_data["count"] >= 1
        assert any(result["doc_id"] == doc_id for result in search_data["results"])

        # Step 4: Test chat functionality with document content
        with patch("app.services.chat_service.ChatService.chat") as mock_chat_method:
            mock_chat_method.return_value = {
                "response": "Based on the IPAR document, the emergency department achieved 89.2% performance against the 4-hour target [Doc 1].",
                "sources": [
                    {
                        "citation_number": 1,
                        "chunk_id": f"{doc_id}_chunk_1",
                        "doc_id": doc_id,
                        "title": filename,
                        "origin_filename": filename,
                        "page_no": 1,
                        "text": "Emergency Department Performance: 4-hour target achieved for 89.2% of patients.",
                        "score": 0.95,
                    }
                ],
                "usage": {
                    "prompt_tokens": 150,
                    "completion_tokens": 50,
                    "total_tokens": 200,
                },
                "model": "gpt-4o-mini",
                "finish_reason": "stop",
                "query": "What is the emergency department performance?",
            }

            chat_payload = {
                "query": "What is the emergency department performance?",
                "top_k": 5,
            }

            chat_response = client.post(
                "/api/documents/chat",
                data=json.dumps(chat_payload),
                content_type="application/json",
            )

        assert chat_response.status_code == 200
        chat_data = json.loads(chat_response.data)
        assert "response" in chat_data
        assert "sources" in chat_data
        assert len(chat_data["sources"]) >= 1
        assert any(source["doc_id"] == doc_id for source in chat_data["sources"])

        # Step 5: Get document details
        mocks["containers"]["documents"].read_item.return_value = {
            "id": doc_id,
            "doc_id": doc_id,
            "logical_id": logical_id,
            "origin_filename": filename,
            "status": "indexed",
            "page_count": 2,
            "chunk_count": 2,
            "indexed_chunk_count": 2,
            "created_at": datetime.utcnow().isoformat(),
            "is_deleted": False,
        }

        detail_response = client.get(f"/api/documents/{doc_id}")
        assert detail_response.status_code == 200
        detail_data = json.loads(detail_response.data)
        assert detail_data["doc_id"] == doc_id
        assert detail_data["status"] == "indexed"

        # Step 6: Delete document
        with (
            patch(
                "app.services.search_index_service.SearchIndexService.delete_chunks_by_doc_id"
            ) as mock_delete_chunks,
            patch(
                "app.services.cosmos_service.CosmosService.mark_as_deleted"
            ) as mock_mark_deleted,
            patch(
                "app.services.storage_service.StorageService.archive_document_blobs"
            ) as mock_archive,
        ):
            mock_delete_chunks.return_value = 2  # 2 chunks deleted
            mock_archive.return_value = {"raw": True, "extracted": True, "thumbs": True}

            delete_response = client.delete(f"/api/documents/{doc_id}")

        assert delete_response.status_code == 200
        delete_data = json.loads(delete_response.data)
        assert delete_data["doc_id"] == doc_id
        assert delete_data["deleted_chunks"] == 2

        # Step 7: Verify document no longer appears in listing (soft delete)
        mocks["containers"][
            "documents"
        ].query_items.return_value = []  # Deleted docs excluded

        list_after_delete = client.get("/api/documents/")
        assert list_after_delete.status_code == 200
        list_after_data = json.loads(list_after_delete.data)
        assert not any(doc["id"] == doc_id for doc in list_after_data["documents"])

        # Step 8: Verify document detail returns 404 or shows as deleted
        mocks["containers"]["documents"].read_item.return_value = {
            "id": doc_id,
            "doc_id": doc_id,
            "status": "deleted",
            "is_deleted": True,
        }

        detail_after_delete = client.get(f"/api/documents/{doc_id}")
        # Document should still exist but marked as deleted
        assert detail_after_delete.status_code == 200
        detail_deleted_data = json.loads(detail_after_delete.data)
        assert detail_deleted_data["is_deleted"] is True


class TestDocumentVersioningWorkflow:
    """
    Test document versioning and duplicate detection workflows.

    This test class validates:
    - Exact duplicate detection (same file bytes)
    - Logical duplicate detection (same content, different file)
    - Version creation workflow
    - Near-duplicate detection
    - Superseding previous versions

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """

    def test_exact_duplicate_detection_workflow(
        self, system_test_client, mock_all_azure_services
    ):
        """
        Test that uploading the exact same file is detected as a duplicate.

        This test validates EPIC D.8 - Exact Duplicate Detection
        """
        client = system_test_client
        mocks = mock_all_azure_services

        doc_id = "exact_duplicate_test"
        filename = "duplicate_test.pdf"
        file_content = b"%PDF-1.4 exact same content"

        # Step 1: Upload first document
        with (
            patch(
                "app.services.storage_service.StorageService.compute_sha256",
                return_value=doc_id,
            ),
            patch(
                "app.services.storage_service.StorageService.compute_logical_id",
                return_value=f"logical_{doc_id}",
            ),
        ):
            # No existing document
            mocks["containers"]["documents"].read_item.return_value = None

            upload1 = client.post(
                "/api/documents/upload",
                data={"file": (BytesIO(file_content), filename)},
                content_type="multipart/form-data",
            )

        assert upload1.status_code == 201

        # Step 2: Upload exact same file again
        with (
            patch(
                "app.services.storage_service.StorageService.compute_sha256",
                return_value=doc_id,
            ),
            patch(
                "app.services.storage_service.StorageService.compute_logical_id",
                return_value=f"logical_{doc_id}",
            ),
        ):
            # Mock existing document (not deleted)
            mocks["containers"]["documents"].read_item.return_value = {
                "id": doc_id,
                "doc_id": doc_id,
                "origin_filename": filename,
                "status": "indexed",
                "is_deleted": False,
            }

            upload2 = client.post(
                "/api/documents/upload",
                data={"file": (BytesIO(file_content), filename)},
                content_type="multipart/form-data",
            )

        # Should detect exact duplicate
        assert upload2.status_code == 200
        duplicate_data = json.loads(upload2.data)
        assert duplicate_data["duplicate"] is True
        assert duplicate_data["duplicate_type"] == "exact"
        assert "already exists" in duplicate_data["message"]

    def test_logical_duplicate_versioning_workflow(
        self, system_test_client, mock_all_azure_services
    ):
        """
        Test logical duplicate detection and version creation workflow.

        This test validates EPIC D.9 - Logical Duplicate Detection and versioning
        """
        client = system_test_client
        mocks = mock_all_azure_services

        doc_id_v1 = "logical_dup_v1"
        doc_id_v2 = "logical_dup_v2"
        logical_id = "logical_same_content_123"

        # Step 1: Upload first document
        with (
            patch(
                "app.services.storage_service.StorageService.compute_sha256",
                return_value=doc_id_v1,
            ),
            patch(
                "app.services.storage_service.StorageService.compute_logical_id",
                return_value=logical_id,
            ),
            patch(
                "app.services.extraction_service.ExtractionService.process_document"
            ) as mock_extract,
            patch(
                "app.services.chunking_service.ChunkingService.chunk_document"
            ) as mock_chunk,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_chunks"
            ) as mock_embed_chunks,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_document"
            ) as mock_embed_doc,
            patch(
                "app.services.search_index_service.SearchIndexService.upload_chunks"
            ) as mock_upload,
        ):
            # Configure mocks for first upload
            mock_extract.return_value = {
                "extraction_data": {
                    "doc_id": doc_id_v1,
                    "full_text": "Same content in both documents",
                    "pages": [
                        {"page_number": 1, "text": "Same content in both documents"}
                    ],
                },
                "manifest": {
                    "page_count": 1,
                    "table_count": 0,
                    "text_length": 30,
                    "thumbnail_count": 1,
                },
            }

            mock_chunk.return_value = [
                {
                    "id": "c1",
                    "doc_id": doc_id_v1,
                    "text": "Same content in both documents",
                }
            ]
            mock_embed_chunks.return_value = [
                {
                    "id": "c1",
                    "text": "Same content in both documents",
                    "vector": [0.5] * 3072,
                }
            ]
            mock_embed_doc.return_value = [0.5] * 3072
            mock_upload.return_value = {"uploaded": 1, "failed": 0}

            # No existing documents
            mocks["containers"]["documents"].read_item.return_value = None
            mocks["containers"]["documents"].query_items.return_value = []

            upload1 = client.post(
                "/api/documents/upload",
                data={"file": (BytesIO(b"PDF version 1"), "doc_v1.pdf")},
                content_type="multipart/form-data",
            )

        assert upload1.status_code == 201
        upload1_data = json.loads(upload1.data)
        assert upload1_data["doc_id"] == doc_id_v1

        # Step 2: Upload second document with same content but different file
        with (
            patch(
                "app.services.storage_service.StorageService.compute_sha256",
                return_value=doc_id_v2,
            ),
            patch(
                "app.services.storage_service.StorageService.compute_logical_id",
                return_value=logical_id,
            ),
        ):
            # Mock existing document with same logical_id
            mocks["containers"]["documents"].query_items.return_value = [
                {
                    "id": doc_id_v1,
                    "doc_id": doc_id_v1,
                    "logical_id": logical_id,
                    "version": 1,
                    "origin_filename": "doc_v1.pdf",
                    "status": "indexed",
                }
            ]

            # Mock get_latest_version call
            with patch(
                "app.services.cosmos_service.CosmosService.get_latest_version"
            ) as mock_latest:
                mock_latest.return_value = {
                    "doc_id": doc_id_v1,
                    "logical_id": logical_id,
                    "version": 1,
                }

                upload2 = client.post(
                    "/api/documents/upload",
                    data={"file": (BytesIO(b"PDF version 2"), "doc_v2.pdf")},
                    content_type="multipart/form-data",
                )

        # Should prompt for version creation
        assert upload2.status_code == 409  # Conflict - requires user decision
        duplicate_data = json.loads(upload2.data)
        assert duplicate_data["duplicate"] is True
        assert duplicate_data["duplicate_type"] == "logical"
        assert duplicate_data["requires_user_decision"] is True
        assert "create_version=true" in duplicate_data["action_url"]

        # Step 3: Confirm version creation
        with (
            patch(
                "app.services.storage_service.StorageService.compute_sha256",
                return_value=doc_id_v2,
            ),
            patch(
                "app.services.storage_service.StorageService.compute_logical_id",
                return_value=logical_id,
            ),
            patch(
                "app.services.extraction_service.ExtractionService.process_document"
            ) as mock_extract,
            patch(
                "app.services.chunking_service.ChunkingService.chunk_document"
            ) as mock_chunk,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_chunks"
            ) as mock_embed_chunks,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_document"
            ) as mock_embed_doc,
            patch(
                "app.services.search_index_service.SearchIndexService.upload_chunks"
            ) as mock_upload,
            patch(
                "app.services.cosmos_service.CosmosService.get_latest_version"
            ) as mock_latest,
            patch(
                "app.services.cosmos_service.CosmosService.mark_as_superseded"
            ) as mock_supersede,
        ):
            # Configure mocks for version creation
            mock_extract.return_value = {
                "extraction_data": {
                    "doc_id": doc_id_v2,
                    "full_text": "Same content in both documents",
                    "pages": [
                        {"page_number": 1, "text": "Same content in both documents"}
                    ],
                },
                "manifest": {
                    "page_count": 1,
                    "table_count": 0,
                    "text_length": 30,
                    "thumbnail_count": 1,
                },
            }

            mock_chunk.return_value = [
                {
                    "id": "c2",
                    "doc_id": doc_id_v2,
                    "text": "Same content in both documents",
                }
            ]
            mock_embed_chunks.return_value = [
                {
                    "id": "c2",
                    "text": "Same content in both documents",
                    "vector": [0.5] * 3072,
                }
            ]
            mock_embed_doc.return_value = [0.5] * 3072
            mock_upload.return_value = {"uploaded": 1, "failed": 0}

            mock_latest.return_value = {
                "doc_id": doc_id_v1,
                "logical_id": logical_id,
                "version": 1,
            }

            # No existing exact duplicate
            mocks["containers"]["documents"].read_item.return_value = None

            upload3 = client.post(
                "/api/documents/upload?create_version=true",
                data={"file": (BytesIO(b"PDF version 2"), "doc_v2.pdf")},
                content_type="multipart/form-data",
            )

        assert upload3.status_code == 201
        version_data = json.loads(upload3.data)
        assert version_data["doc_id"] == doc_id_v2
        assert version_data["version"] == 2
        assert version_data["supersedes"] == doc_id_v1

    def test_near_duplicate_detection_workflow(
        self, system_test_client, mock_all_azure_services
    ):
        """
        Test near-duplicate detection using document embeddings.

        This test validates EPIC D.10 - Near-duplicate Detection
        """
        client = system_test_client
        mocks = mock_all_azure_services

        doc_id_1 = "near_dup_1"
        doc_id_2 = "near_dup_2"

        # Step 1: Upload first document
        with (
            patch(
                "app.services.storage_service.StorageService.compute_sha256",
                return_value=doc_id_1,
            ),
            patch(
                "app.services.storage_service.StorageService.compute_logical_id",
                return_value=f"logical_{doc_id_1}",
            ),
            patch(
                "app.services.extraction_service.ExtractionService.process_document"
            ) as mock_extract,
            patch(
                "app.services.chunking_service.ChunkingService.chunk_document"
            ) as mock_chunk,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_chunks"
            ) as mock_embed_chunks,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_document"
            ) as mock_embed_doc,
            patch(
                "app.services.search_index_service.SearchIndexService.upload_chunks"
            ) as mock_upload,
        ):
            mock_extract.return_value = {
                "extraction_data": {
                    "doc_id": doc_id_1,
                    "full_text": "Emergency department performance metrics and analysis",
                    "pages": [
                        {
                            "page_number": 1,
                            "text": "Emergency department performance metrics and analysis",
                        }
                    ],
                },
                "manifest": {
                    "page_count": 1,
                    "table_count": 0,
                    "text_length": 50,
                    "thumbnail_count": 1,
                },
            }

            mock_chunk.return_value = [
                {
                    "id": "c1",
                    "doc_id": doc_id_1,
                    "text": "Emergency department performance metrics and analysis",
                }
            ]
            mock_embed_chunks.return_value = [
                {
                    "id": "c1",
                    "text": "Emergency department performance metrics and analysis",
                    "vector": [0.7] * 3072,
                }
            ]
            mock_embed_doc.return_value = [0.7] * 3072
            mock_upload.return_value = {"uploaded": 1, "failed": 0}

            mocks["containers"]["documents"].read_item.return_value = None
            mocks["containers"]["documents"].query_items.return_value = []

            upload1 = client.post(
                "/api/documents/upload",
                data={"file": (BytesIO(b"PDF document 1"), "doc1.pdf")},
                content_type="multipart/form-data",
            )

        assert upload1.status_code == 201

        # Step 2: Upload similar document (near-duplicate)
        with (
            patch(
                "app.services.storage_service.StorageService.compute_sha256",
                return_value=doc_id_2,
            ),
            patch(
                "app.services.storage_service.StorageService.compute_logical_id",
                return_value=f"logical_{doc_id_2}",
            ),
            patch(
                "app.services.extraction_service.ExtractionService.process_document"
            ) as mock_extract,
            patch(
                "app.services.chunking_service.ChunkingService.chunk_document"
            ) as mock_chunk,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_chunks"
            ) as mock_embed_chunks,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_document"
            ) as mock_embed_doc,
            patch(
                "app.services.search_index_service.SearchIndexService.upload_chunks"
            ) as mock_upload,
            patch(
                "app.services.embedding_service.EmbeddingService.is_near_duplicate"
            ) as mock_is_near_dup,
            patch(
                "app.services.embedding_service.EmbeddingService.compute_cosine_similarity"
            ) as mock_similarity,
        ):
            mock_extract.return_value = {
                "extraction_data": {
                    "doc_id": doc_id_2,
                    "full_text": "Emergency department performance analysis and metrics",  # Similar but not identical
                    "pages": [
                        {
                            "page_number": 1,
                            "text": "Emergency department performance analysis and metrics",
                        }
                    ],
                },
                "manifest": {
                    "page_count": 1,
                    "table_count": 0,
                    "text_length": 50,
                    "thumbnail_count": 1,
                },
            }

            mock_chunk.return_value = [
                {
                    "id": "c2",
                    "doc_id": doc_id_2,
                    "text": "Emergency department performance analysis and metrics",
                }
            ]
            mock_embed_chunks.return_value = [
                {
                    "id": "c2",
                    "text": "Emergency department performance analysis and metrics",
                    "vector": [0.75] * 3072,
                }
            ]
            mock_embed_doc.return_value = [0.75] * 3072
            mock_upload.return_value = {"uploaded": 1, "failed": 0}

            # Mock near-duplicate detection
            mock_is_near_dup.return_value = True
            mock_similarity.return_value = 0.92  # High similarity

            # Mock existing documents query for near-duplicate check
            mocks["containers"]["documents"].query_items.return_value = [
                {"doc_id": doc_id_1, "doc_embedding": [0.7] * 3072}
            ]

            mocks["containers"][
                "documents"
            ].read_item.return_value = None  # No exact duplicate

            upload2 = client.post(
                "/api/documents/upload",
                data={"file": (BytesIO(b"PDF document 2"), "doc2.pdf")},
                content_type="multipart/form-data",
            )

        assert upload2.status_code == 201
        near_dup_data = json.loads(upload2.data)
        assert near_dup_data["doc_id"] == doc_id_2
        assert near_dup_data["near_duplicate_count"] >= 1
        assert doc_id_1 in near_dup_data["near_duplicates"]


class TestSearchAndChatIntegrationWorkflow:
    """
    Test integrated search and chat workflows.

    This test class validates:
    - Hybrid search functionality (vector + keyword)
    - Search result formatting and citations
    - RAG chat with document grounding
    - Multi-document search scenarios
    - Search within specific documents

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """

    def test_comprehensive_search_and_chat_workflow(
        self, system_test_client, mock_all_azure_services
    ):
        """
        Test complete search → chat workflow with multiple documents.

        This test validates EPIC F.15 (Search API) and EPIC G (RAG Chat)
        """
        client = system_test_client
        mocks = mock_all_azure_services

        # Step 1: Search for documents across multiple sources
        search_query = "emergency department performance"

        with patch(
            "app.services.search_service.SearchService.search"
        ) as mock_search_method:
            mock_search_method.return_value = {
                "query": search_query,
                "count": 3,
                "results": [
                    {
                        "citation_number": 1,
                        "chunk_id": "chunk_ed_1",
                        "doc_id": "ipar_m12_2024",
                        "logical_id": "logical_ipar_m12",
                        "title": "IPAR M12 2024-25",
                        "origin_filename": "IPAR_M12_2024-25.pdf",
                        "page_no": 5,
                        "snippet": "Emergency Department Performance: 4-hour target achieved for 89.2%...",
                        "text": "Emergency Department Performance: 4-hour target achieved for 89.2% of patients (target: 95%). This represents an improvement from the previous quarter.",
                        "observed_date": "2024-01-15",
                        "kpi_tags": ["emergency_department", "performance"],
                        "score": 0.95,
                        "reranker_score": None,
                        "thumb_url": "https://storage.blob.core.windows.net/thumbs/ipar_m12_2024/p5.png?sas=token",
                    },
                    {
                        "citation_number": 2,
                        "chunk_id": "chunk_ed_2",
                        "doc_id": "ipar_m11_2024",
                        "logical_id": "logical_ipar_m11",
                        "title": "IPAR M11 2024-25",
                        "origin_filename": "IPAR_M11_2024-25.pdf",
                        "page_no": 3,
                        "snippet": "Emergency department waiting times have shown consistent improvement...",
                        "text": "Emergency department waiting times have shown consistent improvement with average wait reduced to 3.2 hours.",
                        "observed_date": "2024-01-10",
                        "kpi_tags": ["emergency_department", "waiting_times"],
                        "score": 0.88,
                        "reranker_score": None,
                        "thumb_url": "https://storage.blob.core.windows.net/thumbs/ipar_m11_2024/p3.png?sas=token",
                    },
                    {
                        "citation_number": 3,
                        "chunk_id": "chunk_ed_3",
                        "doc_id": "quality_report_2024",
                        "logical_id": "logical_quality_2024",
                        "title": "Quality Report 2024",
                        "origin_filename": "Quality_Report_2024.pdf",
                        "page_no": 12,
                        "snippet": "Patient satisfaction in emergency department increased to 8.1/10...",
                        "text": "Patient satisfaction in emergency department increased to 8.1/10, with particular improvements in communication and care quality.",
                        "observed_date": "2024-01-20",
                        "kpi_tags": ["patient_satisfaction", "emergency_department"],
                        "score": 0.82,
                        "reranker_score": None,
                        "thumb_url": "https://storage.blob.core.windows.net/thumbs/quality_report_2024/p12.png?sas=token",
                    },
                ],
                "filter": None,
            }

            search_response = client.get(
                f"/api/documents/search?q={search_query}&top=10"
            )

        assert search_response.status_code == 200
        search_data = json.loads(search_response.data)
        assert search_data["count"] == 3
        assert len(search_data["results"]) == 3

        # Verify search results structure
        for i, result in enumerate(search_data["results"]):
            assert result["citation_number"] == i + 1
            assert "chunk_id" in result
            assert "doc_id" in result
            assert "text" in result
            assert "score" in result
            assert "thumb_url" in result

        # Step 2: Use search results in RAG chat
        chat_query = "What is the current emergency department performance and how has it improved?"

        with patch("app.services.chat_service.ChatService.chat") as mock_chat_method:
            mock_chat_method.return_value = {
                "response": "Based on the latest IPAR reports, the emergency department performance shows significant improvement. The 4-hour target is now achieved for 89.2% of patients, up from previous quarters [Doc 1]. Average waiting times have been reduced to 3.2 hours [Doc 2], and patient satisfaction has increased to 8.1/10 with improvements in communication and care quality [Doc 3].",
                "sources": [
                    {
                        "citation_number": 1,
                        "chunk_id": "chunk_ed_1",
                        "doc_id": "ipar_m12_2024",
                        "title": "IPAR M12 2024-25",
                        "origin_filename": "IPAR_M12_2024-25.pdf",
                        "page_no": 5,
                        "text": "Emergency Department Performance: 4-hour target achieved for 89.2% of patients (target: 95%). This represents an improvement from the previous quarter.",
                        "score": 0.95,
                    },
                    {
                        "citation_number": 2,
                        "chunk_id": "chunk_ed_2",
                        "doc_id": "ipar_m11_2024",
                        "title": "IPAR M11 2024-25",
                        "origin_filename": "IPAR_M11_2024-25.pdf",
                        "page_no": 3,
                        "text": "Emergency department waiting times have shown consistent improvement with average wait reduced to 3.2 hours.",
                        "score": 0.88,
                    },
                    {
                        "citation_number": 3,
                        "chunk_id": "chunk_ed_3",
                        "doc_id": "quality_report_2024",
                        "title": "Quality Report 2024",
                        "origin_filename": "Quality_Report_2024.pdf",
                        "page_no": 12,
                        "text": "Patient satisfaction in emergency department increased to 8.1/10, with particular improvements in communication and care quality.",
                        "score": 0.82,
                    },
                ],
                "usage": {
                    "prompt_tokens": 250,
                    "completion_tokens": 120,
                    "total_tokens": 370,
                },
                "model": "gpt-4o-mini",
                "finish_reason": "stop",
                "query": chat_query,
            }

            chat_payload = {"query": chat_query, "top_k": 5, "temperature": 0.3}

            chat_response = client.post(
                "/api/documents/chat",
                data=json.dumps(chat_payload),
                content_type="application/json",
            )

        assert chat_response.status_code == 200
        chat_data = json.loads(chat_response.data)

        # Verify chat response structure
        assert "response" in chat_data
        assert "sources" in chat_data
        assert "usage" in chat_data
        assert len(chat_data["sources"]) == 3

        # Verify response contains information from multiple sources
        response_text = chat_data["response"]
        assert "89.2%" in response_text  # From first source
        assert "3.2 hours" in response_text  # From second source
        assert "8.1/10" in response_text  # From third source

        # Verify citations are properly formatted
        assert "[Doc 1]" in response_text
        assert "[Doc 2]" in response_text
        assert "[Doc 3]" in response_text

        # Step 3: Test search within specific document
        specific_doc_id = "ipar_m12_2024"

        with patch(
            "app.services.search_service.SearchService.search_by_document"
        ) as mock_doc_search:
            mock_doc_search.return_value = [
                {
                    "id": "chunk_ed_1",
                    "doc_id": specific_doc_id,
                    "page_no": 5,
                    "text": "Emergency Department Performance: 4-hour target achieved for 89.2% of patients (target: 95%).",
                    "spans": [],
                },
                {
                    "id": "chunk_cancer_1",
                    "doc_id": specific_doc_id,
                    "page_no": 7,
                    "text": "Cancer Services: 62-day pathway performance at 71.3% (target: 75%).",
                    "spans": [],
                },
            ]

            doc_search_response = client.get(
                f"/api/documents/search/document/{specific_doc_id}?q=performance"
            )

        assert doc_search_response.status_code == 200
        doc_search_data = json.loads(doc_search_response.data)
        assert doc_search_data["doc_id"] == specific_doc_id
        assert len(doc_search_data["chunks"]) == 2

        # Step 4: Test chunk detail retrieval
        chunk_id = "chunk_ed_1"

        with patch(
            "app.services.search_service.SearchService.get_chunk_by_id"
        ) as mock_get_chunk:
            mock_get_chunk.return_value = {
                "id": chunk_id,
                "doc_id": specific_doc_id,
                "title": "IPAR M12 2024-25",
                "page_no": 5,
                "text": "Emergency Department Performance: 4-hour target achieved for 89.2% of patients (target: 95%).",
                "spans": [],
                "kpi_tags": ["emergency_department", "performance"],
            }

            chunk_response = client.get(f"/api/documents/search/chunk/{chunk_id}")

        assert chunk_response.status_code == 200
        chunk_data = json.loads(chunk_response.data)
        assert chunk_data["id"] == chunk_id
        assert chunk_data["doc_id"] == specific_doc_id
        assert "89.2%" in chunk_data["text"]

    def test_multi_document_search_workflow(
        self, system_test_client, mock_all_azure_services
    ):
        """
        Test search across multiple documents with different content types.

        This validates search functionality across diverse document types and content.
        """
        client = system_test_client

        search_query = "financial performance"

        with patch(
            "app.services.search_service.SearchService.search"
        ) as mock_search_method:
            mock_search_method.return_value = {
                "query": search_query,
                "count": 5,
                "results": [
                    {
                        "citation_number": 1,
                        "chunk_id": "chunk_fin_1",
                        "doc_id": "annual_report_2024",
                        "title": "Annual Report 2024",
                        "origin_filename": "Annual_Report_2024.pdf",
                        "page_no": 15,
                        "text": "Financial performance shows year-to-date deficit of £2.1M against planned deficit of £1.8M.",
                        "score": 0.92,
                    },
                    {
                        "citation_number": 2,
                        "chunk_id": "chunk_fin_2",
                        "doc_id": "budget_review_q3",
                        "title": "Q3 Budget Review",
                        "origin_filename": "Budget_Review_Q3.pdf",
                        "page_no": 8,
                        "text": "Cost savings initiatives have delivered £1.2M in efficiency gains this quarter.",
                        "score": 0.87,
                    },
                    {
                        "citation_number": 3,
                        "chunk_id": "chunk_fin_3",
                        "doc_id": "ipar_m12_2024",
                        "title": "IPAR M12 2024-25",
                        "origin_filename": "IPAR_M12_2024-25.pdf",
                        "page_no": 20,
                        "text": "Revenue streams from elective procedures increased by 8% compared to previous year.",
                        "score": 0.83,
                    },
                ],
            }

            search_response = client.get(
                f"/api/documents/search?q={search_query}&top=5"
            )

        assert search_response.status_code == 200
        search_data = json.loads(search_response.data)

        # Verify results from multiple document types
        doc_ids = set(result["doc_id"] for result in search_data["results"])
        assert len(doc_ids) >= 3  # Results from at least 3 different documents

        # Verify different document types are represented
        filenames = [result["origin_filename"] for result in search_data["results"]]
        assert any("Annual_Report" in filename for filename in filenames)
        assert any("Budget_Review" in filename for filename in filenames)
        assert any("IPAR" in filename for filename in filenames)


class TestDocumentReindexingWorkflow:
    """
    Test document reindexing and recovery workflows.

    This test class validates:
    - Document reindexing with updated chunking strategies
    - Recovery from partial upload failures
    - Cleanup and retry mechanisms
    - Data consistency during reprocessing

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """

    def test_successful_document_reindexing_workflow(
        self, system_test_client, mock_all_azure_services
    ):
        """
        Test successful reindexing of an existing document.

        This validates EPIC E.13 - Document reindexing functionality
        """
        client = system_test_client
        mocks = mock_all_azure_services

        doc_id = "reindex_test_doc"

        # Step 1: Mock existing document
        mocks["containers"]["documents"].read_item.return_value = {
            "id": doc_id,
            "doc_id": doc_id,
            "logical_id": f"logical_{doc_id}",
            "origin_filename": "test_reindex.pdf",
            "status": "indexed",
            "page_count": 2,
            "chunk_count": 3,
            "indexed_chunk_count": 3,
            "version": 1,
        }

        # Step 2: Mock extraction data from storage
        extraction_data = {
            "doc_id": doc_id,
            "pages": [
                {
                    "page_number": 1,
                    "text": "Updated content for page 1 with new information",
                },
                {
                    "page_number": 2,
                    "text": "Updated content for page 2 with additional details",
                },
            ],
        }

        mock_blob_client = Mock()
        mock_blob_client.download_blob.return_value.readall.return_value = json.dumps(
            extraction_data
        ).encode()
        mocks["storage"].get_blob_client.return_value = mock_blob_client

        # Step 3: Mock reindexing services
        with (
            patch(
                "app.services.search_index_service.SearchIndexService.delete_chunks_by_doc_id"
            ) as mock_delete,
            patch(
                "app.services.chunking_service.ChunkingService.chunk_document"
            ) as mock_chunk,
            patch(
                "app.services.indexing_pipeline_service.IndexingPipelineService.index_chunks"
            ) as mock_index,
        ):
            mock_delete.return_value = 3  # 3 old chunks deleted

            # New chunking strategy produces different chunks
            mock_chunk.return_value = [
                {
                    "id": f"{doc_id}_new_chunk_1",
                    "doc_id": doc_id,
                    "page_no": 1,
                    "text": "Updated content for page 1 with new information",
                    "offset": 0,
                },
                {
                    "id": f"{doc_id}_new_chunk_2",
                    "doc_id": doc_id,
                    "page_no": 2,
                    "text": "Updated content for page 2 with additional details",
                    "offset": 0,
                },
            ]

            mock_index.return_value = {"uploaded": 2, "failed": 0}

            # Execute reindexing
            reindex_response = client.post(f"/api/documents/{doc_id}/reindex")

        assert reindex_response.status_code == 200
        reindex_data = json.loads(reindex_response.data)
        assert reindex_data["doc_id"] == doc_id
        assert reindex_data["deleted_chunks"] == 3
        assert reindex_data["new_chunks"] == 2
        assert reindex_data["failed_chunks"] == 0

        # Verify delete and index methods were called
        mock_delete.assert_called_once_with(doc_id)
        mock_chunk.assert_called_once()
        mock_index.assert_called_once()


class TestErrorRecoveryWorkflows:
    """
    Test system behavior during partial failures and recovery scenarios.

    This test class validates:
    - Recovery from indexing failures during upload
    - Cleanup procedures for failed operations
    - Data consistency during error conditions
    - Retry mechanisms and error handling

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """

    def test_upload_indexing_failure_recovery_workflow(
        self, system_test_client, mock_all_azure_services
    ):
        """
        Test recovery from indexing failure during upload, followed by successful reindexing.

        This validates error recovery and cleanup mechanisms.
        """
        client = system_test_client
        mocks = mock_all_azure_services

        doc_id = "indexing_failure_test"
        filename = "indexing_failure_test.pdf"

        # Step 1: Upload with indexing failure
        with (
            patch(
                "app.services.storage_service.StorageService.compute_sha256",
                return_value=doc_id,
            ),
            patch(
                "app.services.storage_service.StorageService.compute_logical_id",
                return_value=f"logical_{doc_id}",
            ),
            patch(
                "app.services.extraction_service.ExtractionService.process_document"
            ) as mock_extract,
            patch(
                "app.services.chunking_service.ChunkingService.chunk_document"
            ) as mock_chunk,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_chunks"
            ) as mock_embed_chunks,
            patch(
                "app.services.embedding_service.EmbeddingService.embed_document"
            ) as mock_embed_doc,
            patch(
                "app.services.search_index_service.SearchIndexService.upload_chunks"
            ) as mock_upload,
        ):
            # Configure successful extraction and chunking
            mock_extract.return_value = {
                "extraction_data": {
                    "doc_id": doc_id,
                    "full_text": "Test document content for indexing failure recovery",
                    "pages": [
                        {
                            "page_number": 1,
                            "text": "Test document content for indexing failure recovery",
                        }
                    ],
                },
                "manifest": {
                    "page_count": 1,
                    "table_count": 0,
                    "text_length": 50,
                    "thumbnail_count": 1,
                },
            }

            mock_chunk.return_value = [
                {
                    "id": f"{doc_id}_chunk_1",
                    "doc_id": doc_id,
                    "page_no": 1,
                    "text": "Test document content for indexing failure recovery",
                    "offset": 0,
                }
            ]

            mock_embed_chunks.return_value = [
                {
                    "id": f"{doc_id}_chunk_1",
                    "doc_id": doc_id,
                    "text": "Test document content for indexing failure recovery",
                    "vector": [0.1] * 3072,
                }
            ]

            mock_embed_doc.return_value = [0.1] * 3072

            # Simulate indexing failure
            mock_upload.side_effect = Exception("Search index service unavailable")

            # No existing documents
            mocks["containers"]["documents"].read_item.return_value = None
            mocks["containers"]["documents"].query_items.return_value = []

            upload_response = client.post(
                "/api/documents/upload",
                data={"file": (BytesIO(b"PDF content"), filename)},
                content_type="multipart/form-data",
            )

        # Upload should complete but with indexing failure status
        assert upload_response.status_code in [200, 201, 500]

        if upload_response.status_code in [200, 201]:
            upload_data = json.loads(upload_response.data)
            # Document should be saved but not fully indexed
            assert upload_data["doc_id"] == doc_id
            assert (
                upload_data.get("indexed", False) is False
                or upload_data.get("status") != "indexed"
            )

        # Step 2: Simulate recovery - reindex the document
        with (
            patch(
                "app.services.search_index_service.SearchIndexService.delete_chunks_by_doc_id"
            ) as mock_delete,
            patch(
                "app.services.chunking_service.ChunkingService.chunk_document"
            ) as mock_chunk_retry,
            patch(
                "app.services.indexing_pipeline_service.IndexingPipelineService.index_chunks"
            ) as mock_index_retry,
        ):
            # Mock document exists with failed indexing status
            mocks["containers"]["documents"].read_item.return_value = {
                "id": doc_id,
                "doc_id": doc_id,
                "status": "extraction_complete_indexing_failed",
                "indexing_error": "Search index service unavailable",
            }

            # Mock extraction data retrieval
            extraction_data = {
                "doc_id": doc_id,
                "pages": [
                    {
                        "page_number": 1,
                        "text": "Test document content for indexing failure recovery",
                    }
                ],
            }

            mock_blob_client = Mock()
            mock_blob_client.download_blob.return_value.readall.return_value = (
                json.dumps(extraction_data).encode()
            )
            mocks["storage"].get_blob_client.return_value = mock_blob_client

            mock_delete.return_value = 0  # No existing chunks to delete

            mock_chunk_retry.return_value = [
                {
                    "id": f"{doc_id}_chunk_1_retry",
                    "doc_id": doc_id,
                    "page_no": 1,
                    "text": "Test document content for indexing failure recovery",
                    "offset": 0,
                }
            ]

            # This time indexing succeeds
            mock_index_retry.return_value = {"uploaded": 1, "failed": 0}

            reindex_response = client.post(f"/api/documents/{doc_id}/reindex")

        assert reindex_response.status_code == 200
        reindex_data = json.loads(reindex_response.data)
        assert reindex_data["doc_id"] == doc_id
        assert reindex_data["new_chunks"] == 1
        assert reindex_data["failed_chunks"] == 0

    def test_search_service_failure_recovery(
        self, system_test_client, mock_all_azure_services
    ):
        """
        Test system behavior when search service is temporarily unavailable.

        This validates graceful degradation and error handling in search workflows.
        """
        client = system_test_client

        # Step 1: Test search failure
        with patch("app.services.search_service.SearchService.search") as mock_search:
            mock_search.side_effect = Exception(
                "Search service temporarily unavailable"
            )

            search_response = client.get("/api/documents/search?q=test+query")

        assert search_response.status_code == 500
        error_data = json.loads(search_response.data)
        assert "error" in error_data
        assert "Search failed" in error_data["error"]

        # Step 2: Test chat failure when search is unavailable
        with patch("app.services.chat_service.ChatService.chat") as mock_chat:
            mock_chat.side_effect = Exception("Unable to retrieve context documents")

            chat_payload = {"query": "What are the key metrics?"}
            chat_response = client.post(
                "/api/documents/chat",
                data=json.dumps(chat_payload),
                content_type="application/json",
            )

        assert chat_response.status_code == 500
        chat_error_data = json.loads(chat_response.data)
        assert "error" in chat_error_data
        assert "Chat processing failed" in chat_error_data["error"]

        # Step 3: Test recovery when services are restored
        with patch(
            "app.services.search_service.SearchService.search"
        ) as mock_search_recovery:
            mock_search_recovery.return_value = {
                "query": "recovery test",
                "count": 1,
                "results": [
                    {
                        "citation_number": 1,
                        "chunk_id": "recovery_chunk_1",
                        "doc_id": "recovery_doc",
                        "title": "Recovery Test Document",
                        "text": "This is a recovery test result",
                        "score": 0.9,
                    }
                ],
            }

            recovery_response = client.get("/api/documents/search?q=recovery+test")

        assert recovery_response.status_code == 200
        recovery_data = json.loads(recovery_response.data)
        assert recovery_data["count"] == 1
        assert len(recovery_data["results"]) == 1

    def test_document_deletion_cleanup_workflow(
        self, system_test_client, mock_all_azure_services
    ):
        """
        Test complete cleanup workflow during document deletion.

        This validates EPIC E.14 - Document deletion with proper cleanup
        """
        client = system_test_client
        mocks = mock_all_azure_services

        doc_id = "deletion_cleanup_test"

        # Step 1: Mock existing document
        mocks["containers"]["documents"].read_item.return_value = {
            "id": doc_id,
            "doc_id": doc_id,
            "origin_filename": "deletion_test.pdf",
            "status": "indexed",
            "chunk_count": 3,
            "indexed_chunk_count": 3,
            "is_deleted": False,
        }

        # Step 2: Execute deletion with comprehensive cleanup
        with (
            patch(
                "app.services.search_index_service.SearchIndexService.delete_chunks_by_doc_id"
            ) as mock_delete_chunks,
            patch(
                "app.services.cosmos_service.CosmosService.mark_as_deleted"
            ) as mock_mark_deleted,
            patch(
                "app.services.storage_service.StorageService.archive_document_blobs"
            ) as mock_archive,
        ):
            mock_delete_chunks.return_value = 3  # 3 chunks deleted from search index
            mock_archive.return_value = {"raw": True, "extracted": True, "thumbs": True}

            delete_response = client.delete(f"/api/documents/{doc_id}")

        assert delete_response.status_code == 200
        delete_data = json.loads(delete_response.data)
        assert delete_data["doc_id"] == doc_id
        assert delete_data["deleted_chunks"] == 3
        assert delete_data["archived"]["raw"] is True
        assert delete_data["archived"]["extracted"] is True
        assert delete_data["archived"]["thumbs"] is True

        # Verify all cleanup methods were called
        mock_delete_chunks.assert_called_once_with(doc_id)
        mock_mark_deleted.assert_called_once_with(doc_id)
        mock_archive.assert_called_once_with(doc_id)

        # Step 3: Verify document no longer accessible
        mocks["containers"]["documents"].read_item.return_value = {
            "id": doc_id,
            "doc_id": doc_id,
            "status": "deleted",
            "is_deleted": True,
        }

        # Document should still exist but marked as deleted
        detail_response = client.get(f"/api/documents/{doc_id}")
        assert detail_response.status_code == 200
        detail_data = json.loads(detail_response.data)
        assert detail_data["is_deleted"] is True

        # Step 4: Verify document excluded from listings
        mocks["containers"][
            "documents"
        ].query_items.return_value = []  # Deleted docs excluded

        list_response = client.get("/api/documents/")
        assert list_response.status_code == 200
        list_data = json.loads(list_response.data)
        assert not any(doc["id"] == doc_id for doc in list_data["documents"])
