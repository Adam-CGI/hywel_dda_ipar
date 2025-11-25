"""
Embedding service for generating vector embeddings using Azure OpenAI.
"""
import logging
from typing import List, Dict, Any
from openai import AzureOpenAI
from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_EMBED_DEPLOYMENT

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using Azure OpenAI."""
    
    # Azure OpenAI embedding API limits
    MAX_BATCH_SIZE = 512  # Maximum chunks per batch
    EMBEDDING_DIMENSION = 3072  # text-embedding-3-large dimension
    
    def __init__(self):
        """Initialize Azure OpenAI client."""
        if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
            raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be configured")
        
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version="2024-02-01"
        )
        self.deployment = AZURE_OPENAI_EMBED_DEPLOYMENT
        logger.info(f"Initialized EmbeddingService with deployment: {self.deployment}")
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        Automatically batches if necessary to respect API limits.
        
        Args:
            texts: List of text strings to embed (max 512 per batch)
            
        Returns:
            List of embedding vectors (3072-dim each)
        """
        if not texts:
            logger.warning("Empty texts list provided for embedding")
            return []
        
        # If batch is too large, split into smaller batches
        if len(texts) > self.MAX_BATCH_SIZE:
            logger.info(f"Splitting {len(texts)} texts into batches of {self.MAX_BATCH_SIZE}")
            all_embeddings = []
            
            for i in range(0, len(texts), self.MAX_BATCH_SIZE):
                batch = texts[i:i + self.MAX_BATCH_SIZE]
                batch_embeddings = self._embed_batch(batch)
                all_embeddings.extend(batch_embeddings)
            
            return all_embeddings
        else:
            return self._embed_batch(texts)
    
    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a single batch (≤512 texts).
        
        Args:
            texts: List of text strings (must be ≤512)
            
        Returns:
            List of embedding vectors
        """
        if len(texts) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Batch size {len(texts)} exceeds maximum {self.MAX_BATCH_SIZE}")
        
        try:
            logger.info(f"Generating embeddings for {len(texts)} texts using {self.deployment}")
            
            response = self.client.embeddings.create(
                input=texts,
                model=self.deployment
            )
            
            # Extract embeddings in order
            embeddings = [item.embedding for item in response.data]
            
            # Verify dimensions
            if embeddings and len(embeddings[0]) != self.EMBEDDING_DIMENSION:
                logger.warning(f"Unexpected embedding dimension: {len(embeddings[0])}, expected {self.EMBEDDING_DIMENSION}")
            
            logger.info(f"Successfully generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add embeddings to chunk objects.
        
        Args:
            chunks: List of chunk dictionaries with 'text' field
            
        Returns:
            List of chunks with 'vector' field added
        """
        if not chunks:
            logger.warning("Empty chunks list provided")
            return []
        
        # Extract texts
        texts = [chunk.get("text", "") for chunk in chunks]
        
        # Filter out empty texts
        non_empty_indices = [i for i, text in enumerate(texts) if text.strip()]
        non_empty_texts = [texts[i] for i in non_empty_indices]
        
        if not non_empty_texts:
            logger.warning("All chunks have empty text")
            return chunks
        
        logger.info(f"Embedding {len(non_empty_texts)} non-empty chunks")
        
        # Generate embeddings
        embeddings = self.embed_texts(non_empty_texts)
        
        # Add embeddings back to chunks
        embedding_idx = 0
        for i, chunk in enumerate(chunks):
            if i in non_empty_indices:
                chunk["vector"] = embeddings[embedding_idx]
                embedding_idx += 1
            else:
                # Empty text - use zero vector
                chunk["vector"] = [0.0] * self.EMBEDDING_DIMENSION
                logger.warning(f"Chunk {chunk.get('id')} has empty text, using zero vector")
        
        return chunks
    
    def verify_embedding_dimension(self, embedding: List[float]) -> bool:
        """
        Verify that an embedding has the correct dimension.
        
        Args:
            embedding: Vector to check
            
        Returns:
            bool: True if dimension matches expected
        """
        is_valid = len(embedding) == self.EMBEDDING_DIMENSION
        if not is_valid:
            logger.error(f"Invalid embedding dimension: {len(embedding)}, expected {self.EMBEDDING_DIMENSION}")
        return is_valid
    
    def batch_info(self, num_chunks: int) -> Dict[str, Any]:
        """
        Get information about batching for a given number of chunks.
        
        Args:
            num_chunks: Number of chunks to embed
            
        Returns:
            Dictionary with batch information
        """
        num_batches = (num_chunks + self.MAX_BATCH_SIZE - 1) // self.MAX_BATCH_SIZE
        return {
            "total_chunks": num_chunks,
            "max_batch_size": self.MAX_BATCH_SIZE,
            "num_batches": num_batches,
            "last_batch_size": num_chunks % self.MAX_BATCH_SIZE or self.MAX_BATCH_SIZE
        }
    
    def compute_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First embedding vector
            vec2: Second embedding vector
            
        Returns:
            float: Cosine similarity (0 to 1)
        """
        import math
        
        # Compute dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Compute magnitudes
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))
        
        # Avoid division by zero
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        # Cosine similarity
        return dot_product / (mag1 * mag2)
    
    def is_near_duplicate(self, vec1: List[float], vec2: List[float], threshold: float = 0.995) -> bool:
        """
        Check if two document embeddings are near-duplicates.
        
        Args:
            vec1: First document embedding
            vec2: Second document embedding
            threshold: Similarity threshold (default 0.995)
            
        Returns:
            bool: True if similarity > threshold
        """
        similarity = self.compute_cosine_similarity(vec1, vec2)
        logger.info(f"Document similarity: {similarity:.4f} (threshold: {threshold})")
        return similarity > threshold
    
    def embed_document(self, text: str) -> List[float]:
        """
        Generate a single document-level embedding.
        
        Args:
            text: Full document text (will be truncated if too long)
            
        Returns:
            List[float]: Document embedding vector
        """
        # Truncate very long text (keep first ~8000 chars for embedding)
        max_chars = 8000
        if len(text) > max_chars:
            logger.warning(f"Truncating document text from {len(text)} to {max_chars} chars")
            text = text[:max_chars]
        
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else [0.0] * self.EMBEDDING_DIMENSION
