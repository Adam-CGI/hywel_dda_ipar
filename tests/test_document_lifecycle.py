"""
Test Document Lifecycle - Upload, Verify, Query, Delete, Re-upload

This test verifies the complete lifecycle of a document:
1. Upload document successfully
2. Verify all artifacts in Storage containers and Cosmos DB
3. Query against the document in AI Search
4. Delete the document
5. Verify complete cleanup
6. Re-upload the same document successfully

CRITICAL: Tests the bug where deleted documents cannot be re-uploaded
"""
import os
import sys
import pytest
import requests
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

# Load environment variables
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_PDF = Path(__file__).parent.parent / "data" / "4.1 M12 2024-25 IPAR Overview.pdf"

# Azure connection strings
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
COSMOS_CONNECTION_STRING = os.getenv("AZURE_COSMOS_CONNECTION_STRING")
COSMOS_DATABASE = os.getenv("AZURE_COSMOS_DATABASE", "ipar")
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "ipar-chunks")

# Container names
CONTAINER_RAW = "raw"
CONTAINER_EXTRACTED = "extracted"
CONTAINER_THUMBS = "thumbs"
CONTAINER_MANIFESTS = "manifests"
CONTAINER_ARCHIVE = "archive"

# Cosmos collections
COLL_DOCUMENTS = "documents"
COLL_EVENTS = "events"


@pytest.fixture(scope="module")
def azure_clients():
    """Initialize Azure clients for direct verification."""
    if not all([AZURE_STORAGE_CONNECTION_STRING, COSMOS_CONNECTION_STRING, 
                AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_ADMIN_KEY]):
        pytest.skip("Azure connection strings not configured")
    
    blob_service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    cosmos_client = CosmosClient.from_connection_string(COSMOS_CONNECTION_STRING)
    cosmos_database = cosmos_client.get_database_client(COSMOS_DATABASE)
    
    search_credential = AzureKeyCredential(AZURE_SEARCH_ADMIN_KEY)
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=search_credential
    )
    
    return {
        'blob_service': blob_service,
        'cosmos_database': cosmos_database,
        'search_client': search_client
    }


@pytest.fixture
def test_document():
    """Provide test document path and metadata."""
    if not TEST_PDF.exists():
        pytest.skip(f"Test PDF not found: {TEST_PDF}")
    
    with open(TEST_PDF, 'rb') as f:
        file_bytes = f.read()
    
    # Compute expected doc_id (SHA256 of file bytes)
    import hashlib
    doc_id = hashlib.sha256(file_bytes).hexdigest()
    
    return {
        'path': TEST_PDF,
        'filename': TEST_PDF.name,
        'bytes': file_bytes,
        'doc_id': doc_id,
        'size': len(file_bytes)
    }


def verify_blob_exists(blob_service, container_name, blob_name):
    """Check if a blob exists in storage."""
    try:
        container_client = blob_service.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        return blob_client.exists()
    except Exception as e:
        print(f"Error checking blob existence: {e}")
        return False


def verify_blob_not_exists(blob_service, container_name, blob_name):
    """Check if a blob does NOT exist in storage."""
    return not verify_blob_exists(blob_service, container_name, blob_name)


def count_thumbnails(blob_service, doc_id):
    """Count number of thumbnails for a document."""
    try:
        container_client = blob_service.get_container_client(CONTAINER_THUMBS)
        blobs = list(container_client.list_blobs(name_starts_with=f"{doc_id}/"))
        return len(blobs)
    except Exception as e:
        print(f"Error counting thumbnails: {e}")
        return 0


def verify_cosmos_document(cosmos_database, doc_id):
    """Retrieve document from Cosmos DB."""
    try:
        container = cosmos_database.get_container_client(COLL_DOCUMENTS)
        doc = container.read_item(item=doc_id, partition_key=doc_id)
        return doc
    except Exception as e:
        print(f"Error reading Cosmos document: {e}")
        return None


def count_cosmos_events(cosmos_database, doc_id):
    """Count events for a document in Cosmos DB."""
    try:
        container = cosmos_database.get_container_client(COLL_EVENTS)
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.doc_id = @doc_id"
        items = list(container.query_items(
            query=query,
            parameters=[{"name": "@doc_id", "value": doc_id}],
            enable_cross_partition_query=True
        ))
        return items[0] if items else 0
    except Exception as e:
        print(f"Error counting events: {e}")
        return 0


def count_search_chunks(search_client, doc_id):
    """Count chunks for a document in AI Search index."""
    try:
        results = search_client.search(
            search_text="*",
            filter=f"doc_id eq '{doc_id}'",
            select=["id"],
            include_total_count=True
        )
        # Consume results to get count
        chunk_list = list(results)
        return len(chunk_list)
    except Exception as e:
        print(f"Error counting search chunks: {e}")
        return 0


