"""
Script to delete and recreate the Azure AI Search index with correct schema.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from app.services.search_index_service import SearchIndexService

def main():
    print("Deleting and recreating Azure AI Search index...")
    
    service = SearchIndexService()
    
    # Delete existing index
    print("\n1. Deleting existing index...")
    try:
        service.delete_index()
        print("   ✅ Index deleted")
    except Exception as e:
        print(f"   ⚠️  Could not delete index (may not exist): {e}")
    
    # Recreate index
    print("\n2. Creating new index...")
    try:
        index = service.create_index()
        print(f"   ✅ Index created: {index.name}")
        print(f"   Fields: {len(index.fields)}")
        print(f"   Vector search configured: {index.vector_search is not None}")
    except Exception as e:
        print(f"   ❌ Failed to create index: {e}")
        return False
    
    print("\n✅ Index recreation complete!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
