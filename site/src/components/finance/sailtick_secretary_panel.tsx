/**
 * @file sailtick_secretary_panel.tsx
 * @brief Finance 2.0 — SailTick 日常开销秘书顶部工作台
 *        包含：即时自然语言协商条 + 真实开销/零食拆分概览 + 小票/账单 OCR 识图 + 智能余额核对 + 分级自治清理与一键撤销队列
 */

import React, { useCallback, useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ImageIntakePanel } from '@components/tick/ImageIntakePanel'
import {
  api_get_finance_overview,
  api_list_hygiene_proposals,
  api_run_hygiene_scan,
  api_approve_hygiene_proposal,
  api_dismiss_hygiene_proposal,
  api_revert_hygiene_proposal,
  api_reconcile_account_balance,
} from '@lib/api/money'
import { api_quick_chat, api_send_coach_message } from '@lib/api/tick'
import type { FinanceOverview, HygieneProposal } from '@lib/data/money'
import {
  Camera,
  Check,
  Loader2,
  RefreshCw,
  RotateCcw,
  Scale,
  Send,
  ShieldCheck,
  Sparkles,
  Wrench,
  X,
} from 'lucide-react'

const QUICK_FINANCE_PROMPTS = [
  '/money',
  '/accounts',
  '帮我扫描整理最近未打标和异常账单',
]

export interface SailTickSecretaryPanelProps {
  onDataChanged?: () => void
}

