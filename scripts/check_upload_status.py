"""Quick check of document upload and indexing status."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.cosmos_service import CosmosService
from app.services.search_service import SearchService

print("\n" + "="*80)
print("CHECKING UPLOAD AND INDEXING STATUS")
print("="*80)

# Check Cosmos DB
print("\n1. Documents in Cosmos DB:")
cosmos = CosmosService()
docs = list(cosmos.documents_container.query_items(
    "SELECT c.id, c.status, c.origin_filename, c.chunk_count, c.indexed_chunk_count FROM c WHERE NOT IS_DEFINED(c.is_deleted) OR c.is_deleted = false",
    enable_cross_partition_query=True
))

print(f"   Total: {len(docs)}")
for doc in docs:
    status = doc.get('status', 'unknown')
    chunks = doc.get('chunk_count', 0)
    indexed = doc.get('indexed_chunk_count', 0)
    filename = doc.get('origin_filename', 'Unknown')[:50]
    print(f"   - {filename}")
    print(f"     Status: {status}, Chunks: {chunks}, Indexed: {indexed}")

# Check Search Index
print("\n2. Chunks in Azure AI Search:")
search = SearchService()
results = search.search_client.search(search_text="*", top=1)
result_list = list(results)

print(f"   Total chunks: {len(result_list)}")
if result_list:
    print(f"   Sample chunk: {result_list[0].get('doc_id', 'unknown')}")
else:
    print("   ⚠️  SEARCH INDEX IS EMPTY!")

print("\n" + "="*80)
