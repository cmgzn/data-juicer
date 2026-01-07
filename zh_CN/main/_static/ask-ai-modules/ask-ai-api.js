/**
 * Ask AI Widget - API Communication Layer
 */

export class AskAIApi {
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
