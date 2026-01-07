/**
 * Chat message component with markdown and code highlighting - Claude.ai inspired UI
 */
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ChatMessage as ChatMessageType } from '../types/api';

interface ChatMessageProps {
  message: ChatMessageType;
}

const ChatMessage = ({ message }: ChatMessageProps) => {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-4 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className="flex-shrink-0">
        {isUser ? (
          <div className="w-8 h-8 rounded-full bg-[#1A1A1A] flex items-center justify-center">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
            </svg>
          </div>
        ) : (
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#DA7756] to-[#C86A4A] flex items-center justify-center">
            <span className="text-white font-semibold text-sm">C</span>
          </div>
        )}
      </div>

      {/* Message Content */}
      <div className={`flex-1 ${isUser ? 'text-right' : ''}`}>
        <div className={`text-xs font-medium mb-1 ${isUser ? 'text-[#666666]' : 'text-[#DA7756]'}`}>
          {isUser ? 'You' : 'Code Agent'}
        </div>
        <div
          className={`inline-block max-w-full rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-[#1A1A1A] text-white text-left'
              : 'bg-white text-[#1A1A1A] border border-[#E5E5E5]'
          }`}
        >
          <div className={`prose prose-lg max-w-none ${isUser ? 'prose-invert' : ''}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code(props) {
                  const { children, className, ...rest } = props;
                  const match = /language-(\w+)/.exec(className || '');
                  return match ? (
                    <div className="relative group">
                      <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => navigator.clipboard.writeText(String(children))}
                          className="px-2 py-1 text-xs bg-[#333] text-white rounded hover:bg-[#444]"
                        >
                          Copy
                        </button>
                      </div>
                      <SyntaxHighlighter
                        style={oneDark as any}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{
                          borderRadius: '12px',
                          padding: '16px',
                          margin: '8px 0',
                          fontSize: '16px',
                        }}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    </div>
                  ) : (
                    <code
                      className={`${className} bg-[#F5F4F2] px-1.5 py-0.5 rounded text-[#DA7756] text-base`}
                      {...rest}
                    >
                      {children}
                    </code>
                  );
                },
                p({ children }) {
                  return <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>;
                },
                ul({ children }) {
                  return <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>;
                },
                ol({ children }) {
                  return <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>;
                },
                li({ children }) {
                  return <li className="leading-relaxed">{children}</li>;
                },
                a({ href, children }) {
                  return (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#DA7756] hover:text-[#C86A4A] underline"
                    >
                      {children}
                    </a>
                  );
                },
                h1({ children }) {
                  return <h1 className="text-xl font-semibold mb-3 mt-4 first:mt-0">{children}</h1>;
                },
                h2({ children }) {
                  return <h2 className="text-lg font-semibold mb-2 mt-3 first:mt-0">{children}</h2>;
                },
                h3({ children }) {
                  return <h3 className="text-base font-semibold mb-2 mt-2 first:mt-0">{children}</h3>;
                },
                blockquote({ children }) {
                  return (
                    <blockquote className="border-l-4 border-[#DA7756] pl-4 my-3 italic text-[#666666]">
                      {children}
                    </blockquote>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
