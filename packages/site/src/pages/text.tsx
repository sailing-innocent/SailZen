/**
 * @file text.tsx
 * @brief Text Management Page
 * @author sailing-innocent
 * @date 2025-01-29
 */

import { useState } from 'react'
import PageLayout from '@components/page_layout'
import WorksList from '@components/works_list'
import ChapterReader from '@components/chapter_reader'
import { type Work } from '@lib/data/text'

export default function TextPage() {
  const [selectedWork, setSelectedWork] = useState<Work | null>(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const handleDeleteSuccess = () => {
    setRefreshTrigger((prev) => prev + 1)
  }

  const handleSelectWork = (work: Work) => {
    setSelectedWork(work)
  }

  const handleBack = () => {
    setSelectedWork(null)
  }

  return (
    <PageLayout>
      {selectedWork ? (
        <ChapterReader work={selectedWork} onBack={handleBack} />
      ) : (
        <>
          <WorksList
            onSelectWork={handleSelectWork}
            refreshTrigger={refreshTrigger}
            onDeleteSuccess={handleDeleteSuccess}
          />
        </>
      )}
    </PageLayout>
  )
}
