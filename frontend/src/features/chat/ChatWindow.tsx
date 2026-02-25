import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Terminal, Cpu, AlertCircle, Play, RefreshCw, Car } from 'lucide-react';
import { CHAT_STREAM_URL, getVehicles, type Vehicle } from '../../api';

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
  const [sessionId] = useState(`session-${Math.random().toString(36).substring(7)}`);
  
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selectedVehicleIp, setSelectedVehicleIp] = useState<string>('');
  const [isVehiclesLoading, setIsVehiclesLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const fetchVehicles = async () => {
      setIsVehiclesLoading(true);
      try {
          const data = await getVehicles();
          setVehicles(data);
      } catch (e) {
          console.error("Failed to fetch vehicles", e);
      } finally {
          setIsVehiclesLoading(false);
      }
  };

  useEffect(() => {
    fetchVehicles();
  }, []);

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
          target_vehicle_ip: selectedVehicleIp || null
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
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'system',
        content: 'Connection error. Please try again.',
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
                      content: 'Agent run started...',
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
                      content: `Running tool: ${event.tool || 'unknown'}`,
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
                      content: `Tool finished: ${event.tool}`,
                      timestamp,
                      type: 'tool_result',
                      metadata: event
                  }];
            
              case 'mcp_call_failed':
                   return [...prev, {
                      id: `tool-fail-${Date.now()}`,
                      role: 'system',
                      content: `Tool failed: ${event.message || event.error_code}`,
                      timestamp,
                      type: 'error',
                      metadata: event
                  }];

              case 'run_error':
                   return [...prev, {
                      id: `err-${Date.now()}`,
                      role: 'system',
                      content: `Run Error: ${event.message || event.error_code}`,
                      timestamp,
                      type: 'error',
                      metadata: event
                  }];
              
              case 'run_finished':
                   return [...prev, {
                      id: `fin-${Date.now()}`,
                      role: 'system',
                      content: 'Run finished.',
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
      {/* Vehicle Selection Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-security-surface/50">
          <div className="flex items-center space-x-2 text-security-primary">
              <Terminal className="w-5 h-5" />
              <span className="font-bold tracking-wider">COMMAND_CENTER</span>
          </div>
          
          <div className="flex items-center space-x-3">
              <div className="flex items-center bg-black border border-gray-700 rounded px-2 py-1">
                  <Car className="w-4 h-4 text-gray-400 mr-2" />
                  <select 
                      value={selectedVehicleIp}
                      onChange={(e) => setSelectedVehicleIp(e.target.value)}
                      className="bg-transparent text-sm text-security-text focus:outline-none min-w-[150px] appearance-none cursor-pointer"
                  >
                      <option value="">-- No Vehicle Selected --</option>
                      {vehicles.map(v => (
                          <option key={v.ip} value={v.ip}>
                              {v.vehicle_name} ({v.ip}) {v.status === 'online' ? '●' : '○'}
                          </option>
                      ))}
                  </select>
              </div>
              
              <button 
                  onClick={fetchVehicles}
                  disabled={isVehiclesLoading}
                  className="p-1.5 hover:bg-gray-800 rounded text-gray-400 hover:text-white transition-colors"
                  title="Refresh Vehicles"
              >
                  <RefreshCw className={`w-4 h-4 ${isVehiclesLoading ? 'animate-spin' : ''}`} />
              </button>
          </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-security-dim scrollbar-track-transparent pb-20">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
            <div className={`max-w-[85%] rounded p-3 relative group ${
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
              
              <div className="whitespace-pre-wrap font-mono text-sm leading-relaxed">
                {msg.content}
              </div>
              
              {/* Tool Metadata Visualization (if any) */}
              {msg.metadata && msg.type === 'tool_result' && (
                  <div className="mt-2 p-2 bg-black/30 rounded border border-gray-800 text-xs overflow-x-auto">
                      <pre>{JSON.stringify(msg.metadata.result || msg.metadata, null, 2)}</pre>
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
