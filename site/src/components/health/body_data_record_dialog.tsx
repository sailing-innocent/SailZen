/**
 * @file body_data_record_dialog.tsx
 * @brief Body data record dialog (多指标身体数据录入对话框)
 * @author sailing-innocent
 * @date 2026-09-06
 *
 * 录入语义：每个指标一个输入框，留空 = 本次未测量（data 中不出现该 key）。
 * 内置指标按 category 分组展示（min/max 软校验，越界禁止保存）；
 * 支持自定义 x_ 前缀指标行（key 需匹配 ^x_[a-z0-9_]+$）。
 * data 含 weight 时后端自动 dual-write 体重（source=manual），无需额外操作。
 */

import React from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import DatePicker from '@components/date_picker'
import { type BodyDataState, useBodyDataStore } from '@lib/store/body_data'
import { type BodyDataRecord, type BodyMetricDef } from '@lib/data/body_data'
import { useIsMobile } from '@/hooks/use-mobile'
import { Plus, X } from 'lucide-react'

const CUSTOM_KEY_PATTERN = /^x_[a-z0-9_]+$/

interface CustomMetricRow {
  key: string
  value: string
}

interface BodyDataRecordDialogProps {
  triggerClassName?: string
  onSaved?: (record: BodyDataRecord) => void
}

