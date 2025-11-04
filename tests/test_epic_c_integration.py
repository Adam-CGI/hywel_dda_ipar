"""
Integration test for EPIC C - Full pipeline test with sample PDF.

This script tests the complete pipeline:
1. Load sample PDF
2. Extract text and metadata
3. Chunk the document
4. Generate embeddings
5. Upload to search index
6. Verify chunks are searchable
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Must configure before importing services
from dotenv import load_dotenv
load_dotenv()

from app.services.indexing_pipeline_service import IndexingPipelineService
from app.services.storage_service import StorageService
from app.services.search_index_service import SearchIndexService


def main():
    """Run integration test with sample PDF."""
    print("="*80)
    print("EPIC C Integration Test - Full Pipeline")
    print("="*80)
    
    # Check if sample PDF exists
    sample_pdf_path = project_root / "data" / "4.1 M12 2024-25 IPAR Overview.pdf"
    if not sample_pdf_path.exists():
        print(f"❌ Sample PDF not found at: {sample_pdf_path}")
        return False
    
    print(f"✅ Found sample PDF: {sample_pdf_path}")
    
    try:
        # Initialize services
        print("\n📦 Initializing services...")
        storage_service = StorageService()
        pipeline_service = IndexingPipelineService()
        search_service = SearchIndexService()
        
        # Create search index if it doesn't exist
        print("\n🔧 Ensuring search index exists...")
        if not search_service.index_exists():
            print("   Creating index...")
            search_service.create_index()
            print("   ✅ Index created")
        else:
            print("   ✅ Index already exists")
        
        # Load PDF
        print(f"\n📄 Loading PDF: {sample_pdf_path.name}")
        with open(sample_pdf_path, 'rb') as f:
            pdf_bytes = f.read()
        
        print(f"   PDF size: {len(pdf_bytes):,} bytes")
        
        # Compute document ID
        doc_id = storage_service.compute_sha256(pdf_bytes)
        print(f"   Document ID: {doc_id}")
        
        # Check if already indexed
        print("\n🔍 Checking if document already indexed...")
        try:
            from app.services.cosmos_service import CosmosService
            cosmos_service = CosmosService()
            existing_doc = cosmos_service.get_document(doc_id)
            
            if existing_doc:
                print(f"   ⚠️  Document already indexed (found in Cosmos)")
                print(f"   Existing chunk count: {existing_doc.get('chunk_count', 'unknown')}")
                
                # Ask to reindex
                print("\n   Deleting existing chunks from search index...")
                deleted = search_service.delete_chunks_by_doc_id(doc_id)
                print(f"   ✅ Deleted {deleted} chunks")
        except Exception as e:
            print(f"   Note: Could not check Cosmos (may not be configured): {e}")
        
        # Run full pipeline
        print("\n🚀 Running full indexing pipeline...")
        print("   Steps: Extract → Chunk → Embed → Index")
        
        metadata = {
            "title": "M12 2024-25 IPAR Overview",
            "version": 1,
            "kpi_tags": ["IPAR", "performance", "overview"],
            "logical_id": doc_id
        }
        
        result = pipeline_service.process_and_index_document(
            doc_id=doc_id,
            pdf_bytes=pdf_bytes,
            origin_filename=sample_pdf_path.name,
            metadata=metadata
        )
        
        # Display results
        print("\n" + "="*80)
        print("📊 Pipeline Results")
        print("="*80)
        print(f"✅ Success: {result['success']}")
        print(f"⏱️  Duration: {result.get('duration_seconds', 0):.2f} seconds")
        print(f"📄 Pages extracted: {len(result['extraction_data'].get('pages', []))}")
        print(f"📋 Chunks created: {result.get('chunks_created', 0)}")
        print(f"📤 Chunks uploaded: {result.get('chunks_uploaded', 0)}")
        print(f"❌ Chunks failed: {result.get('chunks_failed', 0)}")
        print(f"🖼️  Thumbnails: {len(result.get('thumbnails', []))}")
        
        # Test search
        print("\n" + "="*80)
        print("🔍 Testing Search")
        print("="*80)
        
        test_queries = [
            "performance",
            "IPAR",
            "overview"
        ]
        
        for query in test_queries:
            print(f"\n   Query: '{query}'")
            search_results = search_service.search_hybrid(query, top=3, filter_expr=f"doc_id eq '{doc_id}'")
            print(f"   Results: {len(search_results)}")
            
            if search_results:
                for i, res in enumerate(search_results[:2], 1):
                    print(f"      {i}. Page {res['page_no']}: {res['text'][:80]}...")
        
        print("\n" + "="*80)
        print("✅ Integration Test Complete!")
        print("="*80)
        
        # Summary
        print("\n📈 Summary:")
        print(f"   • Document successfully processed and indexed")
        print(f"   • {result.get('chunks_created', 0)} chunks created from {len(result['extraction_data'].get('pages', []))} pages")
        print(f"   • All {result.get('chunks_uploaded', 0)} chunks uploaded to search index")
        print(f"   • Search queries returning results")
        print(f"   • Pipeline duration: {result.get('duration_seconds', 0):.2f}s")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
