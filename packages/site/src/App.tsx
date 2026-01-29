import React, { useEffect, Suspense } from 'react'
import { BrowserRouter, Routes, Route, useSearchParams, useNavigate } from 'react-router-dom'
import { useServerStore, type ServerState } from '@lib/store'
import { MobileProviderWithFallback } from '@/hooks/use-mobile'
import './App.css'

// import MainPage from '@pages/main'
const MainPage = React.lazy(() => import('@pages/main'))
const MoneyPage = React.lazy(() => import('@pages/money'))
const HealthPage = React.lazy(() => import('@pages/health'))
const ProjectPage = React.lazy(() => import('@pages/project'))
const ContentPage = React.lazy(() => import('@pages/content'))
const TextPage = React.lazy(() => import('@pages/text'))

interface URLParams {
  path?: string
  content?: string
}

const AppRoutes: React.FC = () => {
  const fetchServerHealth = useServerStore((state: ServerState) => state.fetchServerHealth)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [, setUrlParams] = React.useState<URLParams>({ path: undefined, content: undefined })

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

  return (
    <Routes>
      <Route path="/" element={<MainPage />} />
      <Route path="/money" element={<MoneyPage />} />
      <Route path="/health" element={<HealthPage />} />
      <Route path="/project" element={<ProjectPage />} />
      <Route path="/content" element={<ContentPage />} />
      <Route path="/text" element={<TextPage />} />
    </Routes>
  )
}

function App() {
  return (
    <MobileProviderWithFallback>
      <BrowserRouter>
        <Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
          <AppRoutes />
        </Suspense>
      </BrowserRouter>
    </MobileProviderWithFallback>
  )
}

export default App
