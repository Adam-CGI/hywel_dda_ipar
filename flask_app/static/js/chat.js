/**
 * Chat Interface JavaScript for Hywel Dda IPAR
 * Handles chat functionality, message history, and citation previews
 */

// Conversation history for multi-turn chat
let conversationHistory = [];

// Storage keys
const CHAT_STORAGE_KEY = 'ipar_chat_history';
const CHAT_MESSAGES_KEY = 'ipar_chat_messages';

/* ============================================
   Chat History Persistence
   ============================================ */

function saveChatHistory() {
    try {
        localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(conversationHistory));
    } catch (e) {
        console.warn('Failed to save chat history:', e);
    }
}

function loadChatHistory() {
    try {
        const saved = localStorage.getItem(CHAT_STORAGE_KEY);
        if (saved) {
            conversationHistory = JSON.parse(saved);
        }
    } catch (e) {
        console.warn('Failed to load chat history:', e);
        conversationHistory = [];
    }
}

function saveChatMessages() {
    try {
        const messagesDiv = document.getElementById('chat-messages');
        const messages = [];

        messagesDiv.querySelectorAll('.message').forEach(msg => {
            if (msg.classList.contains('message-user')) {
                const content = msg.querySelector('.message-content');
                if (content) {
                    messages.push({
                        type: 'user',
                        content: content.textContent.trim()
                    });
                }
            } else if (msg.classList.contains('message-assistant') && !msg.classList.contains('skeleton-message')) {
                const content = msg.querySelector('.message-content');
                if (content) {
                    messages.push({
                        type: 'assistant',
                        html: content.innerHTML
                    });
                }
            }
        });

        localStorage.setItem(CHAT_MESSAGES_KEY, JSON.stringify(messages));
    } catch (e) {
        console.warn('Failed to save chat messages:', e);
    }
}

function restoreChatMessages() {
    try {
        const saved = localStorage.getItem(CHAT_MESSAGES_KEY);
        if (!saved) return false;

        const messages = JSON.parse(saved);
        if (!messages || messages.length === 0) return false;

        const messagesDiv = document.getElementById('chat-messages');
        const welcomeMessage = document.getElementById('welcome-message');

        // Hide welcome message
        if (welcomeMessage && !welcomeMessage.classList.contains('hidden')) {
            welcomeMessage.classList.add('hidden');
        }

        // Restore each message
        messages.forEach(msg => {
            if (msg.type === 'user') {
                addUserMessage(msg.content, false);
            } else if (msg.type === 'assistant') {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message message-assistant';
                messageDiv.innerHTML = `
                    <div class="message-label">
                        <div class="avatar">
                            <i class="fas fa-robot"></i>
                        </div>
                        <span>IPAR Insights</span>
                    </div>
                    <div class="message-content">${msg.html}</div>
                `;
                messagesDiv.appendChild(messageDiv);
            }
        });

        setTimeout(() => scrollToBottom(), 100);
        return true;
    } catch (e) {
        console.warn('Failed to restore chat messages:', e);
        return false;
    }
}

function clearChatHistory() {
    conversationHistory = [];
    localStorage.removeItem(CHAT_STORAGE_KEY);
    localStorage.removeItem(CHAT_MESSAGES_KEY);

    // Clear UI
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.querySelectorAll('.message').forEach(msg => msg.remove());

    // Show welcome message again
    const welcomeMessage = document.getElementById('welcome-message');
    if (welcomeMessage) {
        welcomeMessage.classList.remove('hidden');
    }
    
    if (window.ToastManager) {
        ToastManager.success('Chat Cleared', 'Your conversation has been reset.');
    }
}

/* ============================================
   Chat Submission
   ============================================ */

async function handleChatSubmit(event) {
    event.preventDefault();
    
    const query = document.getElementById('chat-input').value.trim();
    if (!query) return;
    
    // Hide welcome message
    const welcomeMessage = document.getElementById('welcome-message');
    if (welcomeMessage && !welcomeMessage.classList.contains('hidden')) {
        welcomeMessage.classList.add('hidden');
    }
    
    // Add user message
    addUserMessage(query);
    
    // Show loading state
    const messagesDiv = document.getElementById('chat-messages');
    const loadingMessage = document.createElement('div');
    loadingMessage.className = 'message message-assistant chat-loading';
    loadingMessage.innerHTML = `
        <div class="chat-loading-bubble">
            <div class="chat-loading-spinner"></div>
            <span class="chat-loading-text">Analyzing documents...</span>
        </div>
    `;
    messagesDiv.appendChild(loadingMessage);
    
    // Update UI state
    const sendButton = document.getElementById('send-button');
    const chatInput = document.getElementById('chat-input');
    
    sendButton.disabled = true;
    chatInput.disabled = true;
    chatInput.value = '';
    autoExpandTextarea(chatInput);
    
    scrollToBottom();
    
    try {
        const formData = new FormData();
        formData.append('query', query);
        formData.append('conversation_history', JSON.stringify(conversationHistory));
        formData.append('top_k', '10');
        formData.append('temperature', '0.3');
        
        const response = await fetch('/api/documents/chat', {
            method: 'POST',
            body: formData
        });
        
        // Remove loading message
        loadingMessage.remove();
        
        if (response.ok) {
            const data = await response.json();
            addAssistantMessage(data);
            
            // Update conversation history
            conversationHistory.push(
                { role: 'user', content: query },
                { role: 'assistant', content: data.response }
            );

            // Keep only last 10 messages
            if (conversationHistory.length > 10) {
                conversationHistory = conversationHistory.slice(-10);
            }

            saveChatHistory();
            saveChatMessages();
        } else {
            let errorMessage = 'Sorry, something went wrong. Please try again.';
            
            if (response.status === 400) {
                errorMessage = 'Invalid request. Please check your input.';
            } else if (response.status === 429) {
                errorMessage = 'Too many requests. Please wait a moment.';
            } else if (response.status >= 500) {
                errorMessage = 'Server error. Please try again later.';
            }
            
            addErrorMessage(errorMessage);
            
            if (window.ToastManager) {
                ToastManager.error('Chat Error', errorMessage);
            }
        }
    } catch (error) {
        console.error('Chat error:', error);
        loadingMessage.remove();
        addErrorMessage('Network error. Please check your connection.');
        
        if (window.ToastManager) {
            ToastManager.error('Connection Error', 'Please check your network connection.');
        }
    } finally {
        sendButton.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();
    }
}

