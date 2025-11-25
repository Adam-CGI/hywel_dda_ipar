"""
Unit tests for ChatService
Tests RAG-powered chat functionality, prompt engineering, and citation generation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from flask_app.services.chat_service import ChatService


class TestChatService:
    """Test ChatService initialization and configuration"""

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('app.services.chat_service.AZURE_OPENAI_CHAT_DEPLOYMENT', 'gpt-4o-mini')
    def test_chat_service_initialization(self):
        """Test ChatService initializes with correct configuration"""
        # Arrange & Act
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService'):
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                service = ChatService()
                
                # Assert
                assert service.deployment == 'gpt-4o-mini'
                mock_azure_openai.assert_called_once()

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', '')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', '')
    def test_chat_service_missing_config(self):
        """Test ChatService raises error with missing configuration"""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            ChatService()
        
        assert "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be configured" in str(exc_info.value)


class TestFormatSourcesForPrompt:
    """Test source formatting for RAG prompts"""

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_format_sources_for_prompt_success(self):
        """Test successful source formatting"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI'):
            with patch('app.services.chat_service.SearchService'):
                service = ChatService()
                
                search_results = [
                    {
                        'title': 'Test Document 1',
                        'page_no': 1,
                        'score': 0.95,
                        'text': 'This is the first test document content.',
                        'kpi_tags': ['performance', 'quality']
                    },
                    {
                        'title': 'Test Document 2',
                        'page_no': 2,
                        'score': 0.87,
                        'text': 'This is the second test document content.',
                        'kpi_tags': []
                    }
                ]
                
                # Act
                result = service._format_sources_for_prompt(search_results)
                
                # Assert
                assert "[SOURCE DOCUMENTS]" in result
                assert "[Doc 1]" in result
                assert "[Doc 2]" in result
                assert "Test Document 1" in result
                assert "Test Document 2" in result
                assert "Page: 1" in result
                assert "Page: 2" in result
                assert "Relevance Score: 0.95" in result
                assert "Relevance Score: 0.87" in result
                assert "KPI Tags: performance, quality" in result

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_format_sources_for_prompt_empty(self):
        """Test source formatting with empty results"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI'):
            with patch('app.services.chat_service.SearchService'):
                service = ChatService()
                
                # Act
                result = service._format_sources_for_prompt([])
                
                # Assert
                assert "[SOURCE DOCUMENTS]" in result
                assert "No relevant documents found." in result


class TestBuildMessages:
    """Test message building for chat completion"""

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_build_messages_basic(self):
        """Test basic message building"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI'):
            with patch('app.services.chat_service.SearchService'):
                service = ChatService()
                
                user_query = "What are the key performance indicators?"
                sources = "[SOURCE DOCUMENTS]\n[Doc 1]\nTitle: Test\nContent: KPI data"
                
                # Act
                messages = service._build_messages(user_query, sources)
                
                # Assert
                assert len(messages) >= 3  # System + few-shot + user
                assert messages[0]['role'] == 'system'
                assert service.SYSTEM_PROMPT in messages[0]['content']
                assert messages[-1]['role'] == 'user'
                assert user_query in messages[-1]['content']
                assert sources in messages[-1]['content']

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_build_messages_with_history(self):
        """Test message building with conversation history"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI'):
            with patch('app.services.chat_service.SearchService'):
                service = ChatService()
                
                user_query = "Follow-up question"
                sources = "[SOURCE DOCUMENTS]\nTest sources"
                conversation_history = [
                    {"role": "user", "content": "Previous question"},
                    {"role": "assistant", "content": "Previous answer"}
                ]
                
                # Act
                messages = service._build_messages(user_query, sources, conversation_history)
                
                # Assert
                # Should include system + few-shot + history + current
                assert len(messages) >= 5
                assert any(msg['content'] == "Previous question" for msg in messages)
                assert any(msg['content'] == "Previous answer" for msg in messages)


class TestChat:
    """Test main chat functionality"""

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_chat_success(self):
        """Test successful chat completion"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService') as mock_search_service_class:
                
                # Mock OpenAI client
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                # Mock search service
                mock_search_service = Mock()
                mock_search_service.search.return_value = {
                    'results': [
                        {
                            'title': 'Test Document',
                            'page_no': 1,
                            'score': 0.95,
                            'text': 'Test content about KPIs',
                            'kpi_tags': ['performance']
                        }
                    ]
                }
                mock_search_service_class.return_value = mock_search_service
                
                # Mock OpenAI completion
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[0].message.content = "Based on the documents, the key performance indicators include..."
                mock_completion.choices[0].finish_reason = "stop"
                mock_completion.usage.prompt_tokens = 150
                mock_completion.usage.completion_tokens = 50
                mock_completion.usage.total_tokens = 200
                
                mock_client.chat.completions.create.return_value = mock_completion
                
                service = ChatService()
                
                # Act
                result = service.chat("What are the key performance indicators?")
                
                # Assert
                assert result['response'] == "Based on the documents, the key performance indicators include..."
                assert result['query'] == "What are the key performance indicators?"
                assert len(result['sources']) == 1
                assert result['usage']['total_tokens'] == 200
                assert result['model'] == 'gpt-4o-mini'
                assert result['finish_reason'] == 'stop'
                
                # Verify search was called
                mock_search_service.search.assert_called_once()
                
                # Verify OpenAI was called
                mock_client.chat.completions.create.assert_called_once()

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_chat_with_conversation_history(self):
        """Test chat with conversation history"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService') as mock_search_service_class:
                
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                mock_search_service = Mock()
                mock_search_service.search.return_value = {'results': []}
                mock_search_service_class.return_value = mock_search_service
                
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[0].message.content = "Follow-up response"
                mock_completion.choices[0].finish_reason = "stop"
                mock_completion.usage.prompt_tokens = 200
                mock_completion.usage.completion_tokens = 30
                mock_completion.usage.total_tokens = 230
                
                mock_client.chat.completions.create.return_value = mock_completion
                
                service = ChatService()
                
                conversation_history = [
                    {"role": "user", "content": "Previous question"},
                    {"role": "assistant", "content": "Previous answer"}
                ]
                
                # Act
                result = service.chat("Follow-up question", conversation_history=conversation_history)
                
                # Assert
                assert result['response'] == "Follow-up response"
                
                # Verify conversation history was included in the call
                call_args = mock_client.chat.completions.create.call_args
                messages = call_args[1]['messages']
                assert any("Previous question" in str(msg) for msg in messages)
                assert any("Previous answer" in str(msg) for msg in messages)

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_chat_custom_parameters(self):
        """Test chat with custom parameters"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService') as mock_search_service_class:
                
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                mock_search_service = Mock()
                mock_search_service.search.return_value = {'results': []}
                mock_search_service_class.return_value = mock_search_service
                
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[0].message.content = "Custom response"
                mock_completion.choices[0].finish_reason = "stop"
                mock_completion.usage.prompt_tokens = 100
                mock_completion.usage.completion_tokens = 25
                mock_completion.usage.total_tokens = 125
                
                mock_client.chat.completions.create.return_value = mock_completion
                
                service = ChatService()
                
                # Act
                result = service.chat(
                    "Test query",
                    top_k=10,
                    temperature=0.7,
                    max_tokens=500
                )
                
                # Assert
                assert result['response'] == "Custom response"
                
                # Verify custom parameters were used
                search_call_args = mock_search_service.search.call_args
                assert search_call_args[1]['top'] == 10
                
                openai_call_args = mock_client.chat.completions.create.call_args
                assert openai_call_args[1]['temperature'] == 0.7
                assert openai_call_args[1]['max_tokens'] == 500

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_chat_error_handling(self):
        """Test chat error handling"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService') as mock_search_service_class:
                
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                mock_search_service = Mock()
                mock_search_service.search.return_value = {'results': []}
                mock_search_service_class.return_value = mock_search_service
                
                mock_client.chat.completions.create.side_effect = Exception("OpenAI API error")
                
                service = ChatService()
                
                # Act & Assert
                with pytest.raises(Exception) as exc_info:
                    service.chat("Test query")
                
                assert "OpenAI API error" in str(exc_info.value)


class TestStreamChat:
    """Test streaming chat functionality"""

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_stream_chat_success(self):
        """Test successful streaming chat"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService') as mock_search_service_class:
                
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                mock_search_service = Mock()
                mock_search_service.search.return_value = {
                    'results': [{'title': 'Test Doc', 'text': 'Test content'}]
                }
                mock_search_service_class.return_value = mock_search_service
                
                # Mock streaming response
                mock_chunk1 = Mock()
                mock_chunk1.choices = [Mock()]
                mock_chunk1.choices[0].delta.content = "This is "
                
                mock_chunk2 = Mock()
                mock_chunk2.choices = [Mock()]
                mock_chunk2.choices[0].delta.content = "a streaming response."
                
                mock_chunk3 = Mock()
                mock_chunk3.choices = [Mock()]
                mock_chunk3.choices[0].delta.content = None  # End of stream
                
                mock_client.chat.completions.create.return_value = [mock_chunk1, mock_chunk2, mock_chunk3]
                
                service = ChatService()
                
                # Act
                chunks = list(service.stream_chat("Test query"))
                
                # Assert
                content_chunks = [chunk for chunk in chunks if chunk['type'] == 'content']
                sources_chunks = [chunk for chunk in chunks if chunk['type'] == 'sources']
                
                assert len(content_chunks) == 2
                assert content_chunks[0]['content'] == "This is "
                assert content_chunks[1]['content'] == "a streaming response."
                
                assert len(sources_chunks) == 1
                assert len(sources_chunks[0]['sources']) == 1

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_stream_chat_error_handling(self):
        """Test streaming chat error handling"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService') as mock_search_service_class:
                
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                mock_search_service = Mock()
                mock_search_service.search.return_value = {'results': []}
                mock_search_service_class.return_value = mock_search_service
                
                mock_client.chat.completions.create.side_effect = Exception("Streaming error")
                
                service = ChatService()
                
                # Act
                chunks = list(service.stream_chat("Test query"))
                
                # Assert
                error_chunks = [chunk for chunk in chunks if chunk['type'] == 'error']
                assert len(error_chunks) == 1
                assert "Streaming error" in error_chunks[0]['error']


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_chat_with_unicode_query(self):
        """Test chat with unicode characters in query"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService') as mock_search_service_class:
                
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                mock_search_service = Mock()
                mock_search_service.search.return_value = {'results': []}
                mock_search_service_class.return_value = mock_search_service
                
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[0].message.content = "Unicode response: 测试回答"
                mock_completion.choices[0].finish_reason = "stop"
                mock_completion.usage.prompt_tokens = 50
                mock_completion.usage.completion_tokens = 20
                mock_completion.usage.total_tokens = 70
                
                mock_client.chat.completions.create.return_value = mock_completion
                
                service = ChatService()
                
                # Act
                result = service.chat("Unicode query: 测试查询 with émojis 🤖")
                
                # Assert
                assert result['query'] == "Unicode query: 测试查询 with émojis 🤖"
                assert result['response'] == "Unicode response: 测试回答"

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_chat_with_no_sources(self):
        """Test chat when no relevant sources are found"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService') as mock_search_service_class:
                
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                mock_search_service = Mock()
                mock_search_service.search.return_value = {'results': []}  # No sources
                mock_search_service_class.return_value = mock_search_service
                
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[0].message.content = "I don't have information about that in the available documents"
                mock_completion.choices[0].finish_reason = "stop"
                mock_completion.usage.prompt_tokens = 100
                mock_completion.usage.completion_tokens = 15
                mock_completion.usage.total_tokens = 115
                
                mock_client.chat.completions.create.return_value = mock_completion
                
                service = ChatService()
                
                # Act
                result = service.chat("Query with no relevant sources")
                
                # Assert
                assert result['sources'] == []
                assert "don't have information" in result['response']

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_chat_with_very_long_query(self):
        """Test chat with very long query"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService') as mock_search_service_class:
                
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                mock_search_service = Mock()
                mock_search_service.search.return_value = {'results': []}
                mock_search_service_class.return_value = mock_search_service
                
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[0].message.content = "Response to long query"
                mock_completion.choices[0].finish_reason = "stop"
                mock_completion.usage.prompt_tokens = 500
                mock_completion.usage.completion_tokens = 20
                mock_completion.usage.total_tokens = 520
                
                mock_client.chat.completions.create.return_value = mock_completion
                
                service = ChatService()
                
                # Very long query
                long_query = "This is a very long query that contains many words and details. " * 50
                
                # Act
                result = service.chat(long_query)
                
                # Assert
                assert result['query'] == long_query
                assert result['response'] == "Response to long query"
                assert result['usage']['total_tokens'] == 520

    @patch('app.services.chat_service.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    @patch('app.services.chat_service.AZURE_OPENAI_API_KEY', 'test-key')
    def test_chat_with_search_error(self):
        """Test chat when search service fails"""
        # Arrange
        with patch('app.services.chat_service.AzureOpenAI') as mock_azure_openai:
            with patch('app.services.chat_service.SearchService') as mock_search_service_class:
                
                mock_client = Mock()
                mock_azure_openai.return_value = mock_client
                
                mock_search_service = Mock()
                mock_search_service.search.side_effect = Exception("Search service error")
                mock_search_service_class.return_value = mock_search_service
                
                service = ChatService()
                
                # Act & Assert
                with pytest.raises(Exception) as exc_info:
                    service.chat("Test query")
                
                assert "Search service error" in str(exc_info.value)