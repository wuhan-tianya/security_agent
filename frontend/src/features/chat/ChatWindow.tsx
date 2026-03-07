import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Terminal, Cpu, AlertCircle, Play, Plus, MessageSquare, Brain, ChevronDown, Paperclip, X, FileArchive } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { CHAT_STREAM_URL, CHAT_STREAM_UPLOAD_URL, getSessions, getSessionMemory, type Session } from '../../api';

interface Message {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;
    type?: 'text' | 'tool_call' | 'tool_result' | 'error' | 'info';
    metadata?: any;
}

const ThinkingProcess = ({ content }: { content: string }) => {
    // Check if content contains <think> tag
    if (!content.includes('<think>')) {
        return (
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                {content}
            </ReactMarkdown>
        );
    }

    // Split content into parts
    const parts = [];
    let remaining = content;

    // Find all think blocks
    while (remaining.includes('<think>')) {
        const startIdx = remaining.indexOf('<think>');
        const preThink = remaining.substring(0, startIdx);

        if (preThink) {
            parts.push({ type: 'text', content: preThink });
        }

        const endIdx = remaining.indexOf('</think>');
        if (endIdx !== -1 && endIdx > startIdx) {
            const thinkContent = remaining.substring(startIdx + 7, endIdx);
            parts.push({ type: 'think', content: thinkContent, isThinking: false });
            remaining = remaining.substring(endIdx + 8);
        } else {
            // Still thinking (no closing tag)
            const thinkContent = remaining.substring(startIdx + 7);
            parts.push({ type: 'think', content: thinkContent, isThinking: true });
            remaining = '';
            break;
        }
    }

    if (remaining) {
        parts.push({ type: 'text', content: remaining });
    }

    return (
        <div className="space-y-2">
            {parts.map((part, idx) => {
                if (part.type === 'text') {
                    return (
                        <div key={idx} className="markdown-content">
                            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                                {part.content}
                            </ReactMarkdown>
                        </div>
                    );
                } else {
                    return (
                        <details
                            key={idx}
                            className="group border border-gray-700/50 rounded-lg overflow-hidden bg-black/20 my-2"
                            open={part.isThinking}
                        >
                            <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer bg-gray-900/50 hover:bg-gray-800/80 transition-colors select-none text-xs text-gray-400 font-medium list-none">
                                <div className="flex items-center gap-2 flex-1">
                                    <Brain className={`w-3.5 h-3.5 ${part.isThinking ? 'animate-pulse text-security-primary' : 'text-gray-500'}`} />
                                    <span>{part.isThinking ? '正在深度思考...' : '思考过程'}</span>
                                </div>
                                <ChevronDown className="w-3 h-3 opacity-50 group-open:rotate-180 transition-transform duration-200" />
                            </summary>
                            <div className="p-3 text-gray-400 text-xs border-t border-gray-700/30 bg-black/10 max-h-[500px] overflow-y-auto font-mono whitespace-pre-wrap break-all leading-relaxed custom-scrollbar">
                                {part.content || (part.isThinking && <span className="animate-pulse">...</span>)}
                            </div>
                        </details>
                    );
                }
            })}
        </div>
    );
};

