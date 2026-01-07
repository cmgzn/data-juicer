/**
 * Ask AI Widget - Internationalization Module
 */

export const I18N = {
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
export function detectLanguage() {
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
