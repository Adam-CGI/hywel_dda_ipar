"""
Debug script to test uploading a single minimal document to identify the problematic field.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from flask_app.services.search_index_service import SearchIndexService
from datetime import datetime

def main():
    print("Testing minimal document upload...")
    
    service = SearchIndexService()
    
    # Test 1: Absolute minimal document
    print("\n1. Testing absolute minimal document (just required fields)...")
    minimal_doc = {
        "id": "test_001",
        "doc_id": "test_doc",
        "logical_id": "test_doc",
        "version": 1,
        "source_uri": "test://uri",
        "title": "Test",
        "origin_filename": "test.pdf",
        "page_no": 1,
        "text": "Test text",
        "spans": "[]",  # JSON string
        "vector": [0.1] * 3072
    }
    
    try:
        result = service.search_client.upload_documents(documents=[minimal_doc])
        print(f"   ✅ Success: {result[0].succeeded if result else 'unknown'}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        print("\n2. Testing without optional fields one by one...")
        
        # Test without observed_date
        try:
            test_doc = minimal_doc.copy()
            test_doc["observed_date"] = None
            test_doc["kpi_tags"] = []
            result = service.search_client.upload_documents(documents=[test_doc])
            print(f"   ✅ With observed_date=None, kpi_tags=[]: Success")
        except Exception as e2:
            print(f"   ❌ With observed_date=None, kpi_tags=[]: {str(e2)[:100]}")
        
        # Test with kpi_tags
        try:
            test_doc = minimal_doc.copy()
            test_doc["kpi_tags"] = ["tag1", "tag2"]
            result = service.search_client.upload_documents(documents=[test_doc])
            print(f"   ✅ With kpi_tags=['tag1', 'tag2']: Success")
        except Exception as e3:
            print(f"   ❌ With kpi_tags: {str(e3)[:100]}")
        
        # Test with observed_date
        try:
            test_doc = minimal_doc.copy()
            test_doc["observed_date"] = datetime.utcnow().isoformat() + "Z"
            result = service.search_client.upload_documents(documents=[test_doc])
            print(f"   ✅ With observed_date: Success")
        except Exception as e4:
            print(f"   ❌ With observed_date: {str(e4)[:100]}")
    
    print("\n3. Testing with JSON spans vs parsed spans...")
    try:
        test_doc = minimal_doc.copy()
        test_doc["id"] = "test_002"
        test_doc["spans"] = [{"start": 0, "end": 9, "page_no": 1}]  # Send as list not JSON string
        result = service.search_client.upload_documents(documents=[test_doc])
        print(f"   ⚠️ Spans as list works!")
    except Exception as e:
        print(f"   ❌ Spans as list failed: {str(e)[:100]}")

if __name__ == "__main__":
    main()
