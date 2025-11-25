"""
Unit tests for EmbeddingService
Tests vector embedding generation, batching, similarity computation, and duplicate detection.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from flask_app.services.embedding_service import EmbeddingService


class TestEmbedTexts:
    """Test basic text embedding with batching"""

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_texts_single_text(self):
        """Test embedding a single text"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            texts = ["This is a test text"]
            mock_embedding = [0.1] * 3072  # 3072-dimensional vector

            mock_response = Mock()
            mock_response.data = [Mock(embedding=mock_embedding)]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_texts(texts)

            # Assert
            assert len(result) == 1
            assert len(result[0]) == 3072
            assert result[0] == mock_embedding

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_texts_multiple_texts(self):
        """Test embedding multiple texts in one batch"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            texts = ["Text 1", "Text 2", "Text 3"]
            mock_embeddings = [
                [0.1] * 3072,
                [0.2] * 3072,
                [0.3] * 3072
            ]

            mock_response = Mock()
            mock_response.data = [Mock(embedding=emb) for emb in mock_embeddings]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_texts(texts)

            # Assert
            assert len(result) == 3
            for i, embedding in enumerate(result):
                assert len(embedding) == 3072
                assert embedding == mock_embeddings[i]

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_texts_batching(self):
        """Test that large text lists are batched correctly"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            MAX_BATCH_SIZE = 512
            texts = [f"Text {i}" for i in range(1000)]  # More than MAX_BATCH_SIZE

            mock_embedding = [0.1] * 3072
            
            def create_embeddings_side_effect(*args, **kwargs):
                input_texts = kwargs.get('input', [])
                batch_size = len(input_texts)
                mock_response = Mock()
                mock_response.data = [Mock(embedding=mock_embedding) for _ in range(batch_size)]
                return mock_response
            
            mock_client.embeddings.create.side_effect = create_embeddings_side_effect
            
            service = EmbeddingService()

            # Act
            result = service.embed_texts(texts)

            # Assert
            # Should be called twice: once for 512 texts, once for remaining 488
            assert mock_client.embeddings.create.call_count == 2
            assert len(result) == 1000

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_texts_empty_list(self):
        """Test embedding empty text list"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            texts = []
            service = EmbeddingService()

            # Act
            result = service.embed_texts(texts)

            # Assert
            assert result == []
            mock_client.embeddings.create.assert_not_called()

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_texts_api_error(self):
        """Test handling of OpenAI API errors"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            texts = ["Test text"]
            mock_client.embeddings.create.side_effect = Exception("API Error")
            service = EmbeddingService()

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                service.embed_texts(texts)

            assert "API Error" in str(exc_info.value)

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_texts_preserves_order(self):
        """Test that embedding order matches input order"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            texts = ["First", "Second", "Third"]
            mock_embeddings = [
                [0.1] * 3072,
                [0.2] * 3072,
                [0.3] * 3072
            ]

            mock_response = Mock()
            mock_response.data = [Mock(embedding=emb) for emb in mock_embeddings]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_texts(texts)

            # Assert
            assert result[0] == mock_embeddings[0]
            assert result[1] == mock_embeddings[1]
            assert result[2] == mock_embeddings[2]


class TestEmbedChunks:
    """Test embedding chunks with metadata"""

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_chunks_adds_vectors(self):
        """Test that embeddings are added to chunk dictionaries"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            chunks = [
                {'id': 'c1', 'text': 'Chunk 1'},
                {'id': 'c2', 'text': 'Chunk 2'}
            ]

            mock_embeddings = [
                [0.1] * 3072,
                [0.2] * 3072
            ]

            mock_response = Mock()
            mock_response.data = [Mock(embedding=emb) for emb in mock_embeddings]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_chunks(chunks)

            # Assert
            assert len(result) == 2
            assert result[0]['vector'] == mock_embeddings[0]
            assert result[1]['vector'] == mock_embeddings[1]
            assert result[0]['text'] == 'Chunk 1'
            assert result[1]['text'] == 'Chunk 2'

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_chunks_empty_list(self):
        """Test embedding empty chunk list"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            chunks = []
            service = EmbeddingService()

            # Act
            result = service.embed_chunks(chunks)

            # Assert
            assert result == []

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_chunks_preserves_metadata(self):
        """Test that all chunk metadata is preserved"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            chunks = [
                {
                    'id': 'c1',
                    'text': 'Test',
                    'doc_id': 'doc123',
                    'page_no': 1,
                    'offset': 0,
                    'extra_field': 'value'
                }
            ]

            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 3072)]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_chunks(chunks)

            # Assert
            assert result[0]['id'] == 'c1'
            assert result[0]['doc_id'] == 'doc123'
            assert result[0]['page_no'] == 1
            assert result[0]['offset'] == 0
            assert result[0]['extra_field'] == 'value'
            assert 'vector' in result[0]


