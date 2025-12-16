/**
 * Main chat interface component
 */
import React, { useState, useRef, useEffect } from 'react';
import { apiClient } from '../api/client';
import { ChatMessage as ChatMessageType, StoredMessage } from '../types/api';
import ChatMessage from './ChatMessage';

interface ChatInterfaceProps {
  sessionId: string;
  taskType: 'reasoning' | 'coding';
  initialMessages?: StoredMessage[];
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ sessionId, taskType, initialMessages }) => {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [useStreaming, setUseStreaming] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load conversation history on mount or when session changes
  useEffect(() => {
    try {
      setError(null);
      // If we have initial messages from a loaded conversation, use them
      if (initialMessages && initialMessages.length > 0) {
        // Convert StoredMessage to ChatMessage format
        const convertedMessages: ChatMessageType[] = initialMessages.map((msg) => ({
          role: msg.role,
          content: msg.content,
        }));
        setMessages(convertedMessages);
        console.log(`Loaded ${convertedMessages.length} messages for session ${sessionId}`);
      } else {
        // For new sessions, start with empty messages
        setMessages([]);
        console.log(`Starting new session ${sessionId} with empty messages`);
      }
    } catch (err) {
      console.error('Error loading messages:', err);
      setError(err instanceof Error ? err.message : 'Failed to load messages');
      setMessages([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: ChatMessageType = {
      role: 'user',
      content: inputMessage,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Save user message to conversation
      try {
        await apiClient.addMessage(sessionId, 'user', inputMessage);
      } catch (err) {
        console.error('Failed to save user message:', err);
      }

      if (useStreaming) {
        // Streaming mode
        const assistantMessage: ChatMessageType = {
          role: 'assistant',
          content: '',
        };
        setMessages((prev) => [...prev, assistantMessage]);

        const stream = apiClient.chatStream({
          message: inputMessage,
          session_id: sessionId,
          task_type: taskType,
          stream: true,
        });

        for await (const chunk of stream) {
          assistantMessage.content += chunk;
          setMessages((prev) => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = { ...assistantMessage };
            return newMessages;
          });
        }

        // Save assistant message to conversation
        try {
          await apiClient.addMessage(sessionId, 'assistant', assistantMessage.content);
        } catch (err) {
          console.error('Failed to save assistant message:', err);
        }
      } else {
        // Non-streaming mode
        const response = await apiClient.chat({
          message: inputMessage,
          session_id: sessionId,
          task_type: taskType,
        });

        const assistantMessage: ChatMessageType = {
          role: 'assistant',
          content: response.response,
        };

        setMessages((prev) => [...prev, assistantMessage]);

        // Save assistant message to conversation
        try {
          await apiClient.addMessage(sessionId, 'assistant', response.response);
        } catch (err) {
          console.error('Failed to save assistant message:', err);
        }
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      setError(`Failed to send message: ${errorMsg}`);
      const errorMessage: ChatMessageType = {
        role: 'assistant',
        content: `Error: ${errorMsg}`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleClearHistory = async () => {
    try {
      await apiClient.clearHistory(sessionId);
      setMessages([]);
    } catch (error) {
      console.error('Failed to clear history:', error);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#FFFFFF] rounded-lg shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#E5E5E7]">
        <div>
          <h2 className="text-xl font-semibold text-[#2D2D2D]">Coding Agent</h2>
          <p className="text-sm text-[#6B6B6B]">
            Mode: {taskType === 'reasoning' ? 'Reasoning (DeepSeek-R1)' : 'Coding (Qwen3)'}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-[#2D2D2D]">
            <input
              type="checkbox"
              checked={useStreaming}
              onChange={(e) => setUseStreaming(e.target.checked)}
              className="rounded"
            />
            Streaming
          </label>
          <button
            onClick={handleClearHistory}
            className="px-3 py-1 text-sm bg-[#F0F0F0] hover:bg-[#E5E5E7] text-[#2D2D2D] rounded transition-colors"
          >
            Clear History
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {error && (
          <div className="mb-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
            <div className="flex items-center gap-2 text-red-400">
              <span className="text-xl">⚠️</span>
              <span className="font-semibold">Error:</span>
              <span>{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="mt-2 text-sm text-red-400 hover:text-red-300 underline"
            >
              Dismiss
            </button>
          </div>
        )}
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-[#6B6B6B]">
            <p>Start a conversation with the coding agent</p>
          </div>
        ) : (
          <>
            {messages.map((message, index) => (
              <ChatMessage key={index} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-[#E5E5E7]">
        <div className="flex gap-2">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message... (Shift+Enter for new line)"
            className="flex-1 px-4 py-2 bg-[#F0F0F0] text-[#2D2D2D] placeholder-[#6B6B6B] rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-[#10A37F] border border-[#E5E5E7]"
            rows={3}
            disabled={isLoading}
          />
          <button
            onClick={handleSendMessage}
            disabled={isLoading || !inputMessage.trim()}
            className="px-6 py-2 bg-[#10A37F] hover:bg-[#0E8C6F] disabled:bg-[#505050] disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
          >
            {isLoading ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