export const SailTickSecretaryPanel: React.FC<SailTickSecretaryPanelProps> = ({
  onDataChanged,
}) => {
  const [overview, setOverview] = useState<FinanceOverview | null>(null)
  const [pendingProposals, setPendingProposals] = useState<HygieneProposal[]>([])
  const [autoProposals, setAutoProposals] = useState<HygieneProposal[]>([])
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanBanner, setScanBanner] = useState<string | null>(null)

  // SailTick 即时协商条
  const [chatInput, setChatInput] = useState('')
  const [chatBusy, setChatBusy] = useState(false)
  const [chatReply, setChatReply] = useState<string | null>(null)
  const [chatNote, setChatNote] = useState<string | null>(null)

  // 展开面板开关
  const [showOcr, setShowOcr] = useState(false)
  const [showHygiene, setShowHygiene] = useState(false)
  const [hygieneTab, setHygieneTab] = useState<'pending' | 'auto'>('pending')
  const [busyProposalId, setBusyProposalId] = useState<number | null>(null)

  // 智能余额核对弹窗
  const [reconcileOpen, setReconcileOpen] = useState(false)
  const [reconcileAccId, setReconcileAccId] = useState<string>('')
  const [reconcileBalance, setReconcileBalance] = useState<string>('')
  const [reconcileForce, setReconcileForce] = useState(false)
  const [reconcileNote, setReconcileNote] = useState('')
  const [reconcileBusy, setReconcileBusy] = useState(false)
  const [reconcileMsg, setReconcileMsg] = useState<string | null>(null)

  const refreshAll = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, pend, autoApplied] = await Promise.all([
        api_get_finance_overview(),
        api_list_hygiene_proposals({ status: 'pending', limit: 30 }),
        api_list_hygiene_proposals({ status: 'applied', autonomy_level: 'auto_applied', limit: 20 }),
      ])
      setOverview(ov)
      setPendingProposals(pend)
      setAutoProposals(autoApplied)
      if (!reconcileAccId && ov.account_health.length > 0) {
        setReconcileAccId(String(ov.account_health[0].id))
      }
    } catch (e) {
      console.error('Failed to load Finance 2.0 overview:', e)
    } finally {
      setLoading(false)
    }
  }, [reconcileAccId])

  useEffect(() => {
    void refreshAll()
  }, [refreshAll])

  const sendToSailTick = async (rawText?: string) => {
    const text = (rawText ?? chatInput).trim()
    if (!text || chatBusy) return
    setChatBusy(true)
    setChatNote(null)
    try {
      const res = await api_quick_chat(text, { channel: 'web_money', session_id: 'web:money' })
      setChatReply(res.reply)
      setChatInput('')
      if (res.finance_updated) {
        setChatNote('SailTick 已同步更新账单数据 ✓')
        await refreshAll()
        onDataChanged?.()
      }
    } catch {
      try {
        await api_send_coach_message({
          content: `[财务秘书] ${text}`,
          category: 'daily_info',
          source_channel: 'web',
          auto_log_diet: false,
        })
        setChatReply('SailTick 快脑暂未在线，已将你的账单说明写入异步消息箱，下次 Tick 唤醒时会自动吸收处理。')
        setChatInput('')
      } catch (e) {
        setChatNote(`发送失败：${e instanceof Error ? e.message : String(e)}`)
      }
    } finally {
      setChatBusy(false)
    }
  }

  const handleRunScan = async () => {
    setScanning(true)
    setScanBanner(null)
    try {
      const res = await api_run_hygiene_scan({ days: 90, auto_apply_safe: true, created_by: 'web_user' })
      setScanBanner(
        `体检完成（扫描 ${res.scanned_transactions} 笔）：静默自动补标 ${res.auto_tagged_count} 笔、隔离历史平账 ${res.legacy_fix_auto_classified} 笔，新增待审建议 ${res.review_proposals_created} 条。`,
      )
      setShowHygiene(true)
      await refreshAll()
      onDataChanged?.()
    } catch (e) {
      setScanBanner(`体检失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setScanning(false)
    }
  }

  const handleProposalAction = async (id: number, action: 'approve' | 'dismiss' | 'revert') => {
    setBusyProposalId(id)
    try {
      if (action === 'approve') await api_approve_hygiene_proposal(id)
      else if (action === 'dismiss') await api_dismiss_hygiene_proposal(id)
      else await api_revert_hygiene_proposal(id)
      await refreshAll()
      onDataChanged?.()
    } finally {
      setBusyProposalId(null)
    }
  }

  const handleReconcile = async () => {
    if (!reconcileAccId || !reconcileBalance.trim()) return
    setReconcileBusy(true)
    setReconcileMsg(null)
    try {
      const res = await api_reconcile_account_balance({
        account_id: Number(reconcileAccId),
        actual_balance: reconcileBalance.trim(),
        force_adjust: reconcileForce,
        note: reconcileNote.trim(),
        source: 'web',
      })
      setReconcileMsg(res.message)
      setReconcileNote('')
      await refreshAll()
      onDataChanged?.()
    } catch (e) {
      setReconcileMsg(`核对失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setReconcileBusy(false)
    }
  }

  const selectedAcc = overview?.account_health.find((a) => String(a.id) === reconcileAccId)
  const previewDrift =
    selectedAcc && reconcileBalance.trim() && !Number.isNaN(Number(reconcileBalance))
      ? Number(reconcileBalance) - Number(selectedAcc.balance)
      : null

  return (
    <div className="space-y-3 mb-4">
      {/* 1. SailTick 财务秘书即时协商条 */}
      <Card className="border-primary/20 bg-gradient-to-r from-primary/5 via-background to-background">
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                SailTick 日常开销秘书
                <Badge variant="secondary" className="text-[11px] font-normal">
                  分级自治 · 可撤销
                </Badge>
              </CardTitle>
              <CardDescription className="text-xs mt-0.5">
                一句话记账/拆分小票、报余额无感平账，夜间静默补标与分析消费习惯
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <Button
                size="sm"
                variant={showOcr ? 'default' : 'outline'}
                className="h-7 text-xs"
                onClick={() => setShowOcr((v) => !v)}
              >
                <Camera className="h-3.5 w-3.5 mr-1" />
                小票/账单识图
              </Button>
              <Dialog open={reconcileOpen} onOpenChange={setReconcileOpen}>
                <DialogTrigger asChild>
                  <Button size="sm" variant="outline" className="h-7 text-xs">
                    <Scale className="h-3.5 w-3.5 mr-1" />
                    智能余额核对
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>智能余额核对（无感小额平账）</DialogTitle>
                    <DialogDescription>
                      差额 ≤ ¥30 将静默记录不污染消费趋势的小额平账（支持撤销）；大额差额默认进入待排查清单，避免盲目抹平。
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-3 py-1">
                    <Select value={reconcileAccId} onValueChange={setReconcileAccId}>
                      <SelectTrigger>
                        <SelectValue placeholder="选择要核对的账户" />
                      </SelectTrigger>
                      <SelectContent>
                        {(overview?.account_health ?? []).map((a) => (
                          <SelectItem key={a.id} value={String(a.id)}>
                            {a.name}（账面 ¥{a.balance}）
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="输入你现在看到的真实余额，如 2950.30"
                      value={reconcileBalance}
                      onChange={(e) => setReconcileBalance(e.target.value)}
                    />
                    {previewDrift !== null && (
                      <div className="rounded-md bg-muted/60 px-3 py-2 text-xs">
                        预计差额：
                        <span className="font-semibold ml-1">
                          {previewDrift >= 0 ? `+¥${previewDrift.toFixed(2)}` : `-¥${Math.abs(previewDrift).toFixed(2)}`}
                        </span>
                        <span className="text-muted-foreground ml-2">
                          {Math.abs(previewDrift) < 0.01
                            ? '账实完全一致'
                            : Math.abs(previewDrift) <= 30
                              ? '→ 将自动执行无感小额平账（不污染统计）'
                              : reconcileForce
                                ? '→ 已勾选强制对齐（不污染统计）'
                                : '→ 超过 ¥30，将生成待排查建议'}
                        </span>
                      </div>
                    )}
                    <Input
                      placeholder="可选备注（如：月末微信核对）"
                      value={reconcileNote}
                      onChange={(e) => setReconcileNote(e.target.value)}
                    />
                    <label className="flex items-center gap-2 text-xs cursor-pointer">
                      <input
                        type="checkbox"
                        checked={reconcileForce}
                        onChange={(e) => setReconcileForce(e.target.checked)}
                      />
                      超过 ¥30 时依然直接强制平账（同样不计入消费统计）
                    </label>
                    {reconcileMsg && (
                      <div className="text-xs rounded bg-primary/10 text-primary px-3 py-2">
                        {reconcileMsg}
                      </div>
                    )}
                  </div>
                  <DialogFooter>
                    <Button size="sm" onClick={handleReconcile} disabled={reconcileBusy}>
                      {reconcileBusy ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : null}
                      提交核对
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                onClick={handleRunScan}
                disabled={scanning}
              >
                {scanning ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                ) : (
                  <Wrench className="h-3.5 w-3.5 mr-1" />
                )}
                账单体检
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                onClick={() => void refreshAll()}
                disabled={loading}
                title="刷新概览"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-2.5">
          {/* 快捷协商输入框 */}
          <div className="flex gap-2">
            <Input
              className="h-8 text-xs"
              placeholder="例如：「盒马花了 128，零食 42 日用 86，支付宝」或「微信余额对齐到 350」"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void sendToSailTick()
              }}
            />
            <Button size="sm" className="h-8 text-xs shrink-0" onClick={() => void sendToSailTick()} disabled={chatBusy}>
              {chatBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5 mr-1" />}
              发送
            </Button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_FINANCE_PROMPTS.map((p) => (
              <button
                key={p}
                type="button"
                className="text-[11px] px-2 py-0.5 rounded-full border bg-background hover:bg-muted transition-colors"
                onClick={() => void sendToSailTick(p)}
              >
                {p}
              </button>
            ))}
          </div>

          {chatReply && (
            <div className="rounded-md border bg-background/80 p-2.5 text-xs whitespace-pre-wrap leading-relaxed">
              {chatReply}
              {chatNote && <div className="mt-1 text-[11px] text-emerald-600 font-medium">{chatNote}</div>}
            </div>
          )}

          {scanBanner && (
            <div className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-300">
              {scanBanner}
            </div>
          )}

          {/* 2. 四格财务健康 KPI 摘要 */}
          {overview && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1">
              <div className="rounded-md border bg-background/70 p-2.5">
                <div className="text-[11px] text-muted-foreground">本月真实支出 ({overview.month})</div>
                <div className="text-base font-bold mt-0.5">¥{overview.mtd_expense}</div>
                <div className="text-[11px] text-muted-foreground">
                  今日 ¥{overview.today_expense} · 已隔离 {overview.excluded_adjustments_count} 笔平账
                </div>
              </div>
              <div className="rounded-md border bg-background/70 p-2.5">
                <div className="text-[11px] text-muted-foreground">真实零食开销（含小票拆分）</div>
                <div className="text-base font-bold mt-0.5">
                  ¥{overview.mtd_snack_total}
                  <span className="text-xs font-normal text-muted-foreground ml-1">
                    ({overview.mtd_snack_pct}%)
                  </span>
                </div>
                <div className="text-[11px] text-muted-foreground">
                  混合采购拆出 ¥{overview.mtd_snack_from_split} · 联动健康
                </div>
              </div>
              <div className="rounded-md border bg-background/70 p-2.5">
                <div className="text-[11px] text-muted-foreground">历史标签覆盖率</div>
                <div className="text-base font-bold mt-0.5">{overview.overall_tag_coverage_pct}%</div>
                <div className="text-[11px] text-muted-foreground">
                  未打标 {overview.overall_untagged_expense_count} 笔
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowHygiene((v) => !v)}
                className="rounded-md border bg-background/70 p-2.5 text-left hover:bg-muted/50 transition-colors"
              >
                <div className="text-[11px] text-muted-foreground flex items-center justify-between">
                  <span>账单治理队列</span>
                  <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                </div>
                <div className="text-base font-bold mt-0.5">
                  待确认 {overview.pending_hygiene_count}
                  <span className="text-xs font-normal text-muted-foreground ml-1.5">
                    / 已托管 {overview.auto_applied_hygiene_count}
                  </span>
                </div>
                <div className="text-[11px] text-primary">
                  {showHygiene ? '收起清理面板' : '展开审阅 / 一键撤销 →'}
                </div>
              </button>
            </div>
          )}

          {overview && overview.silent_accounts.length > 0 && (
            <div className="text-xs rounded-md bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 text-amber-800 dark:text-amber-300">
              沉默账户提醒：
              {overview.silent_accounts
                .map((a) => `${a.name}（已 ${a.days_silent} 天无流水）`)
                .join('、')}
              — 可点右上角「智能余额核对」顺手对齐。
            </div>
          )}
        </CardContent>
      </Card>

      {/* 3. 小票 / 账单截图 OCR 识图面板（可折叠） */}
      {showOcr && (
        <ImageIntakePanel
          onCommitted={() => {
            void refreshAll()
            onDataChanged?.()
          }}
        />
      )}

      {/* 4. 分级自治清理队列与可撤销审计面板 */}
      {showHygiene && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-sm">分级自治账单清理与审计</CardTitle>
              <div className="flex gap-1.5">
                <Button
                  size="sm"
                  variant={hygieneTab === 'pending' ? 'default' : 'outline'}
                  className="h-7 text-xs"
                  onClick={() => setHygieneTab('pending')}
                >
                  待人工确认 ({pendingProposals.length})
                </Button>
                <Button
                  size="sm"
                  variant={hygieneTab === 'auto' ? 'default' : 'outline'}
                  className="h-7 text-xs"
                  onClick={() => setHygieneTab('auto')}
                >
                  AI 已静默处理 ({autoProposals.length})
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {hygieneTab === 'pending' ? (
              pendingProposals.length === 0 ? (
                <div className="text-xs text-muted-foreground py-3 text-center">
                  当前没有待确认的账单清理建议，账本很清爽 ✓
                </div>
              ) : (
                pendingProposals.map((p) => (
                  <div
                    key={p.id}
                    className="flex flex-wrap items-start justify-between gap-2 rounded-md border p-2.5 text-xs"
                  >
                    <div className="space-y-0.5 flex-1 min-w-[200px]">
                      <div className="font-medium flex items-center gap-1.5">
                        <Badge variant="outline" className="text-[10px]">
                          {p.proposal_type}
                        </Badge>
                        <span>{p.title}</span>
                      </div>
                      <div className="text-muted-foreground">{p.reason}</div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Button
                        size="sm"
                        className="h-7 text-xs"
                        disabled={busyProposalId === p.id}
                        onClick={() => void handleProposalAction(p.id, 'approve')}
                      >
                        <Check className="h-3 w-3 mr-1" />
                        批准
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs"
                        disabled={busyProposalId === p.id}
                        onClick={() => void handleProposalAction(p.id, 'dismiss')}
                      >
                        <X className="h-3 w-3 mr-1" />
                        忽略
                      </Button>
                    </div>
                  </div>
                ))
              )
            ) : autoProposals.length === 0 ? (
              <div className="text-xs text-muted-foreground py-3 text-center">
                暂无 AI 静默处理记录，点击「账单体检」或等待今晚 00:00 自动运行。
              </div>
            ) : (
              autoProposals.map((p) => (
                <div
                  key={p.id}
                  className="flex flex-wrap items-start justify-between gap-2 rounded-md border p-2.5 text-xs bg-muted/20"
                >
                  <div className="space-y-0.5 flex-1 min-w-[200px]">
                    <div className="font-medium flex items-center gap-1.5">
                      <Badge variant="secondary" className="text-[10px]">
                        已自动执行
                      </Badge>
                      <span>{p.title}</span>
                    </div>
                    <div className="text-muted-foreground">{p.reason}</div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs shrink-0"
                    disabled={busyProposalId === p.id}
                    onClick={() => void handleProposalAction(p.id, 'revert')}
                  >
                    <RotateCcw className="h-3 w-3 mr-1" />
                    一键撤销
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
