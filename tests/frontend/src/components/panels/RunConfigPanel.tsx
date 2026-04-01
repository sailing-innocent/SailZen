import { useState } from 'react'
import { Play, X } from 'lucide-react'
import type { PipelineInfo } from '../../types'
import { useAppStore } from '../../store/useAppStore'
import { cn } from '../../lib/utils'

interface Props {
  pipeline: PipelineInfo
  onClose: () => void
}

export default function RunConfigPanel({ pipeline, onClose }: Props) {
  const { triggerRun } = useAppStore()
  const [loading, setLoading] = useState(false)

  const initialParams = Object.fromEntries(
    pipeline.params.map((p) => [p.key, p.default])
  )
  const [params, setParams] = useState<Record<string, unknown>>(initialParams)

  const handleRun = async () => {
    setLoading(true)
    try {
      await triggerRun(pipeline.id, params)
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-slate-800 border border-slate-600 rounded-xl p-5 w-full max-w-md shadow-2xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-bold text-slate-100">{pipeline.name}</h3>
          <p className="text-xs text-slate-400 mt-0.5">{pipeline.description}</p>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-slate-700 text-slate-400">
          <X size={18} />
        </button>
      </div>

      <div className="space-y-3 mb-5">
        {pipeline.params.map((p) => (
          <div key={p.key}>
            <label className="text-xs text-slate-400 block mb-1">{p.label}</label>
            {p.type === 'string' && (
              <input
                type="text"
                value={String(params[p.key] ?? '')}
                onChange={(e) => setParams((prev) => ({ ...prev, [p.key]: e.target.value }))}
                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              />
            )}
            {p.type === 'select' && (
              <select
                value={String(params[p.key] ?? '')}
                onChange={(e) => setParams((prev) => ({ ...prev, [p.key]: e.target.value }))}
                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              >
                {p.options?.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            )}
            {p.type === 'boolean' && (
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={Boolean(params[p.key])}
                  onChange={(e) => setParams((prev) => ({ ...prev, [p.key]: e.target.checked }))}
                  className="accent-blue-500 w-4 h-4"
                />
                <span className="text-sm text-slate-300">Enabled</span>
              </label>
            )}
          </div>
        ))}
      </div>

      <button
        onClick={handleRun}
        disabled={loading}
        className={cn(
          'w-full flex items-center justify-center gap-2 py-2 rounded-lg font-semibold text-sm transition-all',
          loading
            ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
            : 'bg-blue-600 hover:bg-blue-500 text-white'
        )}
      >
        <Play size={15} />
        {loading ? 'Starting...' : 'Run Pipeline'}
      </button>
    </div>
  )
}
