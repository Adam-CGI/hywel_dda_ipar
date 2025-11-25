"""
Search service implementing hybrid BM25 + vector retrieval with citations.
Supports EPIC F requirements for search and citation generation.
"""
import logging
import json
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from config import AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_ADMIN_KEY, AZURE_SEARCH_INDEX
from services.embedding_service import EmbeddingService
from services.storage_service import StorageService
from services.cosmos_service import CosmosService

logger = logging.getLogger(__name__)


class SearchService:
    """Service for executing hybrid search queries with citations."""
    
    def __init__(self):
        """Initialize search service with required dependencies."""
        if not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_ADMIN_KEY:
            raise ValueError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY must be configured")
        
        self.index_name = AZURE_SEARCH_INDEX or "ipar-chunks"
        
        credential = AzureKeyCredential(AZURE_SEARCH_ADMIN_KEY)
        self.search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=self.index_name,
            credential=credential
        )
        
        self.embedding_service = EmbeddingService()
        self.storage_service = StorageService()
        self.cosmos_service = CosmosService()
        
        logger.info(f"Initialized SearchService for index: {self.index_name}")
    
    def search(
        self,
        query: str,
        top: int = 10,
        filter_expr: Optional[str] = None,
        include_thumbnails: bool = True
    ) -> Dict[str, Any]:
        """
        Execute hybrid BM25 + vector search with citations.
        
        Args:
            query: Search query text
            top: Number of results to return (default: 10)
            filter_expr: Optional OData filter expression (e.g., "doc_id eq 'abc123'")
            include_thumbnails: Whether to generate SAS URLs for thumbnails (default: True)
        
        Returns:
            Dictionary containing:
            - results: List of search result chunks with citations
            - count: Total number of results
            - query: Original query text
        """
        try:
            logger.info(f"Executing search query: '{query}' (top={top}, filter={filter_expr})")
            
            # Generate embedding for vector search
            query_vector = self.embedding_service.embed_texts([query])[0]
            
            # Create vectorized query for hybrid search
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top,
                fields="vector"
            )
            
            # Execute hybrid search (BM25 + vector)
            results = self.search_client.search(
                search_text=query,  # BM25 text search
                vector_queries=[vector_query],  # Vector search
                top=top,
                filter=filter_expr,
                select=[
                    "id",
                    "doc_id",
                    "logical_id",
                    "title",
                    "origin_filename",
                    "page_no",
                    "text",
                    "spans",
                    "observed_date",
                    "document_date",
                    "year",
                    "month",
                    "quarter",
                    "fiscal_year",
                    "kpi_tags"
                ]
            )
            
            # Format results with citations
            formatted_results = []
            citation_number = 1
            
            for result in results:
                # Parse spans from JSON string
                spans_str = result.get("spans", "[]")
                try:
                    spans = json.loads(spans_str) if isinstance(spans_str, str) else spans_str
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse spans for chunk {result['id']}")
                    spans = []
                
                # Extract snippet from text (first 200 chars or full text if shorter)
                text = result.get("text", "")
                snippet = text[:200] + "..." if len(text) > 200 else text
                
                # Get document metadata from Cosmos for additional context
                doc_id = result.get("doc_id")
                doc_metadata = self.cosmos_service.get_document(doc_id)
                
                # Build result with citation
                citation = {
                    "citation_number": citation_number,
                    "chunk_id": result.get("id"),
                    "doc_id": doc_id,
                    "logical_id": result.get("logical_id"),
                    "title": result.get("title", "Untitled Document"),
                    "origin_filename": result.get("origin_filename", ""),
                    "page_no": result.get("page_no", 1),
                    "spans": spans,
                    "snippet": snippet,
                    "text": text,
                    "observed_date": result.get("observed_date"),
                    "document_date": result.get("document_date"),
                    "year": result.get("year"),
                    "month": result.get("month"),
                    "quarter": result.get("quarter"),
                    "fiscal_year": result.get("fiscal_year"),
                    "kpi_tags": result.get("kpi_tags", []),
                    "score": result.get("@search.score", 0.0),
                    "reranker_score": result.get("@search.reranker_score")
                }
                
                # Add thumbnail URL with SAS token if requested
                if include_thumbnails:
                    page_no = result.get("page_no", 1)
                    # Generate thumbnail blob path: doc_id/pN.png
                    thumb_blob_name = f"{doc_id}/p{page_no}.png"
                    from config import CONTAINER_THUMBS
                    thumb_url = self.storage_service.generate_sas_url(
                        container_name=CONTAINER_THUMBS,
                        blob_name=thumb_blob_name,
                        expiry_hours=1
                    )
                    citation["thumb_url"] = thumb_url
                
                # Add document metadata if available
                if doc_metadata:
                    citation["document_status"] = doc_metadata.get("status")
                    citation["document_version"] = doc_metadata.get("version", 1)
                    citation["uploaded_by"] = doc_metadata.get("uploaded_by")
                    citation["uploaded_at"] = doc_metadata.get("uploaded_at")
                
                formatted_results.append(citation)
                citation_number += 1
            
            response = {
                "query": query,
                "count": len(formatted_results),
                "results": formatted_results,
                "filter": filter_expr
            }
            
            logger.info(f"Search completed: {len(formatted_results)} results returned")
            return response
            
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}", exc_info=True)
            raise
    
    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific chunk by its ID.
        
        Args:
            chunk_id: Unique chunk identifier
        
        Returns:
            Chunk document or None if not found
        """
        try:
            result = self.search_client.get_document(key=chunk_id)
            
            # Parse spans
            spans_str = result.get("spans", "[]")
            try:
                spans = json.loads(spans_str) if isinstance(spans_str, str) else spans_str
            except json.JSONDecodeError:
                spans = []
            
            return {
                "id": result.get("id"),
                "doc_id": result.get("doc_id"),
                "title": result.get("title"),
                "page_no": result.get("page_no"),
                "text": result.get("text"),
                "spans": spans,
                "kpi_tags": result.get("kpi_tags", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to retrieve chunk {chunk_id}: {e}")
            return None
    
    def search_by_document(
        self,
        doc_id: str,
        query: Optional[str] = None,
        top: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search within a specific document.
        
        Args:
            doc_id: Document identifier
            query: Optional search query (if None, returns all chunks)
            top: Maximum number of results
        
        Returns:
            List of chunks from the specified document
        """
        try:
            filter_expr = f"doc_id eq '{doc_id}'"
            
            if query:
                result = self.search(
                    query=query,
                    top=top,
                    filter_expr=filter_expr,
                    include_thumbnails=False
                )
                return result["results"]
            else:
                # Get all chunks for this document
                results = self.search_client.search(
                    search_text="*",
                    filter=filter_expr,
                    top=top,
                    select=["id", "doc_id", "page_no", "text", "spans"]
                )
                
                chunks = []
                for result in results:
                    spans_str = result.get("spans", "[]")
                    try:
                        spans = json.loads(spans_str) if isinstance(spans_str, str) else spans_str
                    except json.JSONDecodeError:
                        spans = []
                    
                    chunks.append({
                        "id": result.get("id"),
                        "doc_id": result.get("doc_id"),
                        "page_no": result.get("page_no"),
                        "text": result.get("text"),
                        "spans": spans
                    })
                
                return chunks
                
        except Exception as e:
            logger.error(f"Failed to search document {doc_id}: {e}")
            raise
