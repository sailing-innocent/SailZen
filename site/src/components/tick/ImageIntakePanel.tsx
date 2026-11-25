/**
 * @file ImageIntakePanel.tsx
 * @brief SailTick 通用视觉识图面板（选图 / 拖拽 / Ctrl+V 粘贴截图 → AI 识别 → 人工确认微调 → 落库）
 * @author sailing-innocent
 * @date 2026-11-23
 */
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  api_analyze_image_intake,
  api_commit_image_intake,
  api_discard_image_intake,
  tickMediaUrl,
  type CommittedRef,
  type ImageIntakeDraft,
  type IntakeEntry,
  type IntakeEntryKind,
  type IntakeScene,
} from '@lib/api/tick'
import {
  Camera,
  CheckCircle2,
  ClipboardPaste,
  Loader2,
  Sparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-react'

const SCENE_LABEL: Record<IntakeScene, string> = {
  diet: '餐饮记录',
  canteen_menu: '食堂/点餐菜单',
  sleep: '睡眠节律',
  exercise: '运动记录',
  weight: '体重/体脂',
  selfie_status: '气色/状态',
  receipt: '消费小票/订单',
  bill_screenshot: '账单流水截图',
  account_balance: '账户余额核对',
  general: '日常记录',
}

const KIND_OPTIONS: Array<{ value: IntakeEntryKind; label: string }> = [
  { value: 'diet', label: '饮食记录' },
  { value: 'canteen_menu', label: '食堂菜单' },
  { value: 'sleep', label: '睡眠记录' },
  { value: 'exercise', label: '运动记录' },
  { value: 'weight', label: '体重/体脂' },
  { value: 'mood', label: '状态/气色' },
  { value: 'transaction', label: '账单交易' },
  { value: 'account_balance_check', label: '余额核对' },
  { value: 'daily_info', label: '日常信息' },
]

const MEAL_OPTIONS = [
  { value: 'breakfast', label: '早餐' },
  { value: 'lunch', label: '午餐' },
  { value: 'dinner', label: '晚餐' },
  { value: 'snack', label: '加餐' },
]

export interface ImageIntakePanelProps {
  /** 从外部传入待确认草稿（如刷新页面后恢复 pending_confirm 草稿） */
  initialDrafts?: ImageIntakeDraft[]
  /** 若从某张票据点击「传图回复」，绑定该票据上下文 */
  linkedTicket?: { id: number; title: string } | null
  onClearLinkedTicket?: () => void
  /** 落库或丢弃成功后回调，用于刷新列表 */
  onCommitted?: (refs: CommittedRef[]) => void
  /** 外部直接触发传图文件（如点击票据卡片的相机按钮选中图片后传入） */
  externalFileRequest?: { file: File; ticketId: number; ticketTitle: string } | null
  onConsumeExternalFile?: () => void
}

function asStr(v: unknown): string {
  return v == null ? '' : String(v)
}

function asNumStr(v: unknown): string {
  if (v == null || v === '') return ''
  return String(v)
}

export const ImageIntakePanel: React.FC<ImageIntakePanelProps> = ({
  initialDrafts = [],
  linkedTicket,
  onClearLinkedTicket,
  onCommitted,
  externalFileRequest,
  onConsumeExternalFile,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [note, setNote] = useState('')
  const [forceOcr, setForceOcr] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const [activeDraft, setActiveDraft] = useState<ImageIntakeDraft | null>(null)
  const [entries, setEntries] = useState<IntakeEntry[]>([])
  const [summaryDraft, setSummaryDraft] = useState('')
  const [replyText, setReplyText] = useState('')

  // 如果当前没有正在编辑的草稿，自动加载最新一条待确认草稿
  useEffect(() => {
    if (!activeDraft && initialDrafts.length > 0) {
      const first = initialDrafts[0]
      setActiveDraft(first)
      setEntries(first.entries ?? [])
      setSummaryDraft(first.summary ?? '')
      setReplyText('')
    }
  }, [initialDrafts, activeDraft])

  const startAnalyze = useCallback(
    async (file: File, overrideTicketId?: number | null) => {
      setError(null)
      setNotice(null)
      setAnalyzing(true)
      try {
        const draft = await api_analyze_image_intake(file, {
          note,
          ticketId: overrideTicketId !== undefined ? overrideTicketId : linkedTicket?.id ?? null,
          sourceChannel: 'web',
          useOcrAssist: forceOcr ? 'true' : 'auto',
        })
        setActiveDraft(draft)
        setEntries(draft.entries ?? [])
        setSummaryDraft(draft.summary ?? '')
        setReplyText('')
        setNote('')
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        setAnalyzing(false)
      }
    },
    [note, linkedTicket, forceOcr],
  )

  // 响应从 Ticket 卡片触发的「传图回复」
  useEffect(() => {
    if (!externalFileRequest) return
    const { file, ticketId } = externalFileRequest
    onConsumeExternalFile?.()
    void startAnalyze(file, ticketId)
  }, [externalFileRequest, onConsumeExternalFile, startAnalyze])

  // 支持页面内直接 Ctrl+V 粘贴剪贴板截图
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      if (analyzing) return
      const items = e.clipboardData?.items
      if (!items) return
      for (const item of Array.from(items)) {
        if (item.type.startsWith('image/')) {
          const file = item.getAsFile()
          if (file) {
            e.preventDefault()
            void startAnalyze(file)
            break
          }
        }
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [analyzing, startAnalyze])

  const updateEntry = (index: number, patch: Partial<IntakeEntry>) => {
    setEntries((prev) => prev.map((it, i) => (i === index ? { ...it, ...patch } : it)))
  }

  const updateEntryData = (index: number, key: string, value: unknown) => {
    setEntries((prev) =>
      prev.map((it, i) =>
        i === index ? { ...it, data: { ...(it.data ?? {}), [key]: value } } : it,
      ),
    )
  }

  const handleCommit = async () => {
    if (!activeDraft) return
    const selectedCount = entries.filter((e) => e.selected).length
    if (selectedCount === 0) {
      setError('请至少勾选一条需要落库的记录')
      return
    }
    setError(null)
    setCommitting(true)
    try {
      const res = await api_commit_image_intake(activeDraft.id, {
        entries,
        summary: summaryDraft.trim() || activeDraft.summary,
        ticket_id: activeDraft.ticket_id ?? linkedTicket?.id ?? null,
        reply_text: replyText.trim() || undefined,
      })
      const labels = res.committed_refs.map((r) => r.label).filter(Boolean).join(' · ')
      setNotice(`已落库：${labels || '同步完成'} ✓`)
      setActiveDraft(null)
      setEntries([])
      setSummaryDraft('')
      setReplyText('')
      onClearLinkedTicket?.()
      onCommitted?.(res.committed_refs)
      setTimeout(() => setNotice(null), 6000)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setCommitting(false)
    }
  }

  const handleDiscard = async () => {
    if (!activeDraft) return
    setError(null)
    try {
      await api_discard_image_intake(activeDraft.id)
      setActiveDraft(null)
      setEntries([])
      setSummaryDraft('')
      setReplyText('')
      onClearLinkedTicket?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const selectedCount = entries.filter((e) => e.selected).length

  return (
    <Card className="mb-4 border-primary/30">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center justify-between gap-2">
          <span className="flex items-center gap-2">
            <Camera className="h-4 w-4 text-primary" />
            拍照 / 传图智能记录（DeepSeek 识图）
          </span>
          <Badge variant="outline" className="text-xs font-normal">
            支持菜单 · 手表睡眠/运动 · 餐盘 · 自拍气色
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {linkedTicket && (
          <div className="flex items-center justify-between rounded-md bg-primary/10 px-3 py-2 text-xs">
            <span>
              正在传图回复票据 <strong>#{linkedTicket.id}</strong>：{linkedTicket.title}
            </span>
            {onClearLinkedTicket && (
              <Button variant="ghost" size="sm" className="h-6 px-2" onClick={onClearLinkedTicket}>
                <X className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        )}

        {/* 上传/拖拽/粘贴区 */}
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            const file = e.dataTransfer.files?.[0]
            if (file && file.type.startsWith('image/')) {
              void startAnalyze(file)
            }
          }}
          className={`rounded-lg border border-dashed p-3 transition-colors ${
            dragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/30 bg-muted/20'
          }`}
        >
          <div className="flex flex-col sm:flex-row gap-2 items-stretch sm:items-center">
            <Input
              placeholder="可选备注：如「午饭打算在这菜单里挑」或留空直接识图…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              disabled={analyzing}
            />
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                e.target.value = ''
                if (f) void startAnalyze(f)
              }}
            />
            <Button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={analyzing}
              className="shrink-0"
            >
              {analyzing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                  识图中…
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-1.5" />
                  选择/拍照上传
                </>
              )}
            </Button>
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <ClipboardPaste className="h-3.5 w-3.5" />
              可直接拖拽图片至此，或按 Ctrl+V 粘贴截图
            </span>
            <label className="flex items-center gap-1.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={forceOcr}
                onChange={(e) => setForceOcr(e.target.checked)}
                disabled={analyzing}
              />
              强制叠加 OCR 工具（长菜单/密字图）
            </label>
          </div>
        </div>

        {error && (
          <div className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}
        {notice && (
          <div className="rounded-md bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{notice}</span>
          </div>
        )}

        {/* 待确认识图草稿确认卡片 */}
        {activeDraft && (
          <div className="rounded-lg border bg-card p-3 space-y-3">
            <div className="flex flex-col sm:flex-row gap-3">
              {activeDraft.media_url && (
                <img
                  src={tickMediaUrl(activeDraft.media_url)}
                  alt="上传图片预览"
                  className="w-full sm:w-28 h-36 sm:h-28 object-cover rounded-md border shrink-0 bg-muted"
                />
              )}
              <div className="flex-1 min-w-0 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{SCENE_LABEL[activeDraft.scene] ?? activeDraft.scene}</Badge>
                  <Badge variant="secondary" className="text-[11px]">
                    {activeDraft.model_used}
                  </Badge>
                  {activeDraft.ticket_id != null && (
                    <Badge variant="outline" className="text-[11px]">
                      关联票据 #{activeDraft.ticket_id}
                    </Badge>
                  )}
                </div>
                <Input
                  value={summaryDraft}
                  onChange={(e) => setSummaryDraft(e.target.value)}
                  className="h-8 text-sm font-medium"
                  placeholder="识别摘要"
                />
                {activeDraft.coach_advice && (
                  <p className="text-xs text-muted-foreground flex items-start gap-1.5 bg-muted/40 rounded p-2">
                    <Sparkles className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
                    <span>{activeDraft.coach_advice}</span>
                  </p>
                )}
              </div>
            </div>

            {/* 可编辑候选条目列表 */}
            <div className="space-y-2">
              {entries.map((entry, idx) => (
                <div
                  key={idx}
                  className={`rounded-md border p-2.5 space-y-2 text-xs ${
                    entry.selected ? 'bg-background' : 'bg-muted/30 opacity-60'
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="checkbox"
                      checked={entry.selected}
                      onChange={(e) => updateEntry(idx, { selected: e.target.checked })}
                    />
                    <select
                      className="h-7 rounded border bg-background px-2 text-xs"
                      value={entry.kind}
                      onChange={(e) =>
                        updateEntry(idx, { kind: e.target.value as IntakeEntryKind })
                      }
                    >
                      {KIND_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    <Input
                      className="h-7 flex-1 min-w-[140px] text-xs"
                      value={entry.title}
                      onChange={(e) => updateEntry(idx, { title: e.target.value })}
                      placeholder="条目标题"
                    />
                    <span className="text-[11px] text-muted-foreground">
                      置信度 {Math.round((entry.confidence ?? 0.85) * 100)}%
                    </span>
                  </div>

                  {/* 按类型渲染可微调字段 */}
                  {entry.kind === 'diet' && (
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                      <select
                        className="h-7 rounded border bg-background px-2 text-xs"
                        value={asStr(entry.data.meal_type) || 'lunch'}
                        onChange={(e) => updateEntryData(idx, 'meal_type', e.target.value)}
                      >
                        {MEAL_OPTIONS.map((m) => (
                          <option key={m.value} value={m.value}>
                            {m.label}
                          </option>
                        ))}
                      </select>
                      <Input
                        type="number"
                        className="h-7 text-xs"
                        placeholder="热量 kcal"
                        value={asNumStr(entry.data.calories)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'calories',
                            e.target.value ? Number(e.target.value) : null,
                          )
                        }
                      />
                      <Input
                        type="number"
                        className="h-7 text-xs"
                        placeholder="蛋白 g"
                        value={asNumStr(entry.data.protein)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'protein',
                            e.target.value ? Number(e.target.value) : null,
                          )
                        }
                      />
                      <Input
                        type="number"
                        className="h-7 text-xs"
                        placeholder="碳水 g"
                        value={asNumStr(entry.data.carbs)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'carbs',
                            e.target.value ? Number(e.target.value) : null,
                          )
                        }
                      />
                      <Input
                        type="number"
                        className="h-7 text-xs"
                        placeholder="脂肪 g"
                        value={asNumStr(entry.data.fat)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'fat',
                            e.target.value ? Number(e.target.value) : null,
                          )
                        }
                      />
                      <Input
                        className="h-7 text-xs col-span-2 sm:col-span-5"
                        placeholder="饮食内容描述"
                        value={asStr(entry.data.description)}
                        onChange={(e) => updateEntryData(idx, 'description', e.target.value)}
                      />
                    </div>
                  )}

                  {entry.kind === 'canteen_menu' && (
                    <div className="space-y-1.5">
                      {Array.isArray(entry.data.recommended_items) &&
                        entry.data.recommended_items.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            <span className="text-muted-foreground">推荐搭配：</span>
                            {(entry.data.recommended_items as string[]).map((item, i) => (
                              <Badge key={i} variant="secondary" className="text-[11px]">
                                {item}
                              </Badge>
                            ))}
                          </div>
                        )}
                      <Input
                        className="h-7 text-xs"
                        placeholder="菜单说明 / 点餐记录"
                        value={asStr(entry.data.description)}
                        onChange={(e) => updateEntryData(idx, 'description', e.target.value)}
                      />
                      <div className="flex flex-wrap items-center gap-3">
                        <label className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={Boolean(entry.data.log_as_diet)}
                            onChange={(e) => updateEntryData(idx, 'log_as_diet', e.target.checked)}
                          />
                          同时记为本餐饮食记录
                        </label>
                        <Input
                          type="number"
                          className="h-7 w-28 text-xs"
                          placeholder="估热量 kcal"
                          value={asNumStr(entry.data.estimated_calories)}
                          onChange={(e) =>
                            updateEntryData(
                              idx,
                              'estimated_calories',
                              e.target.value ? Number(e.target.value) : null,
                            )
                          }
                        />
                      </div>
                    </div>
                  )}

                  {entry.kind === 'sleep' && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <Input
                        type="number"
                        step="0.1"
                        className="h-7 text-xs"
                        placeholder="时长(小时)"
                        value={asNumStr(entry.data.hours)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'hours',
                            e.target.value ? Number(e.target.value) : 7,
                          )
                        }
                      />
                      <Input
                        type="number"
                        min={1}
                        max={5}
                        className="h-7 text-xs"
                        placeholder="质量(1-5)"
                        value={asNumStr(entry.data.quality)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'quality',
                            e.target.value ? Number(e.target.value) : 3,
                          )
                        }
                      />
                      <Input
                        className="h-7 text-xs col-span-2"
                        placeholder="入睡/醒来与深浅睡摘要"
                        value={asStr(entry.data.description)}
                        onChange={(e) => updateEntryData(idx, 'description', e.target.value)}
                      />
                    </div>
                  )}

                  {entry.kind === 'exercise' && (
                    <div className="grid grid-cols-3 gap-2">
                      <Input
                        className="h-7 text-xs"
                        placeholder="运动类型(如 running)"
                        value={asStr(entry.data.exercise_type)}
                        onChange={(e) => updateEntryData(idx, 'exercise_type', e.target.value)}
                      />
                      <Input
                        type="number"
                        className="h-7 text-xs"
                        placeholder="时长(分钟)"
                        value={asNumStr(entry.data.duration_minutes)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'duration_minutes',
                            e.target.value ? Number(e.target.value) : 0,
                          )
                        }
                      />
                      <Input
                        type="number"
                        className="h-7 text-xs"
                        placeholder="消耗(kcal)"
                        value={asNumStr(entry.data.calories)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'calories',
                            e.target.value ? Number(e.target.value) : 0,
                          )
                        }
                      />
                      <Input
                        className="h-7 text-xs col-span-3"
                        placeholder="运动详情（配速/心率/距离）"
                        value={asStr(entry.data.description)}
                        onChange={(e) => updateEntryData(idx, 'description', e.target.value)}
                      />
                    </div>
                  )}

                  {entry.kind === 'weight' && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <Input
                        type="number"
                        step="0.1"
                        className="h-7 text-xs"
                        placeholder="体重(kg)"
                        value={asNumStr(entry.data.value)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'value',
                            e.target.value ? Number(e.target.value) : null,
                          )
                        }
                      />
                      <Input
                        type="number"
                        step="0.1"
                        className="h-7 text-xs"
                        placeholder="体脂(%)"
                        value={asNumStr(entry.data.body_fat)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'body_fat',
                            e.target.value ? Number(e.target.value) : null,
                          )
                        }
                      />
                      <Input
                        className="h-7 text-xs col-span-2"
                        placeholder="备注"
                        value={asStr(entry.data.description)}
                        onChange={(e) => updateEntryData(idx, 'description', e.target.value)}
                      />
                    </div>
                  )}

                  {entry.kind === 'mood' && (
                    <div className="grid grid-cols-4 gap-2">
                      <Input
                        type="number"
                        min={1}
                        max={5}
                        className="h-7 text-xs"
                        placeholder="状态分(1-5)"
                        value={asNumStr(entry.data.score)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'score',
                            e.target.value ? Number(e.target.value) : 3,
                          )
                        }
                      />
                      <Input
                        className="h-7 text-xs col-span-3"
                        placeholder="气色/精神状态观察"
                        value={asStr(entry.data.description)}
                        onChange={(e) => updateEntryData(idx, 'description', e.target.value)}
                      />
                    </div>
                  )}

                  {entry.kind === 'transaction' && (
                    <div className="space-y-2">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        <Input
                          type="number"
                          step="0.01"
                          className="h-7 text-xs"
                          placeholder="金额 (¥)"
                          value={asNumStr(entry.data.amount)}
                          onChange={(e) =>
                            updateEntryData(
                              idx,
                              'amount',
                              e.target.value ? Number(e.target.value) : null,
                            )
                          }
                        />
                        <Input
                          className="h-7 text-xs"
                          placeholder="账户(微信/支付宝)"
                          value={asStr(entry.data.account_hint)}
                          onChange={(e) => updateEntryData(idx, 'account_hint', e.target.value)}
                        />
                        <Input
                          className="h-7 text-xs"
                          placeholder="标签(逗号分隔)"
                          value={asStr(entry.data.tags)}
                          onChange={(e) => updateEntryData(idx, 'tags', e.target.value)}
                        />
                        <Input
                          className="h-7 text-xs"
                          placeholder="发生时间"
                          value={asStr(entry.data.htime)}
                          onChange={(e) => updateEntryData(idx, 'htime', e.target.value)}
                        />
                      </div>
                      <Input
                        className="h-7 text-xs"
                        placeholder="商户 / 消费描述"
                        value={asStr(entry.data.description)}
                        onChange={(e) => updateEntryData(idx, 'description', e.target.value)}
                      />
                      {Array.isArray(entry.data.items) && entry.data.items.length > 0 && (
                        <div className="rounded border bg-muted/30 p-2 space-y-1">
                          <div className="text-[11px] font-medium text-muted-foreground">
                            已自动拆分明细（共 {entry.data.items.length} 项，主账单仍保持 1 笔流水）：
                          </div>
                          {(entry.data.items as Array<Record<string, unknown>>).map((sub, si) => (
                            <div
                              key={si}
                              className="flex flex-wrap items-center justify-between gap-2 text-[11px]"
                            >
                              <span>
                                {asStr(sub.name)}
                                {sub.is_snack ? (
                                  <Badge variant="destructive" className="ml-1.5 text-[10px] py-0">
                                    零食
                                  </Badge>
                                ) : null}
                              </span>
                              <span className="text-muted-foreground">
                                [{asStr(sub.tag) || '未分类'}] ¥{asStr(sub.amount)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      <label className="flex items-center gap-1.5 cursor-pointer text-[11px]">
                        <input
                          type="checkbox"
                          checked={Boolean(entry.data.sync_to_health)}
                          onChange={(e) => updateEntryData(idx, 'sync_to_health', e.target.checked)}
                        />
                        含零食/餐饮时同步记入健康饮食追踪
                      </label>
                    </div>
                  )}

                  {entry.kind === 'account_balance_check' && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-center">
                      <Input
                        className="h-7 text-xs"
                        placeholder="账户名(如支付宝余额宝)"
                        value={asStr(entry.data.account_hint)}
                        onChange={(e) => updateEntryData(idx, 'account_hint', e.target.value)}
                      />
                      <Input
                        type="number"
                        step="0.01"
                        className="h-7 text-xs"
                        placeholder="当前真实余额"
                        value={asNumStr(entry.data.actual_balance)}
                        onChange={(e) =>
                          updateEntryData(
                            idx,
                            'actual_balance',
                            e.target.value ? Number(e.target.value) : null,
                          )
                        }
                      />
                      <Input
                        className="h-7 text-xs col-span-2"
                        placeholder="核对备注"
                        value={asStr(entry.data.description)}
                        onChange={(e) => updateEntryData(idx, 'description', e.target.value)}
                      />
                    </div>
                  )}

                  {entry.kind === 'daily_info' && (
                    <Input
                      className="h-7 text-xs"
                      placeholder="日常健康信息描述"
                      value={asStr(entry.data.description)}
                      onChange={(e) => updateEntryData(idx, 'description', e.target.value)}
                    />
                  )}
                </div>
              ))}
            </div>

            {activeDraft.ticket_id != null && (
              <Input
                className="h-8 text-xs"
                placeholder="可选：自定义回复给教练票据的一句话（留空则自动使用识别汇总）"
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
              />
            )}

            <div className="flex items-center justify-end gap-2 pt-1">
              <Button variant="ghost" size="sm" onClick={handleDiscard} disabled={committing}>
                <Trash2 className="h-3.5 w-3.5 mr-1" />
                丢弃
              </Button>
              <Button
                size="sm"
                onClick={handleCommit}
                disabled={committing || selectedCount === 0}
              >
                {committing ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                    落库中…
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                    确认落库（{selectedCount} 项）
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
