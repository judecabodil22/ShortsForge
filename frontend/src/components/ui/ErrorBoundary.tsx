import { Component, ReactNode } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen bg-40k-black text-white p-8">
          <AlertCircle className="w-16 h-16 text-40k-red-bright mb-6" />
          <h1 className="text-2xl font-display font-bold mb-4">Something went wrong</h1>
          <p className="text-gray-400 mb-6 text-center max-w-md">
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="cyber-button flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Reload Page
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
