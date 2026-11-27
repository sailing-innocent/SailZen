/**
 * @file topics.tsx
 * @brief Content 2.0 Topics Workbench (专题资料包 <-> Rhythm Venture 双向联动)
 * @author sailing-innocent
 * @date 2026-11-26
 */

import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PageLayout from '@components/page_layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
import {
  BookOpen,
  Compass,
  ExternalLink,
  FileText,
  FolderGit2,
  ListTodo,
  Plus,
  Rocket,
  Trash2,
} from 'lucide-react'
import ContentImportDialog from '@components/text/content_import_dialog'
import {
  api_attach_work_to_topic,
  api_create_topic,
  api_delete_topic,
  api_detach_work_from_topic,
  api_get_topic_detail,
  api_get_topics,
  api_get_works,
  api_push_topic_rhythm_task,
  api_upload_asset,
  getAssetFileUrl,
} from '@lib/api/text'
import { api_get_affairs } from '@lib/api/affair'
import type { ContentTopic, ContentTopicDetail, Work } from '@lib/data/text'
import { getPillarLabel, getWorkTypeLabel } from '@lib/data/text'

interface VentureOption {
  id: number
  title: string
}

export default function TopicsPage() {
  const navigate = useNavigate()
  const [topics, setTopics] = useState<ContentTopic[]>([])
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null)
  const [detail, setDetail] = useState<ContentTopicDetail | null>(null)
  const [allWorks, setAllWorks] = useState<Work[]>([])
  const [ventures, setVentures] = useState<VentureOption[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 新建专题弹窗
  const [createOpen, setCreateOpen] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newPillar, setNewPillar] = useState('tech')
  const [newVentureId, setNewVentureId] = useState<string>('none')
  const [newKeywords, setNewKeywords] = useState('')

  // 关联已有作品
  const [attachWorkId, setAttachWorkId] = useState<string>('')
  const [attachRole, setAttachRole] = useState<string>('core')

  // 一键推 Rhythm 任务
  const [taskTitle, setTaskTitle] = useState('')
  const [taskMinutes, setTaskMinutes] = useState('45')
  const [taskWorkId, setTaskWorkId] = useState<string>('none')
  const [pushingTask, setPushingTask] = useState(false)

  const loadTopics = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [topicList, workList, affairList] = await Promise.all([
        api_get_topics(),
        api_get_works({ limit: 100 }),
        api_get_affairs({ kind: 'venture' } as Record<string, unknown>).catch(() => []),
      ])
      setTopics(topicList)
      setAllWorks(workList)
      const vList: VentureOption[] = Array.isArray(affairList)
        ? affairList
            .filter((a: { kind?: string }) => a.kind === 'venture')
            .map((a: { id: number; title: string }) => ({ id: a.id, title: a.title }))
        : []
      setVentures(vList)
      if (!selectedTopicId && topicList.length > 0) {
        setSelectedTopicId(topicList[0].id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载专题失败')
    } finally {
      setLoading(false)
    }
  }, [selectedTopicId])

  const loadDetail = useCallback(async (tid: number) => {
    try {
      const d = await api_get_topic_detail(tid)
      setDetail(d)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载专题详情失败')
    }
  }, [])

  useEffect(() => {
    loadTopics()
  }, [loadTopics])

  useEffect(() => {
    if (selectedTopicId) {
      loadDetail(selectedTopicId)
    } else {
      setDetail(null)
    }
  }, [selectedTopicId, loadDetail])

  const handleCreateTopic = async () => {
    if (!newTitle.trim()) return
    try {
      const created = await api_create_topic({
        title: newTitle.trim(),
        description: newDesc.trim(),
        pillar: newPillar,
        rhythm_venture_id: newVentureId === 'none' ? null : parseInt(newVentureId, 10),
        keywords: newKeywords
          .split(/[,，]/)
          .map((s) => s.trim())
          .filter(Boolean),
      })
      setTopics((prev) => [created, ...prev])
      setSelectedTopicId(created.id)
      setCreateOpen(false)
      setNewTitle('')
      setNewDesc('')
      setNewKeywords('')
      setNewVentureId('none')
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建专题失败')
    }
  }

  const handleDeleteTopic = async (tid: number) => {
    if (!confirm('确认删除该专题？（不会删除关联的书籍、论文或 Rhythm 项目）')) return
    await api_delete_topic(tid)
    const rest = topics.filter((t) => t.id !== tid)
    setTopics(rest)
    setSelectedTopicId(rest[0]?.id ?? null)
  }

  const handleAttachWork = async () => {
    if (!selectedTopicId || !attachWorkId) return
    await api_attach_work_to_topic(selectedTopicId, {
      work_id: parseInt(attachWorkId, 10),
      role: attachRole,
    })
    setAttachWorkId('')
    loadDetail(selectedTopicId)
    loadTopics()
  }

  const handlePushTask = async () => {
    if (!selectedTopicId || !taskTitle.trim()) return
    setPushingTask(true)
    try {
      await api_push_topic_rhythm_task(selectedTopicId, {
        title: taskTitle.trim(),
        work_id: taskWorkId === 'none' ? undefined : parseInt(taskWorkId, 10),
        est_minutes: parseInt(taskMinutes, 10) || 45,
      })
      setTaskTitle('')
      loadDetail(selectedTopicId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '推送 Rhythm 任务失败')
    } finally {
      setPushingTask(false)
    }
  }

  const handleUploadAsset = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f || !selectedTopicId) return
    const kind = f.type.startsWith('image/')
      ? 'moodboard'
      : f.name.toLowerCase().endsWith('.pdf')
        ? 'pdf_source'
        : 'attachment'
    await api_upload_asset(f, { topic_id: selectedTopicId, asset_kind: kind })
    e.target.value = ''
    loadDetail(selectedTopicId)
  }

  const attachedWorkIds = new Set(detail?.works.map((w) => w.work_id) || [])
  const availableWorks = allWorks.filter((w) => !attachedWorkIds.has(w.id))

  return (
    <PageLayout>
      <div className="space-y-4">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl md:text-2xl font-bold flex items-center gap-2">
              <Compass className="w-6 h-6" />
              专题研究工作台
            </h1>
            <p className="text-xs md:text-sm text-muted-foreground">
              将书籍、SIGGRAPH/arXiv 论文、审美参考与 Rhythm 大型项目（Venture）及本地 Vault 笔记绑定推进
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link to="/text">
                <BookOpen className="w-4 h-4 mr-1.5" /> 返回阅读库
              </Link>
            </Button>
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="w-4 h-4 mr-1" /> 新建专题
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle>新建研究专题</DialogTitle>
                  <DialogDescription>
                    可绑定一个 Rhythm 长期项目（Venture），后续论文复现/读书里程碑将自动挂载到该项目下
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-3 py-2">
                  <div className="grid gap-1.5">
                    <Label>专题名称 *</Label>
                    <Input
                      placeholder="如：SIGGRAPH 2026 实时光追复现 / 独立游戏明代背景资料"
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-1.5">
                      <Label>主素养归属</Label>
                      <Select value={newPillar} onValueChange={setNewPillar}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="tech">技术素养</SelectItem>
                          <SelectItem value="history">历史素养</SelectItem>
                          <SelectItem value="aesthetics">审美素养</SelectItem>
                          <SelectItem value="fiction">小说 / 世界观</SelectItem>
                          <SelectItem value="interdisciplinary">跨领域综合</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-1.5">
                      <Label>绑定 Rhythm 项目</Label>
                      <Select value={newVentureId} onValueChange={setNewVentureId}>
                        <SelectTrigger><SelectValue placeholder="不绑定" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">暂不绑定</SelectItem>
                          {ventures.map((v) => (
                            <SelectItem key={v.id} value={String(v.id)}>
                              {v.title}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid gap-1.5">
                    <Label>关键词（逗号分隔，预留给资讯雷达）</Label>
                    <Input
                      placeholder="ReSTIR, Path Tracing, Shader"
                      value={newKeywords}
                      onChange={(e) => setNewKeywords(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label>研究目标 / 简介</Label>
                    <textarea
                      className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={newDesc}
                      onChange={(e) => setNewDesc(e.target.value)}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCreateOpen(false)}>取消</Button>
                  <Button onClick={handleCreateTopic}>创建</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {error && <div className="text-sm text-red-500 p-2 bg-red-50 rounded">{error}</div>}

        <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
          {/* 左侧专题列表 */}
          <Card className="md:col-span-4">
            <CardHeader className="py-3 border-b">
              <CardTitle className="text-sm">全部专题 ({topics.length})</CardTitle>
            </CardHeader>
            <CardContent className="p-2 space-y-1.5">
              {loading ? (
                <div className="text-xs text-muted-foreground p-4 text-center">加载中...</div>
              ) : topics.length === 0 ? (
                <div className="text-xs text-muted-foreground p-6 text-center">
                  暂无专题，点击右上角「新建专题」把书单与 Rhythm 项目串起来
                </div>
              ) : (
                topics.map((t) => (
                  <div
                    key={t.id}
                    className={`p-3 rounded-md border cursor-pointer transition-colors ${
                      selectedTopicId === t.id
                        ? 'border-primary bg-primary/5'
                        : 'hover:bg-muted/50'
                    }`}
                    onClick={() => setSelectedTopicId(t.id)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-medium text-sm truncate">{t.title}</div>
                      <Badge variant="outline" className="text-[10px] shrink-0">
                        {getPillarLabel(t.pillar)}
                      </Badge>
                    </div>
                    {t.venture_title && (
                      <div className="text-[11px] text-primary mt-1 flex items-center gap-1 truncate">
                        <Rocket className="w-3 h-3 shrink-0" />
                        Rhythm: {t.venture_title}
                      </div>
                    )}
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground mt-1.5">
                      <span>{t.work_count} 份资料</span>
                      <span>平均进度 {Math.round(t.avg_progress_pct)}%</span>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          {/* 右侧专题工作区 */}
          <div className="md:col-span-8 space-y-4">
            {!detail ? (
              <Card className="p-10 text-center text-sm text-muted-foreground">
                选择左侧专题，或新建一个专题开始整理资料与项目任务
              </Card>
            ) : (
              <>
                {/* 专题头卡片 */}
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <CardTitle className="text-lg flex items-center gap-2">
                          {detail.topic.title}
                          <Badge variant="secondary">{getPillarLabel(detail.topic.pillar)}</Badge>
                        </CardTitle>
                        {detail.topic.description && (
                          <CardDescription className="mt-1">
                            {detail.topic.description}
                          </CardDescription>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-500"
                        onClick={() => handleDeleteTopic(detail.topic.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 pt-2 text-xs">
                      {detail.venture && (
                        <Badge className="gap-1 cursor-pointer" onClick={() => navigate('/rhythm')}>
                          <Rocket className="w-3 h-3" />
                          绑定项目：{detail.venture.title}
                        </Badge>
                      )}
                      {detail.topic.vault_prefix && (
                        <Badge variant="outline" className="gap-1">
                          <FolderGit2 className="w-3 h-3" />
                          Vault: {detail.topic.vault_prefix}.*
                        </Badge>
                      )}
                      {detail.topic.keywords.map((kw) => (
                        <Badge key={kw} variant="secondary" className="text-[11px]">
                          #{kw}
                        </Badge>
                      ))}
                    </div>
                  </CardHeader>
                </Card>

                {/* 1. 关联书单与论文 */}
                <Card>
                  <CardHeader className="py-3 flex-row items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-1.5">
                      <BookOpen className="w-4 h-4" /> 关联书籍与论文 ({detail.works.length})
                    </CardTitle>
                    <ContentImportDialog
                      defaultTopicId={detail.topic.id}
                      defaultPillar={detail.topic.pillar}
                      onImported={() => {
                        loadDetail(detail.topic.id)
                        loadTopics()
                      }}
                      trigger={
                        <Button size="sm" variant="outline">
                          <Plus className="w-3.5 h-3.5 mr-1" /> 直接导入论文/书
                        </Button>
                      }
                    />
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {availableWorks.length > 0 && (
                      <div className="flex gap-2">
                        <Select value={attachWorkId} onValueChange={setAttachWorkId}>
                          <SelectTrigger className="flex-1 h-8 text-xs">
                            <SelectValue placeholder="从阅读库关联已有作品..." />
                          </SelectTrigger>
                          <SelectContent>
                            {availableWorks.map((w) => (
                              <SelectItem key={w.id} value={String(w.id)}>
                                [{getWorkTypeLabel(w.work_type)}] {w.title}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Select value={attachRole} onValueChange={setAttachRole}>
                          <SelectTrigger className="w-[95px] h-8 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="core">核心精读</SelectItem>
                            <SelectItem value="reference">参考资料</SelectItem>
                            <SelectItem value="background">背景阅读</SelectItem>
                            <SelectItem value="inspiration">灵感来源</SelectItem>
                          </SelectContent>
                        </Select>
                        <Button size="sm" className="h-8" onClick={handleAttachWork} disabled={!attachWorkId}>
                          关联
                        </Button>
                      </div>
                    )}

                    {detail.works.length === 0 ? (
                      <div className="text-xs text-muted-foreground py-4 text-center">
                        暂未关联作品
                      </div>
                    ) : (
                      <div className="divide-y border rounded-md">
                        {detail.works.map((item) => {
                          const pct = Math.round(item.work.progress?.progress_pct ?? 0)
                          return (
                            <div
                              key={item.id}
                              className="p-2.5 flex items-center justify-between gap-2 hover:bg-muted/30"
                            >
                              <div
                                className="min-w-0 flex-1 cursor-pointer"
                                onClick={() => navigate(`/text?workId=${item.work.id}`)}
                              >
                                <div className="text-sm font-medium truncate hover:text-primary">
                                  {item.work.title}
                                </div>
                                <div className="text-xs text-muted-foreground flex items-center gap-2 mt-0.5">
                                  <Badge variant="outline" className="text-[10px] py-0">
                                    {item.role}
                                  </Badge>
                                  <span>{getWorkTypeLabel(item.work.work_type)}</span>
                                  <span>进度 {pct}%</span>
                                </div>
                              </div>
                              <div className="flex items-center gap-1 shrink-0">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 text-xs"
                                  onClick={() => navigate(`/text?workId=${item.work.id}`)}
                                >
                                  阅读
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-7 px-2 text-xs text-muted-foreground"
                                  onClick={async () => {
                                    await api_detach_work_from_topic(detail.topic.id, item.work_id)
                                    loadDetail(detail.topic.id)
                                    loadTopics()
                                  }}
                                >
                                  移除
                                </Button>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* 2. Rhythm 里程碑任务联动 */}
                <Card>
                  <CardHeader className="py-3 flex-row items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-1.5">
                      <ListTodo className="w-4 h-4" /> Rhythm 推进任务 ({detail.rhythm_tasks.length})
                    </CardTitle>
                    <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
                      <Link to="/rhythm">
                        前往节奏页 <ExternalLink className="w-3 h-3 ml-1" />
                      </Link>
                    </Button>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-col sm:flex-row gap-2">
                      <Input
                        placeholder="新增阅读 / 论文复现任务，一键推入 Rhythm..."
                        value={taskTitle}
                        onChange={(e) => setTaskTitle(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handlePushTask()}
                        className="flex-1 h-8 text-xs"
                      />
                      {detail.works.length > 0 && (
                        <Select value={taskWorkId} onValueChange={setTaskWorkId}>
                          <SelectTrigger className="w-[150px] h-8 text-xs">
                            <SelectValue placeholder="关联作品(可选)" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">不关联具体书</SelectItem>
                            {detail.works.map((w) => (
                              <SelectItem key={w.work_id} value={String(w.work_id)}>
                                {w.work.title.slice(0, 18)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                      <Input
                        type="number"
                        value={taskMinutes}
                        onChange={(e) => setTaskMinutes(e.target.value)}
                        className="w-[70px] h-8 text-xs"
                        title="预估分钟"
                      />
                      <Button
                        size="sm"
                        className="h-8"
                        onClick={handlePushTask}
                        disabled={pushingTask || !taskTitle.trim()}
                      >
                        推送任务
                      </Button>
                    </div>

                    {detail.rhythm_tasks.length === 0 ? (
                      <div className="text-xs text-muted-foreground py-3 text-center">
                        暂无关联 Rhythm 任务，在上方输入一条即可自动推入日常排程
                      </div>
                    ) : (
                      <div className="divide-y border rounded-md">
                        {detail.rhythm_tasks.map((task) => (
                          <div key={task.id} className="px-3 py-2 flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2 min-w-0">
                              <Badge
                                variant={task.state === 'DONE' ? 'default' : 'outline'}
                                className="text-[10px]"
                              >
                                {task.state}
                              </Badge>
                              <span
                                className={
                                  task.state === 'DONE'
                                    ? 'line-through text-muted-foreground truncate'
                                    : 'truncate'
                                }
                              >
                                {task.title}
                              </span>
                            </div>
                            <span className="text-muted-foreground shrink-0">{task.est_minutes}m</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* 3. PDF 原件、参考图与 Vault 笔记索引 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Card>
                    <CardHeader className="py-2.5 flex-row items-center justify-between">
                      <CardTitle className="text-sm flex items-center gap-1.5">
                        <FileText className="w-4 h-4" /> PDF / 参考附件 ({detail.assets.length})
                      </CardTitle>
                      <label className="cursor-pointer">
                        <span className="text-xs text-primary hover:underline">+ 上传参考图/PDF</span>
                        <input type="file" className="hidden" onChange={handleUploadAsset} />
                      </label>
                    </CardHeader>
                    <CardContent className="space-y-1.5">
                      {detail.assets.length === 0 ? (
                        <div className="text-xs text-muted-foreground py-3 text-center">暂无附件</div>
                      ) : (
                        detail.assets.map((a) => (
                          <a
                            key={a.id}
                            href={getAssetFileUrl(a)}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center justify-between p-2 rounded border hover:bg-muted/40 text-xs"
                          >
                            <span className="truncate">{a.original_name}</span>
                            <Badge variant="outline" className="text-[10px] shrink-0 ml-2">
                              {a.asset_kind}
                            </Badge>
                          </a>
                        ))
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="py-2.5">
                      <CardTitle className="text-sm flex items-center gap-1.5">
                        <FolderGit2 className="w-4 h-4" /> 本地 Vault 笔记 ({detail.vault_notes.length})
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-1.5">
                      {detail.vault_notes.length === 0 ? (
                        <div className="text-xs text-muted-foreground py-3 text-center">
                          在 D:\vault 下以 <code className="px-1 bg-muted rounded">{detail.topic.vault_prefix}.*</code> 命名并运行{' '}
                          <code className="px-1 bg-muted rounded">sailzen vault sync-content</code> 即可呈现
                        </div>
                      ) : (
                        detail.vault_notes.map((n) => (
                          <div key={n.fname} className="p-2 rounded border text-xs">
                            <div className="font-medium truncate">{n.title || n.fname}</div>
                            <div className="text-[11px] text-muted-foreground truncate mt-0.5">
                              {n.summary || n.fname}
                            </div>
                          </div>
                        ))
                      )}
                    </CardContent>
                  </Card>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
