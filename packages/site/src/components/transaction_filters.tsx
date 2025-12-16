import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { X, Filter, Calendar, Tag, DollarSign } from 'lucide-react'
import DatePicker from './date_picker'
import { Separator } from '@/components/ui/separator'
import { useIsMobile } from '@/hooks/use-mobile'

export interface TransactionFilters {
  dateRange: {
    start?: Date
    end?: Date
  }
  timePreset?: 'today' | 'week' | 'month' | 'quarter' | 'year'
  tags: string[]
  amountRange: {
    min?: number
    max?: number
  }
  amountPreset?: 'small' | 'medium' | 'large' | 'custom'
}

interface TransactionFiltersProps {
  filters: TransactionFilters
  onFiltersChange: (filters: TransactionFilters) => void
  onReset: () => void
}

const TransactionFiltersComponent: React.FC<TransactionFiltersProps> = ({ filters, onFiltersChange, onReset }) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const [tagInput, setTagInput] = useState('')
  const isMobile = useIsMobile()

  const updateFilters = (updates: Partial<TransactionFilters>) => {
    onFiltersChange({ ...filters, ...updates })
  }

  const handleTimePresetChange = (preset: string) => {
    const now = new Date()
    let start: Date, end: Date

    switch (preset) {
      case 'today': {
        start = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
        break
      }
      case 'week': {
        const weekStart = new Date(now)
        weekStart.setDate(now.getDate() - now.getDay())
        start = new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate())
        end = new Date(start)
        end.setDate(start.getDate() + 7)
        break
      }
      case 'month': {
        start = new Date(now.getFullYear(), now.getMonth(), 1)
        end = new Date(now.getFullYear(), now.getMonth() + 1, 1)
        break
      }
      case 'quarter': {
        const quarter = Math.floor(now.getMonth() / 3)
        start = new Date(now.getFullYear(), quarter * 3, 1)
        end = new Date(now.getFullYear(), quarter * 3 + 3, 1)
        break
      }
      case 'year': {
        start = new Date(now.getFullYear(), 0, 1)
        end = new Date(now.getFullYear() + 1, 0, 1)
        break
      }
      default:
        return
    }

    updateFilters({
      timePreset: preset as TransactionFilters['timePreset'],
      dateRange: { start, end },
    })
  }

  const handleAmountPresetChange = (preset: string) => {
    let min: number | undefined, max: number | undefined

    switch (preset) {
      case 'small':
        min = 0
        max = 100
        break
      case 'medium':
        min = 100
        max = 500
        break
      case 'large':
        min = 500
        max = undefined
        break
      case 'custom':
        // Keep current values
        return
      default:
        min = undefined
        max = undefined
    }

    updateFilters({
      amountPreset: preset as TransactionFilters['amountPreset'],
      amountRange: { min, max },
    })
  }

  const addTag = () => {
    if (tagInput.trim() && !filters.tags.includes(tagInput.trim())) {
      updateFilters({
        tags: [...filters.tags, tagInput.trim()],
      })
      setTagInput('')
    }
  }

  const removeTag = (tag: string) => {
    updateFilters({
      tags: filters.tags.filter((t) => t !== tag),
    })
  }

  const hasActiveFilters =
    filters.dateRange.start ||
    filters.dateRange.end ||
    filters.tags.length > 0 ||
    filters.amountRange.min !== undefined ||
    filters.amountRange.max !== undefined

  return (
    <Card className="w-full mb-4">
      <CardHeader className={`pb-3 ${isMobile ? 'px-4 py-3' : ''}`}>
        <div className={`flex items-center justify-between ${isMobile ? 'flex-col gap-2' : ''}`}>
          <CardTitle className={`flex items-center gap-2 ${isMobile ? 'text-base' : ''}`}>
            <Filter className={`${isMobile ? 'h-3 w-3' : 'h-4 w-4'}`} />
            交易筛选器
            {hasActiveFilters && (
              <Badge variant="secondary" className={`ml-2 ${isMobile ? 'text-xs' : ''}`}>
                已激活
              </Badge>
            )}
          </CardTitle>
          <div className={`flex items-center gap-2 ${isMobile ? 'w-full justify-between' : ''}`}>
            {hasActiveFilters && (
              <Button variant="outline" size={isMobile ? 'sm' : 'sm'} onClick={onReset} className={`${isMobile ? 'h-8 text-xs' : ''}`}>
                重置
              </Button>
            )}
            <Button
              variant="ghost"
              size={isMobile ? 'sm' : 'sm'}
              onClick={() => setIsExpanded(!isExpanded)}
              className={`${isMobile ? 'h-8 text-xs' : ''}`}
            >
              {isExpanded ? '隐藏' : '显示'} 筛选器
            </Button>
          </div>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className={`space-y-6 ${isMobile ? 'px-4 py-3 space-y-4' : ''}`}>
          {/* Time Range Filters */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Calendar className={`${isMobile ? 'h-3 w-3' : 'h-4 w-4'}`} />
              <Label className={`font-medium ${isMobile ? 'text-sm' : 'text-sm'}`}>时间范围</Label>
            </div>

            <div className={`grid gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-2'}`}>
              <div>
                <Label htmlFor="time-preset" className={`${isMobile ? 'text-sm' : 'text-sm'}`}>
                  快速选择
                </Label>
                <Select value={filters.timePreset || ''} onValueChange={handleTimePresetChange}>
                  <SelectTrigger className={`${isMobile ? 'h-10' : ''}`}>
                    <SelectValue placeholder="选择时间段" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="today">Today</SelectItem>
                    <SelectItem value="week">This Week</SelectItem>
                    <SelectItem value="month">This Month</SelectItem>
                    <SelectItem value="quarter">This Quarter</SelectItem>
                    <SelectItem value="year">This Year</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <DatePicker
                label="Start Date"
                placeholder="Select start date"
                value={filters.dateRange.start}
                onChange={(date) =>
                  updateFilters({
                    dateRange: { ...filters.dateRange, start: date },
                    timePreset: undefined,
                  })
                }
              />
              <DatePicker
                label="End Date"
                placeholder="Select end date"
                value={filters.dateRange.end}
                onChange={(date) =>
                  updateFilters({
                    dateRange: { ...filters.dateRange, end: date },
                    timePreset: undefined,
                  })
                }
              />
            </div>
          </div>

          <Separator />

          {/* Tags Filter */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Tag className="h-4 w-4" />
              <Label className="text-sm font-medium">Tags</Label>
            </div>

            <div className="flex gap-2">
              <Input
                placeholder="Enter tag name"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addTag()}
                className="flex-1"
              />
              <Button onClick={addTag} size="sm">
                Add
              </Button>
            </div>

            {filters.tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {filters.tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="flex items-center gap-1">
                    {tag}
                    <X className="h-3 w-3 cursor-pointer" onClick={() => removeTag(tag)} />
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <Separator />

          {/* Amount Range Filter */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4" />
              <Label className="text-sm font-medium">Amount Range</Label>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="amount-preset" className="text-sm">
                  Quick Select
                </Label>
                <Select value={filters.amountPreset || ''} onValueChange={handleAmountPresetChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select range" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="small">Small (0-100)</SelectItem>
                    <SelectItem value="medium">Medium (100-500)</SelectItem>
                    <SelectItem value="large">Large (500+)</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="min-amount" className="text-sm">
                  Minimum Amount (¥)
                </Label>
                <Input
                  id="min-amount"
                  type="number"
                  placeholder="0"
                  value={filters.amountRange.min || ''}
                  onChange={(e) =>
                    updateFilters({
                      amountRange: {
                        ...filters.amountRange,
                        min: e.target.value ? parseFloat(e.target.value) : undefined,
                      },
                      amountPreset: 'custom',
                    })
                  }
                />
              </div>
              <div>
                <Label htmlFor="max-amount" className="text-sm">
                  Maximum Amount (¥)
                </Label>
                <Input
                  id="max-amount"
                  type="number"
                  placeholder="No limit"
                  value={filters.amountRange.max || ''}
                  onChange={(e) =>
                    updateFilters({
                      amountRange: {
                        ...filters.amountRange,
                        max: e.target.value ? parseFloat(e.target.value) : undefined,
                      },
                      amountPreset: 'custom',
                    })
                  }
                />
              </div>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}

export default TransactionFiltersComponent
