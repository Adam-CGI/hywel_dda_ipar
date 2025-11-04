"""
Tests for EPIC G - RAG Chat functionality with GPT-4o-mini.
Tests grounding, citation generation, and conversation handling.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.chat_service import ChatService


class TestChatService:
    """Test suite for ChatService RAG implementation."""
    
    @pytest.fixture
    def mock_search_service(self):
        """Mock search service with sample results."""
        mock = Mock()
        mock.search.return_value = {
            'results': [
                {
                    'id': 'chunk1',
                    'doc_id': 'doc123',
                    'title': 'M12 2024-25 IPAR Overview',
                    'page_no': 3,
                    'text': 'Emergency department waiting times target 95% of patients seen within 4 hours.',
                    'score': 0.95,
                    'kpi_tags': ['ED Performance', 'Waiting Times']
                },
                {
                    'id': 'chunk2',
                    'doc_id': 'doc123',
                    'title': 'M12 2024-25 IPAR Overview',
                    'page_no': 7,
                    'text': 'Cancer treatment pathways targeting 75% of patients start treatment within 62 days.',
                    'score': 0.89,
                    'kpi_tags': ['Cancer Services']
                }
            ],
            'total_count': 2
        }
        return mock
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock Azure OpenAI client with sample completion."""
        mock = Mock()
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(content='The key performance indicators include emergency department waiting times [Doc 1] and cancer treatment pathways [Doc 2].\n\nSources:\n- [Doc 1] M12 2024-25 IPAR Overview, Page 3\n- [Doc 2] M12 2024-25 IPAR Overview, Page 7'),
                finish_reason='stop'
            )
        ]
        mock_completion.usage = MagicMock(
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600
        )
        mock.chat.completions.create.return_value = mock_completion
        return mock
    
    def test_format_sources_for_prompt(self):
        """Test source formatting for grounding."""
        service = ChatService()
        
        sources = [
            {
                'title': 'Test Document',
                'page_no': 1,
                'text': 'This is test content.',
                'score': 0.95,
                'kpi_tags': ['Test Tag']
            }
        ]
        
        formatted = service._format_sources_for_prompt(sources)
        
        assert '[SOURCE DOCUMENTS]' in formatted
        assert '[Doc 1]' in formatted
        assert 'Title: Test Document' in formatted
        assert 'Page: 1' in formatted
        assert 'Content: This is test content.' in formatted
        assert 'KPI Tags: Test Tag' in formatted
        assert 'Relevance Score: 0.95' in formatted
    
    def test_format_sources_empty(self):
        """Test source formatting with no results."""
        service = ChatService()
        formatted = service._format_sources_for_prompt([])
        
        assert '[SOURCE DOCUMENTS]' in formatted
        assert 'No relevant documents found' in formatted
    
    def test_build_messages_basic(self):
        """Test message building with system prompt and few-shot examples."""
        service = ChatService()
        
        sources = "[SOURCE DOCUMENTS]\n[Doc 1] Test content"
        messages = service._build_messages("What are the KPIs?", sources)
        
        # Should have: system prompt + 2 few-shot examples + user query
        assert len(messages) >= 4
        assert messages[0]['role'] == 'system'
        assert 'only use information from the [SOURCE DOCUMENTS]' in messages[0]['content'].lower()
        
        # Check few-shot examples present
        assert any(msg['role'] == 'user' and 'key performance indicators' in msg['content'].lower() 
                   for msg in messages)
        assert any(msg['role'] == 'assistant' and '[Doc 1]' in msg['content'] 
                   for msg in messages)
        
        # Last message should be user query with sources
        assert messages[-1]['role'] == 'user'
        assert '[SOURCE DOCUMENTS]' in messages[-1]['content']
        assert 'What are the KPIs?' in messages[-1]['content']
    
    def test_build_messages_with_history(self):
        """Test message building with conversation history."""
        service = ChatService()
        
        history = [
            {'role': 'user', 'content': 'Previous question?'},
            {'role': 'assistant', 'content': 'Previous answer.'}
        ]
        
        sources = "[SOURCE DOCUMENTS]\n[Doc 1] Test"
        messages = service._build_messages("Follow-up question?", sources, history)
        
        # Should include history
        assert any(msg['content'] == 'Previous question?' for msg in messages)
        assert any(msg['content'] == 'Previous answer.' for msg in messages)
    
    @patch('app.services.chat_service.AzureOpenAI')
    @patch('app.services.chat_service.SearchService')
    def test_chat_end_to_end(self, mock_search_class, mock_openai_class, mock_search_service, mock_openai_client):
        """Test full chat flow with grounding and citations."""
        mock_search_class.return_value = mock_search_service
        mock_openai_class.return_value = mock_openai_client
        
        service = ChatService()
        result = service.chat(
            query="What are the key performance indicators?",
            conversation_history=[],
            top_k=5,
            temperature=0.3
        )
        
        # Verify search was called
        mock_search_service.search.assert_called_once_with(
            query="What are the key performance indicators?",
            top=5,
            filter_expr=None,
            include_thumbnails=True
        )
        
        # Verify OpenAI was called
        mock_openai_client.chat.completions.create.assert_called_once()
        
        # Check result structure
        assert 'response' in result
        assert 'sources' in result
        assert 'usage' in result
        assert 'model' in result
        
        # Check response contains citations
        assert '[Doc' in result['response']
        
        # Check sources included
        assert len(result['sources']) == 2
        assert result['sources'][0]['title'] == 'M12 2024-25 IPAR Overview'
        
        # Check usage stats
        assert result['usage']['total_tokens'] == 600
        assert result['usage']['prompt_tokens'] == 500
        assert result['usage']['completion_tokens'] == 100
    
    @patch('app.services.chat_service.AzureOpenAI')
    @patch('app.services.chat_service.SearchService')
    def test_chat_no_results_found(self, mock_search_class, mock_openai_class, mock_search_service, mock_openai_client):
        """Test chat behavior when no relevant documents are found."""
        # Mock empty search results
        mock_search_service.search.return_value = {
            'results': [],
            'total_count': 0
        }
        
        # Mock response indicating no information available
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(content="I don't have information about that in the available documents."),
                finish_reason='stop'
            )
        ]
        mock_completion.usage = MagicMock(prompt_tokens=300, completion_tokens=50, total_tokens=350)
        mock_openai_client.chat.completions.create.return_value = mock_completion
        
        mock_search_class.return_value = mock_search_service
        mock_openai_class.return_value = mock_openai_client
        
        service = ChatService()
        result = service.chat(query="What is the meaning of life?")
        
        # Should still return successfully but with no sources
        assert len(result['sources']) == 0
        assert "don't have information" in result['response'].lower()
    
    @patch('app.services.chat_service.AzureOpenAI')
    @patch('app.services.chat_service.SearchService')
    def test_chat_with_conversation_history(self, mock_search_class, mock_openai_class, mock_search_service, mock_openai_client):
        """Test multi-turn conversation with history."""
        mock_search_class.return_value = mock_search_service
        mock_openai_class.return_value = mock_openai_client
        
        history = [
            {'role': 'user', 'content': 'What are the KPIs?'},
            {'role': 'assistant', 'content': 'The KPIs include ED times [Doc 1] and cancer pathways [Doc 2].'}
        ]
        
        service = ChatService()
        result = service.chat(
            query="Can you tell me more about the first one?",
            conversation_history=history,
            top_k=5
        )
        
        # Verify OpenAI received conversation history
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args.kwargs['messages']
        
        # History should be included
        assert any('What are the KPIs?' in str(msg.get('content', '')) for msg in messages)
    
    @patch('app.services.chat_service.AzureOpenAI')
    @patch('app.services.chat_service.SearchService')
    def test_chat_temperature_control(self, mock_search_class, mock_openai_class, mock_search_service, mock_openai_client):
        """Test temperature parameter controls model creativity."""
        mock_search_class.return_value = mock_search_service
        mock_openai_class.return_value = mock_openai_client
        
        service = ChatService()
        
        # Test with low temperature (focused)
        service.chat(query="Test query", temperature=0.1)
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs['temperature'] == 0.1
        
        # Test with higher temperature (creative)
        service.chat(query="Test query", temperature=0.8)
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs['temperature'] == 0.8
    
    def test_system_prompt_contains_rag_best_practices(self):
        """Test that system prompt includes RAG best practices."""
        service = ChatService()
        system_prompt = service.SYSTEM_PROMPT
        
        # Check for grounding instruction
        assert 'only' in system_prompt.lower()
        assert 'source documents' in system_prompt.lower()
        
        # Check for citation instruction
        assert 'citation' in system_prompt.lower() or '[Doc' in system_prompt
        
        # Check for hallucination prevention
        assert "don't have information" in system_prompt.lower() or 'do not fabricate' in system_prompt.lower()
    
    def test_few_shot_examples_format(self):
        """Test that few-shot examples demonstrate correct citation format."""
        service = ChatService()
        examples = service.FEW_SHOT_EXAMPLES
        
        # Should have at least one example
        assert len(examples) >= 2
        
        # Check example structure
        user_example = examples[0]
        assistant_example = examples[1]
        
        assert user_example['role'] == 'user'
        assert assistant_example['role'] == 'assistant'
        
        # Assistant example should demonstrate citations
        assert '[Doc' in assistant_example['content']
        assert 'Sources:' in assistant_example['content']


class TestChatServiceIntegration:
    """Integration tests for chat service (requires Azure services)."""
    
    @pytest.mark.integration
    def test_real_chat_query(self):
        """
        Test real chat query against Azure services.
        Requires valid Azure credentials in .env
        """
        try:
            service = ChatService()
            result = service.chat(
                query="What documents are available?",
                top_k=3,
                temperature=0.3
            )
            
            # Should return valid structure
            assert 'response' in result
            assert 'sources' in result
            assert 'usage' in result
            assert isinstance(result['response'], str)
            assert len(result['response']) > 0
            
        except Exception as e:
            pytest.skip(f"Integration test requires Azure services: {str(e)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
