"""
Diagnostic script to identify why chat is not finding documents.
"""
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

from flask_app.services.cosmos_service import CosmosService
from flask_app.services.search_service import SearchService
from flask_app.services.search_index_service import SearchIndexService

def main():
    print("\n" + "="*80)
    print("DIAGNOSING CHAT 'NO DOCUMENTS FOUND' ISSUE")
    print("="*80)
    
    # Step 1: Check Cosmos DB for documents
    print("\n1. Checking Cosmos DB for documents...")
    try:
        cosmos_service = CosmosService()
        query = "SELECT c.id, c.title, c.origin_filename, c.is_deleted FROM c"
        docs = list(cosmos_service.container_documents.query_items(
            query,
            enable_cross_partition_query=True
        ))
        
        active_docs = [d for d in docs if not d.get('is_deleted', False)]
        deleted_docs = [d for d in docs if d.get('is_deleted', False)]
        
        print(f"   ✅ Total documents in Cosmos: {len(docs)}")
        print(f"   ✅ Active documents: {len(active_docs)}")
        print(f"   ⚠️  Deleted documents: {len(deleted_docs)}")
        
        if active_docs:
            print("\n   Active documents:")
            for doc in active_docs[:5]:
                print(f"      - {doc.get('title', doc.get('origin_filename', 'Unknown'))} (id: {doc['id'][:16]}...)")
        else:
            print("\n   ❌ NO ACTIVE DOCUMENTS FOUND IN COSMOS!")
            
    except Exception as e:
        print(f"   ❌ Error accessing Cosmos: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 2: Check Azure AI Search index
    print("\n2. Checking Azure AI Search index...")
    try:
        search_service = SearchService()
        
        # Try wildcard search to get ANY documents
        results = search_service.search_client.search(
            search_text="*",
            top=1,
            select=["id", "doc_id", "title"]
        )
        
        result_list = list(results)
        print(f"   Documents in search index: {len(result_list)}")
        
        if result_list:
            print(f"   ✅ Search index has documents")
            print(f"      Sample: {result_list[0].get('title', 'Unknown')}")
        else:
            print(f"   ❌ SEARCH INDEX IS EMPTY!")
            print(f"      This is the problem! Documents exist in Cosmos but not indexed.")
            
    except Exception as e:
        print(f"   ❌ Error accessing search index: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 3: Check search index schema
    print("\n3. Checking search index schema...")
    try:
        index_service = SearchIndexService()
        index = index_service.index_client.get_index(index_service.index_name)
        
        print(f"   ✅ Index exists: {index.name}")
        print(f"   Fields: {len(index.fields)}")
        
        # Check for vector field
        vector_fields = [f for f in index.fields if hasattr(f, 'vector_search_dimensions')]
        if vector_fields:
            print(f"   ✅ Vector field found: {vector_fields[0].name} ({vector_fields[0].vector_search_dimensions} dims)")
        else:
            print(f"   ⚠️  No vector field found")
            
    except Exception as e:
        print(f"   ❌ Error checking index schema: {e}")
    
    # Step 4: Try a real search query
    print("\n4. Testing hybrid search query...")
    try:
        results = search_service.search(
            query="performance indicators",
            top=5,
            include_thumbnails=False
        )
        
        print(f"   Search returned: {results['count']} results")
        
        if results['count'] > 0:
            print(f"   ✅ Search is working!")
            for i, r in enumerate(results['results'][:3], 1):
                print(f"      {i}. {r.get('title', 'Unknown')} (score: {r.get('score', 0):.2f})")
        else:
            print(f"   ❌ Search returned 0 results")
            
    except Exception as e:
        print(f"   ❌ Error during search: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "="*80)
    print("DIAGNOSIS SUMMARY")
    print("="*80)
    
    if len(active_docs) > 0 and len(result_list) == 0:
        print("\n❌ ROOT CAUSE IDENTIFIED:")
        print("   Documents exist in Cosmos DB but are NOT indexed in Azure AI Search!")
        print("\n💡 SOLUTION:")
        print("   You need to re-index your documents. Options:")
        print("   1. Re-upload documents (triggers indexing)")
        print("   2. Run the indexing pipeline manually")
        print("   3. Use scripts/recreate_index.py to rebuild the index")
        
    elif len(active_docs) == 0:
        print("\n❌ ROOT CAUSE IDENTIFIED:")
        print("   No active documents in the system!")
        print("\n💡 SOLUTION:")
        print("   Upload documents via /api/documents/upload")
        
    else:
        print("\n✅ Documents are properly indexed - chat should be working!")
        print("   If chat still fails, check:")
        print("   - Azure OpenAI configuration")
        print("   - Embedding service configuration")
        print("   - Network connectivity")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
