import { Component } from 'react';
import { Home, RefreshCcw } from 'lucide-react';

export default class AppErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('Cinema Paradiso workspace crashed', error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <main className="app-crash-screen" role="alert">
        <section className="app-crash-panel">
          <p className="screen-kicker">Workspace error</p>
          <h1>Cinema Paradiso hit a display error.</h1>
          <p>{this.state.error.message || 'The current workspace could not be displayed.'}</p>
          <div className="app-crash-actions">
            <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
              <RefreshCcw size={16} /> Reload
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => window.location.assign('/')}>
              <Home size={16} /> Home
            </button>
          </div>
        </section>
      </main>
    );
  }
}
