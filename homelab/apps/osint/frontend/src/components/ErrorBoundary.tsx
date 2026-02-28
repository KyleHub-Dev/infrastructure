import { Component, type ReactNode, type ErrorInfo } from "react";

interface ErrorBoundaryState {
  error: Error | null;
}

export class AppErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("React ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-background text-foreground p-8">
          <h1 className="font-display text-xl font-bold text-error mb-4">Something went wrong</h1>
          <pre className="text-xs text-muted-foreground bg-card border border-border rounded-lg p-4 max-w-lg overflow-auto whitespace-pre-wrap">
            {this.state.error.message}
          </pre>
          <button
            className="mt-4 bg-primary text-primary-foreground text-sm px-4 py-2 rounded-md hover:bg-primary/90"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
