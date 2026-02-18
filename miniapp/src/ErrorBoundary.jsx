import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // In production, send to your error tracking service here
    console.error('[ErrorBoundary] Uncaught error:', error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100dvh',
            padding: '24px',
            textAlign: 'center',
            background: '#000',
            color: '#fff',
            gap: '16px',
          }}
          role="alert"
        >
          <div style={{ fontSize: '48px' }}>🌑</div>
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 600 }}>
            Что-то пошло не так
          </h2>
          <p style={{ margin: 0, opacity: 0.6, fontSize: '14px', maxWidth: '280px' }}>
            Произошла неожиданная ошибка. Попробуйте обновить страницу.
          </p>
          <button
            onClick={this.handleReset}
            style={{
              marginTop: '8px',
              padding: '12px 24px',
              background: '#5E5CE6',
              color: '#fff',
              border: 'none',
              borderRadius: '12px',
              fontSize: '16px',
              cursor: 'pointer',
            }}
          >
            Попробовать снова
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
