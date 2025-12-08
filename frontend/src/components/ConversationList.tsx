/**
 * ConversationList component - sidebar showing saved conversations
 */
import { useState, useEffect } from 'react';
import { Conversation } from '../types/api';
import apiClient from '../api/client';

interface ConversationListProps {
  currentSessionId: string;
  mode: 'chat' | 'workflow';
  onSelectConversation: (conversation: Conversation) => void;
  onNewConversation: () => void;
}

const ConversationList = ({
  currentSessionId,
  mode,
  onSelectConversation,
  onNewConversation,
}: ConversationListProps) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadConversations();
  }, [mode]);

  const loadConversations = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.listConversations(50, 0, mode);
      setConversations(response.conversations);
    } catch (err) {
      console.error('Failed to load conversations:', err);
      setError('Failed to load conversations');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;

    try {
      await apiClient.deleteConversation(sessionId);
      setConversations((prev) => prev.filter((c) => c.session_id !== sessionId));
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
      return 'Yesterday';
    } else if (days < 7) {
      return date.toLocaleDateString([], { weekday: 'short' });
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
  };

  return (
    <div className="w-64 bg-[#1A1A1A] border-r border-[#404040] flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-[#404040]">
        <button
          onClick={onNewConversation}
          className="w-full px-4 py-2 bg-[#10A37F] hover:bg-[#0E8C6F] text-white rounded-lg flex items-center justify-center gap-2 transition-colors"
        >
          <span className="text-lg">+</span>
          <span>New {mode === 'workflow' ? 'Workflow' : 'Chat'}</span>
        </button>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center p-4">
            <div className="animate-spin h-6 w-6 border-2 border-[#10A37F] border-t-transparent rounded-full"></div>
          </div>
        ) : error ? (
          <div className="p-4 text-center text-red-400">{error}</div>
        ) : conversations.length === 0 ? (
          <div className="p-4 text-center text-[#9B9B9B]">
            No conversations yet
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {conversations.map((conversation) => (
              <div
                key={conversation.session_id}
                onClick={() => onSelectConversation(conversation)}
                className={`group p-3 rounded-lg cursor-pointer transition-colors ${
                  conversation.session_id === currentSessionId
                    ? 'bg-[#343434]'
                    : 'hover:bg-[#2A2A2A]'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium text-[#ECECF1] truncate">
                      {conversation.title}
                    </h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-[#9B9B9B]">
                        {formatDate(conversation.updated_at)}
                      </span>
                      <span className="text-xs text-[#6B6B6B]">
                        {conversation.message_count} messages
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, conversation.session_id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-[#9B9B9B] hover:text-red-400 transition-all"
                    title="Delete conversation"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-4 w-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Refresh button */}
      <div className="p-2 border-t border-[#404040]">
        <button
          onClick={loadConversations}
          className="w-full px-3 py-2 text-sm text-[#9B9B9B] hover:text-[#ECECF1] hover:bg-[#2A2A2A] rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          Refresh
        </button>
      </div>
    </div>
  );
};

export default ConversationList;
