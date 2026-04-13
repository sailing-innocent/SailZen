import type { NodeStatus } from '@lib/data/dag_pipeline'

export const STATUS_COLOR: Record<NodeStatus, string> = {
  pending: 'bg-slate-700 border-slate-500 text-slate-300',
  running: 'bg-blue-900/60 border-blue-400 text-blue-200',
  success: 'bg-emerald-900/60 border-emerald-400 text-emerald-200',
  failed: 'bg-red-900/60 border-red-400 text-red-200',
  waiting: 'bg-amber-900/60 border-amber-400 text-amber-200',
  skipped: 'bg-slate-800 border-slate-600 text-slate-500',
}

export const STATUS_DOT: Record<NodeStatus, string> = {
  pending: 'bg-slate-500',
  running: 'bg-blue-400 animate-pulse',
  success: 'bg-emerald-400',
  failed: 'bg-red-400',
  waiting: 'bg-amber-400 animate-pulse',
  skipped: 'bg-slate-600',
}

export const NODE_TYPE_ICON: Record<string, string> = {
  git: '\u2387',
  shell: '$',
  build: '\u2699',
  test: '\u2713',
  docker: '\uD83D\uDC33',
  deploy: '\uD83D\uDE80',
  notification: '\uD83D\uDD14',
  security: '\uD83D\uDEE1',
  monitor: '\uD83D\uDCE1',
  agent: '\uD83E\uDD16',
  llm: '\uD83E\uDDE0',
  popo: '\uD83D\uDCE8',
  report: '\uD83D\uDCCA',
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return '\u2014'
  if (seconds < 60) return `${seconds.toFixed(0)}s`
  return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`
}

export function formatDatetime(iso: string | null): string {
  if (!iso) return '\u2014'
  return new Date(iso).toLocaleTimeString()
}

export function layoutNodes(
  nodeDefs: Array<{ node_id: string; depends_on: string[] }>
): Record<string, { x: number; y: number }> {
  const levels: Record<string, number> = {}
  const resolved = new Set<string>()
  const allIds = nodeDefs.map((n) => n.node_id)

  function getLevel(id: string): number {
    if (levels[id] !== undefined) return levels[id]
    const node = nodeDefs.find((n) => n.node_id === id)
    if (!node || node.depends_on.length === 0) {
      levels[id] = 0
      return 0
    }
    const parentLevels = node.depends_on
      .filter((d) => allIds.includes(d))
      .map((d) => getLevel(d))
    levels[id] = Math.max(...parentLevels) + 1
    return levels[id]
  }

  for (const id of allIds) {
    if (!resolved.has(id)) {
      getLevel(id)
      resolved.add(id)
    }
  }

  const byLevel: Record<number, string[]> = {}
  for (const [id, lvl] of Object.entries(levels)) {
    if (!byLevel[lvl]) byLevel[lvl] = []
    byLevel[lvl].push(id)
  }

  const positions: Record<string, { x: number; y: number }> = {}
  const NODE_W = 220
  const NODE_H = 90
  const GAP_X = 60
  const GAP_Y = 40

  for (const [lvl, ids] of Object.entries(byLevel)) {
    const level = Number(lvl)
    ids.forEach((id, idx) => {
      positions[id] = {
        x: level * (NODE_W + GAP_X),
        y: idx * (NODE_H + GAP_Y),
      }
    })
  }

  return positions
}
