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
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load conversation history on mount or when initial messages change
  useEffect(() => {
    if (initialMessages && initialMessages.length > 0) {
      // Convert StoredMessage to ChatMessage format
      const convertedMessages: ChatMessageType[] = initialMessages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));
      setMessages(convertedMessages);
    } else {
      loadHistory();
    }
  }, [sessionId, initialMessages]);

  const loadHistory = async () => {
    try {
      const status = await apiClient.getAgentStatus(sessionId);
      setMessages(status.history);
    } catch (error) {
      console.error('Failed to load history:', error);
      setMessages([]);
    }
  };

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
      const errorMessage: ChatMessageType = {
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
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
    <div className="flex flex-col h-full bg-[#2A2A2A] rounded-lg shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#404040]">
        <div>
          <h2 className="text-xl font-semibold text-[#ECECF1]">Coding Agent</h2>
          <p className="text-sm text-[#9B9B9B]">
            Mode: {taskType === 'reasoning' ? 'Reasoning (DeepSeek-R1)' : 'Coding (Qwen3)'}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-[#ECECF1]">
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
            className="px-3 py-1 text-sm bg-[#343434] hover:bg-[#404040] text-[#ECECF1] rounded transition-colors"
          >
            Clear History
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-[#9B9B9B]">
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
      <div className="px-6 py-4 border-t border-[#404040]">
        <div className="flex gap-2">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message... (Shift+Enter for new line)"
            className="flex-1 px-4 py-2 bg-[#343434] text-[#ECECF1] placeholder-[#9B9B9B] rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-[#10A37F] border border-[#404040]"
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