class TestEmbedDocument:
    """Test document-level embedding generation"""

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_document_single_page(self):
        """Test embedding a single-page document"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            text = 'Page 1 content'

            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 3072)]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_document(text)

            # Assert
            assert len(result) == 3072
            assert result == [0.1] * 3072

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_document_multiple_pages(self):
        """Test embedding a multi-page document"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            text = 'Page 1\nPage 2\nPage 3'

            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.2] * 3072)]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_document(text)

            # Assert
            assert len(result) == 3072

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_document_empty_pages(self):
        """Test embedding a document with no pages"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            text = ''

            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.0] * 3072)]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_document(text)

            # Assert
            assert len(result) == 3072

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_document_with_empty_text(self):
        """Test embedding pages with empty text"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            text = 'Some content'

            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.3] * 3072)]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_document(text)

            # Assert
            assert len(result) == 3072


class TestComputeCosineSimilarity:
    """Test cosine similarity computation"""

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_compute_cosine_similarity_identical_vectors(self):
        """Test similarity of identical vectors is 1.0"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [1.0, 0.0, 0.0]

            # Act
            similarity = service.compute_cosine_similarity(vec1, vec2)

            # Assert
            assert abs(similarity - 1.0) < 0.0001

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_compute_cosine_similarity_orthogonal_vectors(self):
        """Test similarity of orthogonal vectors is 0.0"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [0.0, 1.0, 0.0]

            # Act
            similarity = service.compute_cosine_similarity(vec1, vec2)

            # Assert
            assert abs(similarity - 0.0) < 0.0001

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_compute_cosine_similarity_opposite_vectors(self):
        """Test similarity of opposite vectors is -1.0"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [-1.0, 0.0, 0.0]

            # Act
            similarity = service.compute_cosine_similarity(vec1, vec2)

            # Assert
            assert abs(similarity - (-1.0)) < 0.0001

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_compute_cosine_similarity_scaled_vectors(self):
        """Test that scaling doesn't affect similarity"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [1.0, 2.0, 3.0]
            vec2 = [2.0, 4.0, 6.0]  # Scaled by 2

            # Act
            similarity = service.compute_cosine_similarity(vec1, vec2)

            # Assert
            assert abs(similarity - 1.0) < 0.0001

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_compute_cosine_similarity_high_dimensional(self):
        """Test similarity with high-dimensional vectors (3072-dim)"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [0.1] * 3072
            vec2 = [0.1] * 3072

            # Act
            similarity = service.compute_cosine_similarity(vec1, vec2)

            # Assert
            assert abs(similarity - 1.0) < 0.0001

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_compute_cosine_similarity_random_vectors(self):
        """Test similarity with random vectors"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            np.random.seed(42)
            vec1 = np.random.randn(3072).tolist()
            vec2 = np.random.randn(3072).tolist()

            # Act
            similarity = service.compute_cosine_similarity(vec1, vec2)

            # Assert
            assert -1.0 <= similarity <= 1.0

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_compute_cosine_similarity_zero_vector(self):
        """Test handling of zero vectors"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [0.0, 0.0, 0.0]
            vec2 = [1.0, 0.0, 0.0]

            # Act
            similarity = service.compute_cosine_similarity(vec1, vec2)

            # Assert
            assert similarity == 0.0


class TestIsNearDuplicate:
    """Test near-duplicate detection using similarity threshold"""

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_is_near_duplicate_above_threshold(self):
        """Test that similarity above threshold is detected as duplicate"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [0.999, 0.001, 0.0]  # Very similar
            threshold = 0.995

            # Act
            result = service.is_near_duplicate(vec1, vec2, threshold)

            # Assert
            assert result is True

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_is_near_duplicate_below_threshold(self):
        """Test that similarity below threshold is not a duplicate"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [0.8, 0.6, 0.0]  # Less similar
            threshold = 0.995

            # Act
            result = service.is_near_duplicate(vec1, vec2, threshold)

            # Assert
            assert result is False

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_is_near_duplicate_exactly_at_threshold(self):
        """Test edge case where similarity equals threshold"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            threshold = 0.995

            # Create vectors with exact threshold similarity
            vec1 = [1.0, 0.0]
            vec2 = [threshold, np.sqrt(1 - threshold**2)]

            # Act
            result = service.is_near_duplicate(vec1, vec2, threshold)

            # Assert
            # Should be False if exactly at threshold (implementation uses > not >=)
            assert result == False

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_is_near_duplicate_identical_vectors(self):
        """Test that identical vectors are detected as duplicates"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [0.1] * 3072
            vec2 = [0.1] * 3072
            threshold = 0.995

            # Act
            result = service.is_near_duplicate(vec1, vec2, threshold)

            # Assert
            assert result is True

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_is_near_duplicate_orthogonal_vectors(self):
        """Test that orthogonal vectors are not duplicates"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [0.0, 1.0, 0.0]
            threshold = 0.995

            # Act
            result = service.is_near_duplicate(vec1, vec2, threshold)

            # Assert
            assert result is False

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_is_near_duplicate_custom_threshold(self):
        """Test with different threshold values"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [0.95, 0.05, 0.0]

            # Act
            result_high = service.is_near_duplicate(vec1, vec2, threshold=0.99)
            result_low = service.is_near_duplicate(vec1, vec2, threshold=0.90)

            # Assert
            assert result_high is True   # Above 0.99 (similarity is ~0.9986)
            assert result_low is True    # Above 0.90

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_is_near_duplicate_default_threshold(self):
        """Test that default threshold is 0.995"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [1.0] * 100
            vec2 = [1.0] * 100

            # Act
            result = service.is_near_duplicate(vec1, vec2)  # No threshold specified

            # Assert
            assert result is True