/* ============================================
   Message Rendering
   ============================================ */

function addUserMessage(text, shouldScroll = true) {
    const messagesDiv = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-user';
    messageDiv.innerHTML = `
        <div class="message-content">${escapeHtml(text)}</div>
        <div class="message-timestamp">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
    `;
    messagesDiv.appendChild(messageDiv);

    if (shouldScroll) {
        setTimeout(() => scrollToBottom(), 100);
    }
}

function addAssistantMessage(response) {
    const messagesDiv = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-assistant';
    
    // Format response with citations
    const formattedResponse = formatResponseWithCitations(response.response, response.sources);
    const referencesHtml = buildReferencesSection(response.sources);
    
    const sourceCount = response.sources ? response.sources.length : 0;
    const contextHtml = sourceCount > 0 ? `
        <div class="document-context">
            <i class="fas fa-database"></i>
            <span>Based on ${sourceCount} IPAR document${sourceCount !== 1 ? 's' : ''}</span>
        </div>
    ` : '';
    
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="prose">
                ${formattedResponse}
            </div>
            ${referencesHtml}
            ${contextHtml}
        </div>
        <div class="message-timestamp">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
    `;
    messagesDiv.appendChild(messageDiv);

    // Scroll to message
    setTimeout(() => scrollToMessage(messageDiv), 100);

    return messageDiv;
}

function addErrorMessage(text) {
    const messagesDiv = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-assistant';
    
    messageDiv.innerHTML = `
        <div class="message-content" style="background: #fef2f2; border-color: var(--nhs-red); color: #991b1b;">
            <div class="flex items-center gap-3">
                <i class="fas fa-exclamation-circle text-red-500"></i>
                <span>${escapeHtml(text)}</span>
            </div>
        </div>
    `;
    messagesDiv.appendChild(messageDiv);
    
    setTimeout(() => scrollToBottom(), 100);
}

/* ============================================
   Response Formatting
   ============================================ */

function formatResponseWithCitations(text, sources) {
    let formattedText = text;

    // Handle markdown formatting
    formattedText = formattedText
        .replace(/^#### (.*?)$/gm, '<h4>$1</h4>')
        .replace(/^### (.*?)$/gm, '<h3>$1</h3>')
        .replace(/^## (.*?)$/gm, '<h2>$1</h2>')
        .replace(/^# (.*?)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, '<em>$1</em>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
    
    // Handle lists
    formattedText = formattedText.replace(/^- (.+)$/gm, '<li>$1</li>');
    formattedText = formattedText.replace(/(<li>.*?<\/li>)(\s*<li>.*?<\/li>)*/gs, function(match) {
        return '<ul>' + match + '</ul>';
    });
    formattedText = formattedText.replace(/<\/ul>\s*<ul>/g, '');

    // Clean up headers
    formattedText = formattedText.replace(/<p>(<h[1-6]>.*?<\/h[1-6]>)<\/p>/g, '$1');

    // Wrap in paragraphs
    if (!formattedText.startsWith('<p>') && !formattedText.startsWith('<ul>') && !formattedText.startsWith('<h')) {
        formattedText = '<p>' + formattedText + '</p>';
    }
    
    // Convert [Doc X] to inline citations
    formattedText = formattedText.replace(/\[Doc\s+(\d+)\]/g, function(match, docNum) {
        const idx = parseInt(docNum) - 1;
        
        if (sources && sources[idx]) {
            const source = sources[idx];
            const sourceTitle = escapeHtml(source.title || 'Document');
            const pageInfo = source.page_no ? `, p. ${source.page_no}` : '';
            const tooltip = `${sourceTitle}${pageInfo}`;
            
            if (source.thumb_url) {
                return `<span class="citation-inline" 
                              onclick="showCitationPreview('${source.chunk_id}', '${source.doc_id}', ${source.page_no}, '${source.thumb_url}', '${sourceTitle.replace(/'/g, "\\'")}')" 
                              title="${tooltip}"
                              tabindex="0"
                              role="button">${docNum}</span>`;
            } else {
                return `<span class="citation-inline" title="${tooltip}">${docNum}</span>`;
            }
        }
        return `<span class="citation-inline" title="Reference ${docNum}">${docNum}</span>`;
    });
    
    return formattedText;
}

function buildReferencesSection(sources) {
    if (!sources || sources.length === 0) return '';
    
    let html = `
        <div class="references-section">
            <div class="references-header">
                <i class="fas fa-book-open"></i>
                <span>References</span>
            </div>
            <div class="references-list">
    `;
    
    sources.forEach((source, idx) => {
        const docNum = idx + 1;
        const title = escapeHtml(source.title || 'Unknown Document');
        const filename = escapeHtml(source.origin_filename || 'Document');
        const pageNo = source.page_no ? `Page ${source.page_no}` : '';
        const hasPreview = source.thumb_url;
        
        html += `
            <div class="reference-item" ${hasPreview ? `onclick="showCitationPreview('${source.chunk_id}', '${source.doc_id}', ${source.page_no || 'null'}, '${source.thumb_url}', '${title.replace(/'/g, "\\'")}')"` : ''}>
                <div class="reference-number">${docNum}</div>
                <div class="reference-content">
                    <div class="reference-title">${title}</div>
                    <div class="reference-meta">
                        <i class="fas fa-file-pdf mr-1"></i>${filename}${pageNo ? ' · ' + pageNo : ''}
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div></div>';
    return html;
}

