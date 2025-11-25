"""
Simulate the exact upload flow to see where indexing fails.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from flask_app.services.storage_service import StorageService
from flask_app.services.extraction_service import ExtractionService
from flask_app.services.cosmos_service import CosmosService
from flask_app.services.embedding_service import EmbeddingService
from flask_app.services.search_index_service import SearchIndexService
from flask_app.services.chunking_service import ChunkingService
from datetime import datetime

print("\n" + "="*80)
print("SIMULATING UPLOAD FLOW")
print("="*80)

# Get the document
cosmos_service = CosmosService()
storage_service = StorageService()
extraction_service = ExtractionService()
embedding_service = EmbeddingService()
search_index_service = SearchIndexService()
chunking_service = ChunkingService()

docs = list(cosmos_service.documents_container.query_items(
    "SELECT * FROM c WHERE NOT IS_DEFINED(c.is_deleted) OR c.is_deleted = false",
    enable_cross_partition_query=True
))

if not docs:
    print("No documents found!")
    sys.exit(1)

doc = docs[0]
doc_id = doc['id']
origin_filename = doc.get('origin_filename', 'test.pdf')
logical_id = doc.get('logical_id', doc_id)
version = doc.get('version', 1)

print(f"\nDocument: {origin_filename}")
print(f"Doc ID: {doc_id}")
print(f"Current status: {doc.get('status')}")

# Simulate Step 8 from upload route
print("\n" + "="*80)
print("STEP 8: INDEX DOCUMENT")
print("="*80)

try:
    # Get extraction data (simulating processing_result['extraction_data'])
    print("\n1. Loading extraction data...")
    extraction_data = storage_service.download_json('extracted', f"{doc_id}.json")
    print(f"   ✅ Loaded {len(extraction_data.get('pages', []))} pages")
    
    # Chunk the extracted text
    print("\n2. Chunking document...")
    chunks = chunking_service.chunk_document(
        doc_id=doc_id,
        extraction_data=extraction_data
    )
    print(f"   ✅ Created {len(chunks)} chunks")
    
    # Enrich chunks with metadata
    print("\n3. Enriching chunks with metadata...")
    blob_url = doc.get('source_uri', f'blob://{doc_id}')
    for chunk in chunks:
        chunk["logical_id"] = logical_id
        chunk["version"] = version
        chunk["title"] = origin_filename
        chunk["origin_filename"] = origin_filename
        chunk["source_uri"] = blob_url
        chunk["observed_date"] = datetime.utcnow().isoformat() + 'Z'  # Add Z for UTC timezone
        chunk["kpi_tags"] = []
    print(f"   ✅ Enriched {len(chunks)} chunks")
    
    # Embed chunks
    print("\n4. Generating embeddings...")
    chunks_with_embeddings = embedding_service.embed_chunks(chunks)
    print(f"   ✅ Generated embeddings for {len(chunks_with_embeddings)} chunks")
    
    # Upload to search index
    print("\n5. Uploading to search index...")
    upload_result = search_index_service.upload_chunks(chunks_with_embeddings)
    print(f"   ✅ Uploaded {upload_result['uploaded']} chunks")
    print(f"      Failed: {upload_result.get('failed', 0)}")
    
    # Update document status
    print("\n6. Updating document status...")
    doc['status'] = 'indexed'
    doc['chunk_count'] = len(chunks)
    doc['indexed_chunk_count'] = upload_result['uploaded']
    doc['indexed_at'] = datetime.utcnow().isoformat()
    cosmos_service.save_document(doc)
    print(f"   ✅ Updated document status to 'indexed'")
    
    print("\n" + "="*80)
    print("✅ INDEXING COMPLETED SUCCESSFULLY!")
    print("="*80)
    print(f"\nFinal status:")
    print(f"  - Chunks created: {len(chunks)}")
    print(f"  - Chunks indexed: {upload_result['uploaded']}")
    print(f"  - Status: indexed")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
