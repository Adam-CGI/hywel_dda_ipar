"""
Bulk reindex all existing documents in Cosmos DB.
This script will trigger reindexing for all documents that don't have chunks in the search index.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.cosmos_service import CosmosService
from app.services.search_index_service import SearchIndexService
import requests
import time

def main():
    print("\n" + "="*80)
    print("BULK REINDEX ALL DOCUMENTS")
    print("="*80)
    
    cosmos_service = CosmosService()
    search_index_service = SearchIndexService()
    
    # Get all non-deleted documents from Cosmos
    print("\n1. Fetching documents from Cosmos DB...")
    query = """
    SELECT c.id, c.origin_filename, c.status, c.chunk_count 
    FROM c 
    WHERE c.is_deleted != true OR NOT IS_DEFINED(c.is_deleted)
    """
    docs = list(cosmos_service.documents_container.query_items(
        query,
        enable_cross_partition_query=True
    ))
    
    print(f"   Found {len(docs)} documents in Cosmos")
    
    if not docs:
        print("   No documents to reindex!")
        return
    
    # Check which documents need reindexing
    docs_to_reindex = []
    for doc in docs:
        doc_id = doc['id']
        
        # Check if document has chunks in search index
        try:
            # Try to find at least one chunk for this document
            result = search_index_service.search_client.search(
                search_text="*",
                filter=f"doc_id eq '{doc_id}'",
                top=1
            )
            
            has_chunks = len(list(result)) > 0
            
            if not has_chunks:
                docs_to_reindex.append(doc)
                status = "❌ NO CHUNKS"
            else:
                status = "✅ HAS CHUNKS"
            
            print(f"   {doc.get('origin_filename', 'Unknown')[:50]:50} - {status}")
            
        except Exception as e:
            print(f"   ⚠️  Error checking {doc_id}: {e}")
            docs_to_reindex.append(doc)
    
    print(f"\n2. Documents needing reindex: {len(docs_to_reindex)}")
    
    if not docs_to_reindex:
        print("   All documents already indexed!")
        return
    
    # Ask for confirmation
    print("\n" + "="*80)
    print("⚠️  WARNING: This will reindex the following documents:")
    for doc in docs_to_reindex:
        print(f"   - {doc.get('origin_filename', doc['id'])}")
    print("="*80)
    
    response = input("\nProceed with reindexing? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Aborted.")
        return
    
    # Reindex documents
    print("\n3. Starting reindex process...\n")
    
    base_url = "http://localhost:8000"  # Change if running on different port/host
    
    success_count = 0
    failed_count = 0
    
    for i, doc in enumerate(docs_to_reindex, 1):
        doc_id = doc['id']
        filename = doc.get('origin_filename', doc_id)
        
        print(f"   [{i}/{len(docs_to_reindex)}] Reindexing {filename}...")
        
        try:
            response = requests.post(
                f"{base_url}/api/documents/{doc_id}/reindex",
                timeout=300  # 5 minute timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                chunks = result.get('new_chunks', 0)
                print(f"      ✅ Success - {chunks} chunks indexed")
                success_count += 1
            else:
                print(f"      ❌ Failed: {response.status_code} - {response.text[:100]}")
                failed_count += 1
                
        except Exception as e:
            print(f"      ❌ Error: {str(e)}")
            failed_count += 1
        
        # Small delay to avoid overwhelming the system
        if i < len(docs_to_reindex):
            time.sleep(1)
    
    # Summary
    print("\n" + "="*80)
    print("REINDEX COMPLETE")
    print("="*80)
    print(f"   ✅ Successfully reindexed: {success_count}")
    print(f"   ❌ Failed: {failed_count}")
    print(f"   📊 Total: {len(docs_to_reindex)}")
    
    if success_count > 0:
        print("\n💡 Test chat functionality now:")
        print("   1. Go to http://localhost:8000/api/documents/ui/chat")
        print("   2. Ask a question about your documents")
        print("   3. You should now see grounded responses with citations!")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
