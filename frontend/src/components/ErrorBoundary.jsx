import { Component } from "react";

/**
 * ErrorBoundary — catches render errors in child components
 * and displays a user-friendly fallback UI with a retry option.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("[ErrorBoundary] Caught render error:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="canvas-container">
          <div className="canvas-frame">
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                gap: "16px",
                color: "#64748b",
                padding: "32px",
                textAlign: "center",
              }}
            >
              <span style={{ fontSize: "48px" }}>⚠</span>
              <span style={{ fontSize: "18px", fontWeight: 600, color: "#334155" }}>
                Something went wrong
              </span>
              <span style={{ fontSize: "14px", maxWidth: "400px" }}>
                The visualization encountered an error. This is usually caused by
                unexpected DFA data. Try generating a new DFA.
              </span>
              <button
                onClick={this.handleRetry}
                style={{
                  marginTop: "8px",
                  padding: "10px 24px",
                  borderRadius: "8px",
                  border: "none",
                  background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                  color: "white",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
                }}
              >
                ⟲ Retry
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