const BodyDataRecordDialog: React.FC<BodyDataRecordDialogProps> = ({ triggerClassName, onSaved }) => {
  const metrics = useBodyDataStore((state: BodyDataState) => state.metrics)
  const createRecord = useBodyDataStore((state: BodyDataState) => state.createRecord)
  const isMobile = useIsMobile()

  const [open, setOpen] = React.useState<boolean>(false)
  const [createDate, setCreateDate] = React.useState<Date>(new Date())
  const [values, setValues] = React.useState<Record<string, string>>({})
  const [customRows, setCustomRows] = React.useState<CustomMetricRow[]>([])
  const [tag, setTag] = React.useState<string>('raw')
  const [description, setDescription] = React.useState<string>('')

  // Builtin metrics grouped by category, preserving registry order
  const groupedBuiltin = React.useMemo(() => {
    const groups: Partial<Record<BodyMetricDef['category'], BodyMetricDef[]>> = {}
    for (const metric of metrics) {
      if (!metric.builtin) continue
      const list = groups[metric.category] ?? []
      list.push(metric)
      groups[metric.category] = list
    }
    return groups
  }, [metrics])

  const resetForm = () => {
    setCreateDate(new Date())
    setValues({})
    setCustomRows([])
    setTag('raw')
    setDescription('')
  }

  const setMetricValue = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  // Parse one builtin metric entry; empty string = not measured
  const parseBuiltinEntry = (metric: BodyMetricDef): number | null => {
    const raw = (values[metric.key] ?? '').trim()
    if (raw === '') return null
    const value = parseFloat(raw)
    if (!isFinite(value)) return NaN
    if (metric.min !== undefined && value < metric.min) return NaN
    if (metric.max !== undefined && value > metric.max) return NaN
    return value
  }

  const builtinEntries = React.useMemo(
    () =>
      metrics
        .filter((m) => m.builtin)
        .map((m) => ({ metric: m, value: parseBuiltinEntry(m) })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [metrics, values]
  )

  const customEntries = React.useMemo(
    () =>
      customRows.map((row) => {
        const key = row.key.trim()
        const raw = row.value.trim()
        if (key === '' && raw === '') return { row, key, value: null as number | null, error: '' }
        if (!CUSTOM_KEY_PATTERN.test(key)) {
          return { row, key, value: NaN, error: 'key 需以 x_ 开头（小写字母/数字/下划线）' }
        }
        if (metrics.some((m) => m.key === key)) {
          return { row, key, value: NaN, error: '与内置指标重复' }
        }
        if (raw === '') return { row, key, value: NaN, error: '请输入数值' }
        const value = parseFloat(raw)
        if (!isFinite(value)) return { row, key, value: NaN, error: '数值无效' }
        return { row, key, value: value as number | null, error: '' }
      }),
    [customRows, metrics]
  )

  const invalidBuiltin = builtinEntries.filter((e) => e.value !== null && isNaN(e.value))
  const invalidCustom = customEntries.filter((e) => e.error !== '')
  const measuredBuiltin = builtinEntries.filter((e) => e.value !== null && !isNaN(e.value))
  const measuredCustom = customEntries.filter((e) => e.value !== null && !isNaN(e.value))
  const canSave =
    (measuredBuiltin.length > 0 || measuredCustom.length > 0) &&
    invalidBuiltin.length === 0 &&
    invalidCustom.length === 0

  const handleSave = async () => {
    const data: Record<string, number> = {}
    for (const entry of measuredBuiltin) {
      data[entry.metric.key] = entry.value as number
    }
    for (const entry of measuredCustom) {
      data[entry.key] = entry.value as number
    }
    if (Object.keys(data).length === 0) return

    const record = await createRecord({
      htime: Math.floor(createDate.getTime() / 1000),
      data,
      tag: tag || 'raw',
      description,
    })
    resetForm()
    setOpen(false)
    onSaved?.(record)
  }

  const renderBuiltinRow = (metric: BodyMetricDef) => {
    const raw = values[metric.key] ?? ''
    const parsed = parseBuiltinEntry(metric)
    const showError = raw.trim() !== '' && isNaN(parsed as number)
    return (
      <div
        key={metric.key}
        className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}
      >
        <Label htmlFor={`metric-${metric.key}`} className={isMobile ? '' : 'text-right'}>
          {metric.labelZh}
          {metric.unit ? ` (${metric.unit})` : ''}
        </Label>
        <div className={isMobile ? 'w-full' : 'col-span-3'}>
          <Input
            id={`metric-${metric.key}`}
            className="w-full"
            placeholder={
              metric.min !== undefined && metric.max !== undefined
                ? `${metric.min} - ${metric.max}`
                : 'e.g., 70.5'
            }
            value={raw}
            onChange={(e) => setMetricValue(metric.key, e.target.value)}
          />
          {showError && (
            <div className="text-xs text-red-500 mt-1">
              无效数值
              {metric.min !== undefined && metric.max !== undefined
                ? `（范围 ${metric.min} - ${metric.max}）`
                : ''}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger className={triggerClassName}>
        <Input id="add-body-data" placeholder="Add Body Data" readOnly />
      </DialogTrigger>
      <DialogContent className={isMobile ? 'w-[95vw] max-w-[95vw]' : ''}>
        <DialogHeader>
          <DialogTitle>Add Body Data</DialogTitle>
          <DialogDescription>
            Enter any measured metrics below. Leave a field empty if not measured.
            {metrics.some((m) => m.key === 'weight') &&
              ' Weight entries are also recorded to the weight plan automatically.'}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto pr-1">
          <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
            <Label htmlFor="body-data-date" className={isMobile ? '' : 'text-right'}>
              Date
            </Label>
            <DatePicker
              label=""
              placeholder="Select date"
              onChange={(date: Date) => {
                setCreateDate(date)
              }}
            />
          </div>

          {(Object.keys(groupedBuiltin) as BodyMetricDef['category'][]).map((category) => (
            <React.Fragment key={category}>
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                {category === 'body' ? '身体' : category === 'intake' ? '摄入' : '健身'}
              </div>
              {groupedBuiltin[category]?.map(renderBuiltinRow)}
            </React.Fragment>
          ))}

          {/* Custom x_ metrics */}
          <div className="flex items-center justify-between">
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              自定义指标
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setCustomRows((prev) => [...prev, { key: '', value: '' }])}
            >
              <Plus className="h-4 w-4 mr-1" />
              Add
            </Button>
          </div>
          {customEntries.map((entry, index) => (
            <div key={index} className={`grid items-center gap-2 ${isMobile ? 'grid-cols-1' : 'grid-cols-12'}`}>
              <div className={isMobile ? 'w-full' : 'col-span-5'}>
                <Input
                  placeholder="x_metric_key"
                  value={entry.row.key}
                  onChange={(e) =>
                    setCustomRows((prev) =>
                      prev.map((r, i) => (i === index ? { ...r, key: e.target.value } : r))
                    )
                  }
                />
              </div>
              <div className={isMobile ? 'w-full' : 'col-span-5'}>
                <Input
                  placeholder="value"
                  value={entry.row.value}
                  onChange={(e) =>
                    setCustomRows((prev) =>
                      prev.map((r, i) => (i === index ? { ...r, value: e.target.value } : r))
                    )
                  }
                />
              </div>
              <div className={isMobile ? 'w-full' : 'col-span-2 flex justify-end'}>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setCustomRows((prev) => prev.filter((_, i) => i !== index))}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              {entry.error && (
                <div className={`text-xs text-red-500 ${isMobile ? '' : 'col-span-12'}`}>
                  {entry.key ? `${entry.key}: ` : ''}{entry.error}
                </div>
              )}
            </div>
          ))}

          <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
            <Label htmlFor="body-data-tag" className={isMobile ? '' : 'text-right'}>
              Tag
            </Label>
            <Input
              id="body-data-tag"
              className={isMobile ? 'w-full' : 'col-span-3'}
              placeholder="e.g., morning / raw"
              value={tag}
              onChange={(e) => setTag(e.target.value)}
            />
          </div>
          <div className={`grid items-start gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
            <Label htmlFor="body-data-description" className={isMobile ? '' : 'text-right pt-2'}>
              Description
            </Label>
            <Textarea
              id="body-data-description"
              className={isMobile ? 'w-full' : 'col-span-3'}
              placeholder="Optional note..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={handleSave} disabled={!canSave}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default BodyDataRecordDialog
