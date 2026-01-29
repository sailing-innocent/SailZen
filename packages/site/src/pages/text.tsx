/**
 * @file text.tsx
 * @brief Text Management Page
 * @author sailing-innocent
 * @date 2025-01-29
 */

import { useState } from 'react'
import PageLayout from '@components/page_layout'
import TextImportDialog from '@components/text_import_dialog'
import WorksList from '@components/works_list'
import ChapterReader from '@components/chapter_reader'
import type { Work, ImportResponse } from '@lib/data/text'

export default function TextPage() {
  const [selectedWork, setSelectedWork] = useState<Work | null>(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const handleImportSuccess = (response: ImportResponse) => {
    setRefreshTrigger((prev) => prev + 1)
    // 自动选择刚导入的作品
    setSelectedWork(response.work)
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
          <div className="flex items-center justify-between px-2 md:px-0 mb-4">
            <div className="text-xl md:text-2xl font-bold">文本管理</div>
            <TextImportDialog onImportSuccess={handleImportSuccess} />
          </div>
          <WorksList onSelectWork={handleSelectWork} refreshTrigger={refreshTrigger} />
        </>
      )}
    </PageLayout>
  )
}
