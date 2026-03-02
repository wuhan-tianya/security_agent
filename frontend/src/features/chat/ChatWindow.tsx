import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Terminal, Cpu, AlertCircle, Play, Plus, MessageSquare } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { CHAT_STREAM_URL, getSessions, getSessionMemory, type Session } from '../../api';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  type?: 'text' | 'tool_call' | 'tool_result' | 'error' | 'info';
  metadata?: any;
}

const ChatWindow = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // Session State
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState<string>(() => {
      const stored = localStorage.getItem('current_session_id');
      return stored || `session-${Math.random().toString(36).substring(7)}`;
  });
  const [isSessionsLoading, setIsSessionsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch sessions on mount
  useEffect(() => {
    fetchSessions();
  }, []);

  // Load session memory when ID changes
  useEffect(() => {
    if (sessionId) {
        localStorage.setItem('current_session_id', sessionId);
        loadSessionHistory(sessionId);
    }
  }, [sessionId]);

  const fetchSessions = async () => {
      setIsSessionsLoading(true);
      try {
          const data = await getSessions();
          setSessions(data);
      } catch (e) {
          console.error("Failed to fetch sessions", e);
      } finally {
          setIsSessionsLoading(false);
      }
  };

  const loadSessionHistory = async (id: string) => {
      // If it's a new random session that doesn't exist in backend yet, don't try to fetch
      const exists = sessions.find(s => s.session_id === id);
      if (!exists && sessions.length > 0 && !id.startsWith('session-')) {
           // It might be a new valid ID, but let's be safe. 
           // Actually, if user selects from dropdown, it exists. 
           // If we just created it locally, it doesn't exist yet.
      }

      try {
          const memory = await getSessionMemory(id);
          if (memory && memory.recent_messages) {
              const history: Message[] = memory.recent_messages.map((msg: any, index: number) => {
                  let metadata = undefined;
                  if (msg.tool_json) {
                      try {
                          metadata = JSON.parse(msg.tool_json);
                      } catch (e) {
                          console.warn('Failed to parse tool_json', e);
                          metadata = { raw: msg.tool_json, error: 'JSON parse error' };
                      }
                  }
                  return {
                      id: `hist-${index}-${Date.now()}`,
                      role: msg.role,
                      content: msg.content,
                      timestamp: msg.ts || new Date().toLocaleTimeString(),
                      type: 'text', // Simple mapping for now
                      metadata
                  };
              });
              setMessages(history);
          } else {
              setMessages([]);
          }
      } catch (e) {
          // Likely session doesn't exist yet (new session), so empty history
          setMessages([]);
      }
  };

  const createNewSession = () => {
      const newId = `session-${Math.random().toString(36).substring(7)}`;
      setSessionId(newId);
      setMessages([]);
      inputRef.current?.focus();
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toLocaleTimeString(),
      type: 'text'
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // Optimistically add to session list if it's new
    if (!sessions.find(s => s.session_id === sessionId)) {
        setSessions(prev => [{ 
            session_id: sessionId, 
            created_at: new Date().toISOString(), 
            updated_at: new Date().toISOString() 
        }, ...prev]);
    }

    try {
      const response = await fetch(CHAT_STREAM_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          user_input: userMessage.content,
          model: 'gpt-4o-mini',
        }),
      });

      if (!response.body) throw new Error('ReadableStream not supported');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let currentEventType: string | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        // Keep the last partial line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmedLine = line.trim();
          if (!trimmedLine) {
             currentEventType = null;
             continue;
          }

          if (line.startsWith('event: ')) {
             currentEventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();
            if (dataStr === '[DONE]') continue;
            
            try {
              const data = JSON.parse(dataStr);
              // Combine event type with data for the handler
              // If the data is an object, we merge it. If it's a primitive (unlikely given backend), we wrap it.
              const eventObj = typeof data === 'object' && data !== null ? data : { data };
              eventObj.type = currentEventType; 
              handleSSEEvent(eventObj);
            } catch (e) {
              console.error('Error parsing SSE event', e);
            }
          }
        }
      }
      // Refresh session list after chat (to update timestamps or add new)
      fetchSessions();
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'system',
        content: '连接错误，请重试。',
        timestamp: new Date().toLocaleTimeString(),
        type: 'error'
      }]);
    } finally {
      setIsLoading(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const handleSSEEvent = (event: any) => {
      setMessages(prev => {
          const lastMsg = prev[prev.length - 1];
          const timestamp = new Date().toLocaleTimeString();

          switch (event.type) {
              case 'run_started':
                  return [...prev, {
                      id: `run-${Date.now()}`,
                      role: 'system',
                      content: '任务已启动...',
                      timestamp,
                      type: 'info'
                  }];

              case 'llm_token':
                  // If the last message is an assistant text message, append to it
                  if (lastMsg && lastMsg.role === 'assistant' && lastMsg.type === 'text') {
                      return [
                          ...prev.slice(0, -1),
                          { ...lastMsg, content: lastMsg.content + (event.token || '') }
                      ];
                  } else {
                      // Otherwise start a new assistant message
                      return [...prev, {
                          id: `msg-${Date.now()}`,
                          role: 'assistant',
                          content: event.token || '',
                          timestamp,
                          type: 'text'
                      }];
                  }

              case 'mcp_call_started':
                  return [...prev, {
                      id: `tool-${Date.now()}`,
                      role: 'system',
                      content: `正在调用工具: ${event.tool || '未知'}`,
                      timestamp,
                      type: 'tool_call',
                      metadata: event
                  }];

              case 'mcp_call_finished':
                  // Update the previous tool call message if possible, or just append result
                  // For simplicity, we append a result message
                  return [...prev, {
                      id: `tool-res-${Date.now()}`,
                      role: 'system',
                      content: `工具执行完成: ${event.tool}`,
                      timestamp,
                      type: 'tool_result',
                      metadata: event
                  }];
            
              case 'mcp_call_failed':
                   return [...prev, {
                      id: `tool-fail-${Date.now()}`,
                      role: 'system',
                      content: `工具调用失败: ${event.message || event.error_code}`,
                      timestamp,
                      type: 'error',
                      metadata: event
                  }];

              case 'reasoning_trace':
                  // Format reasoning trace for display
                  let traceContent = `思考: ${event.decision}`;
                  if (event.decision === 'intent_classified') {
                      traceContent = `意图分析: ${event.security_intent ? '安全相关' : '普通查询'}`;
                  } else if (event.decision === 'skill_result_reflected') {
                      traceContent = `正在反思工具结果...`;
                  } else if (event.decision === 'no_tool_selected') {
                       traceContent = `未找到合适的工具。`;
                  }
                  
                  return [...prev, {
                      id: `trace-${Date.now()}`,
                      role: 'system',
                      content: traceContent,
                      timestamp,
                      type: 'info',
                      metadata: event
                  }];

              case 'skills_discovered':
                  return [...prev, {
                      id: `skills-${Date.now()}`,
                      role: 'system',
                      content: `发现 ${event.count} 个可用工具: ${event.tools.join(', ')}`,
                      timestamp,
                      type: 'info',
                      metadata: event
                  }];

              case 'run_error':
                   return [...prev, {
                      id: `err-${Date.now()}`,
                      role: 'system',
                      content: `运行错误: ${event.message || event.error_code}`,
                      timestamp,
                      type: 'error',
                      metadata: event
                  }];

              case 'memory_read':
                  return [...prev, {
                      id: `mem-${Date.now()}`,
                      role: 'system',
                      content: `上下文加载: ${event.message_count} 条消息${event.has_summary ? ' + 摘要' : ''}`,
                      timestamp,
                      type: 'info',
                      metadata: event
                  }];
              
              case 'memory_write':
                  // Optionally show save confirmation, or skip
                  return prev;

              case 'run_finished':
                   return [...prev, {
                      id: `fin-${Date.now()}`,
                      role: 'system',
                      content: '任务完成。',
                      timestamp,
                      type: 'info'
                  }];

              default:
                  return prev;
          }
      });
  };

  return (
    <div className="flex flex-col h-full max-w-5xl mx-auto w-full">
      {/* Session Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-security-surface/50">
          <div className="flex items-center space-x-2 text-security-primary">
              <Terminal className="w-5 h-5" />
              <span className="font-bold tracking-wider">COMMAND_CENTER</span>
          </div>

          <div className="flex items-center space-x-3">
              <div className="flex items-center bg-black border border-gray-700 rounded px-2 py-1">
                  <MessageSquare className="w-4 h-4 text-gray-400 mr-2" />
                  <select 
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      disabled={isSessionsLoading}
                      className="bg-transparent text-sm text-security-text focus:outline-none min-w-[200px] max-w-[300px] appearance-none cursor-pointer disabled:opacity-50"
                  >
                      {/* Always show current if not in list yet */}
                      {!sessions.find(s => s.session_id === sessionId) && (
                          <option value={sessionId}>{sessionId} (New)</option>
                      )}
                      {sessions.map(s => (
                          <option key={s.session_id} value={s.session_id}>
                              {s.session_id}
                          </option>
                      ))}
                  </select>
              </div>
              
              <button 
                  onClick={createNewSession}
                  className="p-1.5 hover:bg-gray-800 rounded text-security-primary hover:text-white transition-colors"
                  title="New Session"
              >
                  <Plus className="w-4 h-4" />
              </button>
          </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-security-dim scrollbar-track-transparent pb-20">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
            <div className={`max-w-[85%] rounded p-3 relative group overflow-hidden ${
              msg.role === 'user' 
                ? 'bg-security-primary/10 border border-security-primary/30 text-security-text' 
                : msg.role === 'system'
                    ? msg.type === 'error' 
                        ? 'bg-red-900/20 border border-red-800 text-red-400 font-mono text-xs w-full max-w-full'
                        : 'bg-gray-900/50 border border-gray-700 text-xs font-mono text-gray-400 w-full max-w-full'
                : 'bg-security-surface border border-gray-800 text-security-text shadow-lg shadow-black/50'
            }`}>
              <div className="flex items-center space-x-2 mb-1 opacity-50 text-[10px] tracking-wider uppercase">
                 {msg.role === 'assistant' && <Cpu className="w-3 h-3" />}
                 {msg.role === 'system' && (msg.type === 'error' ? <AlertCircle className="w-3 h-3 text-red-500" /> : <Terminal className="w-3 h-3" />)}
                 {msg.role === 'user' && <span className="text-security-primary">USER</span>}
                 {msg.role !== 'user' && <span>{msg.role}</span>}
                 <span className="ml-auto">{msg.timestamp}</span>
              </div>
              
              <div className="font-mono text-sm leading-relaxed markdown-content break-words">
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                    {msg.content}
                </ReactMarkdown>
              </div>
              
              {/* Tool Call Arguments */}
              {msg.type === 'tool_call' && msg.metadata?.arguments && (
                  <div className="mt-2 p-2 bg-black/30 rounded border border-gray-800 text-xs overflow-x-auto">
                      <div className="text-gray-500 mb-1 font-bold">INPUT:</div>
                      <pre className="text-security-primary">{JSON.stringify(msg.metadata.arguments, null, 2)}</pre>
                  </div>
              )}
              
              {/* Tool Result Output */}
              {msg.type === 'tool_result' && (
                  <div className="mt-2">
                      <details className="group">
                          <summary className="cursor-pointer text-xs text-gray-500 hover:text-security-primary transition-colors flex items-center select-none">
                              <span>▶ SHOW_OUTPUT</span>
                          </summary>
                          <div className="mt-2 p-2 bg-black/30 rounded border border-gray-800 text-xs overflow-x-auto max-h-96">
                              <pre className="text-gray-300">{
                                  typeof (msg.metadata?.result ?? msg.metadata) === 'string' 
                                      ? (msg.metadata?.result ?? msg.metadata)
                                      : JSON.stringify(msg.metadata?.result ?? msg.metadata, null, 2)
                              }</pre>
                          </div>
                      </details>
                  </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
            <div className="flex justify-start animate-pulse">
                <div className="bg-security-surface border border-gray-800 p-2 rounded flex items-center space-x-2">
                    <div className="w-2 h-2 bg-security-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 bg-security-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 bg-security-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
            </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-gray-800 bg-security-bg">
        <form onSubmit={handleSubmit} className="flex space-x-2 relative">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Input command..."
            className="flex-1 bg-black border border-gray-700 rounded p-3 pl-4 text-security-text font-mono focus:outline-none focus:border-security-primary focus:ring-1 focus:ring-security-primary transition-all placeholder-gray-600"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-security-primary hover:bg-green-400 text-black px-6 rounded font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center min-w-[100px]"
          >
            {isLoading ? <Cpu className="w-5 h-5 animate-spin" /> : <div className="flex items-center">EXEC <Play className="w-3 h-3 ml-1 fill-current" /></div>}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatWindow;
