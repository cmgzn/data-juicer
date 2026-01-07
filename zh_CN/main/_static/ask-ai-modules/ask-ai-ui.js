/**
 * Ask AI Widget - UI Management Module
 */

export class AskAIUI {
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
