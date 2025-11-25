"""
Chat service implementing RAG (Retrieval Augmented Generation) with GPT-4o-mini.
Implements Microsoft best practices for RAG:
- Grounding responses in search results to reduce hallucination
- Inline citations for transparency and verification
- Prompt engineering with structured instructions
- Few-shot learning examples
- Conversation history support
"""
import logging
from typing import List, Dict, Any, Optional
from openai import AzureOpenAI
from config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_CHAT_DEPLOYMENT
)
from services.search_service import SearchService

logger = logging.getLogger(__name__)


class ChatService:
    """Service for RAG-powered chat using Azure OpenAI GPT-4o-mini."""
    
    # System prompt implementing RAG best practices
    SYSTEM_PROMPT = """You are an intelligent assistant for the Hywel Dda Health Board's Integrated Performance Assessment Report (IPAR) document system.

Your role is to help users understand and analyze IPAR documents by answering questions based ONLY on the provided source documents.

CRITICAL RULES:
1. ONLY use information from the [SOURCE DOCUMENTS] section provided below
2. Include inline citations using the format [Doc X] immediately after each claim
3. If the sources don't contain relevant information, say "I don't have information about that in the available documents"
4. Never fabricate or infer information not present in the sources
5. When multiple sources support a claim, cite all relevant documents [Doc 1, Doc 2]
6. Be concise but thorough - aim for clear, professional responses
7. If asked about recent events, remind users of the document observation dates

FORMAT YOUR RESPONSE:
- Use inline citations [Doc X] after every factual statement
- Use bullet points for lists
- Keep paragraphs short and scannable
- End with "Sources:" section listing all cited documents with their titles and page numbers"""

    # Few-shot examples to guide model behavior
    FEW_SHOT_EXAMPLES = [
        {
            "role": "user",
            "content": "What are the key performance indicators mentioned?"
        },
        {
            "role": "assistant",
            "content": """Based on the available documents, the key performance indicators include:

- **Emergency department waiting times** - targeting 95% of patients seen within 4 hours [Doc 1]
- **Cancer treatment pathways** - ensuring 75% of patients start treatment within 62 days of referral [Doc 1]
- **Infection control rates** - monitoring hospital-acquired infections like C. difficile and MRSA [Doc 2]
- **Financial performance** - tracking budget variance and cost improvement programmes [Doc 2]

Sources:
- [Doc 1] M12 2024-25 IPAR Overview, Page 3
- [Doc 2] M12 2024-25 IPAR Overview, Page 7"""
        }
    ]
    
    def __init__(self):
        """Initialize chat service with Azure OpenAI and search capabilities."""
        if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
            raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be configured")
        
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version="2024-02-01"
        )
        self.deployment = AZURE_OPENAI_CHAT_DEPLOYMENT or "gpt-4o-mini"
        self.search_service = SearchService()
        
        logger.info(f"Initialized ChatService with deployment: {self.deployment}")
    
    def _format_sources_for_prompt(self, search_results: List[Dict[str, Any]]) -> str:
        """
        Format search results into a structured source list for the prompt.
        
        Args:
            search_results: List of search result chunks
            
        Returns:
            Formatted source text for prompt
        """
        if not search_results:
            return "[SOURCE DOCUMENTS]\nNo relevant documents found.\n"
        
        sources_text = "[SOURCE DOCUMENTS]\n\n"
        for idx, result in enumerate(search_results, 1):
            sources_text += f"[Doc {idx}]\n"
            sources_text += f"Title: {result.get('title', 'Unknown')}\n"
            sources_text += f"Page: {result.get('page_no', 'N/A')}\n"
            sources_text += f"Relevance Score: {result.get('score', 0):.2f}\n"
            sources_text += f"Content: {result.get('text', '')}\n"
            
            # Include KPI tags if present
            kpi_tags = result.get('kpi_tags', [])
            if kpi_tags:
                sources_text += f"KPI Tags: {', '.join(kpi_tags)}\n"
            
            sources_text += "\n---\n\n"
        
        return sources_text
    
    def _build_messages(
        self,
        user_query: str,
        sources: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        """
        Build the message list for the chat completion API.
        Implements prompt engineering best practices with few-shot examples.
        
        Args:
            user_query: User's question
            sources: Formatted source documents
            conversation_history: Previous messages in conversation
            
        Returns:
            List of message dictionaries
        """
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]
        
        # Add few-shot examples to guide model behavior
        messages.extend(self.FEW_SHOT_EXAMPLES)
        
        # Add conversation history if present (for multi-turn conversations)
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add current query with grounding sources
        user_message = f"{sources}\n\n[USER QUERY]\n{user_query}"
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def chat(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 5,
        temperature: float = 0.3,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """
        Execute a RAG-powered chat query.
        
        Workflow:
        1. Retrieve relevant documents using hybrid search
        2. Format documents as grounding sources
        3. Build prompt with system instructions, few-shot examples, and sources
        4. Call GPT-4o-mini for response generation
        5. Return response with citations and source metadata
        
        Args:
            query: User's question
            conversation_history: Previous messages (for multi-turn chat)
            top_k: Number of documents to retrieve for grounding (default: 5)
            temperature: Model creativity (0.0-1.0, lower = more focused)
            max_tokens: Maximum response length
            
        Returns:
            Dictionary containing:
            - response: Generated answer with inline citations
            - sources: List of source documents used
            - usage: Token usage statistics
            - model: Model used for generation
        """
        try:
            logger.info(f"Processing chat query: '{query[:100]}...' (top_k={top_k})")
            
            # Step 1: Retrieve relevant documents (RAG retrieval phase)
            search_results = self.search_service.search(
                query=query,
                top=top_k,
                filter_expr=None,
                include_thumbnails=True
            )
            
            sources_list = search_results.get('results', [])
            logger.info(f"Retrieved {len(sources_list)} source documents")
            
            # Step 2: Format sources for grounding
            sources_text = self._format_sources_for_prompt(sources_list)
            
            # Step 3: Build prompt with few-shot examples
            messages = self._build_messages(query, sources_text, conversation_history)
            
            # Step 4: Call Azure OpenAI (RAG generation phase)
            logger.info(f"Calling Azure OpenAI {self.deployment}")
            completion = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.95,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            # Step 5: Extract response and usage
            response_text = completion.choices[0].message.content
            finish_reason = completion.choices[0].finish_reason
            
            usage_stats = {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens
            }
            
            logger.info(f"Generated response ({usage_stats['total_tokens']} tokens)")
            
            # Return structured response
            return {
                "response": response_text,
                "sources": sources_list,
                "usage": usage_stats,
                "model": self.deployment,
                "finish_reason": finish_reason,
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Error in chat service: {str(e)}", exc_info=True)
            raise
    
    def stream_chat(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 5,
        temperature: float = 0.3,
        max_tokens: int = 1000
    ):
        """
        Execute a RAG-powered chat query with streaming response.
        
        Yields response chunks as they are generated for better UX.
        
        Args:
            query: User's question
            conversation_history: Previous messages
            top_k: Number of documents to retrieve
            temperature: Model creativity
            max_tokens: Maximum response length
            
        Yields:
            Response chunks as they are generated
        """
        try:
            logger.info(f"Processing streaming chat query: '{query[:100]}...'")
            
            # Retrieve and format sources (same as non-streaming)
            search_results = self.search_service.search(
                query=query,
                top=top_k,
                filter_expr=None,
                include_thumbnails=True
            )
            
            sources_list = search_results.get('results', [])
            sources_text = self._format_sources_for_prompt(sources_list)
            messages = self._build_messages(query, sources_text, conversation_history)
            
            # Call Azure OpenAI with streaming enabled
            stream = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True  # Enable streaming
            )
            
            # Yield chunks as they arrive
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {
                        "type": "content",
                        "content": chunk.choices[0].delta.content
                    }
            
            # After streaming completes, send sources
            yield {
                "type": "sources",
                "sources": sources_list
            }
            
        except Exception as e:
            logger.error(f"Error in streaming chat: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e)
            }
