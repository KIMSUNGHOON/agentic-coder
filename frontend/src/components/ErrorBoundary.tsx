/**
 * Error Boundary to catch React component errors and prevent full page crash
 */
import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error details
    console.error('React Error Boundary caught an error:', error, errorInfo);
    this.setState({
      error,
      errorInfo,
    });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
    // Reload the page
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-[#1A1A1A]">
          <div className="max-w-2xl p-8 bg-[#2A2A2A] border border-[#404040] rounded-lg">
            <div className="text-center mb-6">
              <div className="text-6xl mb-4">⚠️</div>
              <h1 className="text-2xl font-bold text-[#ECECF1] mb-2">
                Something went wrong
              </h1>
              <p className="text-[#9B9B9B]">
                The application encountered an error and couldn't continue.
              </p>
            </div>

            {this.state.error && (
              <div className="mb-6 p-4 bg-[#1A1A1A] rounded border border-red-500/30">
                <h3 className="text-sm font-semibold text-red-400 mb-2">
                  Error Details:
                </h3>
                <pre className="text-xs text-[#ECECF1] whitespace-pre-wrap break-words">
                  {this.state.error.toString()}
                </pre>
                {this.state.errorInfo && (
                  <details className="mt-3">
                    <summary className="text-xs text-[#9B9B9B] cursor-pointer hover:text-[#ECECF1]">
                      Stack Trace
                    </summary>
                    <pre className="mt-2 text-xs text-[#9B9B9B] whitespace-pre-wrap break-words">
                      {this.state.errorInfo.componentStack}
                    </pre>
                  </details>
                )}
              </div>
            )}

            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleReset}
                className="px-6 py-2 bg-[#10A37F] hover:bg-[#0E8C6F] text-white rounded-lg font-medium transition-colors"
              >
                Reload Application
              </button>
              <button
                onClick={() => window.history.back()}
                className="px-6 py-2 bg-[#343434] hover:bg-[#404040] text-[#ECECF1] rounded-lg font-medium transition-colors"
              >
                Go Back
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
