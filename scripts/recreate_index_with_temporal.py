"""
Script to recreate the search index with temporal fields.
This will delete the existing index and create a new one with the updated schema.
"""
import sys
import os

# Add the flask_app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'flask_app'))

from services.search_index_service import SearchIndexService
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Recreate the search index with temporal fields."""
    try:
        logger.info("Initializing SearchIndexService...")
        search_service = SearchIndexService()
        
        # Delete existing index if it exists
        try:
            logger.info(f"Attempting to delete existing index: {search_service.INDEX_NAME}")
            search_service.index_client.delete_index(search_service.INDEX_NAME)
            logger.info("✓ Existing index deleted successfully")
        except Exception as e:
            logger.info(f"Index may not exist (this is OK): {e}")
        
        # Create new index with temporal fields
        logger.info("Creating new index with temporal fields...")
        new_index = search_service.create_index()
        
        logger.info(f"✓ Index '{new_index.name}' created successfully!")
        logger.info("\nNew temporal fields added:")
        logger.info("  - document_date (DateTimeOffset) - Filterable, Sortable")
        logger.info("  - year (Int32) - Filterable, Sortable")
        logger.info("  - month (Int32) - Filterable, Sortable")
        logger.info("  - quarter (Int32) - Filterable, Sortable")
        logger.info("  - fiscal_year (String) - Filterable, Sortable")
        
        logger.info("\nIndex is ready. You can now upload documents with temporal metadata.")
        
    except Exception as e:
        logger.error(f"Failed to recreate index: {e}")
        raise


if __name__ == "__main__":
    main()
