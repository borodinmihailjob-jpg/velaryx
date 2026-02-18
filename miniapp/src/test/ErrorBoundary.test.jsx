import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ErrorBoundary from '../ErrorBoundary';

// Silence expected console.error output from ErrorBoundary during tests
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

function ThrowingChild({ shouldThrow }) {
  if (shouldThrow) throw new Error('Test error');
  return <div>Content rendered successfully</div>;
}

describe('ErrorBoundary', () => {
  it('renders children when no error is thrown', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={false} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Content rendered successfully')).toBeInTheDocument();
  });

  it('renders fallback UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow />
      </ErrorBoundary>
    );
    expect(screen.getByText('Что-то пошло не так')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /попробовать снова/i })).toBeInTheDocument();
  });

  it('has role="alert" on the fallback container', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow />
      </ErrorBoundary>
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('resets and renders children again after clicking retry', () => {
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow />
      </ErrorBoundary>
    );
    expect(screen.getByText('Что-то пошло не так')).toBeInTheDocument();

    // Update children to non-throwing BEFORE clicking retry,
    // so that after state reset ErrorBoundary renders the fixed children
    rerender(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={false} />
      </ErrorBoundary>
    );

    fireEvent.click(screen.getByRole('button', { name: /попробовать снова/i }));

    expect(screen.getByText('Content rendered successfully')).toBeInTheDocument();
  });
});
