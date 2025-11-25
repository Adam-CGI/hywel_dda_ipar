"""
Script to clear existing documents and reindex with temporal metadata.
"""
import sys
import os

# Add the flask_app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'flask_app'))

from services.storage_service import StorageService
from services.indexing_pipeline_service import IndexingPipelineService
from services.cosmos_service import CosmosService
from services.search_index_service import SearchIndexService
from services.date_parser_service import DateParserService
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clear_existing_data():
    """Clear existing documents from index and Cosmos DB."""
    logger.info("=" * 80)
    logger.info("CLEARING EXISTING DATA")
    logger.info("=" * 80)
    
    try:
        # Initialize services
        search_service = SearchIndexService()
        cosmos_service = CosmosService()
        
        # Delete and recreate the index
        logger.info("Deleting existing search index...")
        try:
            search_service.index_client.delete_index(search_service.INDEX_NAME)
            logger.info("✓ Index deleted")
        except Exception as e:
            logger.info(f"Index may not exist: {e}")
        
        logger.info("Creating new index with temporal fields...")
        search_service.create_index()
        logger.info("✓ New index created")
        
        # Clear Cosmos DB documents
        logger.info("\nClearing Cosmos DB documents...")
        all_docs = cosmos_service.query_documents("SELECT c.id, c.doc_id FROM c")
        deleted_count = 0
        for doc in all_docs:
            try:
                cosmos_service.delete_document(doc['doc_id'])
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete doc {doc['doc_id']}: {e}")
        
        logger.info(f"✓ Deleted {deleted_count} documents from Cosmos DB")
        
        logger.info("\n" + "=" * 80)
        logger.info("DATA CLEARED SUCCESSFULLY")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error clearing data: {e}", exc_info=True)
        raise


def upload_documents_with_temporal():
    """Upload all PDFs from the data folder with temporal metadata."""
    logger.info("\n" + "=" * 80)
    logger.info("UPLOADING DOCUMENTS WITH TEMPORAL METADATA")
    logger.info("=" * 80)
    
    # Initialize services
    storage_service = StorageService()
    pipeline_service = IndexingPipelineService()
    
    # Get data folder path
    data_folder = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    if not os.path.exists(data_folder):
        logger.error(f"Data folder not found: {data_folder}")
        return []
    
    # Find all PDF files
    pdf_files = sorted([f for f in os.listdir(data_folder) if f.lower().endswith('.pdf')])
    
    if not pdf_files:
        logger.error("No PDF files found in data folder")
        return []
    
    logger.info(f"Found {len(pdf_files)} PDF files to upload\n")
    
    uploaded_docs = []
    
    for i, filename in enumerate(pdf_files, 1):
        logger.info(f"[{i}/{len(pdf_files)}] Processing: {filename}")
        
        try:
            # Parse temporal metadata from filename
            date_metadata = DateParserService.extract_date_metadata(filename)
            logger.info(f"  Temporal: {date_metadata.get('document_date')} | FY: {date_metadata.get('fiscal_year')} | Q{date_metadata.get('quarter')}")
            
            # Read file
            file_path = os.path.join(data_folder, filename)
            with open(file_path, 'rb') as f:
                pdf_bytes = f.read()
            
            # Compute doc_id
            doc_id = storage_service.compute_sha256(pdf_bytes)
            
            # Upload to raw storage
            doc_id, blob_url = storage_service.upload_to_raw(pdf_bytes, filename)
            
            # Process and index
            result = pipeline_service.process_and_index_document(
                doc_id=doc_id,
                pdf_bytes=pdf_bytes,
                origin_filename=filename,
                metadata={
                    'title': filename.replace('.pdf', ''),
                    'observed_date': datetime.utcnow().isoformat() + 'Z'
                }
            )
            
            if result['success']:
                logger.info(f"  ✓ Indexed: {result['chunks_uploaded']} chunks in {result['duration_seconds']:.1f}s")
                uploaded_docs.append({
                    'doc_id': doc_id,
                    'filename': filename,
                    'date_metadata': date_metadata,
                    'chunks': result['chunks_uploaded']
                })
            else:
                logger.error(f"  ✗ Failed: {result.get('error')}")
        
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
    
    logger.info("\n" + "=" * 80)
    logger.info(f"UPLOAD COMPLETE: {len(uploaded_docs)}/{len(pdf_files)} documents indexed")
    logger.info("=" * 80)
    
    # Summary
    if uploaded_docs:
        logger.info("\nSummary:")
        total_chunks = sum(doc['chunks'] for doc in uploaded_docs)
        logger.info(f"  Total chunks indexed: {total_chunks}")
        logger.info(f"  Documents with dates:")
        for doc in uploaded_docs:
            date_str = doc['date_metadata'].get('document_date', 'No date')
            logger.info(f"    - {doc['filename']}: {date_str}")
    
    return uploaded_docs


def main():
    """Main execution function."""
    logger.info("Starting reindexing with temporal metadata...")
    
    # Step 1: Clear existing data
    clear_existing_data()
    
    # Step 2: Upload documents with temporal metadata
    uploaded_docs = upload_documents_with_temporal()
    
    if not uploaded_docs:
        logger.error("No documents were uploaded. Exiting.")
        return
    
    logger.info("\n✓ Reindexing complete! You can now run temporal queries.")
    logger.info("  Run: python scripts/test_temporal_queries.py")


if __name__ == "__main__":
    main()
