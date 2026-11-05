import { Component } from 'react'

/**
 * Error Boundary — catches uncaught errors in child components and shows
 * a fallback UI instead of a white screen. The user can click "Retry" to
 * re-render the component tree.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <YourComponent />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary] Caught:', error, errorInfo)
    this.setState({ errorInfo })
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleRetry)
      }
      return (
        <div className="flex min-h-[400px] flex-col items-center justify-center gap-4 p-8 text-center">
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 max-w-md">
            <h3 className="text-base font-semibold text-rose-900">
              Une erreur est survenue
            </h3>
            <p className="mt-2 text-sm text-rose-700">
              {this.state.error?.message || 'Erreur inattendue dans le composant.'}
            </p>
            {this.state.errorInfo?.componentStack && (
              <pre className="mt-3 max-h-32 overflow-auto rounded bg-rose-100 p-2 text-[10px] text-rose-600">
                {this.state.errorInfo.componentStack.slice(0, 500)}
              </pre>
            )}
            <button
              onClick={this.handleRetry}
              className="mt-4 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700"
            >
              Réessayer
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

/**
 * Minimal fallback for tab content — compact error display inside a tab.
 */
export function TabErrorFallback({ error, onRetry }) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-center">
      <p className="text-sm font-medium text-rose-800">Erreur dans cet onglet</p>
      <p className="mt-1 text-xs text-rose-600">{error?.message || 'Erreur inattendue'}</p>
      <button
        onClick={onRetry}
        className="mt-3 rounded-lg border border-rose-300 px-3 py-1 text-xs font-medium text-rose-700 hover:bg-rose-100"
      >
        Réessayer
      </button>
    </div>
  )
}