/* ============================================
   Citation Preview Modal
   ============================================ */

function showCitationPreview(chunkId, docId, pageNo, thumbUrl, sourceTitle) {
    const modal = document.getElementById('citation-modal');
    const title = document.getElementById('modal-title');
    const subtitle = document.getElementById('modal-subtitle');
    const content = document.getElementById('modal-content');
    
    title.textContent = sourceTitle;
    subtitle.textContent = `Page ${pageNo}`;
    
    // Show loading
    content.innerHTML = `
        <div class="text-center p-8">
            <div class="loading-spinner mx-auto mb-4"></div>
            <p class="text-muted">Loading preview...</p>
        </div>
    `;
    
    modal.style.display = 'flex';
    
    // Load thumbnail
    const img = new Image();
    img.onload = function() {
        content.innerHTML = `
            <div class="text-center">
                <img src="${thumbUrl}" 
                     alt="Page ${pageNo} from ${sourceTitle}" 
                     style="max-width: 100%; height: auto; border-radius: var(--radius-md); box-shadow: var(--shadow-md);">
                <div class="mt-4 p-4 bg-secondary rounded-md">
                    <p class="text-sm"><strong>${sourceTitle}</strong></p>
                    <p class="text-xs text-muted">Page ${pageNo} · Document ID: ${docId.substring(0, 8)}...</p>
                </div>
            </div>
        `;
    };
    
    img.onerror = function() {
        content.innerHTML = `
            <div class="text-center p-8">
                <i class="fas fa-exclamation-triangle text-3xl text-error mb-4"></i>
                <p>Preview unavailable</p>
            </div>
        `;
    };
    
    img.src = thumbUrl;
}

function closeCitationModal() {
    const modal = document.getElementById('citation-modal');
    modal.style.display = 'none';
}

/* ============================================
   Utility Functions
   ============================================ */

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function scrollToBottom() {
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function scrollToMessage(messageElement) {
    const messagesDiv = document.getElementById('chat-messages');
    if (messageElement) {
        const messageTop = messageElement.offsetTop;
        messagesDiv.scrollTo({
            top: messageTop - 20,
            behavior: 'smooth'
        });
    }
}

function autoExpandTextarea(textarea) {
    textarea.style.height = 'auto';
    const newHeight = Math.min(textarea.scrollHeight, 150);
    textarea.style.height = newHeight + 'px';
}

function askExample(element) {
    const query = element.textContent.trim();
    const chatInput = document.getElementById('chat-input');
    chatInput.value = query;
    chatInput.focus();
    autoExpandTextarea(chatInput);
}

/* ============================================
   Initialization
   ============================================ */

document.addEventListener('DOMContentLoaded', function() {
    // Load persisted data
    loadChatHistory();
    restoreChatMessages();

    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.focus();

        // Auto-expand on input
        chatInput.addEventListener('input', function() {
            autoExpandTextarea(this);
        });

        // Handle Enter key
        chatInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                handleChatSubmit(event);
            }
        });

        autoExpandTextarea(chatInput);
    }

    // Close modal on click outside
    const modal = document.getElementById('citation-modal');
    if (modal) {
        modal.addEventListener('click', function(event) {
            if (event.target === modal) {
                closeCitationModal();
            }
        });
    }

    // Close modal on Escape
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeCitationModal();
        }
    });
});

