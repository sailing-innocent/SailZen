/**
 * @file text.tsx
 * @brief Text Management Page
 * @author sailing-innocent
 * @date 2025-01-29
 */

import { useState } from 'react'
import PageLayout from '@components/page_layout'
<<<<<<< HEAD
import WorksList from '@components/works_list'
import ChapterReader from '@components/chapter_reader'
import type { Work } from '@lib/data/text'
=======
import WorksList from '@components/text/works_list'
import ChapterReader from '@components/text/chapter_reader'
import { type Work } from '@lib/data/text'
>>>>>>> ai

export default function TextPage() {
  const [selectedWork, setSelectedWork] = useState<Work | null>(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

<<<<<<< HEAD
=======
  const handleDeleteSuccess = () => {
    setRefreshTrigger((prev) => prev + 1)
  }

>>>>>>> ai
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
<<<<<<< HEAD
          <div className="flex items-center justify-between px-2 md:px-0 mb-4">
            <div className="text-xl md:text-2xl font-bold">文本管理</div>
          </div>
          <WorksList onSelectWork={handleSelectWork} refreshTrigger={refreshTrigger} />
=======
          <WorksList
            onSelectWork={handleSelectWork}
            refreshTrigger={refreshTrigger}
            onDeleteSuccess={handleDeleteSuccess}
          />
>>>>>>> ai
        </>
      )}
    </PageLayout>
  )
}
