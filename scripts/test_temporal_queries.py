"""
Quick test of temporal query functionality.
Tests searching with date filters on already-indexed documents.
"""
import sys
import os

# Add the flask_app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'flask_app'))

from services.search_service import SearchService
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_temporal_queries():
    """Test temporal queries on indexed documents."""
    logger.info("=" * 80)
    logger.info("TESTING TEMPORAL QUERIES")
    logger.info("=" * 80)
    
    search_service = SearchService()
    
    # Test cases for temporal queries
    test_queries = [
        {
            "description": "All documents from June 2025",
            "query": "performance report",
            "filter": "month eq 6 and year eq 2025"
        },
        {
            "description": "Documents from Q2 2025 (Apr-Jun)",
            "query": "hospital performance",
            "filter": "quarter eq 2 and year eq 2025"
        },
        {
            "description": "Documents from Q3 2025 (Jul-Sep)",
            "query": "IPAR report",
            "filter": "quarter eq 3 and year eq 2025"
        },
        {
            "description": "Documents from fiscal year 2024-25",
            "query": "IPAR",
            "filter": "fiscal_year eq '2024-25'"
        },
        {
            "description": "Documents from fiscal year 2025-26",
            "query": "performance",
            "filter": "fiscal_year eq '2025-26'"
        },
        {
            "description": "Most recent documents (August onwards 2025)",
            "query": "report",
            "filter": "document_date ge 2025-08-01T00:00:00Z"
        },
        {
            "description": "Documents before July 2025",
            "query": "performance assurance",
            "filter": "document_date lt 2025-07-01T00:00:00Z"
        },
        {
            "description": "Documents from August 2025 specifically",
            "query": "integrated performance",
            "filter": "year eq 2025 and month eq 8"
        },
        {
            "description": "All documents sorted by document date (newest first)",
            "query": "IPAR report",
            "filter": None,
            "order_by": "document_date desc"
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
                    logger.info(f"    Quarter: Q{result.get('quarter', 'N/A')}")
                    logger.info(f"    Year/Month: {result.get('year', 'N/A')}/{result.get('month', 'N/A')}")
                    logger.info(f"    Page: {result['page_no']}")
                    logger.info(f"    Score: {result['score']:.4f}")
                    snippet = result['snippet'][:100] + "..." if len(result['snippet']) > 100 else result['snippet']
                    logger.info(f"    Snippet: {snippet}")
            else:
                logger.warning("✗ No results found")
        
        except Exception as e:
            logger.error(f"✗ Query failed: {e}", exc_info=True)
    
    logger.info("\n" + "=" * 80)
    logger.info("TEMPORAL QUERY TESTING COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    test_temporal_queries()
