"""
Test script to verify EPIC B - Ingestion Pipeline
"""
import os
import sys
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_PDF = Path(__file__).parent.parent / "data" / "4.1 M12 2024-25 IPAR Overview.pdf"


def test_health_check():
    """Test health check endpoint."""
    print("\n=== Testing Health Check ===")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        assert response.status_code == 200
        print("✅ Health check passed")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_upload_document():
    """Test document upload endpoint."""
    print("\n=== Testing Document Upload ===")
    
    if not TEST_PDF.exists():
        print(f"❌ Test PDF not found: {TEST_PDF}")
        return False
    
    try:
        print(f"Uploading: {TEST_PDF.name}")
        print(f"File size: {TEST_PDF.stat().st_size / 1024:.2f} KB")
        
        with open(TEST_PDF, 'rb') as f:
            files = {'file': (TEST_PDF.name, f, 'application/pdf')}
            response = requests.post(
                f"{API_BASE_URL}/api/documents/upload",
                files=files,
                timeout=300  # 5 minutes for extraction
            )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"\n✅ Upload successful!")
            print(f"   Document ID: {result.get('doc_id')}")
            print(f"   Page Count: {result.get('page_count')}")
            print(f"   Table Count: {result.get('table_count')}")
            print(f"   Thumbnails: {result.get('thumbnail_count')}")
            print(f"   Status: {result.get('status')}")
            print(f"   Duplicate: {result.get('duplicate')}")
            return result.get('doc_id')
        else:
            print(f"❌ Upload failed with status {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_list_documents():
    """Test list documents endpoint."""
    print("\n=== Testing List Documents ===")
    try:
        response = requests.get(f"{API_BASE_URL}/api/documents/")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Document count: {result.get('count')}")
            if result.get('documents'):
                print("\nDocuments:")
                for doc in result.get('documents', [])[:5]:  # Show first 5
                    print(f"  - {doc.get('origin_filename')} ({doc.get('doc_id')[:16]}...)")
            print("✅ List documents passed")
            return True
        else:
            print(f"❌ List documents failed")
            return False
            
    except Exception as e:
        print(f"❌ List documents failed: {e}")
        return False


def test_get_document(doc_id):
    """Test get document endpoint."""
    print(f"\n=== Testing Get Document ({doc_id[:16]}...) ===")
    try:
        response = requests.get(f"{API_BASE_URL}/api/documents/{doc_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Document details:")
            print(f"  Origin Filename: {result.get('origin_filename')}")
            print(f"  Page Count: {result.get('page_count')}")
            print(f"  Status: {result.get('status')}")
            print(f"  Created At: {result.get('created_at')}")
            print("✅ Get document passed")
            return True
        else:
            print(f"❌ Get document failed")
            return False
            
    except Exception as e:
        print(f"❌ Get document failed: {e}")
        return False


def verify_azure_resources():
    """Verify Azure resources exist (Blob containers, Cosmos collections)."""
    print("\n=== Verifying Azure Resources ===")
    print("Checking .env configuration...")
    
    required_vars = [
        "AZURE_STORAGE_CONNSTR",
        "COSMOS_ENDPOINT",
        "COSMOS_KEY",
        "AZURE_DOCINTEL_ENDPOINT",
        "AZURE_DOCINTEL_KEY"
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        return False
    
    print("✅ All required environment variables are set")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("EPIC B - Ingestion Pipeline Test Suite")
    print("=" * 60)
    
    # Check environment variables
    if not verify_azure_resources():
        print("\n⚠️  Please ensure .env is configured correctly")
        return False
    
    # Test health check
    if not test_health_check():
        print("\n❌ API is not responding. Is the Flask app running?")
        print("   Run: python app.py")
        return False
    
    # Test upload
    doc_id = test_upload_document()
    if not doc_id:
        print("\n❌ Upload test failed")
        return False
    
    # Test list documents
    if not test_list_documents():
        print("\n❌ List documents test failed")
        return False
    
    # Test get document
    if not test_get_document(doc_id):
        print("\n❌ Get document test failed")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All EPIC B tests passed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Check Azure Storage containers (raw, extracted, thumbs, manifests)")
    print("2. Verify Cosmos DB documents and events collections")
    print("3. Proceed to EPIC C - Chunking, Embedding & Indexing")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
