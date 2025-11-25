"""
Integration tests for RAG (Retrieval Augmented Generation) chat functionality
Tests chat service integration with search service and OpenAI API.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from flask_app.services.chat_service import ChatService


class TestRAGChatIntegration:
    """Integration tests for RAG-powered chat functionality"""

    def test_rag_chat_workflow_integration(
        self,
        mock_openai_client,
        mock_search_service,
        sample_search_results
    ):
        """Test complete RAG workflow: query → search → prompt → generate → response"""
        # Arrange
        user_query = "What are the key performance indicators?"
        
        # Mock search service to return relevant documents
        mock_search_service.search.return_value = {
            'query': user_query,
            'count': 2,
            'results': sample_search_results[:2]  # Use first 2 results
        }
        
        # Mock OpenAI completion response
        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = "Based on the available documents, the key performance indicators include emergency department waiting times [Doc 1] and cancer treatment pathways [Doc 2]."
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.prompt_tokens = 150
        mock_completion.usage.completion_tokens = 50
        mock_completion.usage.total_tokens = 200
        
        mock_openai_client.chat.completions.create.return_value = mock_completion

        # Create chat service with mocked dependencies
        chat_service = ChatService()
        chat_service.client = mock_openai_client
        chat_service.search_service = mock_search_service

        # Act
        result = chat_service.chat(
            query=user_query,
            conversation_history=None,
            top_k=5,
            temperature=0.3,
            max_tokens=1000
        )

        # Assert - verify RAG workflow
        # 1. Search was performed to retrieve relevant documents
        mock_search_service.search.assert_called_once_with(
            query=user_query,
            top=5,
            filter_expr=None,
            include_thumbnails=True
        )
        
        # 2. OpenAI completion was called with properly formatted prompt
        openai_call = mock_openai_client.chat.completions.create.call_args
        messages = openai_call[1]['messages']
        
        # Should include system prompt, few-shot examples, and user query with sources
        assert len(messages) >= 3  # System + examples + user query
        assert messages[0]['role'] == 'system'
        assert any('[SOURCE DOCUMENTS]' in msg['content'] for msg in messages if msg['role'] == 'user')
        
        # 3. Response structure is correct
        assert result['response'] == mock_completion.choices[0].message.content
        assert result['sources'] == sample_search_results[:2]
        assert result['usage']['total_tokens'] == 200
        assert result['model'] == chat_service.deployment
        assert result['finish_reason'] == 'stop'
        assert result['query'] == user_query

    def test_chat_with_conversation_history(
        self,
        mock_openai_client,
        mock_search_service,
        sample_search_results
    ):
        """Test chat with multi-turn conversation history"""
        # Arrange
        current_query = "Can you provide more details about the first indicator?"
        conversation_history = [
            {"role": "user", "content": "What are the key performance indicators?"},
            {"role": "assistant", "content": "The key indicators include emergency department waiting times and cancer treatment pathways."}
        ]
        
        mock_search_service.search.return_value = {
            'query': current_query,
            'count': 1,
            'results': sample_search_results[:1]
        }
        
        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = "Emergency department waiting times target 95% of patients seen within 4 hours [Doc 1]."
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.prompt_tokens = 200
        mock_completion.usage.completion_tokens = 30
        mock_completion.usage.total_tokens = 230
        
        mock_openai_client.chat.completions.create.return_value = mock_completion

        # Create chat service
        chat_service = ChatService()
        chat_service.client = mock_openai_client
        chat_service.search_service = mock_search_service

        # Act
        result = chat_service.chat(
            query=current_query,
            conversation_history=conversation_history,
            top_k=3,
            temperature=0.2
        )

        # Assert - verify conversation history integration
        openai_call = mock_openai_client.chat.completions.create.call_args
        messages = openai_call[1]['messages']
        
        # Should include conversation history between examples and current query
        history_messages = [msg for msg in messages if msg['role'] in ['user', 'assistant'] and '[SOURCE DOCUMENTS]' not in msg['content']]
        assert len(history_messages) >= 2  # Previous user and assistant messages
        
        # Verify temperature and other parameters
        assert openai_call[1]['temperature'] == 0.2
        assert openai_call[1]['max_tokens'] == 1000  # Default value

    def test_chat_source_formatting_and_grounding(
        self,
        mock_openai_client,
        mock_search_service
    ):
        """Test proper source formatting for grounding in RAG prompt"""
        # Arrange
        query = "Test source formatting"
        
        # Mock search results with rich metadata
        mock_sources = [
            {
                'chunk_id': 'chunk1',
                'doc_id': 'doc1',
                'title': 'Performance Report Q1',
                'page_no': 3,
                'text': 'Emergency department performance shows 92% of patients seen within 4 hours.',
                'score': 0.95,
                'kpi_tags': ['emergency', 'performance'],
                'thumb_url': 'https://example.com/thumb1.png'
            },
            {
                'chunk_id': 'chunk2',
                'doc_id': 'doc2', 
                'title': 'Quality Metrics Dashboard',
                'page_no': 1,
                'text': 'Cancer treatment pathways achieved 78% compliance with 62-day target.',
                'score': 0.88,
                'kpi_tags': ['cancer', 'treatment'],
                'thumb_url': 'https://example.com/thumb2.png'
            }
        ]
        
        mock_search_service.search.return_value = {
            'query': query,
            'count': 2,
            'results': mock_sources
        }
        
        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = "Test response"
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.prompt_tokens = 100
        mock_completion.usage.completion_tokens = 20
        mock_completion.usage.total_tokens = 120
        
        mock_openai_client.chat.completions.create.return_value = mock_completion

        # Create chat service
        chat_service = ChatService()
        chat_service.client = mock_openai_client
        chat_service.search_service = mock_search_service

        # Act
        result = chat_service.chat(query=query, top_k=2)

        # Assert - verify source formatting in prompt
        openai_call = mock_openai_client.chat.completions.create.call_args
        messages = openai_call[1]['messages']
        
        # Find the user message with sources
        user_message_with_sources = None
        for msg in messages:
            if msg['role'] == 'user' and '[SOURCE DOCUMENTS]' in msg['content']:
                user_message_with_sources = msg['content']
                break
        
        assert user_message_with_sources is not None
        
        # Verify source formatting includes all required fields
        assert '[SOURCE DOCUMENTS]' in user_message_with_sources
        assert '[Doc 1]' in user_message_with_sources
        assert '[Doc 2]' in user_message_with_sources
        assert 'Performance Report Q1' in user_message_with_sources
        assert 'Quality Metrics Dashboard' in user_message_with_sources
        assert 'Page: 3' in user_message_with_sources
        assert 'Page: 1' in user_message_with_sources
        assert 'Relevance Score: 0.95' in user_message_with_sources
        assert 'Relevance Score: 0.88' in user_message_with_sources
        assert 'KPI Tags: emergency, performance' in user_message_with_sources
        assert 'KPI Tags: cancer, treatment' in user_message_with_sources
        assert '[USER QUERY]' in user_message_with_sources
        assert query in user_message_with_sources

    def test_chat_error_handling_and_fallbacks(
        self,
        mock_openai_client,
        mock_search_service
    ):
        """Test chat error handling when services fail"""
        # Arrange
        query = "Test error handling"
        
        # Mock search service failure
        mock_search_service.search.side_effect = Exception("Search service unavailable")

        # Create chat service
        chat_service = ChatService()
        chat_service.client = mock_openai_client
        chat_service.search_service = mock_search_service

        # Act & Assert - search failure should propagate
        with pytest.raises(Exception) as exc_info:
            chat_service.chat(query=query)
        
        assert "Search service unavailable" in str(exc_info.value)
        
        # OpenAI should not be called if search fails
        mock_openai_client.chat.completions.create.assert_not_called()

    def test_chat_openai_api_failure(
        self,
        mock_openai_client,
        mock_search_service,
        sample_search_results
    ):
        """Test chat handling of OpenAI API failures"""
        # Arrange
        query = "Test OpenAI failure"
        
        mock_search_service.search.return_value = {
            'query': query,
            'count': 1,
            'results': sample_search_results[:1]
        }
        
        # Mock OpenAI API failure
        mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI API rate limit exceeded")

        # Create chat service
        chat_service = ChatService()
        chat_service.client = mock_openai_client
        chat_service.search_service = mock_search_service

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            chat_service.chat(query=query)
        
        assert "OpenAI API rate limit exceeded" in str(exc_info.value)
        
        # Search should have been called before OpenAI failure
        mock_search_service.search.assert_called_once()

    def test_streaming_chat_integration(
        self,
        mock_openai_client,
        mock_search_service,
        sample_search_results
    ):
        """Test streaming chat functionality with real-time response chunks"""
        # Arrange
        query = "Test streaming response"
        
        mock_search_service.search.return_value = {
            'query': query,
            'count': 1,
            'results': sample_search_results[:1]
        }
        
        # Mock streaming response chunks
        mock_chunks = [
            Mock(choices=[Mock(delta=Mock(content="Based"))]),
            Mock(choices=[Mock(delta=Mock(content=" on"))]),
            Mock(choices=[Mock(delta=Mock(content=" the"))]),
            Mock(choices=[Mock(delta=Mock(content=" documents"))]),
            Mock(choices=[Mock(delta=Mock(content=None))])  # End of stream
        ]
        
        mock_openai_client.chat.completions.create.return_value = iter(mock_chunks)

        # Create chat service
        chat_service = ChatService()
        chat_service.client = mock_openai_client
        chat_service.search_service = mock_search_service

        # Act
        stream_chunks = list(chat_service.stream_chat(query=query, top_k=3))

        # Assert - verify streaming workflow
        # 1. Search was performed first
        mock_search_service.search.assert_called_once_with(
            query=query,
            top=3,
            filter_expr=None,
            include_thumbnails=True
        )
        
        # 2. OpenAI streaming was called
        openai_call = mock_openai_client.chat.completions.create.call_args
        assert openai_call[1]['stream'] is True
        
        # 3. Content chunks were yielded
        content_chunks = [chunk for chunk in stream_chunks if chunk['type'] == 'content']
        assert len(content_chunks) == 4  # Excluding None content
        assert content_chunks[0]['content'] == "Based"
        assert content_chunks[1]['content'] == " on"
        assert content_chunks[2]['content'] == " the"
        assert content_chunks[3]['content'] == " documents"
        
        # 4. Sources were provided at the end
        source_chunks = [chunk for chunk in stream_chunks if chunk['type'] == 'sources']
        assert len(source_chunks) == 1
        assert source_chunks[0]['sources'] == sample_search_results[:1]

    def test_chat_parameter_validation_and_limits(
        self,
        mock_openai_client,
        mock_search_service,
        sample_search_results
    ):
        """Test chat parameter validation and OpenAI API parameter passing"""
        # Arrange
        query = "Test parameters"
        
        mock_search_service.search.return_value = {
            'query': query,
            'count': 1,
            'results': sample_search_results[:1]
        }
        
        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = "Response"
        mock_completion.choices[0].finish_reason = "length"  # Stopped due to max_tokens
        mock_completion.usage.prompt_tokens = 500
        mock_completion.usage.completion_tokens = 100
        mock_completion.usage.total_tokens = 600
        
        mock_openai_client.chat.completions.create.return_value = mock_completion

        # Create chat service
        chat_service = ChatService()
        chat_service.client = mock_openai_client
        chat_service.search_service = mock_search_service

        # Act
        result = chat_service.chat(
            query=query,
            top_k=8,
            temperature=0.7,
            max_tokens=500
        )

        # Assert - verify parameter passing
        openai_call = mock_openai_client.chat.completions.create.call_args
        
        # OpenAI parameters
        assert openai_call[1]['temperature'] == 0.7
        assert openai_call[1]['max_tokens'] == 500
        assert openai_call[1]['top_p'] == 0.95
        assert openai_call[1]['frequency_penalty'] == 0.0
        assert openai_call[1]['presence_penalty'] == 0.0
        
        # Search parameters
        search_call = mock_search_service.search.call_args
        assert search_call[1]['top'] == 8
        
        # Result includes finish reason
        assert result['finish_reason'] == 'length'


class TestChatPromptEngineering:
    """Integration tests for chat prompt engineering and few-shot learning"""

    def test_system_prompt_and_few_shot_examples(
        self,
        mock_openai_client,
        mock_search_service,
        sample_search_results
    ):
        """Test that system prompt and few-shot examples are properly included"""
        # Arrange
        query = "Test prompt engineering"
        
        mock_search_service.search.return_value = {
            'query': query,
            'count': 1,
            'results': sample_search_results[:1]
        }
        
        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = "Response with citations [Doc 1]"
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.prompt_tokens = 300
        mock_completion.usage.completion_tokens = 50
        mock_completion.usage.total_tokens = 350
        
        mock_openai_client.chat.completions.create.return_value = mock_completion

        # Create chat service
        chat_service = ChatService()
        chat_service.client = mock_openai_client
        chat_service.search_service = mock_search_service

        # Act
        result = chat_service.chat(query=query)

        # Assert - verify prompt structure
        openai_call = mock_openai_client.chat.completions.create.call_args
        messages = openai_call[1]['messages']
        
        # Should have system prompt
        system_messages = [msg for msg in messages if msg['role'] == 'system']
        assert len(system_messages) == 1
        
        system_prompt = system_messages[0]['content']
        assert 'Hywel Dda Health Board' in system_prompt
        assert 'IPAR' in system_prompt
        assert 'ONLY use information from the [SOURCE DOCUMENTS]' in system_prompt
        assert 'Include inline citations using the format [Doc X]' in system_prompt
        assert 'Sources:' in system_prompt
        
        # Should have few-shot examples
        example_messages = [msg for msg in messages if msg['role'] in ['user', 'assistant'] and '[SOURCE DOCUMENTS]' not in msg['content']]
        assert len(example_messages) >= 2  # At least one user-assistant pair
        
        # Example should demonstrate citation format
        assistant_examples = [msg for msg in example_messages if msg['role'] == 'assistant']
        assert len(assistant_examples) >= 1
        assert '[Doc 1]' in assistant_examples[0]['content']
        assert 'Sources:' in assistant_examples[0]['content']

    def test_prompt_engineering_best_practices(
        self,
        mock_openai_client,
        mock_search_service,
        sample_search_results
    ):
        """Test that prompt follows RAG best practices"""
        # Arrange
        query = "What are the latest performance metrics?"
        
        mock_search_service.search.return_value = {
            'query': query,
            'count': 2,
            'results': sample_search_results[:2]
        }
        
        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = "Based on the documents, performance metrics show [Doc 1] and [Doc 2]."
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.prompt_tokens = 250
        mock_completion.usage.completion_tokens = 40
        mock_completion.usage.total_tokens = 290
        
        mock_openai_client.chat.completions.create.return_value = mock_completion

        # Create chat service
        chat_service = ChatService()
        chat_service.client = mock_openai_client
        chat_service.search_service = mock_search_service

        # Act
        result = chat_service.chat(query=query)

        # Assert - verify RAG best practices in prompt
        openai_call = mock_openai_client.chat.completions.create.call_args
        messages = openai_call[1]['messages']
        
        # Find user message with sources
        user_message = None
        for msg in messages:
            if msg['role'] == 'user' and '[SOURCE DOCUMENTS]' in msg['content']:
                user_message = msg['content']
                break
        
        assert user_message is not None
        
        # Verify grounding structure
        assert '[SOURCE DOCUMENTS]' in user_message
        assert '[USER QUERY]' in user_message
        
        # Verify source documents are properly structured
        assert '[Doc 1]' in user_message
        assert '[Doc 2]' in user_message
        
        # Each source should have required metadata
        for i in range(1, 3):
            doc_section = user_message.split(f'[Doc {i}]')[1].split(f'[Doc {i+1}]' if i < 2 else '[USER QUERY]')[0]
            assert 'Title:' in doc_section
            assert 'Page:' in doc_section
            assert 'Relevance Score:' in doc_section
            assert 'Content:' in doc_section
        
        # User query should be at the end
        assert user_message.endswith(f'[USER QUERY]\n{query}')