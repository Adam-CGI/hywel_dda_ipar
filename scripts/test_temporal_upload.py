"""
Script to upload IPAR documents with temporal metadata and test temporal queries.
"""
import sys
import os

# Add the flask_app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'flask_app'))

from services.storage_service import StorageService
from services.indexing_pipeline_service import IndexingPipelineService
from services.search_service import SearchService
from services.date_parser_service import DateParserService
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def upload_documents():
    """Upload all PDFs from the data folder."""
    logger.info("=" * 80)
    logger.info("STARTING DOCUMENT UPLOAD WITH TEMPORAL METADATA")
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
    pdf_files = [f for f in os.listdir(data_folder) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        logger.error("No PDF files found in data folder")
        return []
    
    logger.info(f"Found {len(pdf_files)} PDF files to upload")
    logger.info("-" * 80)
    
    uploaded_docs = []
    
    for filename in pdf_files:
        logger.info(f"\nProcessing: {filename}")
        
        # Parse temporal metadata from filename
        date_metadata = DateParserService.extract_date_metadata(filename)
        logger.info(f"  Temporal metadata:")
        logger.info(f"    - Document Date: {date_metadata.get('document_date')}")
        logger.info(f"    - Fiscal Year: {date_metadata.get('fiscal_year')}")
        logger.info(f"    - Quarter: Q{date_metadata.get('quarter')}")
        logger.info(f"    - Year: {date_metadata.get('year')}")
        logger.info(f"    - Month: {date_metadata.get('month')}")
        
        # Read file
        file_path = os.path.join(data_folder, filename)
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        
        # Compute doc_id
        doc_id = storage_service.compute_sha256(pdf_bytes)
        logger.info(f"  Document ID: {doc_id[:16]}...")
        
        # Upload to raw storage
        doc_id, blob_url = storage_service.upload_to_raw(pdf_bytes, filename)
        logger.info(f"  ✓ Uploaded to blob storage")
        
        # Process and index
        try:
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
                logger.info(f"  ✓ Indexed successfully:")
                logger.info(f"    - Chunks created: {result['chunks_created']}")
                logger.info(f"    - Chunks uploaded: {result['chunks_uploaded']}")
                logger.info(f"    - Duration: {result['duration_seconds']:.2f}s")
                uploaded_docs.append({
                    'doc_id': doc_id,
                    'filename': filename,
                    'date_metadata': date_metadata
                })
            else:
                logger.error(f"  ✗ Indexing failed: {result.get('error')}")
        
        except Exception as e:
            logger.error(f"  ✗ Error processing document: {e}")
    
    logger.info("\n" + "=" * 80)
    logger.info(f"UPLOAD COMPLETE: {len(uploaded_docs)}/{len(pdf_files)} documents successfully indexed")
    logger.info("=" * 80)
    
    return uploaded_docs


def test_temporal_queries(uploaded_docs):
    """Test temporal queries on uploaded documents."""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING TEMPORAL QUERIES")
    logger.info("=" * 80)
    
    search_service = SearchService()
    
    # Test cases for temporal queries
    test_queries = [
        {
            "description": "All documents from June 2025",
            "query": "performance",
            "filter": "month eq 6 and year eq 2025"
        },
        {
            "description": "Documents from Q2 2025",
            "query": "hospital performance",
            "filter": "quarter eq 2 and year eq 2025"
        },
        {
            "description": "Documents from fiscal year 2024-25",
            "query": "IPAR",
            "filter": "fiscal_year eq '2024-25'"
        },
        {
            "description": "Most recent documents (August onwards 2025)",
            "query": "report",
            "filter": "document_date ge 2025-08-01T00:00:00Z"
        },
        {
            "description": "Documents before October 2025",
            "query": "performance assurance",
            "filter": "document_date lt 2025-10-01T00:00:00Z"
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        logger.info(f"\n{'─' * 80}")
        logger.info(f"Test Query {i}: {test['description']}")
        logger.info(f"Query: '{test['query']}'")
        logger.info(f"Filter: {test['filter']}")
        logger.info("─" * 80)
        
        try:
            results = search_service.search(
                query=test['query'],
                top=5,
                filter_expr=test['filter']
            )
            
            if results['count'] > 0:
                logger.info(f"✓ Found {results['count']} results")
                for j, result in enumerate(results['results'], 1):
                    logger.info(f"\n  Result {j}:")
                    logger.info(f"    Title: {result['title']}")
                    logger.info(f"    Filename: {result['origin_filename']}")
                    logger.info(f"    Document Date: {result.get('document_date', 'N/A')}")
                    logger.info(f"    Fiscal Year: {result.get('fiscal_year', 'N/A')}")
                    logger.info(f"    Page: {result['page_no']}")
                    logger.info(f"    Score: {result['score']:.4f}")
                    logger.info(f"    Snippet: {result['snippet'][:150]}...")
            else:
                logger.warning(f"✗ No results found")
        
        except Exception as e:
            logger.error(f"✗ Query failed: {e}")
    
    logger.info("\n" + "=" * 80)
    logger.info("TEMPORAL QUERY TESTING COMPLETE")
    logger.info("=" * 80)


def main():
    """Main execution function."""
    logger.info("Starting temporal metadata integration test...")
    
    # Upload documents with temporal metadata
    uploaded_docs = upload_documents()
    
    if not uploaded_docs:
        logger.error("No documents were uploaded. Exiting.")
        return
    
    # Test temporal queries
    test_temporal_queries(uploaded_docs)
    
    logger.info("\n✓ All tests complete!")


if __name__ == "__main__":
    main()
