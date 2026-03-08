/**
 * @file outline_error_boundary.tsx
 * @brief Error boundary for outline components
 * @author sailing-innocent
 * @date 2026-03-07
 */

import React, { Component, type ReactNode } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

interface OutlineErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
  onReset?: () => void
}

interface OutlineErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: React.ErrorInfo | null
}

/**
 * Error boundary for outline components with recovery options
 */
export class OutlineErrorBoundary extends Component<
  OutlineErrorBoundaryProps,
  OutlineErrorBoundaryState
> {
  constructor(props: OutlineErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    }
  }

  static getDerivedStateFromError(error: Error): OutlineErrorBoundaryState {
    return {
      hasError: true,
      error,
      errorInfo: null,
    }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Outline component error:', error, errorInfo)
    this.setState({
      error,
      errorInfo,
    })
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    })
    this.props.onReset?.()
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="p-6">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>大纲加载失败</AlertTitle>
            <AlertDescription className="space-y-4">
              <p>
                {this.state.error?.message ||
                  '发生了意外错误，请尝试刷新页面或联系管理员。'}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={this.handleReset}
                  className="gap-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  重试
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.location.reload()}
                >
                  刷新页面
                </Button>
              </div>
              {this.state.errorInfo && (
                <pre className="mt-4 text-xs bg-muted p-2 rounded overflow-auto max-h-40">
                  {this.state.errorInfo.componentStack}
                </pre>
              )}
            </AlertDescription>
          </Alert>
        </div>
      )
    }

    return this.props.children
  }
}

interface OutlinePanelErrorBoundaryProps {
  children: ReactNode
  editionId: number
  onRetry?: () => void
}

/**
 * Specialized error boundary for outline panel with edition context
 */
export function OutlinePanelErrorBoundary({
  children,
  editionId,
  onRetry,
}: OutlinePanelErrorBoundaryProps) {
  return (
    <OutlineErrorBoundary
      onReset={onRetry}
      fallback={
        <div className="p-4 space-y-4">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>无法加载大纲列表</AlertTitle>
            <AlertDescription className="space-y-4">
              <p>无法加载版本 (ID: {editionId}) 的大纲列表。</p>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={onRetry}>
                  重试
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        </div>
      }
    >
      {children}
    </OutlineErrorBoundary>
  )
}

export default OutlineErrorBoundary
