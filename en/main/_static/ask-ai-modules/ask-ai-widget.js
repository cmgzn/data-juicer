/**
 * Ask AI Widget - Main Controller
 * 
 * This is the main entry point that integrates all modules:
 * - I18N: Internationalization
 * - API: Communication with backend
 * - UI: User interface management
 */

import { I18N, detectLanguage } from './ask-ai-i18n.js';
import { AskAIApi } from './ask-ai-api.js';
import { AskAIUI } from './ask-ai-ui.js';

class AskAIWidget {
  constructor() {
    // Check if marked library is loaded
    if (typeof marked === 'undefined') {
      console.error('Marked library not loaded!');
      console.info('Add this to your HTML: <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>');
      return;
    }

    // Initialize session and language
    this.sessionId = this.generateSessionId();
    this.language = detectLanguage();
    this.i18n = I18N[this.language.replace('-', '_')] || I18N.en;

    // Initialize modules
    this.api = new AskAIApi(this.sessionId, this.i18n);
    this.ui = new AskAIUI(this.i18n);

    // Configure marked
    marked.setOptions({
      breaks: true,
      gfm: true,
      headerIds: false,
      mangle: false,
    });

    this.init();
  }

  /**
   * Generate or retrieve session ID
   * @returns {string} Session ID
   */
  generateSessionId() {
    // Try to get existing session ID from sessionStorage
    let sessionId = sessionStorage.getItem('ask-ai-session-id');

    if (!sessionId) {
      // Generate new session ID if none exists
      sessionId = `browser-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      sessionStorage.setItem('ask-ai-session-id', sessionId);
    }

    console.log('Using session ID:', sessionId);
    return sessionId;
  }

  /**
   * Initialize the widget
   */
  async init() {
    // Create UI
    this.ui.createWidget();
    
    // Bind events
    this.ui.bindEvents({
      onToggle: () => this.ui.toggleModal(),
      onClose: () => this.ui.closeModal(),
      onClear: () => this.clearConversation(),
      onExpand: () => this.ui.toggleExpand(),
      onSend: () => this.sendMessage(),
    });

    // Observe theme changes
    this.ui.observeThemeChanges();

    // Check API connection
    await this.api.checkApiConnection();

    // Load conversation history
    await this.loadConversationHistory();

    // Add welcome message
    this.addWelcomeMessage();
  }

  /**
   * Load conversation history from API
   */
  async loadConversationHistory() {
    const messages = await this.api.loadConversationHistory();

    if (messages && messages.length > 0) {
      messages.forEach(msg => {
        if (msg.content && typeof msg.content === 'string') {
          const isUser = msg.role === 'user';
          const content = msg.content.trim();

          // Skip JSON array messages (tool calls)
          if (!(content.startsWith('[{') && content.endsWith('}]'))) {
            if (content) {
              const messageId = msg.id || `history_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
              this.ui.addMessage(content, isUser ? 'user' : 'assistant', messageId);
            }
          }
        }
      });

      if (messages.length > 0) {
        this.ui.scrollToBottom();
      }
    }
  }

  /**
   * Add welcome message based on API connection status
   */
  addWelcomeMessage() {
    this.ui.addWelcomeMessage(this.api.apiConnected);
  }

  /**
   * Send user message
   */
  async sendMessage() {
    const message = this.ui.getInputValue().trim();
    if (!message || this.ui.isTyping) return;

    // Add user message to UI
    this.ui.addMessage(message, 'user');
    this.ui.clearInput();

    // Create assistant message placeholder
    const assistantMessageDiv = this.ui.showTypingIndicator();
    const messageId = assistantMessageDiv.getAttribute('data-message-id') || 
                      `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    assistantMessageDiv.setAttribute('data-message-id', messageId);

    // Track active tool calls by call_id
    const activeToolCalls = new Map();

    try {
      // Get AI response with streaming
      await this.api.getAIResponseStream(
        message,
        // onContentUpdate
        (content) => {
          // Remove typing class when we start receiving content
          assistantMessageDiv.classList.remove('typing');
          this.ui.updateMessageContent(assistantMessageDiv, content);
        },
        // onToolUse
        (toolName, toolArgs, callId) => {
          // Remove typing indicator when first tool is called
          assistantMessageDiv.classList.remove('typing');
          // Clear the typing dots content
          const typingIndicator = assistantMessageDiv.querySelector('.typing-indicator');
          if (typingIndicator) {
            typingIndicator.remove();
          }
          
          // Add tool call to panel
          const toolId = this.ui.addToolCall(toolName, toolArgs, assistantMessageDiv);
          
          // Store mapping from callId to toolId
          if (callId) {
            activeToolCalls.set(callId, toolId);
          }
        },
        // onComplete
        (finalContent, serverMessageId) => {
          // Mark all remaining tools as done
          activeToolCalls.forEach(toolId => {
            this.ui.markToolCallDone(toolId);
          });
          
          // Ensure typing class is removed
          assistantMessageDiv.classList.remove('typing');
          // Remove the typingIndicator ID to prevent it from being deleted
          assistantMessageDiv.removeAttribute('id');
          this.ui.updateMessageContent(assistantMessageDiv, finalContent);
          if (serverMessageId) {
            assistantMessageDiv.setAttribute('data-message-id', serverMessageId);
          }
          // Mark typing as complete
          this.ui.isTyping = false;
          this.ui.sendBtn.disabled = false;
          this.ui.messages.push({
            content: finalContent,
            type: 'assistant',
            timestamp: Date.now(),
            messageId: serverMessageId || messageId
          });
        },
        // onError
        (error) => {
          assistantMessageDiv.classList.remove('typing');
          assistantMessageDiv.removeAttribute('id');
          this.ui.updateMessageContent(assistantMessageDiv, this.i18n.connectionError);
          this.ui.isTyping = false;
          this.ui.sendBtn.disabled = false;
          console.error('AI response error:', error);
        },
        // onToolComplete
        (callId) => {
          // Mark specific tool as done when its output is received
          const toolId = activeToolCalls.get(callId);
          if (toolId) {
            this.ui.markToolCallDone(toolId);
            console.log('Tool completed:', callId, '-> toolId:', toolId);
          }
        }
      );
    } catch (error) {
      assistantMessageDiv.classList.remove('typing');
      assistantMessageDiv.removeAttribute('id');
      this.ui.updateMessageContent(assistantMessageDiv, this.i18n.sendError);
      this.ui.isTyping = false;
      this.ui.sendBtn.disabled = false;
      console.error('Send message error:', error);
    }
  }

  /**
   * Clear conversation history
   */
  async clearConversation() {
    if (!confirm(this.i18n.clearConfirm)) {
      return;
    }

    const success = await this.api.clearConversation();

    if (success) {
      // Clear UI
      this.ui.clearMessages();

      // Add welcome message back
      const welcomeDiv = document.createElement('div');
      welcomeDiv.className = 'ask-ai-welcome';
      welcomeDiv.innerHTML = this.i18n.welcomeMessage;
      this.ui.messagesContainer.appendChild(welcomeDiv);

      console.log('Conversation cleared successfully');
    } else {
      alert(this.i18n.clearFailed);
    }
  }
}

// Initialize the widget when DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
  // Check if we're in a Sphinx documentation page
  if (document.body.classList.contains('furo') || document.querySelector('.furo')) {
    new AskAIWidget();
  } else {
    // Fallback for other themes
    setTimeout(() => {
      new AskAIWidget();
    }, 1000);
  }
});

// Export for potential external usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AskAIWidget;
}

export default AskAIWidget;
