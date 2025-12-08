/**
 * WorkflowStep component - displays individual agent step in workflow
 */
import { WorkflowUpdate } from '../types/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface WorkflowStepProps {
  update: WorkflowUpdate;
}

const WorkflowStep = ({ update }: WorkflowStepProps) => {
  const getStatusIcon = () => {
    switch (update.status) {
      case 'running':
        return (
          <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full"></div>
        );
      case 'completed':
        return <span className="text-green-500 text-2xl">✓</span>;
      case 'error':
        return <span className="text-red-500 text-2xl">✗</span>;
      case 'finished':
        return <span className="text-green-500 text-2xl">🎉</span>;
      default:
        return null;
    }
  };

  const getStatusColor = () => {
    switch (update.status) {
      case 'running':
        return 'border-blue-500 bg-blue-500/10';
      case 'completed':
        return 'border-green-500 bg-green-500/10';
      case 'error':
        return 'border-red-500 bg-red-500/10';
      case 'finished':
        return 'border-green-500 bg-green-500/20';
      default:
        return 'border-gray-500 bg-gray-500/10';
    }
  };

  const getAgentColor = () => {
    switch (update.agent) {
      case 'PlanningAgent':
        return 'text-purple-400';
      case 'CodingAgent':
        return 'text-blue-400';
      case 'ReviewAgent':
        return 'text-yellow-400';
      case 'Workflow':
        return 'text-green-400';
      default:
        return 'text-gray-400';
    }
  };

  return (
    <div className={`border-2 rounded-lg p-4 mb-4 ${getStatusColor()}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          {getStatusIcon()}
          <h3 className={`font-semibold text-lg ${getAgentColor()}`}>
            {update.agent}
          </h3>
          <span className="text-xs text-gray-400 uppercase px-2 py-1 bg-gray-800 rounded">
            {update.status}
          </span>
        </div>
      </div>

      {update.content && (
        <div className={`prose prose-invert max-w-none ${update.status === 'running' ? 'opacity-90' : ''}`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ node, inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <SyntaxHighlighter
                    style={vscDarkPlus}
                    language={match[1]}
                    PreTag="div"
                    {...props}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {update.content}
          </ReactMarkdown>
        </div>
      )}

      {update.status === 'running' && !update.content && (
        <p className="text-gray-400 italic animate-pulse">Initializing...</p>
      )}
    </div>
  );
};

export default WorkflowStep;