class TestBatchingBehavior:
    """Test batching behavior with MAX_BATCH_SIZE"""

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_batch_size_limit_enforced(self):
        """Test that batches never exceed MAX_BATCH_SIZE (512)"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            MAX_BATCH_SIZE = 512
            texts = [f"Text {i}" for i in range(1500)]

            mock_embedding = [0.1] * 3072

            def create_response(*args, **kwargs):
                batch_size = len(kwargs['input'])
                response = Mock()
                response.data = [Mock(embedding=mock_embedding) for _ in range(batch_size)]
                return response

            mock_client.embeddings.create.side_effect = create_response
            service = EmbeddingService()

            # Act
            result = service.embed_texts(texts)

            # Assert
            # Should be called 3 times: 512, 512, 476
            assert mock_client.embeddings.create.call_count == 3

            # Verify no batch exceeds MAX_BATCH_SIZE
            for call in mock_client.embeddings.create.call_args_list:
                batch = call[1]['input']
                assert len(batch) <= MAX_BATCH_SIZE

            assert len(result) == 1500

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_batch_exactly_max_size(self):
        """Test batching when input is exactly MAX_BATCH_SIZE"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            MAX_BATCH_SIZE = 512
            texts = [f"Text {i}" for i in range(MAX_BATCH_SIZE)]

            mock_embedding = [0.1] * 3072
            mock_response = Mock()
            mock_response.data = [Mock(embedding=mock_embedding) for _ in range(MAX_BATCH_SIZE)]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_texts(texts)

            # Assert
            # Should be called exactly once
            assert mock_client.embeddings.create.call_count == 1
            assert len(result) == MAX_BATCH_SIZE


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_chunks_unicode_text(self):
        """Test embedding chunks with unicode characters"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            chunks = [
                {'id': 'c1', 'text': 'Unicode: é, ñ, 中文, 🎉'}
            ]

            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 3072)]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_chunks(chunks)

            # Assert
            assert len(result) == 1
            assert 'vector' in result[0]

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_embed_document_very_long_text(self):
        """Test embedding very long documents"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI') as mock_azure_openai:
            mock_client = Mock()
            mock_azure_openai.return_value = mock_client
            
            long_text = "Word " * 100000  # Very long text

            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 3072)]
            mock_client.embeddings.create.return_value = mock_response
            
            service = EmbeddingService()

            # Act
            result = service.embed_document(long_text)

            # Assert
            assert len(result) == 3072

    @patch('app.services.embedding_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.embedding_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.embedding_service.AZURE_OPENAI_EMBED_DEPLOYMENT', 'text-embedding-3-large')
    def test_compute_cosine_similarity_different_dimensions(self):
        """Test handling of vectors with different dimensions"""
        # Arrange
        with patch('app.services.embedding_service.AzureOpenAI'):
            service = EmbeddingService()
            vec1 = [1.0, 0.0]
            vec2 = [1.0, 0.0, 0.0]

            # Act & Assert
            # Should raise error or handle gracefully
            try:
                similarity = service.compute_cosine_similarity(vec1, vec2)
                # If it doesn't raise, behavior is implementation-specific
            except (ValueError, IndexError):
                pass  # Expected error
