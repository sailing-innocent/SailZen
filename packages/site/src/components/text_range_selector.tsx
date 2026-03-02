/**
 * @file text_range_selector.tsx
 * @brief Text Range Selector Component
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AlertCircle, BookOpen, FileText, Layers, ChevronRight, ChevronDown, Loader2 } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import type { ChapterListItem } from '@lib/data/text'
import type { RangeSelectionMode, SelectedChapterInfo } from '@lib/data/analysis'
import { getRangeModeLabel, formatCharCount, formatTokenCount } from '@lib/data/analysis'

// ============================================================================
// Types
// ============================================================================

export interface TextRangeSelectorProps {
  editionId: number
  chapters: ChapterListItem[]
  selectedMode: RangeSelectionMode
  onModeChange: (mode: RangeSelectionMode) => void
  selectedChapterIndex?: number
  onSelectedChapterChange: (index: number | undefined) => void
  startIndex?: number
  onStartIndexChange: (index: number | undefined) => void
  endIndex?: number
  onEndIndexChange: (index: number | undefined) => void
  selectedIndices: number[]
  onSelectedIndicesChange: (indices: number[]) => void
  chapterCount: number
  totalChars: number
  estimatedTokens: number
  selectedChapters: SelectedChapterInfo[]
  warnings: string[]
  isLoading?: boolean
  className?: string
}

// ============================================================================
// Mode Selector Component
// ============================================================================

interface ModeSelectorProps {
  selectedMode: RangeSelectionMode
  onModeChange: (mode: RangeSelectionMode) => void
}

const MODE_OPTIONS: { value: RangeSelectionMode; label: string; icon: React.ReactNode; description: string }[] = [
  {
    value: 'single_chapter',
    label: '单章选择',
    icon: <FileText className="w-4 h-4" />,
    description: '选择单个章节',
  },
  {
    value: 'chapter_range',
    label: '连续章节',
    icon: <Layers className="w-4 h-4" />,
    description: '选择一个连续的章节范围',
  },
  {
    value: 'multi_chapter',
    label: '多章选择',
    icon: <BookOpen className="w-4 h-4" />,
    description: '选择多个不连续的章节',
  },
  {
    value: 'full_edition',
    label: '整部作品',
    icon: <BookOpen className="w-4 h-4" />,
    description: '选择整部作品的所有章节',
  },
  {
    value: 'current_to_end',
    label: '到结尾',
    icon: <ChevronRight className="w-4 h-4" />,
    description: '从指定章节到作品结尾',
  },
]

function ModeSelector({ selectedMode, onModeChange }: ModeSelectorProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
      {MODE_OPTIONS.map((mode) => (
        <Button
          key={mode.value}
          variant={selectedMode === mode.value ? 'default' : 'outline'}
          size="sm"
          className="flex flex-col items-center justify-center h-auto py-2 px-1 gap-1"
          onClick={() => onModeChange(mode.value)}
          title={mode.description}
        >
          {mode.icon}
          <span className="text-xs">{mode.label}</span>
        </Button>
      ))}
    </div>
  )
}

// ============================================================================
// Chapter Tree Component
// ============================================================================

interface ChapterTreeProps {
  chapters: ChapterListItem[]
  selectedMode: RangeSelectionMode
  selectedChapterIndex?: number
  onSelectedChapterChange: (index: number | undefined) => void
  startIndex?: number
  onStartIndexChange: (index: number | undefined) => void
  endIndex?: number
  onEndIndexChange: (index: number | undefined) => void
  selectedIndices: number[]
  onSelectedIndicesChange: (indices: number[]) => void
}

function ChapterTree({
  chapters,
  selectedMode,
  selectedChapterIndex,
  onSelectedChapterChange,
  startIndex,
  onStartIndexChange,
  endIndex,
  onEndIndexChange,
  selectedIndices,
  onSelectedIndicesChange,
}: ChapterTreeProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['all']))

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  const handleSingleSelect = (index: number) => {
    onSelectedChapterChange(selectedChapterIndex === index ? undefined : index)
  }

  const handleRangeStartChange = (index: number | undefined) => {
    onStartIndexChange(index)
    // 确保结束索引不小于起始索引
    if (index !== undefined && endIndex !== undefined && endIndex < index) {
      onEndIndexChange(index)
    }
  }

  const handleRangeEndChange = (index: number | undefined) => {
    onEndIndexChange(index)
    // 确保起始索引不大于结束索引
    if (index !== undefined && startIndex !== undefined && startIndex > index) {
      onStartIndexChange(index)
    }
  }

  const handleMultiToggle = (index: number) => {
    onSelectedIndicesChange(
      selectedIndices.includes(index)
        ? selectedIndices.filter((i) => i !== index)
        : [...selectedIndices, index].sort((a, b) => a - b)
    )
  }

  const handleSelectAll = () => {
    if (selectedIndices.length === chapters.length) {
      onSelectedIndicesChange([])
    } else {
      onSelectedIndicesChange(chapters.map((_, i) => i))
    }
  }

  const isInRange = (index: number) => {
    if (selectedMode === 'chapter_range' && startIndex !== undefined && endIndex !== undefined) {
      return index >= startIndex && index <= endIndex
    }
    return false
  }

  const isSelected = (index: number) => {
    switch (selectedMode) {
      case 'single_chapter':
        return selectedChapterIndex === index
      case 'chapter_range':
        return isInRange(index)
      case 'multi_chapter':
        return selectedIndices.includes(index)
      case 'full_edition':
        return true
      case 'current_to_end':
        return startIndex !== undefined && index >= startIndex
      default:
        return false
    }
  }

  return (
    <div className="space-y-2">
      {/* 全选按钮（仅多章模式） */}
      {selectedMode === 'multi_chapter' && (
        <div className="flex items-center gap-2 px-2 py-1 bg-muted/50 rounded">
          <Checkbox
            checked={selectedIndices.length === chapters.length && chapters.length > 0}
            onCheckedChange={handleSelectAll}
            id="select-all"
          />
          <Label htmlFor="select-all" className="text-sm cursor-pointer">
            全选 ({selectedIndices.length}/{chapters.length})
          </Label>
        </div>
      )}

      {/* 范围选择器（连续章节模式） */}
      {selectedMode === 'chapter_range' && (
        <div className="flex items-center gap-2 px-2 py-2 bg-muted/50 rounded">
          <div className="flex items-center gap-2">
            <Label className="text-xs whitespace-nowrap">从</Label>
            <select
              className="h-8 px-2 text-sm border rounded bg-background"
              value={startIndex !== undefined ? chapters.find(ch => ch.sort_index === startIndex)?.id ?? '' : ''}
              onChange={(e) => {
                const selectedId = e.target.value ? parseInt(e.target.value) : undefined
                const selectedChapter = selectedId !== undefined ? chapters.find(ch => ch.id === selectedId) : undefined
                handleRangeStartChange(selectedChapter?.sort_index)
              }}
            >
              <option value="">选择章节</option>
              {chapters.map((ch) => (
                <option key={`start-${ch.id}`} value={ch.id}>
                  {ch.label} {ch.title}
                </option>
              ))}
            </select>
          </div>
          <span className="text-muted-foreground">-</span>
          <div className="flex items-center gap-2">
            <select
              className="h-8 px-2 text-sm border rounded bg-background"
              value={endIndex !== undefined ? chapters.find(ch => ch.sort_index === endIndex)?.id ?? '' : ''}
              onChange={(e) => {
                const selectedId = e.target.value ? parseInt(e.target.value) : undefined
                const selectedChapter = selectedId !== undefined ? chapters.find(ch => ch.id === selectedId) : undefined
                handleRangeEndChange(selectedChapter?.sort_index)
              }}
            >
              <option value="">选择章节</option>
              {chapters.map((ch) => (
                <option key={`end-${ch.id}`} value={ch.id}>
                  {ch.label} {ch.title}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* 起始章节选择器（到结尾模式） */}
      {selectedMode === 'current_to_end' && (
        <div className="flex items-center gap-2 px-2 py-2 bg-muted/50 rounded">
          <Label className="text-xs whitespace-nowrap">从章节</Label>
          <select
            className="h-8 px-2 text-sm border rounded bg-background flex-1"
            value={startIndex !== undefined ? chapters.find(ch => ch.sort_index === startIndex)?.id ?? '' : ''}
            onChange={(e) => {
              const selectedId = e.target.value ? parseInt(e.target.value) : undefined
              const selectedChapter = selectedId !== undefined ? chapters.find(ch => ch.id === selectedId) : undefined
              onStartIndexChange(selectedChapter?.sort_index)
            }}
          >
            <option value="">选择起始章节</option>
            {chapters.map((ch) => (
              <option key={`current-${ch.id}`} value={ch.id}>
                {ch.label} {ch.title}
              </option>
            ))}
          </select>
          <span className="text-xs text-muted-foreground">到结尾</span>
        </div>
      )}

      {/* 章节列表 */}
      <ScrollArea className="h-[300px] border rounded-md">
        <div className="p-2 space-y-1">
          {chapters.map((chapter, idx) => {
            const selected = isSelected(chapter.sort_index)
            const inRange = isInRange(chapter.sort_index)

            return (
              <div
                key={chapter.id}
                className={`
                  flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors
                  ${selected ? 'bg-primary/10 border-primary/30' : 'hover:bg-muted'}
                  ${inRange && selectedMode === 'chapter_range' ? 'border-l-2 border-l-primary' : ''}
                `}
                onClick={() => {
                  if (selectedMode === 'single_chapter') {
                    handleSingleSelect(chapter.sort_index)
                  } else if (selectedMode === 'multi_chapter') {
                    handleMultiToggle(chapter.sort_index)
                  }
                }}
              >
                {/* 选择控件 */}
                {selectedMode === 'single_chapter' && (
                  <div
                    className={`
                      w-4 h-4 rounded-full border-2 flex items-center justify-center
                      ${selected ? 'border-primary bg-primary' : 'border-muted-foreground'}
                    `}
                  >
                    {selected && <div className="w-2 h-2 rounded-full bg-primary-foreground" />}
                  </div>
                )}
                {(selectedMode === 'multi_chapter' || selectedMode === 'full_edition') && (
                  <Checkbox
                    checked={selected}
                    onCheckedChange={() => handleMultiToggle(chapter.sort_index)}
                    onClick={(e) => e.stopPropagation()}
                  />
                )}
                {(selectedMode === 'chapter_range' || selectedMode === 'current_to_end') && (
                  <div
                    className={`
                      w-4 h-4 rounded flex items-center justify-center text-xs
                      ${selected ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}
                    `}
                  >
                    {selected && <span>✓</span>}
                  </div>
                )}

                {/* 章节信息 */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">
                    <span className="text-muted-foreground mr-1">{chapter.label}</span>
                    {chapter.title && <span>{chapter.title}</span>}
                  </div>
                </div>

                {/* 字数 */}
                {chapter.char_count !== undefined && chapter.char_count > 0 && (
                  <Badge variant="secondary" className="text-xs shrink-0">
                    {formatCharCount(chapter.char_count)}
                  </Badge>
                )}
              </div>
            )
          })}
        </div>
      </ScrollArea>
    </div>
  )
}

// ============================================================================
// Statistics Panel Component
// ============================================================================

interface StatisticsPanelProps {
  chapterCount: number
  totalChars: number
  estimatedTokens: number
  selectedChapters: SelectedChapterInfo[]
  isLoading?: boolean
}

function StatisticsPanel({
  chapterCount,
  totalChars,
  estimatedTokens,
  selectedChapters,
  isLoading,
}: StatisticsPanelProps) {
  return (
    <div className="space-y-4">
      {/* 主要统计 */}
      <div className="grid grid-cols-3 gap-2">
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-2xl font-bold text-primary">{chapterCount}</div>
            <div className="text-xs text-muted-foreground">选中章节</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-2xl font-bold text-primary">{formatCharCount(totalChars)}</div>
            <div className="text-xs text-muted-foreground">总字数</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 text-center">
            <div className="text-2xl font-bold text-primary">
              {isLoading ? (
                <Loader2 className="w-6 h-6 animate-spin mx-auto" />
              ) : (
                formatTokenCount(estimatedTokens)
              )}
            </div>
            <div className="text-xs text-muted-foreground">预估Token</div>
          </CardContent>
        </Card>
      </div>

      {/* 选中章节列表 */}
      {selectedChapters.length > 0 && (
        <div>
          <h4 className="text-sm font-medium mb-2">选中章节预览</h4>
          <ScrollArea className="h-[150px] border rounded-md">
            <div className="p-2 space-y-1">
              {selectedChapters.map((chapter) => (
                <div
                  key={chapter.id}
                  className="flex items-center justify-between px-2 py-1 text-sm bg-muted/50 rounded"
                >
                  <span className="truncate">
                    <span className="text-muted-foreground mr-1">{chapter.label}</span>
                    {chapter.title}
                  </span>
                  {chapter.char_count !== undefined && chapter.char_count > 0 && (
                    <Badge variant="outline" className="text-xs shrink-0 ml-2">
                      {formatCharCount(chapter.char_count)}
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export function TextRangeSelector({
  editionId,
  chapters,
  selectedMode,
  onModeChange,
  selectedChapterIndex,
  onSelectedChapterChange,
  startIndex,
  onStartIndexChange,
  endIndex,
  onEndIndexChange,
  selectedIndices,
  onSelectedIndicesChange,
  chapterCount,
  totalChars,
  estimatedTokens,
  selectedChapters,
  warnings,
  isLoading,
  className,
}: TextRangeSelectorProps) {
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <BookOpen className="w-4 h-4" />
          文本范围选择
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 警告信息 */}
        {warnings.length > 0 && (
          <Alert variant="warning" className="py-2">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <ul className="list-disc list-inside text-sm">
                {warnings.map((warning, idx) => (
                  <li key={idx}>{warning}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        {/* 模式选择 */}
        <div className="space-y-2">
          <Label className="text-sm font-medium">选择模式</Label>
          <ModeSelector selectedMode={selectedMode} onModeChange={onModeChange} />
        </div>

        <Separator />

        {/* 章节选择和统计 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* 左侧：章节树 */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">
              章节列表
              <span className="text-muted-foreground font-normal ml-1">({chapters.length} 章)</span>
            </Label>
            <ChapterTree
              chapters={chapters}
              selectedMode={selectedMode}
              selectedChapterIndex={selectedChapterIndex}
              onSelectedChapterChange={onSelectedChapterChange}
              startIndex={startIndex}
              onStartIndexChange={onStartIndexChange}
              endIndex={endIndex}
              onEndIndexChange={onEndIndexChange}
              selectedIndices={selectedIndices}
              onSelectedIndicesChange={onSelectedIndicesChange}
            />
          </div>

          {/* 右侧：统计面板 */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">选择统计</Label>
            <StatisticsPanel
              chapterCount={chapterCount}
              totalChars={totalChars}
              estimatedTokens={estimatedTokens}
              selectedChapters={selectedChapters}
              isLoading={isLoading}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default TextRangeSelector
