/**
 * OneDay.run Platform - React Chat Component
 * Główny komponent chatu z AI dla realizacji zamówień
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';

interface Message {
  id: string;
  type: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: Date;
}

interface Progress {
  project_id: string;
  current_phase: string;
  progress_percent: number;
  files_generated: number;
  components_used: number;
  tokens_used: number;
  github_repo?: string;
  deployment_url?: string;
}

interface OneDayChatProps {
  projectId: string;
  apiBaseUrl?: string;
}

const OneDayChat: React.FC<OneDayChatProps> = ({ 
  projectId, 
  apiBaseUrl = 'ws://localhost:8003'
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('');
  
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingMessage]);

  const connect = useCallback(() => {
    const ws = new WebSocket(`${apiBaseUrl}/ws/${projectId}`);

    ws.onopen = () => {
      setIsConnected(true);
      console.log('WebSocket connected');
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket disconnected');
      // Auto-reconnect after 2 seconds
      setTimeout(connect, 2000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleMessage(data);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [projectId, apiBaseUrl]);

  useEffect(() => {
    const cleanup = connect();
    return cleanup;
  }, [connect]);

  const handleMessage = (data: any) => {
    switch (data.type) {
      case 'system':
        addMessage('system', data.content);
        if (data.project) {
          setProgress(data.project);
        }
        break;

      case 'response_start':
        setIsTyping(true);
        setCurrentStreamingMessage('');
        break;

      case 'response_chunk':
        setCurrentStreamingMessage(prev => prev + data.content);
        break;

      case 'response_end':
        setIsTyping(false);
        if (data.full_content) {
          addMessage('assistant', data.full_content);
        } else if (currentStreamingMessage) {
          addMessage('assistant', currentStreamingMessage);
        }
        setCurrentStreamingMessage('');
        break;

      case 'typing':
        setIsTyping(data.content);
        break;

      case 'progress':
        setProgress(data.data);
        break;

      case 'tool':
        addMessage('tool', `🔧 ${data.name}: ${data.status}`);
        break;

      case 'error':
        addMessage('system', `❌ ${data.content}`);
        break;

      default:
        console.log('Unknown message type:', data.type);
    }
  };

  const addMessage = (type: Message['type'], content: string) => {
    setMessages(prev => [...prev, {
      id: crypto.randomUUID(),
      type,
      content,
      timestamp: new Date()
    }]);
  };

  const sendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !wsRef.current || !isConnected) return;

    // Add user message
    addMessage('user', input);

    // Send to WebSocket
    wsRef.current.send(JSON.stringify({
      type: 'message',
      content: input
    }));

    setInput('');
  };

  const sendCommand = (command: string, params: object = {}) => {
    if (!wsRef.current || !isConnected) return;

    wsRef.current.send(JSON.stringify({
      type: 'command',
      command,
      ...params
    }));
  };

  const formatContent = (content: string) => {
    // Simple code block formatting
    return content.split(/(```[\s\S]*?```)/g).map((part, i) => {
      if (part.startsWith('```')) {
        const lines = part.split('\n');
        const language = lines[0].replace('```', '') || 'code';
        const code = lines.slice(1, -1).join('\n');
        return (
          <pre key={i} className="bg-gray-900 rounded-lg p-4 my-2 overflow-x-auto">
            <code className="text-sm font-mono text-green-400">{code}</code>
          </pre>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-pink-500">🚀 OneDay.run</h1>
            <p className="text-sm text-gray-400">Project: {projectId}</p>
          </div>
          <div className="flex items-center gap-4">
            <span className={`px-3 py-1 rounded-full text-sm ${
              isConnected ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
            }`}>
              {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
            </span>
          </div>
        </div>

        {/* Progress Bar */}
        {progress && (
          <div className="mt-4 bg-gray-700 rounded-lg p-3">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-gray-300">
                Phase: <strong className="text-pink-400">{progress.current_phase}</strong>
              </span>
              <span className="text-gray-300">
                {progress.progress_percent}% Complete
              </span>
            </div>
            <div className="w-full bg-gray-600 rounded-full h-2">
              <div 
                className="bg-pink-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${progress.progress_percent}%` }}
              />
            </div>
            <div className="flex gap-4 mt-2 text-xs text-gray-400">
              <span>📄 Files: {progress.files_generated}</span>
              <span>📦 Components: {progress.components_used}</span>
              <span>🔤 Tokens: {Math.round(progress.tokens_used).toLocaleString()}</span>
              {progress.github_repo && (
                <a href={`https://github.com/${progress.github_repo}`} 
                   target="_blank" 
                   rel="noopener noreferrer"
                   className="text-blue-400 hover:underline">
                  📁 GitHub
                </a>
              )}
              {progress.deployment_url && (
                <a href={progress.deployment_url} 
                   target="_blank" 
                   rel="noopener noreferrer"
                   className="text-green-400 hover:underline">
                  🌐 Live
                </a>
              )}
            </div>
          </div>
        )}
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map(message => (
          <div 
            key={message.id}
            className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[80%] rounded-lg px-4 py-3 ${
              message.type === 'user' 
                ? 'bg-pink-600' 
                : message.type === 'assistant'
                ? 'bg-gray-800 border border-gray-700'
                : message.type === 'tool'
                ? 'bg-blue-900/50 border border-blue-700'
                : 'bg-gray-700 text-center'
            }`}>
              <div className="text-sm whitespace-pre-wrap">
                {formatContent(message.content)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}

        {/* Streaming message */}
        {currentStreamingMessage && (
          <div className="flex justify-start">
            <div className="max-w-[80%] bg-gray-800 border border-gray-700 rounded-lg px-4 py-3">
              <div className="text-sm whitespace-pre-wrap">
                {formatContent(currentStreamingMessage)}
                <span className="animate-pulse">▊</span>
              </div>
            </div>
          </div>
        )}

        {/* Typing indicator */}
        {isTyping && !currentStreamingMessage && (
          <div className="flex justify-start">
            <div className="bg-gray-800 rounded-lg px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{animationDelay: '0ms'}} />
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{animationDelay: '150ms'}} />
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{animationDelay: '300ms'}} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Actions */}
      <div className="border-t border-gray-700 px-6 py-2 flex gap-2">
        <button 
          onClick={() => sendCommand('status')}
          className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          📊 Status
        </button>
        <button 
          onClick={() => sendCommand('components', { query: '' })}
          className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          📦 Components
        </button>
        <button 
          onClick={() => sendCommand('deploy', { platform: 'railway' })}
          className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          🚀 Deploy
        </button>
      </div>

      {/* Input */}
      <form onSubmit={sendMessage} className="border-t border-gray-700 p-4">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Opisz co chcesz zbudować..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 
                       focus:outline-none focus:border-pink-500 transition-colors"
            disabled={!isConnected}
          />
          <button
            type="submit"
            disabled={!isConnected || !input.trim()}
            className="bg-pink-600 hover:bg-pink-500 disabled:bg-gray-700 disabled:cursor-not-allowed
                       px-6 py-3 rounded-lg font-semibold transition-colors"
          >
            Wyślij
          </button>
        </div>
      </form>
    </div>
  );
};

export default OneDayChat;
