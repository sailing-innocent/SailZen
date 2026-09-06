/**
 * @file body_metric_picker.tsx
 * @brief Body metric picker (指标选择器)
 * @author sailing-innocent
 * @date 2026-09-06
 *
 * 指标注册表来自 body_data store（后端 /metrics 动态下发，含 x_ 自定义指标），
 * 按 BodyMetricCategory 分组展示，选项显示中文标签 + 单位。
 */

import React from 'react'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { type BodyDataState, useBodyDataStore } from '@lib/store/body_data'
import { type BodyMetricCategory } from '@lib/data/body_data'

const CATEGORY_LABELS: Record<BodyMetricCategory, string> = {
  body: '身体',
  intake: '摄入',
  fitness: '健身',
}

interface BodyMetricPickerProps {
  value: string
  onChange: (metric: string) => void
  className?: string
  id?: string
}

const BodyMetricPicker: React.FC<BodyMetricPickerProps> = ({ value, onChange, className, id }) => {
  const metrics = useBodyDataStore((state: BodyDataState) => state.metrics)

  const grouped = React.useMemo(() => {
    const groups: Partial<Record<BodyMetricCategory, typeof metrics>> = {}
    for (const metric of metrics) {
      const list = groups[metric.category] ?? []
      list.push(metric)
      groups[metric.category] = list
    }
    return groups
  }, [metrics])

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id={id} className={className}>
        <SelectValue placeholder="选择指标" />
      </SelectTrigger>
      <SelectContent>
        {(Object.keys(CATEGORY_LABELS) as BodyMetricCategory[]).map((category) => {
          const list = grouped[category]
          if (!list || list.length === 0) return null
          return (
            <SelectGroup key={category}>
              <SelectLabel>{CATEGORY_LABELS[category]}</SelectLabel>
              {list.map((metric) => (
                <SelectItem key={metric.key} value={metric.key}>
                  {metric.labelZh}
                  {metric.unit ? ` (${metric.unit})` : ''}
                </SelectItem>
              ))}
            </SelectGroup>
          )
        })}
      </SelectContent>
    </Select>
  )
}

export default BodyMetricPicker
