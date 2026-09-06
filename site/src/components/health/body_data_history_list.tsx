/**
 * @file body_data_history_list.tsx
 * @brief Body data history list (身体数据记录列表)
 * @author sailing-innocent
 * @date 2026-09-06
 *
 * 每条记录展示：时间、tag、本次实际测量的全部指标（label: value unit 形式）、描述。
 * 删除走 body_data store；后端会级联删除 dual-write 的体重记录（若有 weightId），
 * 因此删除含 weight 的记录后需要通过 onChanged 通知页面刷新 health store 的计划状态。
 */

import React from 'react'
import { Badge } from '@/components/ui/badge'
import { type BodyDataState, useBodyDataStore } from '@lib/store/body_data'
import { Trash2 } from 'lucide-react'

interface BodyDataHistoryListProps {
  onChanged?: (info: { hadWeight: boolean }) => void
}

// Format timestamp to date string
const formatDate = (timestamp: number) => {
  return new Date(timestamp * 1000).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const BodyDataHistoryList: React.FC<BodyDataHistoryListProps> = ({ onChanged }) => {
  const records = useBodyDataStore((state: BodyDataState) => state.records)
  const deleteRecord = useBodyDataStore((state: BodyDataState) => state.deleteRecord)
  const getMetricDef = useBodyDataStore((state: BodyDataState) => state.getMetricDef)

  const sortedRecords = React.useMemo(() => {
    return [...records].sort((a, b) => b.htime - a.htime)
  }, [records])

  const formatMetric = (key: string, value: number): string => {
    const def = getMetricDef(key)
    const precision = def?.precision ?? 1
    const unit = def?.unit ?? ''
    return `${def?.labelZh ?? key}: ${value.toFixed(precision)}${unit ? ` ${unit}` : ''}`
  }

  const handleDelete = async (recordId: number, hadWeight: boolean) => {
    await deleteRecord(recordId)
    onChanged?.({ hadWeight })
  }

  if (sortedRecords.length === 0) {
    return <div className="text-gray-500 text-sm">No body data records yet.</div>
  }

  return (
    <div className="space-y-2">
      {sortedRecords.map((record) => {
        const hadWeight = record.data['weight'] !== undefined
        const metricKeys = Object.keys(record.data)
        return (
          <div
            key={record.id}
            className="border rounded-lg p-3 bg-white dark:bg-gray-800 flex justify-between items-start gap-2"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <div className="text-xs text-gray-500">{formatDate(record.htime)}</div>
                {record.tag && record.tag !== 'raw' && (
                  <Badge variant="outline" className="text-xs">
                    {record.tag}
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {metricKeys.map((key) => (
                  <Badge key={key} variant="secondary" className="text-xs font-normal">
                    {formatMetric(key, record.data[key])}
                  </Badge>
                ))}
              </div>
              {record.description && (
                <div className="text-xs text-gray-500 mt-1 break-words">{record.description}</div>
              )}
            </div>
            <button
              onClick={() => handleDelete(record.id, hadWeight)}
              className="text-red-500 hover:text-red-700 p-1 flex-shrink-0"
              title="Delete"
            >
              <Trash2 size={16} />
            </button>
          </div>
        )
      })}
    </div>
  )
}

export default BodyDataHistoryList
