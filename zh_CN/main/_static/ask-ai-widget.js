/**
 * Ask AI Widget - Bundled Version
 * Generated from modular source files
 */
var AskAIWidget = (function () {
  'use strict';

  /**
   * Ask AI Widget - Internationalization Module
   */

  const I18N = {
    en: {
      title: 'Data-Juicer Q&A Copilot',
      buttonTitle: 'Ask Juicer',
      clearTitle: 'Restart conversation',
      expandTitle: 'Expand/Collapse',
      collapseTitle: 'Collapse',
      minimizeTitle: 'Minimize',
      sendTitle: 'Send message',
      inputPlaceholder: 'Type your question here...',
      welcomeMessage: '👋 Hi! I\'m Juicer. Ask me anything about Data-Juicer!',
      welcomeConnected: '👋 Hi! I\'m Juicer. <span style="color: #28a745;">🟢 Connected</span><br>Ask me anything about Data-Juicer!',
      welcomeOffline: '👋 Hi! I\'m Juicer. <span style="color: #dc3545;">🔴 Offline Mode</span><br>Please ensure the API service is running.',
      clearConfirm: 'Are you sure you want to clear the conversation history? This action cannot be undone.',
      clearFailed: 'Failed to clear conversation history. Please try again.',
      clearError: 'Error clearing conversation history. Please check your connection and try again.',
      sendError: 'Sorry, I encountered an error. Please try again later.',
      noResponse: 'I processed your request but no valid response was generated. Please try again.',
      connectionError: 'Unable to connect to AI service, please check network or contact administrator.',
      offlineResponse: 'Sorry, the Q&A Bot API is not configured or currently unavailable. Please refer to the Data-Juicer documentation for information, or contact the administrator to configure the API service.',
      usingTool: 'Using',
      toolCalls: 'Tool Calls',
      done: 'Done',
      running: 'Running'
    },
    zh_CN: {
      title: 'Data-Juicer Q&A Copilot',
      buttonTitle: '询问 Juicer',
      clearTitle: '重新开始对话',
      expandTitle: '展开/收起',
      collapseTitle: '收起',
      minimizeTitle: '最小化',
      sendTitle: '发送消息',
      inputPlaceholder: '在此输入您的问题...',
      welcomeMessage: '👋 你好！我是 Juicer。问我任何关于 Data-Juicer 的问题！',
      welcomeConnected: '👋 你好！我是 Juicer。<span style="color: #28a745;">🟢 已连接</span><br>问我任何关于 Data-Juicer 的问题！',
      welcomeOffline: '👋 你好！我是 Juicer。<span style="color: #dc3545;">🔴 离线模式</span><br>请确保 API 服务正在运行。',
      clearConfirm: '确定要清除对话历史吗？此操作无法撤销。',
      clearFailed: '清除对话历史失败。请重试。',
      clearError: '清除对话历史时出错。请检查您的连接并重试。',
      sendError: '抱歉，遇到了一个错误。请稍后再试。',
      noResponse: '我处理了您的请求，但没有生成有效的响应。请重试。',
      connectionError: '无法连接到 AI 服务，请检查网络或联系管理员。',
      offlineResponse: '抱歉，Juicer API 未配置或当前不可用。请参阅 Data-Juicer 文档获取信息，或联系管理员配置 API 服务。',
      usingTool: '正在调用',
      toolCalls: '工具调用',
      done: '完成',
      running: '执行中'
    }
  };

  /**
   * Detect the current language from HTML attributes or URL
   * @returns {string} Language code (e.g., 'en' or 'zh_CN')
   */
  function detectLanguage() {
    // Try to get language from HTML lang attribute
    const htmlLang = document.documentElement.lang;
    if (htmlLang) {
      // Handle both 'zh-CN' and 'zh_CN' formats
      const normalizedLang = htmlLang.replace('-', '_');
      if (I18N[normalizedLang]) {
        return normalizedLang;
      }
      // Try just the language code (e.g., 'zh' from 'zh-CN')
      const langCode = normalizedLang.split('_')[0];
      if (langCode === 'zh') {
        return 'zh_CN';
      }
    }
    
    // Try to get language from meta tag
    const metaLang = document.querySelector('meta[name="language"]');
    if (metaLang && metaLang.content) {
      const normalizedLang = metaLang.content.replace('-', '_');
      if (I18N[normalizedLang]) {
        return normalizedLang;
      }
    }
    
    // Try to detect from URL (e.g., /zh_CN/version/page.html)
    const urlMatch = window.location.pathname.match(/\/(zh_CN|en)\//);
    if (urlMatch && I18N[urlMatch[1]]) {
      return urlMatch[1];
    }
    
    // Default to English
    return 'en';
  }

  /**
   * Ask AI Widget - API Communication Layer
   */

  class AskAIApi {
    constructor(sessionId, i18n) {
      this.sessionId = sessionId;
      this.i18n = i18n;
      this.apiConnected = false;
    }

    /**
     * Get the API base URL from configuration
     * @returns {string} API base URL
     */
    getApiBaseUrl() {
      // Prefer configuration from meta tags
      const metaApiUrl = document.querySelector('meta[name="juicer-api-url"]');
      if (metaApiUrl && metaApiUrl.content) {
        return metaApiUrl.content;
      }

      // Get configuration from global variables
      if (window.JUICER_API_URL) {
        return window.JUICER_API_URL;
      }

      const currentHost = window.location.hostname;

      // Default to localhost for development
      if (currentHost === 'localhost' || currentHost === '127.0.0.1') {
        return 'http://localhost:8080';
      }

      return 'http://localhost:8080';
    }

    /**
     * Check if API service is available
     * @returns {Promise<boolean>} True if API is connected
     */
    async checkApiConnection() {
      try {
        const response = await fetch(`${this.getApiBaseUrl()}/health`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          }
        });

        if (response.ok) {
          const data = await response.json();
          this.apiConnected = data.status === 'healthy';
        } else {
          this.apiConnected = false;
        }
      } catch (error) {
        console.warn('Failed to connect to API:', error);
        this.apiConnected = false;
      }
      return this.apiConnected;
    }

    /**
     * Load conversation history from server
     * @returns {Promise<Array>} Array of historical messages
     */
    async loadConversationHistory() {
      if (!this.apiConnected) {
        console.log('API not connected, skipping history load');
        return [];
      }

      try {
        const requestBody = {
          input: [
            {
              role: "user",
              content: [
                {
                  type: "text",
                  text: "",
                },
              ],
            },
          ],
          session_id: this.sessionId,
          user_id: this.sessionId,
        };
        console.log('Loading conversation history for session:', this.sessionId);

        const response = await fetch(`${this.getApiBaseUrl()}/memory`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(requestBody)
        });

        if (response.ok) {
          const data = await response.json();
          const messages = data.messages || [];
          console.log('Loaded', messages.length, 'historical messages');
          return messages;
        } else {
          console.warn('Failed to load conversation history:', response.status);
          return [];
        }
      } catch (error) {
        console.warn('Error loading conversation history:', error);
        return [];
      }
    }

    /**
     * Clear conversation history on server
     * @returns {Promise<boolean>} True if successful
     */
    async clearConversation() {
      try {
        const requestBody = {
          input: [
            {
              role: "user",
              content: [
                {
                  type: "text",
                  text: "",
                },
              ],
            },
          ],
          session_id: this.sessionId,
          user_id: this.sessionId,
        };

        const response = await fetch(`${this.getApiBaseUrl()}/clear`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-session-id': this.sessionId
          },
          body: JSON.stringify(requestBody)
        });

        if (response.ok) {
          console.log('Conversation history cleared successfully');
          return true;
        } else {
          console.error('Failed to clear conversation history:', response.status);
          return false;
        }
      } catch (error) {
        console.error('Error clearing conversation history:', error);
        return false;
      }
    }

    /**
     * Get AI response using streaming
     * @param {string} message - User message
     * @param {Function} onContentUpdate - Callback for content updates (text)
     * @param {Function} onToolUse - Callback for tool usage (toolName, toolArgs, callId)
     * @param {Function} onComplete - Callback when stream completes (finalContent, messageId)
     * @param {Function} onError - Callback for errors (error)
     * @param {Function} onToolComplete - Callback when tool execution completes (callId)
     */
    async getAIResponseStream(message, onContentUpdate, onToolUse, onComplete, onError, onToolComplete) {
      let currentStreamContent = '';
      let messageId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      let hasReceivedContent = false;

      try {
        const requestBody = {
          input: [
            {
              role: "user",
              content: [
                {
                  type: "text",
                  text: message.trim(),
                },
              ],
            },
          ],
          session_id: this.sessionId,
          user_id: this.sessionId,
        };

        console.log('Sending streaming request to:', `${this.getApiBaseUrl()}/process`);
        console.log('Request body:', requestBody);

        const response = await fetch(`${this.getApiBaseUrl()}/process`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-session-id': this.sessionId,
          },
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.trim() || !line.startsWith('data:')) continue;

            const jsonString = line.slice(5).trim();
            if (!jsonString) continue;

            try {
              const data = JSON.parse(jsonString);
              console.log('Parsed SSE event:', data);

              // End of stream
              if (data.object === "response" && data.status === "completed") {
                console.log('Stream ended normally.');
                break;
              }

              // Handle errors
              if (data.object === "response" && data.error) {
                throw new Error(data.error.message || 'An error occurred during processing.');
              }

              // Handle tool use: plugin_call
              if (data.object === "message" && data.type === "plugin_call") {
                if (Array.isArray(data.content)) {
                  // content is an array with 2 elements:
                  // index 0: has name, call_id, but empty arguments
                  // index 1: has complete arguments
                  const toolCallWithId = data.content[0]?.type === "data" ? data.content[0].data : null;
                  const toolCallWithArgs = data.content.length > 1 ? data.content[1] : data.content[0];
                  const toolCall = toolCallWithArgs?.type === "data" ? toolCallWithArgs.data : null;
                  
                  if (toolCall && onToolUse) {
                    const toolName = toolCall.name || 'Unknown Tool';
                    let toolArgs = toolCall.arguments || {};
                    
                    // Parse arguments if it's a JSON string
                    if (typeof toolArgs === 'string') {
                      try {
                        toolArgs = JSON.parse(toolArgs);
                      } catch (e) {
                        console.warn('Failed to parse tool arguments:', e);
                        toolArgs = {};
                      }
                    }
                    
                    // Get call_id from the first element
                    const callId = toolCallWithId?.call_id || null;
                    
                    console.log('Tool call detected:', { toolName, toolArgs, callId });
                    onToolUse(toolName, toolArgs, callId);
                  }
                }
              }

              // Handle tool output: plugin_call_output
              if (data.object === "message" && data.type === "plugin_call_output") {
                if (Array.isArray(data.content)) {
                  const outputData = data.content.find(item => item.type === "data")?.data;
                  const callId = outputData?.call_id || null;
                  const output = outputData?.output;
                  
                  if (output && callId && onToolComplete) {
                    console.log('Tool output received for call_id:', callId);
                    onToolComplete(callId);
                  }
                }
              }

              // Handle incremental text content
              if (
                data.object === "content" &&
                data.type === "text" &&
                data.delta === true &&
                data.text !== undefined
              ) {
                if (!hasReceivedContent) {
                  currentStreamContent = '';
                  hasReceivedContent = true;
                }
                currentStreamContent += data.text;
                if (onContentUpdate) {
                  onContentUpdate(currentStreamContent);
                }
              }

              // Final message delivery
              if (
                data.object === "message" &&
                data.status === "completed" &&
                data.role === "assistant" &&
                Array.isArray(data.content)
              ) {
                const fullText = data.content
                  .filter(c => c.type === "text")
                  .map(c => c.text)
                  .join('');
                
                if (fullText && !hasReceivedContent) {
                  currentStreamContent = fullText;
                  hasReceivedContent = true;
                  if (onContentUpdate) {
                    onContentUpdate(currentStreamContent);
                  }
                }

                // Use server-provided message ID
                if (data.id) {
                  messageId = data.id;
                  console.log('Using server message ID:', data.id);
                }
              }
            } catch (parseError) {
              console.warn('Failed to parse SSE data:', parseError, 'Raw:', jsonString);
            }
          }
        }

        // Final callback
        if (!hasReceivedContent || !currentStreamContent.trim()) {
          currentStreamContent = this.i18n.noResponse;
        }
        
        if (onComplete) {
          onComplete(currentStreamContent, messageId);
        }

      } catch (error) {
        console.error('Fetch error:', error);
        if (onError) {
          onError(error);
        }
      }
    }

    /**
     * Get offline response when API is not available
     * @param {string} message - User message (unused)
     * @returns {string} Offline response message
     */
    getOfflineResponse(message) {
      return this.i18n.offlineResponse;
    }
  }

  /**
   * Ask AI Widget - UI Management Module
   */

  class AskAIUI {
    constructor(i18n) {
      this.i18n = i18n;
      this.isOpen = false;
      this.isExpanded = false;
      this.isTyping = false;
      this.messages = [];
      
      // DOM references (will be set after createWidget)
      this.button = null;
      this.modal = null;
      this.closeBtn = null;
      this.clearBtn = null;
      this.expandBtn = null;
      this.messagesContainer = null;
      this.input = null;
      this.sendBtn = null;
    }

    /**
     * Create the widget HTML structure
     */
    createWidget() {
      const widget = document.createElement('div');
      widget.className = 'ask-ai-widget';
      widget.innerHTML = `
      <!-- Ask AI Button -->
      <button class="ask-ai-button" id="askAiButton" title="${this.i18n.buttonTitle}">
        🤖
      </button>

      <!-- Chat Modal -->
      <div class="ask-ai-modal" id="askAiModal">
        <!-- Header -->
        <div class="ask-ai-header">
          <h3 class="ask-ai-title">${this.i18n.title}</h3>
          <div class="ask-ai-header-buttons">
            <button class="ask-ai-clear" id="askAiClear" title="${this.i18n.clearTitle}"><i class="fa-solid fa-arrows-rotate"></i></button>
            <button class="ask-ai-expand" id="askAiExpand" title="${this.i18n.expandTitle}"><i class="fa-solid fa-expand"></i></button>
            <button class="ask-ai-close" id="askAiClose" title="${this.i18n.minimizeTitle}"><i class="fa-solid fa-minus"></i></button>
          </div>
        </div>

        <!-- Messages Area -->
        <div class="ask-ai-messages" id="askAiMessages">
          <div class="ask-ai-welcome">
            ${this.i18n.welcomeMessage}
          </div>
        </div>

        <!-- Input Area -->
        <div class="ask-ai-input-area">
          <textarea 
            class="ask-ai-input" 
            id="askAiInput" 
            placeholder="${this.i18n.inputPlaceholder}"
            rows="1"
          ></textarea>
          <button class="ask-ai-send" id="askAiSend" title="${this.i18n.sendTitle}">
            ➤
          </button>
        </div>
      </div>
    `;

      document.body.appendChild(widget);

      // Store references
      this.button = document.getElementById('askAiButton');
      this.modal = document.getElementById('askAiModal');
      this.closeBtn = document.getElementById('askAiClose');
      this.clearBtn = document.getElementById('askAiClear');
      this.expandBtn = document.getElementById('askAiExpand');
      this.messagesContainer = document.getElementById('askAiMessages');
      this.input = document.getElementById('askAiInput');
      this.sendBtn = document.getElementById('askAiSend');
    }

    /**
     * Bind event handlers
     * @param {Object} callbacks - Object containing callback functions
     */
    bindEvents(callbacks) {
      const {
        onToggle,
        onClose,
        onClear,
        onExpand,
        onSend,
        onInputChange
      } = callbacks;

      // Toggle modal
      if (onToggle) {
        this.button.addEventListener('click', onToggle);
      }

      // Close modal
      if (onClose) {
        this.closeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          onClose();
        });
      }

      // Clear conversation
      if (onClear) {
        this.clearBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          onClear();
        });
      }

      // Expand/collapse
      if (onExpand) {
        this.expandBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          onExpand();
        });
      }

      // Send message
      if (onSend) {
        this.sendBtn.addEventListener('click', onSend);

        // Handle Enter key in input
        this.input.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onSend();
          }
        });
      }

      // Auto-resize textarea
      this.input.addEventListener('input', () => this.autoResizeInput());
      if (onInputChange) {
        this.input.addEventListener('input', onInputChange);
      }

      // Close modal when clicking outside
      document.addEventListener('click', (e) => {
        if (this.isOpen &&
          !this.modal.contains(e.target) &&
          !this.button.contains(e.target) &&
          !this.expandBtn.contains(e.target) &&
          !this.closeBtn.contains(e.target) &&
          !this.clearBtn.contains(e.target)) {
          if (onClose) onClose();
        }
      });

      // Handle escape key
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.isOpen) {
          if (onClose) onClose();
        }
      });
    }

    /**
     * Open the modal
     */
    openModal() {
      this.isOpen = true;
      this.modal.classList.add('show');
      this.input.focus();
      this.scrollToBottom();
    }

    /**
     * Close the modal
     */
    closeModal() {
      this.isOpen = false;
      this.modal.classList.remove('show');
    }

    /**
     * Toggle modal open/close
     */
    toggleModal() {
      if (this.isOpen) {
        this.closeModal();
      } else {
        this.openModal();
      }
    }

    /**
     * Toggle expand/collapse state
     */
    toggleExpand() {
      this.isExpanded = !this.isExpanded;

      if (this.isExpanded) {
        this.modal.classList.add('expanded');
        const icon = this.expandBtn.querySelector('i, svg');
        if (icon) {
          icon.classList.remove('fa-expand');
          icon.classList.add('fa-compress');
        }
        this.expandBtn.title = this.i18n.collapseTitle;
      } else {
        this.modal.classList.remove('expanded');
        const icon = this.expandBtn.querySelector('i, svg');
        if (icon) {
          icon.classList.remove('fa-compress');
          icon.classList.add('fa-expand');
        }
        this.expandBtn.title = this.i18n.expandTitle;
      }
    }

    /**
     * Auto-resize the input textarea
     */
    autoResizeInput() {
      this.input.style.height = 'auto';
      this.input.style.height = Math.min(this.input.scrollHeight, 100) + 'px';
    }

    /**
     * Add a message to the chat
     * @param {string} content - Message content
     * @param {string} type - Message type ('user' or 'assistant')
     * @param {string} messageId - Optional message ID
     * @returns {HTMLElement} The created message element
     */
    addMessage(content, type, messageId = null) {
      const messageDiv = document.createElement('div');
      messageDiv.className = `ask-ai-message ${type}`;

      // For assistant messages, render as markdown; for user messages, keep as plain text
      if (type === 'assistant') {
        messageDiv.innerHTML = this.renderMarkdown(content);
      } else {
        messageDiv.textContent = content;
      }

      // Generate unique message ID if not provided
      const msgId = messageId || `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      messageDiv.setAttribute('data-message-id', msgId);

      this.messagesContainer.appendChild(messageDiv);
      this.scrollToBottom();

      // Store message
      this.messages.push({ content, type, timestamp: Date.now(), messageId: msgId });

      return messageDiv;
    }

    /**
     * Update an existing assistant message
     * @param {string} messageId - Message ID to update
     * @param {string} content - New content
     */
    updateMessage(messageId, content) {
      const messageDiv = this.messagesContainer.querySelector(`[data-message-id="${messageId}"]`);
      if (messageDiv) {
        messageDiv.innerHTML = this.renderMarkdown(content);
        this.scrollToBottom();
      }
    }

    /**
     * Update message content while preserving tool calls
     * @param {HTMLElement} messageDiv - Message element
     * @param {string} content - New content
     */
    updateMessageContent(messageDiv, content) {
      if (!messageDiv) return;

      // Check if there's a tool calls container
      const toolContainer = messageDiv.querySelector('.tool-calls-inline');
      
      if (toolContainer) {
        // Find or create content wrapper
        let contentWrapper = messageDiv.querySelector('.message-content');
        if (!contentWrapper) {
          contentWrapper = document.createElement('div');
          contentWrapper.className = 'message-content';
          messageDiv.appendChild(contentWrapper);
        }
        // Update only the content part
        contentWrapper.innerHTML = this.renderMarkdown(content);
      } else {
        // No tool calls, safe to replace entire innerHTML
        messageDiv.innerHTML = this.renderMarkdown(content);
      }
      
      this.scrollToBottom();
    }

    /**
     * Show typing indicator
     * @returns {HTMLElement} The typing indicator element
     */
    showTypingIndicator() {
      this.isTyping = true;
      this.sendBtn.disabled = true;

      const typingDiv = document.createElement('div');
      typingDiv.className = 'ask-ai-message assistant typing';
      typingDiv.id = 'typingIndicator';
      typingDiv.innerHTML = `
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    `;

      this.messagesContainer.appendChild(typingDiv);
      this.scrollToBottom();

      return typingDiv;
    }

    /**
     * Hide typing indicator
     */
    hideTypingIndicator() {
      this.isTyping = false;
      this.sendBtn.disabled = false;

      const typingIndicator = document.getElementById('typingIndicator');
      if (typingIndicator) {
        typingIndicator.remove();
      }
    }

    /**
     * Add tool call info inside message bubble
     * @param {string} toolName - Name of the tool being used
     * @param {Object} toolArgs - Tool arguments
     * @param {HTMLElement} messageDiv - Message element to add tool info to
     */
    addToolCall(toolName, toolArgs, messageDiv) {
      if (!messageDiv) return;

      // Find or create tool calls container inside message
      let toolContainer = messageDiv.querySelector('.tool-calls-inline');
      if (!toolContainer) {
        toolContainer = document.createElement('div');
        toolContainer.className = 'tool-calls-inline';
        
        // Add collapsible header
        const header = document.createElement('div');
        header.className = 'tool-calls-inline-header';
        header.innerHTML = `
        <span class="tool-calls-inline-title">🔧 ${this.i18n.toolCalls}</span>
        <button class="tool-calls-inline-toggle">▼</button>
      `;
        toolContainer.appendChild(header);
        
        // Add content container
        const content = document.createElement('div');
        content.className = 'tool-calls-inline-content';
        toolContainer.appendChild(content);
        
        messageDiv.insertBefore(toolContainer, messageDiv.firstChild);
        
        // Add toggle functionality
        const toggleBtn = header.querySelector('.tool-calls-inline-toggle');
        toggleBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const isCollapsed = content.style.display === 'none';
          content.style.display = isCollapsed ? 'block' : 'none';
          toggleBtn.textContent = isCollapsed ? '▼' : '▶';
          toolContainer.classList.toggle('collapsed', !isCollapsed);
        });
      }

      // Get content container
      const content = toolContainer.querySelector('.tool-calls-inline-content');

      // Create tool call item
      const toolId = `tool_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      const toolItem = document.createElement('div');
      toolItem.className = 'tool-call-inline running';
      toolItem.setAttribute('data-tool-id', toolId);
      
      // Format arguments for display (compact)
      let argsPreview = '';
      if (toolArgs && Object.keys(toolArgs).length > 0) {
        const argsList = Object.entries(toolArgs).map(([key, value]) => {
          const displayValue = typeof value === 'string' && value.length > 50 
            ? value.substring(0, 50) + '...' 
            : JSON.stringify(value);
          return `${key}: ${this.escapeHtml(displayValue)}`;
        }).join(', ');
        argsPreview = `<div class="tool-args-preview">${argsList}</div>`;
      }

      toolItem.innerHTML = `
      <div class="tool-inline-header">
        <span class="tool-name-inline">${this.escapeHtml(toolName)}</span>
        <span class="tool-status-inline running"></span>
      </div>
      ${argsPreview}
    `;

      content.appendChild(toolItem);
      this.scrollToBottom();

      return toolId;
    }

    /**
     * Mark a tool call as completed
     * @param {string} toolId - Tool ID to mark as done
     */
    markToolCallDone(toolId) {
      const toolItem = this.messagesContainer.querySelector(`[data-tool-id="${toolId}"]`);
      if (toolItem) {
        toolItem.classList.remove('running');
        const statusSpan = toolItem.querySelector('.tool-status-inline');
        if (statusSpan) {
          statusSpan.textContent = 'Done';
          statusSpan.classList.remove('running');
        }
      }
    }

    /**
     * Scroll messages container to bottom
     */
    scrollToBottom() {
      setTimeout(() => {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
      }, 100);
    }

    /**
     * Clear all messages from UI
     */
    clearMessages() {
      this.messages = [];
      const existingMessages = this.messagesContainer.querySelectorAll('.ask-ai-message');
      existingMessages.forEach(msg => msg.remove());

      // Remove welcome message if it exists
      const welcomeElement = this.messagesContainer.querySelector('.ask-ai-welcome');
      if (welcomeElement) {
        welcomeElement.remove();
      }
    }

    /**
     * Add welcome message
     * @param {boolean} apiConnected - Whether API is connected
     */
    addWelcomeMessage(apiConnected) {
      // Only add welcome message if no history was loaded
      if (this.messages.length === 0) {
        const welcomeElement = this.messagesContainer.querySelector('.ask-ai-welcome');
        if (welcomeElement) {
          if (apiConnected) {
            welcomeElement.innerHTML = this.i18n.welcomeConnected;
          } else {
            welcomeElement.innerHTML = this.i18n.welcomeOffline;
          }
        }
      } else {
        // Remove welcome message if we have history
        const welcomeElement = this.messagesContainer.querySelector('.ask-ai-welcome');
        if (welcomeElement) {
          welcomeElement.remove();
        }
      }
    }

    /**
     * Render markdown text to HTML
     * @param {string} text - Markdown text
     * @returns {string} HTML string
     */
    renderMarkdown(text) {
      if (!text) return '';

      try {
        const renderer = new marked.Renderer();

        // Custom heading renderer
        renderer.heading = (token) => {
          const size = ['1.3em', '1.2em', '1.1em', '1em', '0.95em', '0.9em'];
          const escapedText = this.escapeHtml(token.text);
          return `<h${token.depth} style="font-size: ${size[token.depth - 1]}; margin: 0.3em 0;">
        ${escapedText}
      </h${token.depth}>`;
        };

        // Custom link renderer - open in new tab
        renderer.link = (token) => {
          const href = token.href;
          const title = token.title ? ` title="${this.escapeHtml(token.title)}"` : '';
          const text = token.text;
          return `<a href="${href}"${title} target="_blank" rel="noopener noreferrer">${text}</a>`;
        };

        return marked.parse(text, { renderer });
      } catch (error) {
        console.error('Markdown rendering error:', error);
        return this.escapeHtml(text).replace(/\n/g, '<br>');
      }
    }

    /**
     * Escape HTML special characters
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    /**
     * Observe theme changes from the Sphinx theme
     */
    observeThemeChanges() {
      // Apply initial theme
      this.updateWidgetTheme();

      // Watch for theme changes on html or body element
      const targetNode = document.documentElement || document.body;

      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.type === 'attributes' &&
            (mutation.attributeName === 'class' ||
              mutation.attributeName === 'data-theme' ||
              mutation.attributeName === 'data-bs-theme')) {
            this.updateWidgetTheme();
          }
        });
      });

      observer.observe(targetNode, {
        attributes: true,
        attributeFilter: ['class', 'data-theme', 'data-bs-theme']
      });
    }

    /**
     * Update widget theme based on page theme
     */
    updateWidgetTheme() {
      const html = document.documentElement;

      // Check various theme indicators
      const isDark = html.getAttribute('data-theme') === 'dark';

      if (isDark) {
        this.modal.classList.add('theme-dark');
        this.button.classList.add('theme-dark');
      } else {
        this.modal.classList.remove('theme-dark');
        this.button.classList.remove('theme-dark');
      }
    }

    /**
     * Get current input value
     * @returns {string} Input value
     */
    getInputValue() {
      return this.input.value;
    }

    /**
     * Clear input value
     */
    clearInput() {
      this.input.value = '';
      this.autoResizeInput();
    }
  }

  /**
   * Ask AI Widget - Main Controller
   * 
   * This is the main entry point that integrates all modules:
   * - I18N: Internationalization
   * - API: Communication with backend
   * - UI: User interface management
   */


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

  return AskAIWidget;

})();
