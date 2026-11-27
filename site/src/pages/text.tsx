/**
 * @file text.tsx
 * @brief Content 2.0 Reading Library Page (supports ?workId= deep links from Topics & Rhythm)
 * @author sailing-innocent
 * @date 2026-11-26
 */

import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageLayout from '@components/page_layout'
import WorksList from '@components/text/works_list'
import ChapterReader from '@components/text/chapter_reader'
import { api_get_work } from '@lib/api/text'
import { type Work } from '@lib/data/text'

export default function TextPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedWork, setSelectedWork] = useState<Work | null>(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const workIdParam = searchParams.get('workId')

  useEffect(() => {
    if (!workIdParam) return
    const id = parseInt(workIdParam, 10)
    if (Number.isNaN(id)) return
    if (selectedWork?.id === id) return
    api_get_work(id)
      .then((w) => setSelectedWork(w))
      .catch(() => {})
  }, [workIdParam, selectedWork?.id])

  const handleDeleteSuccess = () => {
    setRefreshTrigger((prev) => prev + 1)
  }

  const handleSelectWork = (work: Work) => {
    setSelectedWork(work)
    setSearchParams({ workId: String(work.id) }, { replace: true })
  }

  const handleBack = () => {
    setSelectedWork(null)
    setSearchParams({}, { replace: true })
    setRefreshTrigger((prev) => prev + 1)
  }

  return (
    <PageLayout>
      {selectedWork ? (
        <ChapterReader work={selectedWork} onBack={handleBack} />
      ) : (
        <WorksList
          onSelectWork={handleSelectWork}
          refreshTrigger={refreshTrigger}
          onDeleteSuccess={handleDeleteSuccess}
        />
      )}
    </PageLayout>
  )
}