const ChatWindow = () => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    // Session State
    const [sessions, setSessions] = useState<Session[]>([]);
    const [sessionId, setSessionId] = useState<string>(() => {
        const stored = localStorage.getItem('current_session_id');
        return stored || `session-${Math.random().toString(36).substring(7)}`;
    });
    const [isSessionsLoading, setIsSessionsLoading] = useState(false);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

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

        const fileToUpload = selectedFile;
        const displayContent = fileToUpload
            ? `${input}\n📎 已上传文件: ${fileToUpload.name}`
            : input;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: displayContent,
            timestamp: new Date().toLocaleTimeString(),
            type: 'text'
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setSelectedFile(null);
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
            let response: Response;

            if (fileToUpload) {
                // 有文件上传时，使用 multipart/form-data
                const formData = new FormData();
                formData.append('session_id', sessionId);
                formData.append('user_input', input);
                formData.append('file', fileToUpload);

                response = await fetch(CHAT_STREAM_UPLOAD_URL, {
                    method: 'POST',
                    body: formData,
                });
            } else {
                // 无文件时，使用原有 JSON 接口
                response = await fetch(CHAT_STREAM_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        session_id: sessionId,
                        user_input: input,
                        model: 'gpt-4o-mini',
                    }),
                });
            }

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

                case 'llm_reasoning': {
                    // Wrap reasoning tokens inside <think>…</think> so the
                    // ThinkingProcess component picks them up automatically.
                    const rToken = event.token || '';
                    if (lastMsg && lastMsg.role === 'assistant' && lastMsg.type === 'text') {
                        const cur = lastMsg.content;
                        // If there's already an open <think> block (still thinking), append inside it
                        if (cur.includes('<think>') && !cur.includes('</think>')) {
                            return [
                                ...prev.slice(0, -1),
                                { ...lastMsg, content: cur + rToken }
                            ];
                        }
                        // If there's a closed think block, we shouldn't normally get more reasoning,
                        // but handle it by opening a new block
                        return [
                            ...prev.slice(0, -1),
                            { ...lastMsg, content: cur + '<think>' + rToken }
                        ];
                    }
                    // No assistant message yet — create one with an open <think> block
                    return [...prev, {
                        id: `msg-${Date.now()}`,
                        role: 'assistant',
                        content: '<think>' + rToken,
                        timestamp,
                        type: 'text'
                    }];
                }

                case 'llm_token':
                    // If the last message is an assistant text message, append to it
                    if (lastMsg && lastMsg.role === 'assistant' && lastMsg.type === 'text') {
                        let cur = lastMsg.content;
                        // Close any unclosed <think> block before appending content tokens
                        if (cur.includes('<think>') && !cur.includes('</think>')) {
                            cur = cur + '</think>';
                        }
                        return [
                            ...prev.slice(0, -1),
                            { ...lastMsg, content: cur + (event.token || '') }
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

                case 'file_uploaded':
                    return [...prev, {
                        id: `file-${Date.now()}`,
                        role: 'system',
                        content: `📁 文件已上传: ${event.filename || '未知文件'}`,
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
                    if (event.final_response) {
                        if (lastMsg && lastMsg.role === 'assistant' && lastMsg.type === 'text') {
                            // Preserve any <think>...</think> block accumulated during streaming
                            let thinkBlock = '';
                            const thinkMatch = lastMsg.content.match(/<think>[\s\S]*?<\/think>/);
                            if (thinkMatch) {
                                thinkBlock = thinkMatch[0];
                            } else if (lastMsg.content.includes('<think>')) {
                                // Close unclosed think block
                                const startIdx = lastMsg.content.indexOf('<think>');
                                thinkBlock = lastMsg.content.substring(startIdx) + '</think>';
                            }
                            const finalContent = thinkBlock
                                ? thinkBlock + event.final_response
                                : event.final_response;
                            const updated = [...prev.slice(0, -1), { ...lastMsg, content: finalContent }];
                            return [...updated, {
                                id: `fin-${Date.now()}`,
                                role: 'system',
                                content: '任务完成。',
                                timestamp,
                                type: 'info'
                            }];
                        }
                        return [...prev, {
                            id: `final-msg-${Date.now()}`,
                            role: 'assistant',
                            content: event.final_response,
                            timestamp,
                            type: 'text'
                        }, {
                            id: `fin-${Date.now()}`,
                            role: 'system',
                            content: '任务完成。',
                            timestamp,
                            type: 'info'
                        }];
                    }
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
                        <div className={`max-w-[85%] rounded p-3 relative group overflow-hidden ${msg.role === 'user'
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
                                <ThinkingProcess content={msg.content} />
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
                {/* 文件预览 */}
                {selectedFile && (
                    <div className="mb-2 flex items-center gap-2 px-3 py-2 bg-security-surface border border-gray-700 rounded-lg animate-in fade-in slide-in-from-bottom-2 duration-200">
                        <FileArchive className="w-4 h-4 text-security-primary flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                            <span className="text-sm text-security-text font-mono truncate block">
                                {selectedFile.name}
                            </span>
                            <span className="text-xs text-gray-500">
                                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                            </span>
                        </div>
                        <button
                            type="button"
                            onClick={() => setSelectedFile(null)}
                            className="p-1 hover:bg-red-900/30 rounded text-gray-400 hover:text-red-400 transition-colors flex-shrink-0"
                            title="移除文件"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="flex space-x-2 relative">
                    {/* 隐藏的文件输入 */}
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".apk"
                        className="hidden"
                        onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                                setSelectedFile(file);
                            }
                            // 重置 input 以便重复选择相同文件
                            e.target.value = '';
                        }}
                    />

                    {/* 文件上传按钮 */}
                    <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isLoading}
                        className={`p-3 rounded border transition-all flex items-center justify-center ${selectedFile
                            ? 'bg-security-primary/20 border-security-primary text-security-primary'
                            : 'bg-black border-gray-700 text-gray-400 hover:text-security-primary hover:border-security-primary/50'
                            } disabled:opacity-50 disabled:cursor-not-allowed`}
                        title="上传 APK 文件"
                    >
                        <Paperclip className="w-5 h-5" />
                    </button>

                    <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder={selectedFile ? `分析 ${selectedFile.name}...` : 'Input command...'}
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
