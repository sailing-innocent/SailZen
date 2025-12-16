import React from 'react'
// import Pagebar from '@/components/pagebar'
import PageLayout from '@components/page_layout'
import { get_url } from '@lib/api'
import { useServerStore } from '@lib/store/'

const MainPage = () => {
  const url = get_url()
  const serverHealth = useServerStore((state) => state.serverHealth)

  return (
    <>
      <PageLayout>
        <div>MainPage</div>
        <div>
          SERVER URL: {url} {serverHealth ? 'Healthy' : 'Unhealthy'}
        </div>
      </PageLayout>
    </>
  )
}

export default MainPage
