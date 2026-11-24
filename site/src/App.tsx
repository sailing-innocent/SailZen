import React, { useEffect, useRef, Suspense } from 'react'
import { BrowserRouter, Routes, Route, useSearchParams, useNavigate, useLocation } from 'react-router-dom'
import { useServerStore, useUserInboxStore, type ServerState } from '@lib/store'
import { MobileProviderWithFallback } from '@/hooks/use-mobile'
import { PAGE_ROUTES, getPageComponent } from './config/basic'
import { flushClientEvents, installGlobalErrorTelemetry, trackClientEvent } from '@lib/telemetry'
import './App.css'

const TelemetryTracker: React.FC = () => {
  const location = useLocation()
  const enteredAtRef = useRef<{ path: string; ts: number } | null>(null)

  useEffect(() => {
    return installGlobalErrorTelemetry()
  }, [])

  useEffect(() => {
    const now = performance.now()
    const prev = enteredAtRef.current
    if (prev && prev.path !== location.pathname) {
      const dwellMs = Math.round(now - prev.ts)
      trackClientEvent({
        category: 'page_view',
        module: prev.path.split('/').filter(Boolean)[0] || 'main',
        name: prev.path,
        duration_ms: dwellMs,
        detail: {
          viewport: typeof window !== 'undefined' ? `${window.innerWidth}x${window.innerHeight}` : '',
        },
      })
    }
    enteredAtRef.current = { path: location.pathname, ts: now }
  }, [location.pathname])

  useEffect(() => {
    const onBeforeUnload = () => {
      const cur = enteredAtRef.current
      if (cur) {
        trackClientEvent({
          category: 'page_view',
          module: cur.path.split('/').filter(Boolean)[0] || 'main',
          name: cur.path,
          duration_ms: Math.round(performance.now() - cur.ts),
        })
        flushClientEvents()
      }
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [])

  return null
}

interface URLParams {
  path?: string
  content?: string
}

const AppRoutes: React.FC = () => {
  const fetchServerHealth = useServerStore((state: ServerState) => state.fetchServerHealth)
  const bootstrapUser = useUserInboxStore((state) => state.bootstrap)
  const disconnectWs = useUserInboxStore((state) => state.disconnectWs)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [, setUrlParams] = React.useState<URLParams>({ path: undefined, content: undefined })

  useEffect(() => {
    bootstrapUser()
    return () => {
      disconnectWs()
    }
  }, [bootstrapUser, disconnectWs])

  useEffect(() => {

    fetchServerHealth() // fetch server health
    const redirectPath = searchParams?.get('path') ?? undefined
    const contentPath = searchParams.get('content') ?? undefined

    setUrlParams({
      path: redirectPath,
      content: contentPath,
    })

    if (redirectPath) {
      navigate(`${redirectPath}?content=${contentPath}`)
    }
  }, [fetchServerHealth, searchParams, navigate])

  const MainComponent = getPageComponent('/main')

  return (
    <Routes>
      <Route path="/" element={MainComponent ? <MainComponent /> : null} />
      {PAGE_ROUTES.map((item) => {
        const Component = item.component
        return <Route key={item.path} path={item.path} element={<Component />} />
      })}
    </Routes>
  )
}

function App() {
  return (
    <MobileProviderWithFallback>
      <BrowserRouter>
        <TelemetryTracker />
        <Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
          <AppRoutes />
        </Suspense>
      </BrowserRouter>
    </MobileProviderWithFallback>
  )
}

export default App
