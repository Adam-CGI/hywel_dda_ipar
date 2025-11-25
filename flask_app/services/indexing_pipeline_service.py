"""
Indexing pipeline orchestrator for document processing.
Orchestrates: extraction → chunking → embedding → indexing
"""
import logging
from typing import Dict, Any, List
from datetime import datetime
from services.extraction_service import ExtractionService
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService
from services.search_index_service import SearchIndexService
from services.cosmos_service import CosmosService
from services.storage_service import StorageService
from services.date_parser_service import DateParserService

logger = logging.getLogger(__name__)


class IndexingPipelineService:
    """Service for orchestrating the full document indexing pipeline."""
    
    def __init__(self):
        """Initialize all required services."""
        self.extraction_service = ExtractionService()
        self.chunking_service = ChunkingService()
        self.embedding_service = EmbeddingService()
        self.search_index_service = SearchIndexService()
        self.cosmos_service = CosmosService()
        self.storage_service = StorageService()
        
        logger.info("Initialized IndexingPipelineService")
    
    def process_and_index_document(
        self,
        doc_id: str,
        pdf_bytes: bytes,
        origin_filename: str,
        metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Full pipeline: extract → chunk → embed → index.
        
        Args:
            doc_id: Document identifier (SHA256 of PDF bytes)
            pdf_bytes: PDF file content
            origin_filename: Original filename
            metadata: Optional additional metadata (title, version, etc.)
            
        Returns:
            Dictionary with pipeline results
        """
        try:
            logger.info(f"Starting indexing pipeline for document {doc_id}")
            start_time = datetime.utcnow()
            
            # Step 1: Extract text and generate thumbnails
            logger.info(f"Step 1: Extracting document {doc_id}")
            processing_result = self.extraction_service.process_document(
                doc_id,
                pdf_bytes,
                origin_filename
            )
            extraction_data = processing_result["extraction_data"]
            thumbnails = processing_result["thumbnails"]
            manifest = processing_result["manifest"]
            
            # Step 2: Chunk the extracted text
            logger.info(f"Step 2: Chunking document {doc_id}")
            chunks = self.chunking_service.chunk_document(doc_id, extraction_data)
            
            if not chunks:
                logger.warning(f"No chunks created for document {doc_id}")
                return {
                    "doc_id": doc_id,
                    "success": False,
                    "error": "No chunks created",
                    "extraction_data": extraction_data,
                    "manifest": manifest
                }
            
            # Extract temporal metadata from filename
            date_metadata = DateParserService.extract_date_metadata(origin_filename)
            logger.info(f"Extracted temporal metadata: document_date={date_metadata.get('document_date')}, fiscal_year={date_metadata.get('fiscal_year')}")
            
            # Enrich chunks with metadata
            for chunk in chunks:
                chunk["logical_id"] = metadata.get("logical_id", doc_id) if metadata else doc_id
                chunk["version"] = metadata.get("version", 1) if metadata else 1
                chunk["title"] = metadata.get("title", origin_filename) if metadata else origin_filename
                chunk["origin_filename"] = origin_filename
                chunk["source_uri"] = f"blob://{doc_id}"
                chunk["observed_date"] = metadata.get("observed_date") if metadata else (datetime.utcnow().isoformat() + 'Z')
                chunk["kpi_tags"] = metadata.get("kpi_tags", []) if metadata else []
                # Add temporal metadata
                chunk["document_date"] = date_metadata.get("document_date")
                chunk["year"] = date_metadata.get("year")
                chunk["month"] = date_metadata.get("month")
                chunk["quarter"] = date_metadata.get("quarter")
                chunk["fiscal_year"] = date_metadata.get("fiscal_year")
            
            # Step 3: Generate embeddings
            logger.info(f"Step 3: Generating embeddings for {len(chunks)} chunks")
            chunks_with_embeddings = self.embedding_service.embed_chunks(chunks)
            
            # Step 4: Upload to search index
            logger.info(f"Step 4: Uploading {len(chunks_with_embeddings)} chunks to search index")
            upload_result = self.search_index_service.upload_chunks(chunks_with_embeddings)
            
            # Step 5: Record in Cosmos DB
            logger.info(f"Step 5: Recording document metadata in Cosmos DB")
            doc_metadata = {
                "id": doc_id,
                "doc_id": doc_id,
                "logical_id": metadata.get("logical_id", doc_id) if metadata else doc_id,
                "version": metadata.get("version", 1) if metadata else 1,
                "title": metadata.get("title", origin_filename) if metadata else origin_filename,
                "origin_filename": origin_filename,
                "page_count": len(extraction_data.get("pages", [])),
                "chunk_count": len(chunks),
                "indexed_chunk_count": upload_result["uploaded"],
                "status": "indexed" if upload_result["uploaded"] > 0 else "failed",
                "created_at": start_time.isoformat(),
                "indexed_at": datetime.utcnow().isoformat(),
                "manifest": manifest,
                # Add temporal metadata
                "document_date": date_metadata.get("document_date"),
                "year": date_metadata.get("year"),
                "month": date_metadata.get("month"),
                "quarter": date_metadata.get("quarter"),
                "fiscal_year": date_metadata.get("fiscal_year")
            }
            
            self.cosmos_service.create_document(doc_metadata)
            
            # Record event
            event = {
                "event_type": "document_indexed",
                "doc_id": doc_id,
                "timestamp": datetime.utcnow().isoformat(),
                "details": {
                    "chunks_created": len(chunks),
                    "chunks_uploaded": upload_result["uploaded"],
                    "chunks_failed": upload_result["failed"]
                }
            }
            self.cosmos_service.create_event(event)
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"Successfully indexed document {doc_id} in {duration:.2f}s")
            
            return {
                "doc_id": doc_id,
                "success": True,
                "duration_seconds": duration,
                "extraction_data": extraction_data,
                "chunks_created": len(chunks),
                "chunks_uploaded": upload_result["uploaded"],
                "chunks_failed": upload_result["failed"],
                "thumbnails": thumbnails,
                "manifest": manifest
            }
            
        except Exception as e:
            logger.error(f"Indexing pipeline failed for document {doc_id}: {e}")
            
            # Record failure event
            try:
                event = {
                    "event_type": "indexing_failed",
                    "doc_id": doc_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                }
                self.cosmos_service.create_event(event)
            except Exception:
                pass
            
            raise
    
    def reindex_document(self, doc_id: str) -> Dict[str, Any]:
        """
        Reindex an existing document (re-chunk, re-embed, re-upload).
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Dictionary with reindexing results
        """
        try:
            logger.info(f"Reindexing document {doc_id}")
            
            # Step 1: Delete existing chunks from index
            logger.info(f"Step 1: Deleting existing chunks for {doc_id}")
            deleted_count = self.search_index_service.delete_chunks_by_doc_id(doc_id)
            
            # Step 2: Get document metadata from Cosmos
            logger.info(f"Step 2: Retrieving document metadata from Cosmos")
            doc_metadata = self.cosmos_service.get_document(doc_id)
            
            if not doc_metadata:
                raise ValueError(f"Document {doc_id} not found in Cosmos DB")
            
            # Step 3: Download extraction data from blob storage
            logger.info(f"Step 3: Downloading extraction data")
            from config import CONTAINER_EXTRACTED
            extraction_blob_name = f"{doc_id}.json"
            extraction_data = self.storage_service.download_json(CONTAINER_EXTRACTED, extraction_blob_name)
            
            # Step 4: Re-chunk
            logger.info(f"Step 4: Re-chunking document")
            chunks = self.chunking_service.chunk_document(doc_id, extraction_data)
            
            # Enrich with metadata
            for chunk in chunks:
                chunk["logical_id"] = doc_metadata.get("logical_id", doc_id)
                chunk["version"] = doc_metadata.get("version", 1)
                chunk["title"] = doc_metadata.get("title", "")
                chunk["origin_filename"] = doc_metadata.get("origin_filename", "")
                chunk["source_uri"] = doc_metadata.get("source_uri", f"blob://{doc_id}")
                chunk["observed_date"] = doc_metadata.get("observed_date")
                chunk["kpi_tags"] = doc_metadata.get("kpi_tags", [])
            
            # Step 5: Re-embed
            logger.info(f"Step 5: Re-generating embeddings")
            chunks_with_embeddings = self.embedding_service.embed_chunks(chunks)
            
            # Step 6: Re-upload
            logger.info(f"Step 6: Re-uploading chunks to index")
            upload_result = self.search_index_service.upload_chunks(chunks_with_embeddings)
            
            # Step 7: Update Cosmos metadata
            logger.info(f"Step 7: Updating Cosmos metadata")
            doc_metadata["chunk_count"] = len(chunks)
            doc_metadata["indexed_chunk_count"] = upload_result["uploaded"]
            doc_metadata["reindexed_at"] = datetime.utcnow().isoformat()
            self.cosmos_service.update_document(doc_metadata)
            
            # Record event
            event = {
                "event_type": "document_reindexed",
                "doc_id": doc_id,
                "timestamp": datetime.utcnow().isoformat(),
                "details": {
                    "chunks_deleted": deleted_count,
                    "chunks_created": len(chunks),
                    "chunks_uploaded": upload_result["uploaded"]
                }
            }
            self.cosmos_service.create_event(event)
            
            logger.info(f"Successfully reindexed document {doc_id}")
            
            return {
                "doc_id": doc_id,
                "success": True,
                "chunks_deleted": deleted_count,
                "chunks_created": len(chunks),
                "chunks_uploaded": upload_result["uploaded"],
                "chunks_failed": upload_result["failed"]
            }
            
        except Exception as e:
            logger.error(f"Reindexing failed for document {doc_id}: {e}")
            raise
