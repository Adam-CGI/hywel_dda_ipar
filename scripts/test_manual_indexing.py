"""Test manual indexing to see what error occurs."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from flask_app.services.cosmos_service import CosmosService
from flask_app.services.chunking_service import ChunkingService
from flask_app.services.embedding_service import EmbeddingService
from flask_app.services.search_index_service import SearchIndexService
from flask_app.services.storage_service import StorageService

print("\n" + "="*80)
print("TESTING MANUAL INDEXING")
print("="*80)

# Get document from Cosmos
cosmos = CosmosService()
docs = list(cosmos.documents_container.query_items(
    "SELECT * FROM c WHERE NOT IS_DEFINED(c.is_deleted) OR c.is_deleted = false",
    enable_cross_partition_query=True
))

if not docs:
    print("\n❌ No documents found!")
    sys.exit(1)

doc = docs[0]
doc_id = doc['id']
print(f"\nTesting with document: {doc.get('origin_filename')}")
print(f"Doc ID: {doc_id}")

# Download extraction data
print("\n1. Downloading extraction data...")
storage = StorageService()
try:
    extraction_data = storage.download_json('extracted', f"{doc_id}.json")
    print(f"   ✅ Downloaded extraction data")
    print(f"   Pages: {len(extraction_data.get('pages', []))}")
except Exception as e:
    print(f"   ❌ Failed to download: {e}")
    sys.exit(1)

# Try chunking
print("\n2. Chunking document...")
chunking = ChunkingService()
try:
    chunks = chunking.chunk_document(doc_id, extraction_data)
    print(f"   ✅ Created {len(chunks)} chunks")
    if chunks:
        print(f"   Sample chunk ID: {chunks[0]['id']}")
        print(f"   Sample chunk text: {chunks[0]['text'][:100]}...")
except Exception as e:
    print(f"   ❌ Chunking failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Try embedding
print("\n3. Generating embeddings...")
embedding = EmbeddingService()
try:
    chunks_with_embeddings = embedding.embed_chunks(chunks[:2])  # Test with just 2 chunks
    print(f"   ✅ Generated embeddings")
    print(f"   Vector dimension: {len(chunks_with_embeddings[0]['vector'])}")
except Exception as e:
    print(f"   ❌ Embedding failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Try indexing
print("\n4. Uploading to search index...")
search_index = SearchIndexService()
try:
    result = search_index.upload_chunks(chunks_with_embeddings)
    print(f"   ✅ Upload result: {result}")
except Exception as e:
    print(f"   ❌ Index upload failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("✅ ALL STEPS COMPLETED SUCCESSFULLY!")
print("="*80)
