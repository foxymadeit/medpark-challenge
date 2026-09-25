import { Component, type ReactNode } from "react";
import StatePanel from "./StatePanel";
export default class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="page-container">
        <StatePanel
          error="requestFailed"
          retry={() => window.location.reload()}
        />
      </main>
    ) : (
      this.props.children
    );
  }
}
