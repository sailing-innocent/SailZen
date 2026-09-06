import React, { useEffect, Suspense } from 'react'
import { BrowserRouter, Routes, Route, useSearchParams, useNavigate } from 'react-router-dom'
import { useServerStore, type ServerState } from '@lib/store'
import { MobileProviderWithFallback } from '@/hooks/use-mobile'
import { PAGE_ROUTES, getPageComponent } from './config/basic'
import './App.css'

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
        <Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
          <AppRoutes />
        </Suspense>
      </BrowserRouter>
    </MobileProviderWithFallback>
  )
}

export default App