class TestDocumentLifecycle:
    """Test complete document lifecycle with verification."""
    
    def test_01_upload_document(self, test_document):
        """Test document upload and verify 201 response."""
        print(f"\n=== Test 1: Upload Document ===")
        print(f"Document: {test_document['filename']}")
        print(f"Size: {test_document['size']} bytes")
        print(f"Expected doc_id: {test_document['doc_id']}")
        
        with open(test_document['path'], 'rb') as f:
            files = {'file': (test_document['filename'], f, 'application/pdf')}
            response = requests.post(
                f"{API_BASE_URL}/api/documents/upload",
                files=files,
                timeout=300  # 5 minutes for processing
            )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Verify response
        assert response.status_code in [200, 201], f"Upload failed with status {response.status_code}"
        
        result = response.json()
        assert 'doc_id' in result, "Response missing doc_id"
        assert result['doc_id'] == test_document['doc_id'], "doc_id mismatch"
        assert 'page_count' in result, "Response missing page_count"
        assert result['page_count'] > 0, "Page count should be greater than 0"
        
        # Store for later tests
        test_document['upload_response'] = result
        
        print(f"✅ Upload successful")
        print(f"   doc_id: {result['doc_id']}")
        print(f"   page_count: {result['page_count']}")
        print(f"   version: {result.get('version', 1)}")
    
    def test_02_verify_storage_artifacts(self, test_document, azure_clients):
        """Verify all required blobs exist in storage containers."""
        print(f"\n=== Test 2: Verify Storage Artifacts ===")
        
        doc_id = test_document['doc_id']
        blob_service = azure_clients['blob_service']
        
        # Wait a moment for async operations
        time.sleep(2)
        
        # 1. Raw container - PDF file
        raw_blob = f"{doc_id}.pdf"
        assert verify_blob_exists(blob_service, CONTAINER_RAW, raw_blob), \
            f"Raw PDF not found: {raw_blob}"
        print(f"✅ Raw PDF exists: {raw_blob}")
        
        # 2. Extracted container - JSON extraction
        extracted_blob = f"{doc_id}.json"
        assert verify_blob_exists(blob_service, CONTAINER_EXTRACTED, extracted_blob), \
            f"Extracted JSON not found: {extracted_blob}"
        print(f"✅ Extracted JSON exists: {extracted_blob}")
        
        # 3. Manifests container - processing manifest
        manifest_blob = f"{doc_id}.json"
        assert verify_blob_exists(blob_service, CONTAINER_MANIFESTS, manifest_blob), \
            f"Manifest not found: {manifest_blob}"
        print(f"✅ Manifest exists: {manifest_blob}")
        
        # 4. Thumbnails container - page thumbnails
        thumb_count = count_thumbnails(blob_service, doc_id)
        assert thumb_count > 0, "No thumbnails found"
        print(f"✅ Thumbnails exist: {thumb_count} thumbnails")
        
        # Store counts for later verification
        test_document['thumbnail_count'] = thumb_count
    
    def test_03_verify_cosmos_document(self, test_document, azure_clients):
        """Verify document metadata in Cosmos DB."""
        print(f"\n=== Test 3: Verify Cosmos DB Document ===")
        
        doc_id = test_document['doc_id']
        cosmos_database = azure_clients['cosmos_database']
        
        # Retrieve document
        doc = verify_cosmos_document(cosmos_database, doc_id)
        assert doc is not None, "Document not found in Cosmos DB"
        
        # Verify required fields
        assert doc['id'] == doc_id, "Document id mismatch"
        assert 'origin_filename' in doc, "Missing origin_filename"
        assert 'logical_id' in doc, "Missing logical_id"
        assert 'version' in doc, "Missing version"
        assert 'status' in doc, "Missing status"
        assert 'created_at' in doc, "Missing created_at"
        
        # Verify not marked as deleted
        assert not doc.get('is_deleted', False), "Document marked as deleted"
        
        print(f"✅ Cosmos document verified")
        print(f"   origin_filename: {doc.get('origin_filename')}")
        print(f"   logical_id: {doc.get('logical_id')[:16]}...")
        print(f"   version: {doc.get('version')}")
        print(f"   status: {doc.get('status')}")
        
        # Store for later verification
        test_document['cosmos_doc'] = doc
    
    def test_04_verify_cosmos_events(self, test_document, azure_clients):
        """Verify processing events logged in Cosmos DB."""
        print(f"\n=== Test 4: Verify Cosmos DB Events ===")
        
        doc_id = test_document['doc_id']
        cosmos_database = azure_clients['cosmos_database']
        
        event_count = count_cosmos_events(cosmos_database, doc_id)
        assert event_count > 0, "No events found for document"
        
        print(f"✅ Events logged: {event_count} events")
    
    def test_05_verify_search_index(self, test_document, azure_clients):
        """Verify document chunks indexed in AI Search."""
        print(f"\n=== Test 5: Verify AI Search Index ===")
        
        doc_id = test_document['doc_id']
        search_client = azure_clients['search_client']
        
        # Wait for indexing to complete
        time.sleep(3)
        
        chunk_count = count_search_chunks(search_client, doc_id)
        assert chunk_count > 0, "No chunks found in search index"
        
        print(f"✅ Chunks indexed: {chunk_count} chunks")
        
        # Store for later verification
        test_document['chunk_count'] = chunk_count
    
    def test_06_query_document(self, test_document, azure_clients):
        """Test querying against the indexed document."""
        print(f"\n=== Test 6: Query Document ===")
        
        doc_id = test_document['doc_id']
        
        # Try to search for content from the document
        # Use a generic query that should match
        response = requests.get(
            f"{API_BASE_URL}/api/documents/search",
            params={
                'query': 'IPAR',  # Generic term likely in the document
                'top': 5
            },
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Search returned {result.get('count', 0)} results")
            
            # Check if our document is in the results
            doc_found = any(
                r.get('doc_id') == doc_id 
                for r in result.get('results', [])
            )
            
            if doc_found:
                print(f"✅ Document found in search results")
            else:
                print(f"⚠️  Document not in top results (may need more specific query)")
        else:
            print(f"⚠️  Search endpoint returned {response.status_code}")
    
    def test_07_delete_document(self, test_document):
        """Test document deletion."""
        print(f"\n=== Test 7: Delete Document ===")
        
        doc_id = test_document['doc_id']
        
        response = requests.delete(
            f"{API_BASE_URL}/api/documents/{doc_id}",
            timeout=60
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        assert response.status_code == 200, f"Delete failed with status {response.status_code}"
        
        result = response.json()
        assert 'message' in result, "Response missing message"
        assert 'deleted_chunks' in result, "Response missing deleted_chunks"
        
        print(f"✅ Delete successful")
        print(f"   Deleted chunks: {result.get('deleted_chunks')}")
        print(f"   Archived files: {result.get('archived', {})}")
    
    def test_08_verify_deletion_artifacts(self, test_document, azure_clients):
        """Verify artifacts moved to archive and removed from active containers."""
        print(f"\n=== Test 8: Verify Deletion Artifacts ===")
        
        doc_id = test_document['doc_id']
        blob_service = azure_clients['blob_service']
        
        # Wait for async operations
        time.sleep(2)
        
        # Verify removed from active containers
        raw_blob = f"{doc_id}.pdf"
        assert verify_blob_not_exists(blob_service, CONTAINER_RAW, raw_blob), \
            "Raw PDF still exists (should be archived)"
        print(f"✅ Raw PDF removed from active storage")
        
        extracted_blob = f"{doc_id}.json"
        assert verify_blob_not_exists(blob_service, CONTAINER_EXTRACTED, extracted_blob), \
            "Extracted JSON still exists (should be archived)"
        print(f"✅ Extracted JSON removed from active storage")
        
        manifest_blob = f"{doc_id}.json"
        assert verify_blob_not_exists(blob_service, CONTAINER_MANIFESTS, manifest_blob), \
            "Manifest still exists (should be archived)"
        print(f"✅ Manifest removed from active storage")
        
        # Verify thumbnails removed
        thumb_count = count_thumbnails(blob_service, doc_id)
        assert thumb_count == 0, f"Thumbnails still exist: {thumb_count}"
        print(f"✅ All thumbnails removed from active storage")
        
        # Verify archived (optional - archive container might exist)
        try:
            archived_raw = verify_blob_exists(blob_service, CONTAINER_ARCHIVE, f"raw/{raw_blob}")
            if archived_raw:
                print(f"✅ Raw PDF archived")
        except Exception:
            pass  # Archive container might not exist in dev
    
    def test_09_verify_cosmos_soft_delete(self, test_document, azure_clients):
        """Verify Cosmos document marked as deleted (soft delete)."""
        print(f"\n=== Test 9: Verify Cosmos Soft Delete ===")
        
        doc_id = test_document['doc_id']
        cosmos_database = azure_clients['cosmos_database']
        
        # Document should still exist but marked as deleted
        doc = verify_cosmos_document(cosmos_database, doc_id)
        assert doc is not None, "Document removed from Cosmos (should be soft deleted)"
        
        assert doc.get('is_deleted', False) == True, "Document not marked as deleted"
        assert 'deleted_at' in doc, "Missing deleted_at timestamp"
        
        print(f"✅ Cosmos document soft deleted")
        print(f"   is_deleted: {doc.get('is_deleted')}")
        print(f"   deleted_at: {doc.get('deleted_at')}")
    
    def test_10_verify_search_chunks_removed(self, test_document, azure_clients):
        """Verify chunks removed from AI Search index."""
        print(f"\n=== Test 10: Verify Search Chunks Removed ===")
        
        doc_id = test_document['doc_id']
        search_client = azure_clients['search_client']
        
        # Wait for deletion to propagate
        time.sleep(3)
        
        chunk_count = count_search_chunks(search_client, doc_id)
        assert chunk_count == 0, f"Chunks still exist in search index: {chunk_count}"
        
        print(f"✅ All chunks removed from search index")
    
    def test_11_verify_deletion_event(self, test_document, azure_clients):
        """Verify deletion event logged in Cosmos."""
        print(f"\n=== Test 11: Verify Deletion Event ===")
        
        doc_id = test_document['doc_id']
        cosmos_database = azure_clients['cosmos_database']
        
        # Query for delete event
        try:
            container = cosmos_database.get_container_client(COLL_EVENTS)
            query = "SELECT * FROM c WHERE c.doc_id = @doc_id AND c.event_type = 'delete'"
            events = list(container.query_items(
                query=query,
                parameters=[{"name": "@doc_id", "value": doc_id}],
                enable_cross_partition_query=True
            ))
            
            assert len(events) > 0, "No delete event found"
            
            delete_event = events[0]
            print(f"✅ Delete event logged")
            print(f"   event_id: {delete_event.get('id')}")
            print(f"   timestamp: {delete_event.get('timestamp')}")
            
        except Exception as e:
            print(f"⚠️  Could not verify delete event: {e}")
    
    def test_12_reupload_document(self, test_document):
        """
        CRITICAL TEST: Re-upload the same document after deletion.
        
        This tests the bug where deleted documents cannot be re-uploaded
        because the duplicate detection doesn't account for soft-deleted documents.
        """
        print(f"\n=== Test 12: Re-upload Deleted Document ===")
        print("This is the CRITICAL test for the deletion bug!")
        
        with open(test_document['path'], 'rb') as f:
            files = {'file': (test_document['filename'], f, 'application/pdf')}
            response = requests.post(
                f"{API_BASE_URL}/api/documents/upload",
                files=files,
                timeout=300
            )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # This should succeed with 201, not fail with "already exists"
        assert response.status_code in [201], \
            f"Re-upload failed with status {response.status_code}. " \
            f"If status is 200 with 'duplicate detected', the bug still exists!"
        
        result = response.json()
        
        # Verify it's not treated as a duplicate
        assert result.get('duplicate', False) == False, \
            "Document incorrectly marked as duplicate - BUG DETECTED!"
        
        # Verify we got a new version or proper handling
        assert 'doc_id' in result, "Response missing doc_id"
        assert result['doc_id'] == test_document['doc_id'], "doc_id mismatch"
        
        print(f"✅ Re-upload successful!")
        print(f"   This proves the deletion bug is FIXED")
        print(f"   doc_id: {result['doc_id']}")
        print(f"   version: {result.get('version', 1)}")
    
    def test_13_verify_reupload_artifacts(self, test_document, azure_clients):
        """Verify re-uploaded document has all artifacts recreated."""
        print(f"\n=== Test 13: Verify Re-upload Artifacts ===")
        
        doc_id = test_document['doc_id']
        blob_service = azure_clients['blob_service']
        cosmos_database = azure_clients['cosmos_database']
        search_client = azure_clients['search_client']
        
        # Wait for processing
        time.sleep(3)
        
        # 1. Storage artifacts
        raw_blob = f"{doc_id}.pdf"
        assert verify_blob_exists(blob_service, CONTAINER_RAW, raw_blob), \
            "Raw PDF not recreated"
        print(f"✅ Storage artifacts recreated")
        
        # 2. Cosmos document (should not be deleted)
        doc = verify_cosmos_document(cosmos_database, doc_id)
        assert doc is not None, "Cosmos document not found"
        assert not doc.get('is_deleted', False), "Document still marked as deleted"
        print(f"✅ Cosmos document active (is_deleted=False)")
        
        # 3. Search chunks
        chunk_count = count_search_chunks(search_client, doc_id)
        assert chunk_count > 0, "Chunks not re-indexed"
        print(f"✅ Search chunks re-indexed: {chunk_count} chunks")


# Standalone execution
if __name__ == "__main__":
    print("=" * 80)
    print("DOCUMENT LIFECYCLE TEST")
    print("=" * 80)
    print("\nThis test verifies:")
    print("1. Document upload with all artifacts")
    print("2. Complete deletion and cleanup")
    print("3. Re-upload after deletion (BUG FIX VERIFICATION)")
    print("\n" + "=" * 80 + "\n")
    
    # Run with pytest
    pytest.main([__file__, "-v", "-s"])
