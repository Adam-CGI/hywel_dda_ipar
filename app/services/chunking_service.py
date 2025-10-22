"""
Chunking service for splitting extracted text into deterministic, traceable chunks.
Uses llama-index for chunking configuration.
"""
import logging
import hashlib
from typing import List, Dict, Any, Optional
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for chunking extracted document text."""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 128):
        """
        Initialize chunking service with llama-index sentence splitter.
        
        Args:
            chunk_size: Maximum size of each chunk in tokens (default 512)
            chunk_overlap: Overlap between chunks in tokens (default 128)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separator=" ",
            paragraph_separator="\n\n"
        )
        logger.info(f"Initialized ChunkingService with chunk_size={chunk_size}, overlap={chunk_overlap}")
    
    def _generate_chunk_id(self, doc_id: str, page_no: int, start_offset: int, text: str) -> str:
        """
        Generate deterministic chunk ID.
        
        Args:
            doc_id: Document identifier
            page_no: Page number (1-based)
            start_offset: Character offset in page text
            text: Chunk text (first 256 chars used for hash)
            
        Returns:
            str: SHA256 hash as chunk ID
        """
        # Use doc_id, page_no, start_offset, and first 256 chars of text
        hash_input = f"{doc_id}|{page_no}|{start_offset}|{text[:256]}"
        chunk_id = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        return chunk_id
    
    def chunk_page(self, doc_id: str, page_no: int, page_text: str, page_metadata: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """
        Chunk a single page of text.
        
        Args:
            doc_id: Document identifier
            page_no: Page number (1-based)
            page_text: Full text content of the page
            page_metadata: Optional metadata about the page (dimensions, etc.)
            
        Returns:
            List of chunk dictionaries with id, text, spans, and metadata
        """
        if not page_text or not page_text.strip():
            logger.warning(f"Empty text for doc {doc_id}, page {page_no}")
            return []
        
        chunks = []
        
        # Create llama-index Document for this page
        doc = Document(
            text=page_text,
            metadata={
                "doc_id": doc_id,
                "page_no": page_no,
                **(page_metadata or {})
            }
        )
        
        # Split into nodes (chunks)
        nodes = self.splitter.get_nodes_from_documents([doc])
        
        for node in nodes:
            # Calculate character offset in original page text
            # llama-index doesn't provide exact char offset, so we search for the chunk text
            chunk_text = node.get_content()
            start_offset = page_text.find(chunk_text)
            
            if start_offset == -1:
                # If exact match not found (shouldn't happen but defensive)
                start_offset = 0
                logger.warning(f"Could not find chunk text in page {page_no} for doc {doc_id}")
            
            end_offset = start_offset + len(chunk_text)
            
            # Generate deterministic chunk ID
            chunk_id = self._generate_chunk_id(doc_id, page_no, start_offset, chunk_text)
            
            chunk = {
                "id": chunk_id,
                "doc_id": doc_id,
                "page_no": page_no,
                "text": chunk_text,
                "spans": [{
                    "start": start_offset,
                    "end": end_offset,
                    "page_no": page_no
                }],
                "metadata": {
                    "chunk_size": len(chunk_text),
                    **(page_metadata or {})
                }
            }
            
            chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} chunks for doc {doc_id}, page {page_no}")
        return chunks
    
    def chunk_document(self, doc_id: str, extraction_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk entire document from extraction data.
        
        Args:
            doc_id: Document identifier
            extraction_data: Output from ExtractionService with pages array
            
        Returns:
            List of all chunks across all pages
        """
        all_chunks = []
        pages = extraction_data.get("pages", [])
        
        if not pages:
            logger.warning(f"No pages found in extraction data for doc {doc_id}")
            return []
        
        for page_data in pages:
            page_no = page_data.get("page_no")
            page_text = page_data.get("text", "")
            
            # Extract metadata for this page
            page_metadata = {
                "page_width": page_data.get("width"),
                "page_height": page_data.get("height"),
                "page_unit": page_data.get("unit")
            }
            
            # Chunk this page
            page_chunks = self.chunk_page(doc_id, page_no, page_text, page_metadata)
            all_chunks.extend(page_chunks)
        
        logger.info(f"Created total of {len(all_chunks)} chunks for document {doc_id}")
        return all_chunks
    
    def verify_chunk_determinism(self, doc_id: str, page_no: int, page_text: str, iterations: int = 3) -> bool:
        """
        Verify that chunking is deterministic by running multiple times.
        
        Args:
            doc_id: Document identifier
            page_no: Page number
            page_text: Page text
            iterations: Number of times to run chunking (default 3)
            
        Returns:
            bool: True if all runs produce identical chunk IDs
        """
        chunk_id_sets = []
        
        for i in range(iterations):
            chunks = self.chunk_page(doc_id, page_no, page_text)
            chunk_ids = [c["id"] for c in chunks]
            chunk_id_sets.append(chunk_ids)
        
        # Check all sets are identical
        first_set = chunk_id_sets[0]
        all_identical = all(chunk_ids == first_set for chunk_ids in chunk_id_sets)
        
        if all_identical:
            logger.info(f"Chunking is deterministic for doc {doc_id}, page {page_no}")
        else:
            logger.error(f"Chunking is NOT deterministic for doc {doc_id}, page {page_no}")
        
        return all_identical
