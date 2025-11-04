"""
Azure AI Search index service for managing the ipar-chunks index.
Implements hybrid BM25 + vector search with HNSW profile.
"""
import logging
from typing import List, Dict, Any
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    HnswParameters,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)
from azure.core.credentials import AzureKeyCredential
from app.config import AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_ADMIN_KEY, AZURE_SEARCH_INDEX

logger = logging.getLogger(__name__)


class SearchIndexService:
    """Service for managing Azure AI Search index operations."""
    
    INDEX_NAME = AZURE_SEARCH_INDEX or "ipar-chunks"
    VECTOR_DIMENSION = 3072  # text-embedding-3-large dimension
    HNSW_PROFILE_NAME = "veconf"
    
    def __init__(self):
        """Initialize Azure Search clients."""
        if not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_ADMIN_KEY:
            raise ValueError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY must be configured")
        
        credential = AzureKeyCredential(AZURE_SEARCH_ADMIN_KEY)
        
        self.index_client = SearchIndexClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            credential=credential
        )
        
        self.search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=self.INDEX_NAME,
            credential=credential
        )
        
        logger.info(f"Initialized SearchIndexService for index: {self.INDEX_NAME}")
    
    def create_index(self) -> SearchIndex:
        """
        Create the ipar-chunks index with hybrid search configuration.
        
        Returns:
            SearchIndex: The created index
        """
        try:
            # Check if index already exists
            try:
                existing_index = self.index_client.get_index(self.INDEX_NAME)
                logger.info(f"Index {self.INDEX_NAME} already exists")
                return existing_index
            except Exception:
                logger.info(f"Index {self.INDEX_NAME} does not exist, creating...")
            
            # Define fields based on reference.md schema
            fields = [
                SimpleField(
                    name="id",
                    type=SearchFieldDataType.String,
                    key=True,
                    filterable=True
                ),
                SimpleField(
                    name="doc_id",
                    type=SearchFieldDataType.String,
                    filterable=True,
                    sortable=True
                ),
                SimpleField(
                    name="logical_id",
                    type=SearchFieldDataType.String,
                    filterable=True
                ),
                SimpleField(
                    name="version",
                    type=SearchFieldDataType.Int32,
                    filterable=True,
                    sortable=True
                ),
                SimpleField(
                    name="source_uri",
                    type=SearchFieldDataType.String,
                    filterable=False
                ),
                SearchableField(
                    name="title",
                    type=SearchFieldDataType.String,
                    filterable=True,
                    sortable=True
                ),
                SimpleField(
                    name="origin_filename",
                    type=SearchFieldDataType.String,
                    filterable=True
                ),
                SimpleField(
                    name="page_no",
                    type=SearchFieldDataType.Int32,
                    filterable=True,
                    sortable=True
                ),
                SimpleField(
                    name="observed_date",
                    type=SearchFieldDataType.DateTimeOffset,
                    filterable=True,
                    sortable=True
                ),
                SearchField(
                    name="kpi_tags",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                    filterable=True,
                    searchable=True
                ),
                SearchableField(
                    name="text",
                    type=SearchFieldDataType.String,
                    analyzer_name="en.microsoft"
                ),
                SimpleField(
                    name="spans",
                    type=SearchFieldDataType.String,  # JSON serialized
                    filterable=False
                ),
                SearchField(
                    name="vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=self.VECTOR_DIMENSION,
                    vector_search_profile_name=self.HNSW_PROFILE_NAME
                )
            ]
            
            # Configure HNSW vector search
            vector_search = VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="hnsw-config",
                        parameters=HnswParameters(
                            m=4,
                            ef_construction=400,
                            ef_search=500,
                            metric="cosine"
                        )
                    )
                ],
                profiles=[
                    VectorSearchProfile(
                        name=self.HNSW_PROFILE_NAME,
                        algorithm_configuration_name="hnsw-config"
                    )
                ]
            )
            
            # Configure semantic search for better relevance
            semantic_config = SemanticConfiguration(
                name="ipar-semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="text")]
                )
            )
            
            semantic_search = SemanticSearch(
                configurations=[semantic_config]
            )
            
            # Create index
            index = SearchIndex(
                name=self.INDEX_NAME,
                fields=fields,
                vector_search=vector_search,
                semantic_search=semantic_search
            )
            
            result = self.index_client.create_index(index)
            logger.info(f"Successfully created index: {self.INDEX_NAME}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise
    
    def index_exists(self) -> bool:
        """Check if the index exists."""
        try:
            self.index_client.get_index(self.INDEX_NAME)
            return True
        except Exception:
            return False
    
    def delete_index(self):
        """Delete the index if it exists."""
        try:
            if self.index_exists():
                self.index_client.delete_index(self.INDEX_NAME)
                logger.info(f"Deleted index: {self.INDEX_NAME}")
            else:
                logger.info(f"Index {self.INDEX_NAME} does not exist")
        except Exception as e:
            logger.error(f"Failed to delete index: {e}")
            raise
    
    def upload_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upload chunks to the search index.
        
        Args:
            chunks: List of chunk documents with all required fields
            
        Returns:
            Dictionary with upload results
        """
        if not chunks:
            logger.warning("No chunks to upload")
            return {"uploaded": 0, "failed": 0}
        
        try:
            # Ensure index exists
            if not self.index_exists():
                logger.info("Index does not exist, creating...")
                self.create_index()
            
            # Prepare documents for upload
            documents = []
            for chunk in chunks:
                # Convert spans to JSON string
                import json
                from datetime import datetime
                
                # Ensure kpi_tags is a list
                kpi_tags = chunk.get("kpi_tags", [])
                if kpi_tags is None:
                    kpi_tags = []
                
                # Ensure observed_date is properly formatted or None
                observed_date = chunk.get("observed_date")
                if observed_date and isinstance(observed_date, str):
                    # If it's already a string, ensure it's ISO format
                    try:
                        datetime.fromisoformat(observed_date.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        observed_date = None
                
                doc = {
                    "id": chunk["id"],
                    "doc_id": chunk["doc_id"],
                    "logical_id": chunk.get("logical_id", chunk["doc_id"]),
                    "version": chunk.get("version", 1),
                    "source_uri": chunk.get("source_uri", ""),
                    "title": chunk.get("title", ""),
                    "origin_filename": chunk.get("origin_filename", ""),
                    "page_no": chunk["page_no"],
                    "observed_date": observed_date,
                    "kpi_tags": kpi_tags,
                    "text": chunk["text"],
                    "spans": json.dumps(chunk.get("spans", [])),
                    "vector": chunk["vector"]
                }
                documents.append(doc)
            
            # Upload in batches (Azure Search recommends 1000 docs per batch)
            batch_size = 1000
            total_uploaded = 0
            total_failed = 0
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                logger.info(f"Uploading batch {i // batch_size + 1}: {len(batch)} documents")
                
                # Debug: Log first document structure
                if i == 0 and batch:
                    logger.info(f"Sample document structure: {list(batch[0].keys())}")
                    logger.info(f"Vector type: {type(batch[0]['vector'])}, length: {len(batch[0]['vector']) if isinstance(batch[0]['vector'], list) else 'N/A'}")
                    logger.info(f"kpi_tags type: {type(batch[0]['kpi_tags'])}")
                
                result = self.search_client.upload_documents(documents=batch)
                
                succeeded = sum(1 for r in result if r.succeeded)
                failed = len(result) - succeeded
                
                total_uploaded += succeeded
                total_failed += failed
                
                if failed > 0:
                    logger.warning(f"Batch had {failed} failures")
            
            logger.info(f"Upload complete: {total_uploaded} succeeded, {total_failed} failed")
            
            return {
                "uploaded": total_uploaded,
                "failed": total_failed,
                "total": len(documents)
            }
            
        except Exception as e:
            logger.error(f"Failed to upload chunks: {e}")
            raise
    
    def delete_chunks_by_doc_id(self, doc_id: str) -> int:
        """
        Delete all chunks for a specific document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Number of chunks deleted
        """
        try:
            # Search for all chunks with this doc_id
            results = self.search_client.search(
                search_text="*",
                filter=f"doc_id eq '{doc_id}'",
                select=["id"]
            )
            
            chunk_ids = [doc["id"] for doc in results]
            
            if not chunk_ids:
                logger.info(f"No chunks found for doc_id: {doc_id}")
                return 0
            
            # Delete chunks
            documents = [{"id": chunk_id} for chunk_id in chunk_ids]
            result = self.search_client.delete_documents(documents=documents)
            
            deleted = sum(1 for r in result if r.succeeded)
            logger.info(f"Deleted {deleted} chunks for doc_id: {doc_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete chunks for doc_id {doc_id}: {e}")
            raise
    
    # Note: For hybrid BM25 + vector search functionality, use SearchService
    # (app.services.search_service.SearchService) which implements the full
    # hybrid search with query embeddings and citation formatting.
    # SearchIndexService focuses on index management and chunk upload/delete operations.
