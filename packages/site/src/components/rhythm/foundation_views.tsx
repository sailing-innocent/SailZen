import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { useRhythmStore } from '@lib/store/rhythm'
import type { EnergyProfileUpdateProps, DayTemplateCreateProps, PolicyCreateProps, PolicyUpdateProps, PolicyData, DayTemplateData } from '@lib/data/rhythm'
import { PolicyRuleType } from '@lib/data/rhythm'
import { AlertCircle, Plus, Save, Trash2 } from 'lucide-react'

export const EnergyProfileEditor = () => {
  const profile = useRhythmStore((s) => s.energyProfile)
  const saveEnergyProfile = useRhythmStore((s) => s.saveEnergyProfile)
  const recalibrateProfile = useRhythmStore((s) => s.recalibrateProfile)
  const [data, setData] = useState<EnergyProfileUpdateProps>({})

  useEffect(() => {
    if (profile) setData({ ...profile, name: 'default' })
  }, [profile])

  if (!profile) return <div>加载中...</div>

  const handleSave = async () => {
    await saveEnergyProfile({ ...data, name: 'default' })
  }

  const handleRecalibrate = async () => {
    await recalibrateProfile()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          精力画像
          {profile.is_default && (
            <Badge variant="destructive" className="gap-1">
              <AlertCircle className="h-3 w-3" />
              默认导入，建议校准
            </Badge>
          )}
        </CardTitle>
        <CardDescription>校准后 plan_day 会按实际精力重新排程</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label>每日精力预算</Label>
            <Input
              type="number"
              value={data.daily_energy_budget ?? profile.daily_energy_budget}
              onChange={(e) => setData({ ...data, daily_energy_budget: parseInt(e.target.value, 10) })}
            />
          </div>
          <div className="space-y-2">
            <Label>睡眠开始</Label>
            <Input
              value={data.sleep_start ?? profile.sleep_start}
              onChange={(e) => setData({ ...data, sleep_start: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>睡眠结束</Label>
            <Input
              value={data.sleep_end ?? profile.sleep_end}
              onChange={(e) => setData({ ...data, sleep_end: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>工作时长上限</Label>
            <Input
              type="number"
              value={data.work_hours_cap ?? profile.work_hours_cap}
              onChange={(e) => setData({ ...data, work_hours_cap: parseFloat(e.target.value) })}
            />
          </div>
          <div className="space-y-2">
            <Label>缓冲占比</Label>
            <Input
              type="number"
              min={0}
              max={0.5}
              step={0.05}
              value={data.min_buffer_ratio ?? profile.min_buffer_ratio}
              onChange={(e) => setData({ ...data, min_buffer_ratio: parseFloat(e.target.value) })}
            />
          </div>
          <div className="space-y-2">
            <Label>life 权重</Label>
            <Input
              type="number"
              value={data.life_weight ?? profile.life_weight}
              onChange={(e) => setData({ ...data, life_weight: parseFloat(e.target.value) })}
            />
          </div>
          <div className="space-y-2">
            <Label>work 权重</Label>
            <Input
              type="number"
              value={data.work_weight ?? profile.work_weight}
              onChange={(e) => setData({ ...data, work_weight: parseFloat(e.target.value) })}
            />
          </div>
          <div className="space-y-2">
            <Label>career 权重</Label>
            <Input
              type="number"
              value={data.career_weight ?? profile.career_weight}
              onChange={(e) => setData({ ...data, career_weight: parseFloat(e.target.value) })}
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label>业余时间区 (JSON)</Label>
          <Textarea
            value={JSON.stringify(data.spare_time_windows ?? profile.spare_time_windows, null, 2)}
            onChange={(e) => {
              try {
                setData({ ...data, spare_time_windows: JSON.parse(e.target.value) })
              } catch {}
            }}
            className="font-mono text-xs"
          />
        </div>
        <div className="flex gap-2">
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-1" />
            保存
          </Button>
          {profile.is_default && (
            <Button variant="secondary" onClick={handleRecalibrate}>
              确认默认画像已校准
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

const defaultSlot = () => ({
  label: '新槽位',
  start: '09:00',
  end: '10:00',
  block_type: 'work_window',
  micro_cycle: { work_min: 90, rest_min: 15 },
})

export const TemplateEditor = () => {
  const templates = useRhythmStore((s) => s.templates)
  const fetchTemplates = useRhythmStore((s) => s.fetchTemplates)
  const saveTemplate = useRhythmStore((s) => s.saveTemplate)
  const deleteTemplate = useRhythmStore((s) => s.deleteTemplate)
  const ensureDefaultTemplates = useRhythmStore((s) => s.ensureDefaultTemplates)
  const [selected, setSelected] = useState<DayTemplateData | null>(null)

  useEffect(() => {
    fetchTemplates()
  }, [fetchTemplates])

  const handleEnsureDefaults = async () => {
    await ensureDefaultTemplates()
    await fetchTemplates()
  }

  const handleSave = async () => {
    if (!selected) return
    await saveTemplate({
      name: selected.name,
      description: selected.description,
      weekday_mask: selected.weekday_mask,
      slots: selected.slots,
      enabled: selected.enabled,
      priority: selected.priority,
    })
    await fetchTemplates()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">DayTemplate 管理</h3>
        <Button variant="outline" onClick={handleEnsureDefaults}>
          生成默认模板
        </Button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle>模板列表</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {templates.map((t) => (
              <div
                key={t.id}
                className={`p-2 rounded-md border cursor-pointer ${selected?.id === t.id ? 'bg-muted' : ''}`}
                onClick={() => setSelected(t)}
              >
                <div className="font-medium">{t.name}</div>
                <div className="text-xs text-muted-foreground">{t.enabled ? '启用' : '禁用'} · {t.slots.length} 槽位</div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>{selected ? selected.name : '选择模板'}</CardTitle>
          </CardHeader>
          <CardContent>
            {selected && (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={selected.enabled}
                      onCheckedChange={(v) => setSelected({ ...selected, enabled: v })}
                    />
                    <Label>启用</Label>
                  </div>
                  <Button variant="outline" size="sm" onClick={handleSave}>
                    <Save className="h-4 w-4 mr-1" />
                    保存
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => deleteTemplate(selected.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
                <div className="space-y-2">
                  {selected.slots.map((slot: Record<string, unknown>, idx: number) => (
                    <div key={idx} className="grid grid-cols-5 gap-2 items-center">
                      <Input
                        value={String(slot.label ?? '')}
                        onChange={(e) => {
                          const slots = [...selected.slots]
                          slots[idx] = { ...slots[idx], label: e.target.value }
                          setSelected({ ...selected, slots })
                        }}
                      />
                      <Input
                        value={String(slot.start ?? '')}
                        onChange={(e) => {
                          const slots = [...selected.slots]
                          slots[idx] = { ...slots[idx], start: e.target.value }
                          setSelected({ ...selected, slots })
                        }}
                      />
                      <Input
                        value={String(slot.end ?? '')}
                        onChange={(e) => {
                          const slots = [...selected.slots]
                          slots[idx] = { ...slots[idx], end: e.target.value }
                          setSelected({ ...selected, slots })
                        }}
                      />
                      <Select
                        value={String(slot.block_type ?? 'work_window')}
                        onValueChange={(v) => {
                          const slots = [...selected.slots]
                          slots[idx] = { ...slots[idx], block_type: v }
                          setSelected({ ...selected, slots })
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {['sleep', 'commute', 'work_window', 'micro_rest', 'meal', 'precept', 'habit', 'fixed', 'focus', 'light', 'career', 'rest', 'buffer'].map((bt) => (
                            <SelectItem key={bt} value={bt}>
                              {bt}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          const slots = selected.slots.filter((_, i) => i !== idx)
                          setSelected({ ...selected, slots })
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    onClick={() => setSelected({ ...selected, slots: [...selected.slots, defaultSlot()] })}
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    添加槽位
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export const PolicyEditor = () => {
  const policies = useRhythmStore((s) => s.policies)
  const fetchPolicies = useRhythmStore((s) => s.fetchPolicies)
  const savePolicy = useRhythmStore((s) => s.savePolicy)
  const updatePolicy = useRhythmStore((s) => s.updatePolicy)
  const deletePolicy = useRhythmStore((s) => s.deletePolicy)
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<PolicyCreateProps>({
    name: '',
    rule_type: 'protect_window',
    params: {},
    scope: 'day',
    enabled: true,
  })

  useEffect(() => {
    fetchPolicies()
  }, [fetchPolicies])

  const handleCreate = async () => {
    await savePolicy(data)
    setOpen(false)
    setData({ name: '', rule_type: 'protect_window', params: {}, scope: 'day', enabled: true })
  }

  const togglePolicy = async (policy: PolicyData) => {
    await updatePolicy(policy.id, { enabled: !policy.enabled })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">守护策略</h3>
        <Button onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          新增策略
        </Button>
      </div>
      <div className="space-y-2">
        {policies.map((p) => (
          <Card key={p.id}>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-sm text-muted-foreground">
                  {p.rule_type} · {p.scope} · {JSON.stringify(p.params)}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={p.enabled} onCheckedChange={() => togglePolicy(p)} />
                <Button variant="ghost" size="icon" onClick={() => deletePolicy(p.id)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新增策略</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>名称</Label>
              <Input value={data.name} onChange={(e) => setData({ ...data, name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>规则类型</Label>
              <Select value={data.rule_type} onValueChange={(v) => setData({ ...data, rule_type: v as typeof PolicyRuleType[keyof typeof PolicyRuleType] })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.values(PolicyRuleType).map((rt) => (
                    <SelectItem key={rt} value={rt}>
                      {rt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>参数 (JSON)</Label>
              <Textarea
                value={JSON.stringify(data.params ?? {}, null, 2)}
                onChange={(e) => {
                  try {
                    setData({ ...data, params: JSON.parse(e.target.value) })
                  } catch {}
                }}
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-2">
              <Label>作用域</Label>
              <Select value={data.scope} onValueChange={(v) => setData({ ...data, scope: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="day">day</SelectItem>
                  <SelectItem value="week">week</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button onClick={handleCreate}>创建</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
